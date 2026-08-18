#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# run_elliptic_reverse.sh — Run Elliptic++ reverse backfill in a loop
#
# Designed for 24/7 server operation. Auto-restarts on crash with a 30s cooldown.
# Runs with 'nice -n 10' for polite CPU scheduling so it never impacts other tasks.
# Run inside tmux so it survives SSH disconnection.
#
# Usage:
#   tmux new-session -d -s elliptic './run_elliptic_reverse.sh'
#   tmux attach -t elliptic    # to watch live
#   Ctrl+B then D              # to detach (keeps running)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p output logs

LOG="logs/elliptic_reverse.log"

# Auto-activate venv if present
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "========================================" | tee -a "$LOG"
echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Elliptic++ reverse backfill STARTING" | tee -a "$LOG"
echo "Host: $(hostname), User: $(whoami), PID: $$" | tee -a "$LOG"
echo "========================================" | tee -a "$LOG"

while true; do
    echo "" | tee -a "$LOG"
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] === RUN STARTING ===" | tee -a "$LOG"

    # Runs with polite CPU priority (nice -n 10) to never disturb other server users
    nice -n 10 python3 backfill_server.py \
        --queue queues/queue_elliptic_pp.parquet \
        --out output/backfill_elliptic_reverse.csv \
        --reverse \
        --workers 4 \
        --pace 6.0 \
        --chunk 50 \
        --deadline 45 \
        2>&1 | tee -a "$LOG"

    EXIT_CODE=${PIPESTATUS[0]}

    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Queue complete! Exiting." | tee -a "$LOG"
        break
    fi

    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Crashed (exit $EXIT_CODE). Restarting in 30s..." | tee -a "$LOG"
    sleep 30
done
