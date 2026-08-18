#!/usr/bin/env python3
r"""
Server-side REVERSE backfill — standalone, no project dependencies.

Extracts all 53 on-chain features for Bitcoin addresses from public API endpoints.
Designed to run 24/7 on an Ubuntu server, working the queue from the END backwards
while the local machine works forwards. They meet in the middle.

ENDPOINTS (12 total, each with its own independent rate-limit budget per IP):
  Trezor Blockbook x5   btc1-5.trezor.io
  blockchain.info        blockchain.info/rawaddr
  Esplora x4             blockstream.info, mempool.space, mempool.emzy.de, mempool.bitaroo.net
  Trezor-compatible x2   btc.exan.tech, bitcoin.atomicwallet.io

SAFETY:
  * Resumable — skips addresses already in the output CSV
  * Lock file — prevents duplicate concurrent runs
  * Per-endpoint rate-limit pacing (configurable, default 6s between requests to same host)
  * Adaptive — benches endpoints that return 429, uses others meanwhile
  * Crash-safe — flushes after every chunk, auto-restarts via wrapper script

USAGE:
  python3 backfill_server.py --queue queues/queue_kaggle_esplora.parquet \
                              --out output/backfill_kaggle_reverse.csv \
                              --reverse --workers 4
  python3 backfill_server.py --queue queues/queue_elliptic_pp.parquet \
                              --out output/backfill_elliptic_reverse.csv \
                              --reverse --workers 4
  python3 backfill_server.py --status --out output/backfill_kaggle_reverse.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


# Set only while this process owns an output lock.  Cleanup must never remove
# the lock belonging to the other, parallel batch.
ACTIVE_LOCK: Path | None = None

# ─────────────────────────────────────────────────────────────────────────────
# SCHEMA — the 53 feature columns (authoritative order)
# ─────────────────────────────────────────────────────────────────────────────
FEATURE_COLUMNS = [
    "address", "address_type", "label", "label_source", "data_completeness",
    "tx_count", "funded_txo_count", "spent_txo_count",
    "n_tx_as_sender_sampled", "n_tx_as_receiver_sampled", "n_unique_counterparties",
    "total_received_sat", "total_received_btc", "mean_received_sat",
    "max_received_sat", "min_received_sat", "std_received_sat",
    "total_sent_sat", "total_sent_btc", "mean_sent_sat",
    "max_sent_sat", "min_sent_sat", "std_sent_sat",
    "balance_sat", "balance_btc", "net_flow_sat",
    "total_fee_sat_sampled", "mean_fee_sat", "mean_fee_rate_sat_vb",
    "first_tx_time", "last_tx_time", "lifespan_days", "active_days",
    "activity_density", "mean_inter_tx_hours", "std_inter_tx_hours",
    "max_dormancy_days", "tx_velocity",
    "in_degree", "out_degree", "degree_total", "fan_in_ratio", "fan_out_ratio",
    "sender_concentration_hhi", "recipient_concentration_hhi",
    "cio_cluster_size", "peel_chain_len", "consolidation_frac",
    "coinjoin_tx_count_sampled", "round_value_ratio_sampled",
    "mean_output_count_sampled", "mean_input_count_sampled", "mempool_tx_count",
]
assert len(FEATURE_COLUMNS) == 53

UA = {"User-Agent": "btc-intel-research/1.0"}

# ─────────────────────────────────────────────────────────────────────────────
# ENDPOINTS — 12 independent public Bitcoin API sources
# ─────────────────────────────────────────────────────────────────────────────
ENDPOINTS = [
    {"name": "trezor-btc1", "kind": "trezor",
     "url": "https://btc1.trezor.io/api/v2/address/{a}?details=txs&pageSize=50"},
    {"name": "trezor-btc2", "kind": "trezor",
     "url": "https://btc2.trezor.io/api/v2/address/{a}?details=txs&pageSize=50"},
    {"name": "trezor-btc3", "kind": "trezor",
     "url": "https://btc3.trezor.io/api/v2/address/{a}?details=txs&pageSize=50"},
    {"name": "trezor-btc4", "kind": "trezor",
     "url": "https://btc4.trezor.io/api/v2/address/{a}?details=txs&pageSize=50"},
    {"name": "trezor-btc5", "kind": "trezor",
     "url": "https://btc5.trezor.io/api/v2/address/{a}?details=txs&pageSize=50"},
    {"name": "blockchain.info", "kind": "blockchain",
     "url": "https://blockchain.info/rawaddr/{a}?limit=50"},
    {"name": "blockstream", "kind": "esplora_direct",
     "url": "https://blockstream.info/api"},
    {"name": "mempool.space", "kind": "esplora_direct",
     "url": "https://mempool.space/api"},
    {"name": "emzy", "kind": "esplora_direct",
     "url": "https://mempool.emzy.de/api"},
    {"name": "bitaroo", "kind": "esplora_direct",
     "url": "https://mempool.bitaroo.net/api"},
    {"name": "exan", "kind": "trezor",
     "url": "https://btc.exan.tech/api/v2/address/{a}?details=txs&pageSize=50"},
    {"name": "atomic", "kind": "trezor",
     "url": "https://bitcoin.atomicwallet.io/api/v2/address/{a}?details=txs&pageSize=50"},
]
_ALL_ENDPOINTS = list(ENDPOINTS)

# ─────────────────────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

def _get(url, timeout=25):
    """HTTP GET with JSON parse. No retries — the Rotor handles endpoint rotation."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _hhi(values: list) -> float:
    """Herfindahl-Hirschman concentration index (0..1)."""
    tot = sum(v for v in values if v > 0)
    if tot <= 0:
        return 0.0
    return round(sum((v / tot) ** 2 for v in values if v > 0), 4)


