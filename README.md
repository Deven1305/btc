# BTC-Intel Server Backfill

For the exact Ubuntu checks, GitHub authentication test, and copy-paste push commands, see [GITHUB_PUSH_TEST.md](GITHUB_PUSH_TEST.md).

## Queue files: CSV and Parquet

Both formats are supplied. Parquet is faster and smaller; CSV is the portable fallback if `pyarrow` cannot be installed.

| Dataset | CSV (default/fallback) | Parquet (faster) | Rows |
|---|---|---|---:|
| Kaggle | `queues/kaggle_all_addresses.csv` | `queues/queue_kaggle_esplora.parquet` | 1,970,747 |
| Elliptic++ | `queues/queue_elliptic_pp.csv` | `queues/queue_elliptic_pp.parquet` | 265,337 |

The Kaggle wrapper uses the exhaustive CSV and processes it from its final row to its first row. It maps `clean` to `white`, `blacklisted` to `blacklisted`, and all other records to `unlabelled`. To use the faster Parquet file instead, replace its queue argument with `queues/queue_kaggle_esplora.parquet`.

**24/7 reverse-direction Bitcoin address feature extraction for the BTC-Intel research dataset.**

This folder runs on your college Ubuntu server. It extracts all **53 on-chain features** for **~2.23 Million Bitcoin addresses** (1.97M Kaggle BABD/BASD + 265K Elliptic++) from 12 free public API endpoints, working the queue **backwards** while your local machine works forwards. They meet in the middle — no duplicates.

---

## ⚡ One-Line Server Specs & Storage Check (Instant Copy-Paste)

Paste this single command into the Ubuntu terminal to instantly inspect all hardware capacity (CPU, RAM, GPU, Disks, OS) safely and without affecting any running tasks:

```bash
echo "=== 🖥️ HOST & OS ===" && hostnamectl | grep -E "Static hostname|Operating System|Kernel|Architecture" && \
echo -e "\n=== 🧠 CPU ===" && lscpu | grep -E "Model name|Socket|Core|Thread|CPU max MHz|Virtualization" && \
echo -e "\n=== 💾 RAM / MEMORY ===" && free -h && \
echo -e "\n=== 💽 DISK STORAGE ===" && df -h -x tmpfs -x devtmpfs -x squashfs && \
echo -e "\n=== 🎮 GPU ===" && (nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader 2>/dev/null || lspci | grep -i -E "vga|3d|display") && \
echo -e "\n=== ⏱️ UPTIME & USER ===" && echo "User: $(whoami) | Uptime: $(uptime -p)"
```

---

## What this does

| Queue | Total Addresses | Breakdown | Server Direction |
|---|---:|---|---|
| **Kaggle (BABD/BASD)** | **1,970,747** | 436K labelled seeds + 1.01M graph neighbours + 411K ledger | **Reverse (from row 1,970,747 down to 1)** |
| **Elliptic++** | **265,337** | 265K actor addresses | **Reverse (from row 265,337 down to 1)** |

Both batches run simultaneously in separate `tmux` sessions.

---

## Server Setup — Step by Step

### Step 0: Check your environment & identity

```bash
# Check who you are and where you are:
whoami
hostname
pwd

# Check Ubuntu version & disk:
lsb_release -a
df -h .
```

### Step 1: System update

```bash
# Refresh package metadata only. Do not run a system-wide upgrade on a shared server.
sudo apt update
```

### Step 2: Install dependencies

```bash
# Python 3 + pip (likely already installed on Ubuntu GUI)
sudo apt install -y python3 python3-pip python3-venv git git-lfs tmux

# Verify
python3 --version
pip3 --version
git --version
tmux -V
```

### Step 3: Create a dedicated working directory

> **IMPORTANT:** Create your own folder so you don't disturb anyone else's work on the server.

```bash
# Create your workspace (change 'deven' to your username if different)
mkdir -p ~/btc-intel-backfill
cd ~/btc-intel-backfill
```

### Step 4: Clone this repo

```bash
git clone https://github.com/Deven1305/btc.git
cd btc/server_backfill
git lfs install
git lfs pull
```

### Step 5: Set up Python virtual environment

```bash
# Create isolated environment (won't affect system Python)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify pandas + pyarrow work
python3 -c "import pandas; import pyarrow; print('OK:', pandas.__version__)"
```

### Step 6: Make scripts executable

```bash
chmod +x run_kaggle_reverse.sh
chmod +x run_elliptic_reverse.sh
```

### Step 7: Verify with a dry run (5 addresses only)

```bash
# Test Kaggle queue
python3 backfill_server.py \
    --queue queues/queue_kaggle_esplora.parquet \
    --out output/test_kaggle.csv \
    --reverse --limit 5

# Check it worked
head -6 output/test_kaggle.csv
wc -l output/test_kaggle.csv

# Clean up test file
rm output/test_kaggle.csv

# Test Elliptic queue
python3 backfill_server.py \
    --queue queues/queue_elliptic_pp.parquet \
    --out output/test_elliptic.csv \
    --reverse --limit 5

head -6 output/test_elliptic.csv
rm output/test_elliptic.csv
```

If both produce CSV rows with data, you're good to go.

---

## Running the Backfill (24/7)

### Start both batches in parallel

