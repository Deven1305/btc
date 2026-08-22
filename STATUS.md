# BTC-Intel Server Backfill — Live Status Report

> **Last Updated:** `2026-08-22 11:08:17 AM IST` (`2026-08-22 05:38:17 UTC`)  
> **Server Disk Space:** `576.75 GB free out of 1830.18 GB (64.4% used)`

---

## 1. Overall Progress Summary

| Dataset Queue | Queue Total | Fetched by Server (Reverse) | % Completed | File Size | Last File Update |
|---|---:|---:|---:|---:|---|
| **Kaggle (BABD/BASD)** | **1,970,747** | **264,387** | **13.42%** | 97.01 MB | 2026-08-22 05:37:09 UTC |
| **Elliptic++** | **265,337** | **203,414** | **76.66%** | 77.57 MB | 2026-08-22 05:38:05 UTC |
| **Total Combined** | **2,236,084** | **467,801** | **20.92%** | 174.58 MB | — |

---

## 2. Server Process Health

- tmux: `elliptic` session ACTIVE
- tmux: `kaggle` session ACTIVE
- Python workers: 2 process(es) running

---

## 3. Kaggle Reverse Batch Details

- **Output CSV:** [`output/backfill_kaggle_reverse.csv`](output/backfill_kaggle_reverse.csv)
- **Rows Written:** `264,387` / `1,970,747`
- **Class Breakdown:** `{'unlabelled': 264387}`
- **Data Completeness:** `{'FULL': 220336, 'SAMPLED': 44049, 'NO_HISTORY': 2}`
- **Top Active Endpoints:** `{'emzy': 42669, 'bitaroo': 42638, 'exan': 42153, 'atomic': 25782, 'trezor-btc4': 25501, 'mempool.space': 22711, 'trezor-btc1': 15440, 'trezor-btc2': 13435, 'trezor-btc5': 13175, 'trezor-btc3': 12644}`
- **Latest Addresses Fetched:**
  - `bc1q8g9x8uwcyc47wypjjmjsn0sldustdr0ynx0sk0`
  - `15vaPKepLr6sht6akNnRjZFPBvt1pwtq4k`
  - `bc1q4kp7hwe3e2kfchf3ygvnrrryfmm78hd5vrhqgu`

### Latest Log Snippet (Kaggle)
> `trezor-btc1:15410ok/4587f(benched)  trezor-btc2:13416ok/5992f(benched)  trezor-btc3:12639ok/6178f(benched)  trezor-btc4:25479ok/3256f  trezor-btc5:13162ok/5187f(benched)  blockchain.info:501ok/1072f(benched)  blockstream:7738ok/896f(benched)  mempool.space:22672ok/571f(benched)  emzy:42618ok/26f  bitaroo:42587ok/28f  exan:42102ok/109f  atomic:25763ok/2499f(benched)`
> `[264,137/1,970,747] 5573.8min (0.79/s) got 50/50 failed 163 | ETA 600.2h | {'FULL': 220128, 'SAMPLED': 44007, 'NO_HISTORY': 2}`
> `trezor-btc1:15420ok/4587f  trezor-btc2:13419ok/5993f  trezor-btc3:12639ok/6178f(benched)  trezor-btc4:25481ok/3258f(benched)  trezor-btc5:13162ok/5187f(benched)  blockchain.info:501ok/1072f(benched)  blockstream:7738ok/897f(benched)  mempool.space:22672ok/571f(benched)  emzy:42630ok/26f  bitaroo:42599ok/28f  exan:42113ok/109f  atomic:25763ok/2500f(benched)`
> `[264,187/1,970,747] 5574.9min (0.79/s) got 50/50 failed 163 | ETA 600.1h | {'FULL': 220172, 'SAMPLED': 44013, 'NO_HISTORY': 2}`
> `trezor-btc1:15428ok/4587f  trezor-btc2:13420ok/5994f  trezor-btc3:12639ok/6178f(benched)  trezor-btc4:25482ok/3258f  trezor-btc5:13162ok/5187f(benched)  blockchain.info:501ok/1072f(benched)  blockstream:7738ok/897f(benched)  mempool.space:22680ok/571f  emzy:42638ok/26f  bitaroo:42607ok/28f  exan:42122ok/109f  atomic:25770ok/2500f`

---

## 4. Elliptic++ Reverse Batch Details

- **Output CSV:** [`output/backfill_elliptic_reverse.csv`](output/backfill_elliptic_reverse.csv)
- **Rows Written:** `203,414` / `265,337`
- **Class Breakdown:** `{'white': 189156, 'blacklisted': 14258}`
- **Data Completeness:** `{'FULL': 134648, 'SAMPLED': 68766}`
- **Top Active Endpoints:** `{'bitaroo': 33113, 'emzy': 32964, 'exan': 32701, 'atomic': 19424, 'trezor-btc4': 19174, 'mempool.space': 18591, 'trezor-btc1': 11742, 'trezor-btc2': 10594, 'trezor-btc5': 9870, 'trezor-btc3': 9358}`
- **Latest Addresses Fetched:**
  - `18bhYtQJZ1CgRkFVZed25v8ZyxRDFV6ZNF`
  - `18bgpiW8chvXajPB5aKRv1yLTP72Z6GWsR`
  - `18bgdWHRDJuvFTJR4wGqHGaFXi1s7hThS6`

### Latest Log Snippet (Elliptic++)
> `trezor-btc1:11689ok/3999f  trezor-btc2:10544ok/4743f(benched)  trezor-btc3:9294ok/4779f(benched)  trezor-btc4:19067ok/3190f  trezor-btc5:9833ok/3956f(benched)  blockchain.info:485ok/1047f(benched)  blockstream:5396ok/885f(benched)  mempool.space:18544ok/500f  emzy:32775ok/45f  bitaroo:32923ok/36f  exan:32514ok/97f  atomic:19350ok/2420f`
> `[202,464/265,337] 5554.6min (0.61/s) got 50/50 failed 86 | ETA 28.7h | {'SAMPLED': 68435, 'FULL': 134029}`
> `trezor-btc1:11698ok/4000f  trezor-btc2:10544ok/4744f  trezor-btc3:9295ok/4780f(benched)  trezor-btc4:19069ok/3191f  trezor-btc5:9833ok/3957f  blockchain.info:485ok/1048f(benched)  blockstream:5396ok/886f(benched)  mempool.space:18550ok/501f(benched)  emzy:32784ok/45f  bitaroo:32933ok/36f  exan:32524ok/97f  atomic:19353ok/2421f`
> `[202,514/265,337] 5555.8min (0.61/s) got 50/50 failed 86 | ETA 28.7h | {'SAMPLED': 68450, 'FULL': 134064}`
> `trezor-btc1:11698ok/4001f  trezor-btc2:10549ok/4745f(benched)  trezor-btc3:9295ok/4781f  trezor-btc4:19078ok/3191f  trezor-btc5:9833ok/3959f(benched)  blockchain.info:485ok/1048f(benched)  blockstream:5396ok/886f(benched)  mempool.space:18550ok/501f(benched)  emzy:32793ok/45f  bitaroo:32942ok/36f  exan:32533ok/97f  atomic:19362ok/2421f`

---

## 5. CSV Integrity Check

- Kaggle CSV Valid Header & Formatted Rows: **PASSED**
- Elliptic CSV Valid Header & Formatted Rows: **PASSED**

---
*Auto-generated by `sync_status.py` on the Ubuntu Server.*
