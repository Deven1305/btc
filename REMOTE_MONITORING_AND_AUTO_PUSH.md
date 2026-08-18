# Remote Monitoring & 11:00 PM Auto-Push Guide

This guide explains how to monitor the 24/7 server backfill **remotely from home** without having direct remote SSH access to the college server room, and how the automated **11:00 PM GitHub sync** works.

---

## 1. How to Check Progress Remotely (From Home)

Because you do not have remote SSH access to the college server when you are at home, the server automatically updates this GitHub repository.

You can check progress at any time (on your laptop, phone, or tablet) simply by visiting:
👉 **`https://github.com/Deven1305/btc`**

### What you will see on GitHub:
1. **[`STATUS.md`](STATUS.md)**: A rich, auto-updated dashboard rendered directly in GitHub showing:
   - Total addresses completed vs remaining
   - Percentage done (% completed progress bar)
   - Class breakdown (`white`, `blacklisted`, `grey`)
   - Data completeness breakdown (`FULL`, `SAMPLED`, `NO_HISTORY`)
   - Active API endpoint throughput (Trezor, Esplora, etc.)
   - Last 5 addresses fetched
   - Server process health & disk space
   - Last updated timestamp (in IST & UTC)
2. **`output/backfill_kaggle_reverse.csv`**: The actual fetched CSV dataset with all 53 on-chain attributes.
3. **`output/backfill_elliptic_reverse.csv`**: The Elliptic++ reverse dataset.

---

## 2. Automated Git Sync Options (Choose One)

We provide two easy ways to automate the 11:00 PM (23:00) push to GitHub:

### Option A: `tmux` Auto-Sync Daemon (Recommended — Easiest, No `sudo` Needed)

Run the built-in sync daemon in a `tmux` session alongside the backfill batches:

```bash
# In your server terminal:
cd ~/btc-intel-backfill/btc
source venv/bin/activate
chmod +x run_sync_daemon.sh auto_git_sync.sh

# Start the sync daemon in a tmux session named 'sync'
tmux new-session -d -s sync './run_sync_daemon.sh'

# Verify it is running
tmux list-sessions
```

**What this does:**
- Immediately syncs and pushes upon startup so you can verify it works.
- Automatically triggers a push every day at **11:00 PM (23:00 IST)**.
- Also pushes intermediate updates every 4 hours.
- If it crashes, it automatically retries after 60 seconds.

---

### Option B: Linux `cron` Job (Alternative)

If you prefer standard Linux `cron`:

```bash
# Open crontab editor
crontab -e

# Add this line at the bottom to run every night at 11:00 PM (23:00):
0 23 * * * /bin/bash -c "cd $HOME/btc-intel-backfill/btc && ./auto_git_sync.sh" >> $HOME/btc-intel-backfill/btc/logs/cron.log 2>&1

# Save and exit (in nano: Ctrl+O, Enter, Ctrl+X)
```

To test the cron script immediately:
```bash
./auto_git_sync.sh
```

---

## 3. One-Time Setup: Non-Interactive Git Push on Server

To allow `git push` to run automatically at 11 PM without prompting for your GitHub password:

### Method 1: Personal Access Token (PAT) with Credential Helper (Simplest)

1. On GitHub: Go to **Settings -> Developer Settings -> Personal access tokens -> Tokens (classic)**.
2. Click **Generate new token (classic)**, check `repo` scope, and generate.
3. Copy the token (e.g. `ghp_xxxxxxxxxxxx`).
4. On the Ubuntu server, configure Git to remember your credentials:

```bash
git config --global credential.helper store

# Set the remote URL with your token:
git remote set-url origin https://<YOUR_GITHUB_USERNAME>:<YOUR_TOKEN>@github.com/Deven1305/btc.git

# Test push once:
git push origin main
```
From now on, all automated pushes will succeed automatically in the background with zero prompts!

---

### Method 2: SSH Key (Standard)

```bash
# 1. Generate SSH key on server:
ssh-keygen -t ed25519 -C "college-server" -N "" -f ~/.ssh/id_ed25519

# 2. Display public key:
cat ~/.ssh/id_ed25519.pub

# 3. Copy output, go to GitHub -> Settings -> SSH and GPG keys -> New SSH key -> Paste.

# 4. Change remote to SSH:
git remote set-url origin git@github.com:Deven1305/btc.git

# 5. Test connection:
ssh -T git@github.com
```

---

## 4. How to Verify Everything is Running Properly on Server

If you are at the server or want to verify before leaving the room:

### 1. Check active sessions:
```bash
tmux list-sessions
```
You should see 3 active sessions:
- `kaggle` (fetching Kaggle reverse batch)
- `elliptic` (fetching Elliptic++ reverse batch)
- `sync` (handling auto-push at 11 PM)

### 2. Check live progress:
```bash
# Attach to Kaggle:
tmux attach -t kaggle
# (Press Ctrl+B then D to detach)

# Attach to Elliptic:
tmux attach -t elliptic
# (Press Ctrl+B then D to detach)

# Attach to Sync Daemon:
tmux attach -t sync
# (Press Ctrl+B then D to detach)
```

### 3. Check CSV integrity & line counts without attaching:
```bash
# Generate immediate STATUS.md and check in terminal:
python3 sync_status.py
cat STATUS.md

# Quick row counts:
wc -l output/backfill_kaggle_reverse.csv
wc -l output/backfill_elliptic_reverse.csv
```

### 4. Manually trigger a Git push test:
```bash
./auto_git_sync.sh
```

---

## 5. CSV Health & Integrity Checklist

| Check | What to look for | Command / Check |
|---|---|---|
| **Growing row count** | Number increases over time | `wc -l output/*.csv` |
| **No formatting corruptions** | 55 columns per row, no empty rows | Checked automatically in `STATUS.md` |
| **Active API throughput** | At least 0.8 - 2.0 addr/s | Visible in log / `STATUS.md` |
| **No server collision** | Isolated workspace `~/btc-intel-backfill/` | Check `pwd` |
| **Memory / CPU steady** | < 200MB RAM per worker | `top` / System Monitor |

---

## 6. Full Deployment Command Cheat-Sheet (3-Minute Setup)

```bash
# 1. Workspace setup
mkdir -p ~/btc-intel-backfill
cd ~/btc-intel-backfill
git clone https://github.com/Deven1305/btc.git
cd btc

# 2. Virtual environment & dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
chmod +x run_kaggle_reverse.sh run_elliptic_reverse.sh run_sync_daemon.sh auto_git_sync.sh

# 3. Configure Git credentials (replace with your token)
git config --global credential.helper store
git remote set-url origin https://Deven1305:<TOKEN>@github.com/Deven1305/btc.git

# 4. Launch all 3 tmux sessions
tmux new-session -d -s kaggle 'source venv/bin/activate && ./run_kaggle_reverse.sh'
tmux new-session -d -s elliptic 'source venv/bin/activate && ./run_elliptic_reverse.sh'
tmux new-session -d -s sync 'source venv/bin/activate && ./run_sync_daemon.sh'

# 5. Confirm all 3 are running
tmux list-sessions
```
You can now safely log out of the server and go home. Check your GitHub repo at **11:00 PM** to see the day's progress!