```bash
# Make sure you're in the right directory and venv is active
cd ~/btc-intel-backfill/btc/server_backfill
source venv/bin/activate

# Start Kaggle reverse backfill in a tmux session
tmux new-session -d -s kaggle 'source venv/bin/activate && ./run_kaggle_reverse.sh'

# Start Elliptic++ reverse backfill in a separate tmux session
tmux new-session -d -s elliptic 'source venv/bin/activate && ./run_elliptic_reverse.sh'

# Start 11:00 PM Auto-Sync Daemon to push progress to GitHub automatically
tmux new-session -d -s sync 'source venv/bin/activate && ./run_sync_daemon.sh'

# Verify all 3 are running
tmux list-sessions
```

You should see:
```
elliptic: 1 windows ...
kaggle: 1 windows ...
sync: 1 windows ...
```

> 📖 **Remote Monitoring Guide:** See [REMOTE_MONITORING_AND_AUTO_PUSH.md](REMOTE_MONITORING_AND_AUTO_PUSH.md) for how to check progress from home and view the live `STATUS.md` on GitHub.
```

### Watch live progress

```bash
# Watch Kaggle progress
tmux attach -t kaggle
# Press Ctrl+B then D to detach (keeps running)

# Watch Elliptic++ progress
tmux attach -t elliptic
# Press Ctrl+B then D to detach
```

### Check progress without attaching

```bash
# Quick status
source venv/bin/activate
python3 backfill_server.py --queue queues/queue_kaggle_esplora.parquet \
    --out output/backfill_kaggle_reverse.csv --status

python3 backfill_server.py --queue queues/queue_elliptic_pp.parquet \
    --out output/backfill_elliptic_reverse.csv --status

# Row counts
wc -l output/backfill_kaggle_reverse.csv
wc -l output/backfill_elliptic_reverse.csv

# Last few log lines
tail -20 logs/kaggle_reverse.log
tail -20 logs/elliptic_reverse.log
```

---

## Stopping Safely

```bash
# Graceful stop (finishes current chunk, then exits)
tmux send-keys -t kaggle C-c
tmux send-keys -t elliptic C-c

# Wait a few seconds for clean shutdown, then kill sessions
tmux kill-session -t kaggle
tmux kill-session -t elliptic
```

> The scripts flush after every chunk (50 addresses), so even a hard kill loses at most 50 rows.

---

## Pulling Results Back

### Option A: From the server terminal (if VS Code is available)

```bash
# Push results to GitHub from the server
cd ~/btc-intel-backfill/btc/server_backfill
git add output/*.csv
git commit -m "Server reverse backfill progress $(date +%Y-%m-%d)"
git push
```

### Option B: SCP from your local machine

```bash
# From your Windows machine (Git Bash or WSL)
scp username@server-ip:~/btc-intel-backfill/btc/server_backfill/output/*.csv .
```

### Option C: Via VS Code remote

If VS Code is installed on the server with GUI, just open the folder and copy files.

---

## Merging Results

After both directions are complete, merge on your local machine:

```python
import pandas as pd

# Forward (local)
fwd = pd.read_csv("backfill_kaggle_esplora.csv", low_memory=False)

# Reverse (server)
rev = pd.read_csv("backfill_kaggle_reverse.csv", low_memory=False)

# Merge and dedup (forward takes priority — it was fetched first)
merged = pd.concat([fwd, rev]).drop_duplicates("address", keep="first")
merged.to_csv("backfill_kaggle_COMPLETE.csv", index=False)
print(f"Forward: {len(fwd):,}  Reverse: {len(rev):,}  Merged: {len(merged):,}")
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `[lock] another backfill is already running` | Delete the stale lock: `rm output/*.lock` |
| `ModuleNotFoundError: No module named 'pandas'` | Activate venv: `source venv/bin/activate` |
| All endpoints benched | Wait ~5 min (cooldowns expire). Or reduce `--pace` to 8.0 |
| Very slow (<0.5 addr/s) | Server IP might be rate-limited. Try `--endpoints blockstream emzy bitaroo` |
| Permission denied on scripts | `chmod +x run_*.sh` |
| tmux: command not found | `sudo apt install tmux` |
| Disk full | Check `df -h`. Each CSV is ~400 bytes/row → 207K rows ≈ 80MB |

---

## File Structure

```
server_backfill/
├── backfill_server.py          # Main script (standalone, no dependencies on btc-intel)
├── run_kaggle_reverse.sh       # tmux wrapper for Kaggle batch
├── run_elliptic_reverse.sh     # tmux wrapper for Elliptic++ batch
├── requirements.txt            # pandas + pyarrow
├── README.md                   # This file
├── queues/                     # Queue parquet files (committed)
│   ├── queue_kaggle_esplora.parquet
│   └── queue_elliptic_pp.parquet
├── output/                     # Created at runtime
│   ├── backfill_kaggle_reverse.csv
│   └── backfill_elliptic_reverse.csv
└── logs/                       # Created at runtime
    ├── kaggle_reverse.log
    └── elliptic_reverse.log
```

---

## How it works (technical)

1. **12 public endpoints** are rotated via a `Rotor` that paces each one independently (default 6s between requests to the same host)
2. Each address goes through: pick endpoint → HTTP GET → parse JSON → compute 53 features → write CSV row
3. On `HTTP 429` (rate limit), that specific endpoint is **benched for 5 minutes** while others continue
4. On `HTTP 400/404` (bad address), the address is **skipped** (not the endpoint's fault)
5. Each address has a **45-second deadline** — if no endpoint answers in time, skip and retry next run
6. Output CSV is **append-only** and flushed after every chunk of 50 addresses
7. On restart, the script reads the existing CSV to find already-done addresses and skips them

**Sustained throughput:** ~2 addresses/second with 12 endpoints at 6s pacing = **~7,200 addresses/hour**.