def _round_value(v: int) -> bool:
    """True if v looks like a round BTC amount (e.g. 0.01, 0.1, 1.0 BTC)."""
    if v <= 0:
        return False
    for d in [100_000_000, 10_000_000, 1_000_000, 100_000, 10_000]:
        if v % d == 0:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# ROTOR — round-robins endpoints with per-endpoint pacing + cooldown
# ─────────────────────────────────────────────────────────────────────────────

class Rotor:
    """Round-robins endpoints, PACES each one, and benches any that start refusing.

    Hammering does not work: every free endpoint 429s after a handful of rapid requests.
    The winning strategy is to stay UNDER each endpoint's limit — so every endpoint has a
    minimum interval between its own requests, enforced globally across threads.
    """

    def __init__(self, eps, min_interval=6.0):
        self.eps = [dict(e, cooldown_until=0.0, next_ok=0.0, ok=0, fail=0) for e in eps]
        self.i = 0
        self.min_interval = min_interval
        self.lock = threading.Lock()

    def pick(self):
        """Return an endpoint that is neither benched nor inside its pacing window."""
        deadline = time.time() + 12.0
        while time.time() < deadline:
            with self.lock:
                now = time.time()
                soonest = None
                for _ in range(len(self.eps)):
                    e = self.eps[self.i % len(self.eps)]
                    self.i += 1
                    if e["cooldown_until"] > now:
                        continue
                    if e["next_ok"] <= now:
                        e["next_ok"] = now + self.min_interval
                        return e
                    soonest = e["next_ok"] if soonest is None else min(soonest, e["next_ok"])
            time.sleep(min(2.0, max(0.25, (soonest or time.time() + 1) - time.time())))
        return None

    def penalise(self, e, seconds=60.0):
        with self.lock:
            e["cooldown_until"] = time.time() + seconds
            e["fail"] += 1

    def reward(self, e):
        with self.lock:
            e["ok"] += 1

    def report(self):
        now = time.time()
        return "  ".join(
            f"{e['name']}:{e['ok']}ok/{e['fail']}f"
            + ("(benched)" if e["cooldown_until"] > now else "")
            for e in self.eps)


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE EXTRACTORS — three adapters for three API shapes
# ─────────────────────────────────────────────────────────────────────────────

