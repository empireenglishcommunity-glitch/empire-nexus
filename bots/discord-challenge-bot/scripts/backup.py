#!/usr/bin/env python3
"""
Backup utility for the Empire Challenge Bot database.

Usage:
    python scripts/backup.py              # Backup to default location
    python scripts/backup.py /path/to/dir # Backup to custom directory

The script:
  1. Creates a timestamped copy of the SQLite database
  2. Keeps the last N backups (default: 14) and deletes older ones
  3. Prints the backup path on success

Designed to be run via cron:
    0 3 * * * cd /path/to/empire-challenge-bot && python scripts/backup.py

Exit codes:
    0 = success
    1 = database not found
    2 = backup failed
"""
import os
import sys
import shutil
import glob
from datetime import datetime

# ── Configuration ──────────────────────────────────────────────────────────────
MAX_BACKUPS = 14  # Keep this many backup files; delete older ones

# Resolve paths relative to the project root
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_DIR, "challenge.db")
DEFAULT_BACKUP_DIR = os.path.join(PROJECT_DIR, "backups")


def backup(backup_dir: str = None) -> str:
    """Create a timestamped backup of the database. Returns the backup file path."""
    backup_dir = backup_dir or DEFAULT_BACKUP_DIR

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        print("   (The bot creates it on first run. Nothing to back up yet.)")
        sys.exit(1)

    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"challenge_{timestamp}.db")

    try:
        shutil.copy2(DB_PATH, backup_file)
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(2)

    size_kb = os.path.getsize(backup_file) / 1024
    print(f"✅ Backup created: {backup_file} ({size_kb:.1f} KB)")

    # ── Rotate old backups ─────────────────────────────────────────────────────
    existing = sorted(glob.glob(os.path.join(backup_dir, "challenge_*.db")))
    if len(existing) > MAX_BACKUPS:
        to_delete = existing[: len(existing) - MAX_BACKUPS]
        for old_file in to_delete:
            os.remove(old_file)
            print(f"🗑️  Rotated (deleted): {os.path.basename(old_file)}")

    remaining = len(glob.glob(os.path.join(backup_dir, "challenge_*.db")))
    print(f"📦 Total backups kept: {remaining}/{MAX_BACKUPS}")
    return backup_file


def main():
    custom_dir = sys.argv[1] if len(sys.argv) > 1 else None
    backup(custom_dir)


if __name__ == "__main__":
    main()
