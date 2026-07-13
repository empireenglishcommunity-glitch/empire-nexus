#!/usr/bin/env python3
"""
Backup utility for the Empire English Community Bot database.

Usage:
    python scripts/backup.py                       # Backup to default location
    python scripts/backup.py /path/to/dir           # Backup to custom directory
    python scripts/backup.py --tag pre-deploy-abc123  # Tagged backup (default dir)
    python scripts/backup.py /path/to/dir --tag pre-deploy-abc123  # Both

The script:
  1. Creates a timestamped copy of the SQLite database (optionally with
     a label in the filename, e.g. for pre-deploy snapshots — see
     --tag below)
  2. Keeps the last N backups (default: 14) and deletes older ones.
     Tagged backups (--tag) are rotated in the SAME pool as routine
     ones, by design — a pre-deploy snapshot is not meant to live
     forever, just long enough to make a same-day rollback possible.
     If you need a permanent, never-rotated snapshot, copy the file
     out of the backup directory yourself.
  3. Prints the backup path on success

Designed to be run via cron, e.g. daily at 3 AM:
    0 3 * * * cd /opt/empire-english-bot && python3 scripts/backup.py

Or, since this bot runs in Docker with the database on a named volume
(bot-data:/app/data_persist -- see docker-compose.yml), run it inside
the running container so it sees the same volume the bot itself uses:
    0 3 * * * docker exec empire-english-bot python3 scripts/backup.py

--tag is used by scripts/deploy.py (Aegis Phase 2) to take a labeled
snapshot immediately before every deploy, e.g.:
    docker exec empire-english-bot python3 scripts/backup.py --tag pre-deploy-a1b2c3d

Exit codes:
    0 = success
    1 = database not found
    2 = backup failed

Modeled on discord-challenge-bot/scripts/backup.py (same bot family,
same backup strategy), adapted for this bot's database. Deliberately
imports DB_PATH from src/config.py rather than re-deriving the path
independently -- config.py already has the real, tested logic for
picking between the Docker-volume path (data_persist/empire_english.db)
and the local-dev fallback (empire_english.db in the repo root), and
duplicating that logic here would risk the two silently drifting apart
over time (exactly the kind of divergence this whole cleanup pass has
been finding and fixing elsewhere in this project).
"""
import argparse
import os
import sys
import shutil
import glob
from datetime import datetime

# Make src/ importable regardless of the current working directory this
# script is invoked from (project root, or the scripts/ dir itself).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config  # noqa: E402  (import after sys.path setup, by design)

# ── Configuration ────────────────────────────────────────────────────────
MAX_BACKUPS = 14  # Keep this many backup files; delete older ones

DB_PATH = str(config.DB_PATH)
DEFAULT_BACKUP_DIR = os.path.join(config.BASE_DIR, "backups")


def backup(backup_dir: str = None, tag: str = None) -> str:
    """Create a timestamped (optionally tagged) backup of the database.
    Returns the backup file path.

    tag, if given, is sanitized to filesystem-safe characters and
    inserted into the filename (e.g. empire_english_pre-deploy-a1b2c3d_
    20260713_120000.db) so a pre-deploy snapshot is visually
    distinguishable from a routine cron one at a glance, without
    needing a second, separate backup mechanism or directory.
    """
    backup_dir = backup_dir or DEFAULT_BACKUP_DIR

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at: {DB_PATH}")
        print("   (The bot creates it on first run. Nothing to back up yet.)")
        sys.exit(1)

    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_tag = "".join(c for c in tag if c.isalnum() or c in "-_") if tag else None
    filename = f"empire_english_{safe_tag}_{timestamp}.db" if safe_tag else f"empire_english_{timestamp}.db"
    backup_file = os.path.join(backup_dir, filename)

    try:
        shutil.copy2(DB_PATH, backup_file)
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        sys.exit(2)

    size_kb = os.path.getsize(backup_file) / 1024
    print(f"✅ Backup created: {backup_file} ({size_kb:.1f} KB)")

    # ── Rotate old backups ───────────────────────────────────────────────
    # Tagged and untagged backups share one rotation pool, deliberately
    # (see the module docstring) -- glob matches both filename shapes.
    existing = sorted(glob.glob(os.path.join(backup_dir, "empire_english_*.db")))
    if len(existing) > MAX_BACKUPS:
        to_delete = existing[: len(existing) - MAX_BACKUPS]
        for old_file in to_delete:
            os.remove(old_file)
            print(f"🗑️  Rotated (deleted): {os.path.basename(old_file)}")

    remaining = len(glob.glob(os.path.join(backup_dir, "empire_english_*.db")))
    print(f"📦 Total backups kept: {remaining}/{MAX_BACKUPS}")
    return backup_file


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("backup_dir", nargs="?", default=None, help="Custom backup directory (default: BASE_DIR/backups)")
    parser.add_argument("--tag", default=None, help="Label to embed in the backup filename (e.g. pre-deploy-<git-sha>)")
    args = parser.parse_args()
    backup(args.backup_dir, tag=args.tag)


if __name__ == "__main__":
    main()
