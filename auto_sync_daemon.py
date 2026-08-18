#!/usr/bin/env python3
r"""
auto_sync_daemon.py — Background daemon that automatically pushes progress to GitHub.

Runs 24/7. Executes sync_status.py --push immediately at startup and then
every six hours by default. Set SYNC_INTERVAL_HOURS to override the interval.

Usage:
  python3 auto_sync_daemon.py
  (or via ./run_sync_daemon.sh in a tmux session)
"""
from __future__ import annotations

import datetime
import os
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SYNC_SCRIPT = SCRIPT_DIR / "sync_status.py"
SYNC_INTERVAL_HOURS = float(os.environ.get("SYNC_INTERVAL_HOURS", "6"))
if SYNC_INTERVAL_HOURS <= 0:
    raise ValueError("SYNC_INTERVAL_HOURS must be positive")


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
    print("Schedule: immediate sync, then every "
          f"{SYNC_INTERVAL_HOURS:g} hours")
    print("=" * 60)

    # Initial sync on startup
    run_sync()

    last_sync_at = time.monotonic()

    while True:
        try:
            if time.monotonic() - last_sync_at >= SYNC_INTERVAL_HOURS * 3600:
                run_sync()
                last_sync_at = time.monotonic()

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
