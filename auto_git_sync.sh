#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# auto_git_sync.sh — Generates STATUS.md, commits output CSVs, and pushes to GitHub
#
# Can be executed manually, by cron, or by the sync daemon.
#
# Usage:
#   ./auto_git_sync.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p logs output

LOG="logs/auto_sync.log"

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Running auto_git_sync..." | tee -a "$LOG"

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Run the python sync script with --push flag
python3 sync_status.py --push 2>&1 | tee -a "$LOG"

echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] Auto-sync finished." | tee -a "$LOG"
