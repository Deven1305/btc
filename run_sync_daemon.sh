#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# run_sync_daemon.sh — Runs auto_sync_daemon.py in a tmux session
#
# Usage:
#   tmux new-session -d -s sync './run_sync_daemon.sh'
#   tmux attach -t sync
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p logs

LOG="logs/sync_daemon.log"

echo "========================================" | tee -a "$LOG"
echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Auto-Sync Daemon starting" | tee -a "$LOG"
echo "========================================" | tee -a "$LOG"

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

python3 auto_sync_daemon.py 2>&1 | tee -a "$LOG"