def features_from_blockchain_info(addr, d, label, source, atype) -> dict:
    """Compute all 53 attributes from one blockchain.info /rawaddr response."""
    row = {c: 0 for c in FEATURE_COLUMNS}
    txs = d.get("txs", []) or []
    n_tx = int(d.get("n_tx", 0) or 0)
    row.update({"address": addr, "address_type": atype or "UNKNOWN", "label": label,
                "label_source": source,
                "data_completeness": "FULL" if n_tx <= len(txs) else "SAMPLED",
                "tx_count": n_tx,
                "total_received_sat": int(d.get("total_received", 0) or 0),
                "total_sent_sat": int(d.get("total_sent", 0) or 0),
                "balance_sat": int(d.get("final_balance", 0) or 0)})
    row["total_received_btc"] = round(row["total_received_sat"] / 1e8, 8)
    row["total_sent_btc"] = round(row["total_sent_sat"] / 1e8, 8)
    row["balance_btc"] = round(row["balance_sat"] / 1e8, 8)
    row["net_flow_sat"] = row["balance_sat"]
    if n_tx == 0:
        row["data_completeness"] = "NO_HISTORY"
        return {c: row.get(c, 0) for c in FEATURE_COLUMNS}

    recv, sent, fees, rates, outc, inc, times = [], [], [], [], [], [], []
    senders, recipients = {}, {}
    n_send = n_recv = cj = rv = 0
    funded = spent = 0

    for t in txs:
        ins = t.get("inputs", []) or []
        outs = t.get("out", []) or []
        if t.get("time"):
            times.append(int(t["time"]))
        outc.append(len(outs)); inc.append(len(ins))
        is_sender = any((i.get("prev_out") or {}).get("addr") == addr for i in ins)
        got = sum(int(o.get("value", 0) or 0) for o in outs if o.get("addr") == addr)
        if got > 0:
            recv.append(got); n_recv += 1
            funded += sum(1 for o in outs if o.get("addr") == addr)
        if is_sender:
            n_send += 1
            put = sum(int((i.get("prev_out") or {}).get("value", 0) or 0)
                      for i in ins if (i.get("prev_out") or {}).get("addr") == addr)
            if put > 0:
                sent.append(put)
            spent += sum(1 for i in ins if (i.get("prev_out") or {}).get("addr") == addr)
            f = int(t.get("fee", 0) or 0)
            if f > 0:
                fees.append(f)
                vs = (t.get("weight") or 0) / 4.0 or float(t.get("size") or 0)
                if vs > 0:
                    rates.append(f / vs)
        for i in ins:
            a = (i.get("prev_out") or {}).get("addr")
            if a and a != addr:
                senders[a] = senders.get(a, 0) + int((i.get("prev_out") or {}).get("value", 0) or 0)
        for o in outs:
            a = o.get("addr")
            if a and a != addr:
                recipients[a] = recipients.get(a, 0) + int(o.get("value", 0) or 0)
        vals = [int(o.get("value", 0) or 0) for o in outs]
        if len(vals) >= 5 and len(set(vals)) <= max(1, len(vals) // 3):
            cj += 1
        if any(_round_value(v) for v in vals):
            rv += 1

    st = lambda xs, f, d=0.0: round(f(xs), 3) if xs else d
    times.sort()
    iv = [(b - a) / 3600.0 for a, b in zip(times, times[1:])]
    in_deg, out_deg = len(senders), len(recipients)

    row.update({
        "funded_txo_count": funded, "spent_txo_count": spent,
        "n_tx_as_sender_sampled": n_send, "n_tx_as_receiver_sampled": n_recv,
        "n_unique_counterparties": len(set(senders) | set(recipients)),
        "mean_received_sat": st(recv, statistics.fmean),
        "max_received_sat": max(recv) if recv else 0,
        "min_received_sat": min(recv) if recv else 0,
        "std_received_sat": st(recv, statistics.pstdev) if len(recv) > 1 else 0.0,
        "mean_sent_sat": st(sent, statistics.fmean),
        "max_sent_sat": max(sent) if sent else 0,
        "min_sent_sat": min(sent) if sent else 0,
        "std_sent_sat": st(sent, statistics.pstdev) if len(sent) > 1 else 0.0,
        "total_fee_sat_sampled": sum(fees), "mean_fee_sat": st(fees, statistics.fmean),
        "mean_fee_rate_sat_vb": st(rates, statistics.fmean),
        "first_tx_time": (pd.to_datetime(times[0], unit="s", utc=True).isoformat()
                          if times else ""),
        "last_tx_time": (pd.to_datetime(times[-1], unit="s", utc=True).isoformat()
                         if times else ""),
        "lifespan_days": round((times[-1] - times[0]) / 86400.0, 3) if len(times) > 1 else 0.0,
        "active_days": len({t // 86400 for t in times}),
        "mean_inter_tx_hours": st(iv, statistics.fmean),
        "std_inter_tx_hours": st(iv, statistics.pstdev) if len(iv) > 1 else 0.0,
        "max_dormancy_days": round(max(iv) / 24.0, 3) if iv else 0.0,
        "in_degree": in_deg, "out_degree": out_deg, "degree_total": in_deg + out_deg,
        "fan_in_ratio": round(in_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "fan_out_ratio": round(out_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "consolidation_frac": round(in_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "sender_concentration_hhi": _hhi(list(senders.values())),
        "recipient_concentration_hhi": _hhi(list(recipients.values())),
        "coinjoin_tx_count_sampled": cj,
        "round_value_ratio_sampled": round(rv / len(txs), 4) if txs else 0.0,
        "mean_output_count_sampled": st(outc, statistics.fmean),
        "mean_input_count_sampled": st(inc, statistics.fmean),
    })
    lifespan = row["lifespan_days"] or 1.0
    row["activity_density"] = round(n_tx / max(lifespan, 1.0), 4)
    row["tx_velocity"] = round(n_tx / max(row["active_days"], 1), 4)
    return {c: row.get(c, 0) for c in FEATURE_COLUMNS}


def features_from_trezor(addr, d, label, source, atype) -> dict:
    """Compute all 53 attributes from a Trezor Blockbook v2 /address?details=txs response."""
    row = {c: 0 for c in FEATURE_COLUMNS}
    txs = d.get("transactions", []) or []
    n_tx = int(d.get("txs", 0) or 0)
    iv_ = lambda x: int(x or 0)
    row.update({"address": addr, "address_type": atype or "UNKNOWN", "label": label,
                "label_source": source,
                "data_completeness": "FULL" if n_tx <= len(txs) else "SAMPLED",
                "tx_count": n_tx,
                "total_received_sat": iv_(d.get("totalReceived")),
                "total_sent_sat": iv_(d.get("totalSent")),
                "balance_sat": iv_(d.get("balance"))})
    row["total_received_btc"] = round(row["total_received_sat"] / 1e8, 8)
    row["total_sent_btc"] = round(row["total_sent_sat"] / 1e8, 8)
    row["balance_btc"] = round(row["balance_sat"] / 1e8, 8)
    row["net_flow_sat"] = row["balance_sat"]
    if n_tx == 0:
        row["data_completeness"] = "NO_HISTORY"
        return {c: row.get(c, 0) for c in FEATURE_COLUMNS}

    def addrs_of(x):
        a = x.get("addresses") or []
        return a[0] if a else None

    recv, sent, fees, rates, outc, inc, times = [], [], [], [], [], [], []
    senders, recipients = {}, {}
    n_send = n_recv = cj = rv = funded = spent = 0

    for t in txs:
        vin = t.get("vin", []) or []
        vout = t.get("vout", []) or []
        if t.get("blockTime"):
            times.append(int(t["blockTime"]))
        outc.append(len(vout)); inc.append(len(vin))
        is_sender = any(addrs_of(v) == addr for v in vin)
        got = sum(iv_(o.get("value")) for o in vout if addrs_of(o) == addr)
        if got > 0:
            recv.append(got); n_recv += 1
            funded += sum(1 for o in vout if addrs_of(o) == addr)
        if is_sender:
            n_send += 1
            put = sum(iv_(v.get("value")) for v in vin if addrs_of(v) == addr)
            if put > 0:
                sent.append(put)
            spent += sum(1 for v in vin if addrs_of(v) == addr)
            f = iv_(t.get("fees"))
            if f > 0:
                fees.append(f)
                vs = float(t.get("vsize") or t.get("size") or 0)
                if vs > 0:
                    rates.append(f / vs)
        for v in vin:
            a = addrs_of(v)
            if a and a != addr:
                senders[a] = senders.get(a, 0) + iv_(v.get("value"))
        for o in vout:
            a = addrs_of(o)
            if a and a != addr:
                recipients[a] = recipients.get(a, 0) + iv_(o.get("value"))
        vals = [iv_(o.get("value")) for o in vout]
        if len(vals) >= 5 and len(set(vals)) <= max(1, len(vals) // 3):
            cj += 1
        if any(_round_value(v) for v in vals):
            rv += 1

    st = lambda xs, f, dflt=0.0: round(f(xs), 3) if xs else dflt
    times.sort()
    ivh = [(b - a) / 3600.0 for a, b in zip(times, times[1:])]
    in_deg, out_deg = len(senders), len(recipients)
    row.update({
        "funded_txo_count": funded, "spent_txo_count": spent,
        "n_tx_as_sender_sampled": n_send, "n_tx_as_receiver_sampled": n_recv,
        "n_unique_counterparties": len(set(senders) | set(recipients)),
        "mean_received_sat": st(recv, statistics.fmean),
        "max_received_sat": max(recv) if recv else 0,
        "min_received_sat": min(recv) if recv else 0,
        "std_received_sat": st(recv, statistics.pstdev) if len(recv) > 1 else 0.0,
        "mean_sent_sat": st(sent, statistics.fmean),
        "max_sent_sat": max(sent) if sent else 0,
        "min_sent_sat": min(sent) if sent else 0,
        "std_sent_sat": st(sent, statistics.pstdev) if len(sent) > 1 else 0.0,
        "total_fee_sat_sampled": sum(fees), "mean_fee_sat": st(fees, statistics.fmean),
        "mean_fee_rate_sat_vb": st(rates, statistics.fmean),
        "first_tx_time": (pd.to_datetime(times[0], unit="s", utc=True).isoformat()
                          if times else ""),
        "last_tx_time": (pd.to_datetime(times[-1], unit="s", utc=True).isoformat()
                         if times else ""),
        "lifespan_days": round((times[-1] - times[0]) / 86400.0, 3) if len(times) > 1 else 0.0,
        "active_days": len({t // 86400 for t in times}),
        "mean_inter_tx_hours": st(ivh, statistics.fmean),
        "std_inter_tx_hours": st(ivh, statistics.pstdev) if len(ivh) > 1 else 0.0,
        "max_dormancy_days": round(max(ivh) / 24.0, 3) if ivh else 0.0,
        "in_degree": in_deg, "out_degree": out_deg, "degree_total": in_deg + out_deg,
        "fan_in_ratio": round(in_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "fan_out_ratio": round(out_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "consolidation_frac": round(in_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "sender_concentration_hhi": _hhi(list(senders.values())),
        "recipient_concentration_hhi": _hhi(list(recipients.values())),
        "coinjoin_tx_count_sampled": cj,
        "round_value_ratio_sampled": round(rv / len(txs), 4) if txs else 0.0,
        "mean_output_count_sampled": st(outc, statistics.fmean),
        "mean_input_count_sampled": st(inc, statistics.fmean),
    })
    row["activity_density"] = round(n_tx / max(row["lifespan_days"] or 1.0, 1.0), 4)
    row["tx_velocity"] = round(n_tx / max(row["active_days"], 1), 4)
    return {c: row.get(c, 0) for c in FEATURE_COLUMNS}


def _empty_esplora_row(addr, stats, label, source, atype) -> dict:
    """A confirmed-zero-transaction address."""
    row = {c: 0 for c in FEATURE_COLUMNS}
    row.update({"address": addr, "address_type": atype or "UNKNOWN", "label": label,
                "label_source": source, "data_completeness": "NO_HISTORY",
                "first_tx_time": "", "last_tx_time": ""})
    return row


def features_from_esplora_direct(addr, stats, txs, label, source, atype) -> dict:
    """All 53 attributes from Esplora's /address + /address/txs, called directly."""
    cs = stats.get("chain_stats") or {}
    ms = stats.get("mempool_stats") or {}
    n_tx = int(cs.get("tx_count", 0) or 0)
    funded_sum = int(cs.get("funded_txo_sum", 0) or 0)
    spent_sum = int(cs.get("spent_txo_sum", 0) or 0)
    txs = [t for t in (txs or []) if (t.get("status") or {}).get("confirmed")]

    row = {c: 0 for c in FEATURE_COLUMNS}
    row.update({"address": addr, "address_type": atype or "UNKNOWN", "label": label,
                "label_source": source,
                "data_completeness": "FULL" if n_tx <= len(txs) else "SAMPLED",
                "tx_count": n_tx,
                "funded_txo_count": int(cs.get("funded_txo_count", 0) or 0),
                "spent_txo_count": int(cs.get("spent_txo_count", 0) or 0),
                "total_received_sat": funded_sum, "total_sent_sat": spent_sum,
                "balance_sat": funded_sum - spent_sum,
                "net_flow_sat": funded_sum - spent_sum,
                "mempool_tx_count": int(ms.get("tx_count", 0) or 0)})
    row["total_received_btc"] = round(funded_sum / 1e8, 8)
    row["total_sent_btc"] = round(spent_sum / 1e8, 8)
    row["balance_btc"] = round((funded_sum - spent_sum) / 1e8, 8)
    if not txs:
        return {c: row.get(c, 0) for c in FEATURE_COLUMNS}

    recv, sent, fees, rates, outc, inc, times = [], [], [], [], [], [], []
    senders, recipients = {}, {}
    n_send = n_recv = cj = rv = 0
    for t in txs:
        vin, vout = t.get("vin", []) or [], t.get("vout", []) or []
        bt = (t.get("status") or {}).get("block_time")
        if bt:
            times.append(int(bt))
        outc.append(len(vout)); inc.append(len(vin))
        is_in = any((v.get("prevout") or {}).get("scriptpubkey_address") == addr for v in vin)
        got = sum(int(o.get("value", 0) or 0) for o in vout
                  if o.get("scriptpubkey_address") == addr)
        if got > 0:
            recv.append(got); n_recv += 1
        if is_in:
            n_send += 1
            put = sum(int((v.get("prevout") or {}).get("value", 0) or 0) for v in vin
                      if (v.get("prevout") or {}).get("scriptpubkey_address") == addr)
            if put > 0:
                sent.append(put)
            f = int(t.get("fee", 0) or 0)
            if f > 0:
                fees.append(f)
                vs = (t.get("weight") or 0) / 4.0 or float(t.get("size") or 0)
                if vs > 0:
                    rates.append(f / vs)
        for v in vin:
            a = (v.get("prevout") or {}).get("scriptpubkey_address")
            if a and a != addr:
                senders[a] = senders.get(a, 0) + int((v.get("prevout") or {}).get("value", 0) or 0)
        for o in vout:
            a = o.get("scriptpubkey_address")
            if a and a != addr:
                recipients[a] = recipients.get(a, 0) + int(o.get("value", 0) or 0)
        vals = [int(o.get("value", 0) or 0) for o in vout]
        if len(vals) >= 5 and len(set(vals)) <= max(1, len(vals) // 3):
            cj += 1
        if any(_round_value(v) for v in vals):
            rv += 1

    st = lambda xs, f, d=0.0: round(f(xs), 3) if xs else d
    times.sort()
    ivh = [(b - a) / 3600.0 for a, b in zip(times, times[1:])]
    in_deg, out_deg = len(senders), len(recipients)
    row.update({
        "n_tx_as_sender_sampled": n_send, "n_tx_as_receiver_sampled": n_recv,
        "n_unique_counterparties": len(set(senders) | set(recipients)),
        "mean_received_sat": st(recv, statistics.fmean),
        "max_received_sat": max(recv) if recv else 0,
        "min_received_sat": min(recv) if recv else 0,
        "std_received_sat": st(recv, statistics.pstdev) if len(recv) > 1 else 0.0,
        "mean_sent_sat": st(sent, statistics.fmean),
        "max_sent_sat": max(sent) if sent else 0,
        "min_sent_sat": min(sent) if sent else 0,
        "std_sent_sat": st(sent, statistics.pstdev) if len(sent) > 1 else 0.0,
        "total_fee_sat_sampled": sum(fees), "mean_fee_sat": st(fees, statistics.fmean),
        "mean_fee_rate_sat_vb": st(rates, statistics.fmean),
        "first_tx_time": pd.to_datetime(times[0], unit="s", utc=True).isoformat(),
        "last_tx_time": pd.to_datetime(times[-1], unit="s", utc=True).isoformat(),
        "lifespan_days": round((times[-1] - times[0]) / 86400.0, 3) if len(times) > 1 else 0.0,
        "active_days": len({t // 86400 for t in times}),
        "mean_inter_tx_hours": st(ivh, statistics.fmean),
        "std_inter_tx_hours": st(ivh, statistics.pstdev) if len(ivh) > 1 else 0.0,
        "max_dormancy_days": round(max(ivh) / 24.0, 3) if ivh else 0.0,
        "in_degree": in_deg, "out_degree": out_deg, "degree_total": in_deg + out_deg,
        "fan_in_ratio": round(in_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "fan_out_ratio": round(out_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "consolidation_frac": round(in_deg / (in_deg + out_deg), 4) if (in_deg + out_deg) else 0.0,
        "sender_concentration_hhi": _hhi(list(senders.values())),
        "recipient_concentration_hhi": _hhi(list(recipients.values())),
        "coinjoin_tx_count_sampled": cj,
        "round_value_ratio_sampled": round(rv / len(txs), 4) if txs else 0.0,
        "mean_output_count_sampled": st(outc, statistics.fmean),
        "mean_input_count_sampled": st(inc, statistics.fmean),
    })
    row["activity_density"] = round(n_tx / max(row["lifespan_days"] or 1.0, 1.0), 4)
    row["tx_velocity"] = round(n_tx / max(row["active_days"], 1), 4)
    return {c: row.get(c, 0) for c in FEATURE_COLUMNS}


# ─────────────────────────────────────────────────────────────────────────────
# FETCH ONE ADDRESS — tries endpoints via Rotor until one answers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_one(rec, rotor, deadline_s=45.0):
    """Try endpoints in rotation until one answers, OR the per-address deadline expires."""
    addr, cls, src, atype = rec
    label = {"blacklisted": "ILLICIT", "grey": "ILLICIT", "white": "LICIT"}.get(cls, "UNKNOWN")
    give_up_at = time.time() + deadline_s
    for _ in range(len(ENDPOINTS) * 2):
        if time.time() > give_up_at:
            return None
        e = rotor.pick()
        if e is None:
            time.sleep(1.0)
            continue
        try:
            if e["kind"] == "blockchain":
                d = _get(e["url"].format(a=addr))
                row = features_from_blockchain_info(addr, d, label, src, atype)
            elif e["kind"] == "trezor":
                d = _get(e["url"].format(a=addr))
                row = features_from_trezor(addr, d, label, src, atype)
            elif e["kind"] == "esplora_direct":
                stats = _get(f"{e['url']}/address/{addr}", timeout=15)
                cs = stats.get("chain_stats") or {}
                if int(cs.get("tx_count", 0) or 0) == 0:
                    row = _empty_esplora_row(addr, stats, label, src, atype)
                else:
                    txs = _get(f"{e['url']}/address/{addr}/txs", timeout=20)
                    row = features_from_esplora_direct(addr, stats, txs, label, src, atype)
            else:
                continue
            rotor.reward(e)
            row["class"] = cls
            row["source_api"] = e["name"]
            return row
        except urllib.error.HTTPError as ex:
            if ex.code in (429, 430):
                rotor.penalise(e, 300.0)
            elif ex.code in (400, 404, 422):
                return None  # bad address, not bad endpoint
            elif ex.code in (500, 502, 503, 504):
                rotor.penalise(e, 5.0)
            else:
                rotor.penalise(e, 60.0)
        except Exception:
            rotor.penalise(e, 45.0)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# QUEUE INPUT AND LOCK SAFETY

QUEUE_COLUMNS = ["address", "class", "label", "label_source", "address_type", "feature_status"]


def load_queue(path: Path) -> pd.DataFrame:
    """Load a canonical CSV/Parquet queue or raw kaggle_all_addresses.csv."""
    if not path.exists():
        raise FileNotFoundError(f"Queue file does not exist: {path}")
    try:
        if path.suffix.lower() == ".parquet":
            q = pd.read_parquet(path)
        elif path.suffix.lower() == ".csv":
            q = pd.read_csv(path, low_memory=False, dtype={"address": "string"})
        else:
            raise ValueError("Queue must be a .csv or .parquet file")
    except Exception as exc:
        raise RuntimeError(f"Could not read queue {path}: {exc}") from exc

    if "class" not in q.columns:
        # Raw Kaggle inventory: only clean/blacklisted targets are labels; all
        # other records deliberately remain unlabelled.
        if not {"address", "target", "source"}.issubset(q.columns):
            raise ValueError(f"Queue {path} has no class column and is not a supported raw Kaggle CSV")
        target = q["target"].fillna("").astype(str).str.lower()
        q["class"] = target.map({"clean": "white", "blacklisted": "blacklisted"}).fillna("unlabelled")
        q["label"] = q["class"].map({"white": "LICIT", "blacklisted": "ILLICIT"}).fillna("UNKNOWN")
        q["label_source"] = q["source"].fillna("KAGGLE_UNKNOWN").astype(str)
        q["address_type"] = "UNKNOWN"
        q["feature_status"] = "NOT_MEASURED"

    missing = set(QUEUE_COLUMNS) - set(q.columns)
    if missing:
        raise ValueError(f"Queue {path} is missing required columns: {sorted(missing)}")
    q = q[QUEUE_COLUMNS].copy()
    q["address"] = q["address"].astype(str).str.strip()
    q = q[q["address"].ne("")].drop_duplicates("address", keep="first")
    if q.empty:
        raise ValueError(f"Queue {path} has no usable addresses")
    return q


def _pid_alive(pid: int) -> bool:
    """Best-effort check to prevent a second process stealing a live lock."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global ACTIVE_LOCK
    ap = argparse.ArgumentParser(
        description="Server-side reverse backfill — standalone, 24/7 ready.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__)
    ap.add_argument("--queue", required=True,
                    help="CSV or Parquet queue (e.g. queues/kaggle_all_addresses.csv)")
    ap.add_argument("--out", required=True,
                    help="Output CSV path (e.g. output/backfill_kaggle_reverse.csv)")
    ap.add_argument("--reverse", action="store_true", default=True,
                    help="Work from the END of the queue backwards (default: True)")
    ap.add_argument("--forward", action="store_true",
                    help="Work from the START of the queue forwards (overrides --reverse)")
    ap.add_argument("--workers", type=int, default=4,
                    help="Concurrent fetch threads (default: 4)")
    ap.add_argument("--pace", type=float, default=6.0,
                    help="Min seconds between requests to the SAME endpoint (default: 6.0)")
    ap.add_argument("--chunk", type=int, default=50,
                    help="Rows per flush to disk (default: 50)")
    ap.add_argument("--deadline", type=float, default=45.0,
                    help="Max seconds per address before skipping (default: 45)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Max addresses to fetch this run (0 = all remaining)")
    ap.add_argument("--exclude", nargs="*", default=[],
                    help="Other backfill CSVs whose addresses are already done")
    ap.add_argument("--endpoints", nargs="*", default=[],
                    help="Use ONLY these endpoint names (e.g. blockstream emzy)")
    ap.add_argument("--status", action="store_true",
                    help="Just report progress and exit")
    args = ap.parse_args()

    if args.forward:
        args.reverse = False

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    # ── Lock file ────────────────────────────────────────────────────────
    lock = out.with_suffix(out.suffix + ".lock")
    if not args.status:
        if lock.exists():
            age = time.time() - lock.stat().st_mtime
            try:
                owner_pid = int(lock.read_text(encoding="utf-8").strip())
            except Exception:
                owner_pid = -1
            if _pid_alive(owner_pid):
                print(f"[lock] another backfill is already running (PID {owner_pid}, lock {age:.0f}s old).")
                sys.exit(1)
            print(f"[lock] stale lock ({age/60:.0f} min old) — taking over")
        lock.write_text(str(os.getpid()), encoding="utf-8")
        ACTIVE_LOCK = lock

    # ── Already done ─────────────────────────────────────────────────────
    done = set()
    for src in [out] + [Path(x) for x in args.exclude]:
        if src.exists() and src.stat().st_size > 0:
            try:
                done |= set(pd.read_csv(src, usecols=["address"], low_memory=False)["address"])
            except Exception:
                pass

    # ── Load queue ───────────────────────────────────────────────────────
    try:
        q = load_queue(Path(args.queue))
    except Exception as exc:
        print(f"[fatal] {exc}", file=sys.stderr)
        return 2
    miss = q[~q.address.isin(done)]

    print(f"[queue ] {len(q):,} total addresses in queue")
    print(f"[done  ] {len(done):,} already fetched (skipping)")
    print(f"[remain] {len(miss):,} addresses remaining")

    if args.status:
        if done:
            try:
                d = pd.read_csv(out, usecols=["address", "class", "data_completeness",
                                               "source_api"], low_memory=False)
                print(f"\n[stats ] by class: {d['class'].value_counts().to_dict()}")
                print(f"[stats ] by completeness: {d['data_completeness'].value_counts().to_dict()}")
                print(f"[stats ] by endpoint: {d['source_api'].value_counts().to_dict()}")
            except Exception:
                pass
        return

    if miss.empty:
        print("[done  ] nothing left to fetch!")
        return

    # ── Filter non-Bitcoin addresses ─────────────────────────────────────
    BTC_RE = re.compile(r"^(bc1[a-z0-9]{8,87}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
    valid = miss.address.astype(str).str.match(BTC_RE)
    if (~valid).any():
        print(f"[skip  ] {int((~valid).sum())} non-Bitcoin address(es) excluded")
    miss = miss[valid]

    # ── Endpoint filter ──────────────────────────────────────────────────
    if args.endpoints:
        keep = {e.lower() for e in args.endpoints}
        before = len(ENDPOINTS)
        ENDPOINTS[:] = [e for e in ENDPOINTS if any(k in e["name"].lower() for k in keep)]
        if not ENDPOINTS:
            raise SystemExit(f"[fatal] --endpoints matched nothing. "
                             f"Available: {[e['name'] for e in _ALL_ENDPOINTS]}")
        print(f"[endpts] restricted {before} -> {len(ENDPOINTS)}: "
              f"{[e['name'] for e in ENDPOINTS]}")

    # ── Direction ────────────────────────────────────────────────────────
    if args.reverse:
        miss = miss.iloc[::-1]
        print("[order ] REVERSE — working from end of queue backwards")
    else:
        print("[order ] FORWARD — working from start of queue forwards")

    todo = miss if not args.limit else miss.head(args.limit)
    recs = list(zip(todo.address, todo["class"], todo.label_source, todo.address_type))
    rotor = Rotor(ENDPOINTS, min_interval=args.pace)

    print(f"[start ] {len(recs):,} addresses to fetch with {args.workers} workers")
    print(f"[endpts] {len(ENDPOINTS)} endpoints, {args.pace}s pacing each")
    print(f"[start ] {datetime.now(timezone.utc).isoformat()}\n")

    # ── CSV writer ───────────────────────────────────────────────────────
    cols = list(FEATURE_COLUMNS) + ["class", "source_api"]
    new = not out.exists() or out.stat().st_size == 0
    fh = open(out, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    if new:
        w.writeheader()

    # ── Graceful shutdown ────────────────────────────────────────────────
    shutdown = threading.Event()

    def _sig(signum, frame):
        print("\n[signal] Caught signal, finishing current chunk then stopping...")
        shutdown.set()

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    # ── Main loop ────────────────────────────────────────────────────────
    t0, wrote, failed, tally = time.time(), 0, 0, {}
    for i in range(0, len(recs), args.chunk):
        if shutdown.is_set():
            break
        batch = recs[i:i + args.chunk]
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            rows = [r for r in ex.map(
                lambda r: fetch_one(r, rotor, args.deadline), batch) if r]
        failed += len(batch) - len(rows)
        for r in rows:
            w.writerow(r)
            k = r.get("data_completeness", "?")
            tally[k] = tally.get(k, 0) + 1
        fh.flush()
        wrote += len(rows)
        el = time.time() - t0
        rate = wrote / max(el, 1e-9)
        remaining = len(recs) - (i + len(batch))
        eta_min = remaining / max(rate, 1e-9) / 60
        eta_hr = eta_min / 60
        print(f"  [{wrote:>6,}/{len(recs):,}] {el/60:5.1f}min "
              f"({rate:.2f}/s) got {len(rows)}/{len(batch)} failed {failed} "
              f"| ETA {eta_hr:.1f}h | {tally}")
        print(f"        {rotor.report()}")

    fh.close()
    total = time.time() - t0
    print(f"\n[done  ] {wrote:,} addresses in {total/60:.1f} min "
          f"({wrote/max(total,1e-9):.2f}/s)")
    print(f"[done  ] completeness: {tally}")
    print(f"[done  ] wrote -> {out}")
    if shutdown.is_set():
        print("[retry ] interrupted before all remaining addresses were attempted")
        return 130
    if failed:
        print(f"[retry ] {failed} address(es) failed this pass; exiting non-zero so the wrapper retries them")
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        # Never interfere with the other parallel batch's lock.
        if ACTIVE_LOCK is not None:
            try:
                ACTIVE_LOCK.unlink(missing_ok=True)
            except Exception:
                pass
