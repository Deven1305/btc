#!/usr/bin/env python3
r"""
auto_sync_daemon.py — Background daemon that automatically pushes progress to GitHub.

Runs 24/7. Automatically executes sync_status.py --push:
  - Every day at 23:00 (11:00 PM local / IST time)
  - Every 4 hours for intermediate progress
  - Immediately upon startup (so you see an initial check on GitHub)

Usage:
  python3 auto_sync_daemon.py
  (or via ./run_sync_daemon.sh in a tmux session)
"""
from __future__ import annotations

import datetime
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SYNC_SCRIPT = SCRIPT_DIR / "sync_status.py"


def run_sync():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{now_str}] 🚀 Triggering automatic GitHub sync & push...")
    try:
        res = subprocess.run([sys.executable, str(SYNC_SCRIPT), "--push"], cwd=SCRIPT_DIR)
        if res.returncode == 0:
            print(f"[{now_str}] ✅ Sync completed successfully!")
        else:
            print(f"[{now_str}] ⚠️ Sync process returned exit code {res.returncode}")
    except Exception as e:
        print(f"[{now_str}] ❌ Error running sync: {e}")


def main():
    print("=" * 60)
    print("BTC-Intel Auto-Sync Daemon Started")
    print(f"Directory: {SCRIPT_DIR}")
    print("Schedule: Immediate sync, then daily at 11:00 PM (23:00) & every 4 hours")
    print("=" * 60)

    # Initial sync on startup
    run_sync()

    last_sync_hour = datetime.datetime.now().hour

    while True:
        try:
            now = datetime.datetime.now()
            
            # Check conditions to trigger sync:
            # 1. Exactly at hour 23 (11:00 PM)
            # 2. Every 4 hours (e.g. 03:00, 07:00, 11:00, 15:00, 19:00, 23:00)
            should_sync = False
            if now.hour != last_sync_hour:
                if now.hour == 23 or (now.hour % 4 == 0):
                    should_sync = True
                last_sync_hour = now.hour

            if should_sync:
                run_sync()

            # Sleep for 60 seconds before next check
            time.sleep(60)
        except KeyboardInterrupt:
            print("\n[Daemon] Stopped by user.")
            break
        except Exception as e:
            print(f"[Daemon] Unexpected error: {e}. Retrying in 60s...")
            time.sleep(60)


if __name__ == "__main__":
    main()
