#!/usr/bin/env python3
"""Darb Phase 6 — one-time backfill of calendar mastery for existing students.

Existing students were practising before the Phase 1 `practice_mastery`
table existed, so the new personal calendar shows their past active days
as "missed" instead of green. This script reconstructs their mastery from
their real `daily_submissions` history (date-based), so the calendar
reflects the progress they actually made.

Safe to run:
  * Idempotent (INSERT ... ON CONFLICT DO NOTHING) — never lowers a tier
    the student earned for real after launch; re-runnable with no harm.
  * Read-then-write only on `practice_mastery`; never touches streaks,
    points, submissions, or member records.
  * --dry-run shows what WOULD change without writing.

Run inside the bot container:
  docker exec -w /app empire-english-bot python3 scripts/backfill_darb_existing_students.py --dry-run
  docker exec -w /app empire-english-bot python3 scripts/backfill_darb_existing_students.py
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change without writing.")
    parser.add_argument("--id", help="Backfill a single discord_id only.")
    args = parser.parse_args()

    database.init_db()

    if args.id:
        members = [database.get_member(args.id)]
        members = [m for m in members if m]
    else:
        members = database.all_active_members()

    print(f"{'DRY RUN — ' if args.dry_run else ''}Darb Phase 6 backfill")
    print(f"Members to process: {len(members)}")
    print("=" * 60)

    total_days = 0
    total_ex = 0
    for m in members:
        did = m["discord_id"]
        name = (m.get("discord_name") or "?").split("#")[0]
        level = m.get("level", "L0")
        anchor = database.level_anchor_iso(m)[:10]

        if args.dry_run:
            # Simulate: count practice submissions without writing
            conn = database._connect()
            rows = conn.execute(
                "SELECT DISTINCT date, task_id FROM daily_submissions "
                "WHERE discord_id=? AND task_id IN ('accent','vocab','shadow','listening')",
                (did,),
            ).fetchall()
            conn.close()
            n = len(rows)
            print(f"  {name:20s} {level}  anchor={anchor}  "
                  f"{n} practice submission(s) would be mapped")
            total_ex += n
        else:
            result = database.backfill_practice_mastery_from_submissions(did)
            total_days += result["days_marked"]
            total_ex += result["exercises_marked"]
            print(f"  {name:20s} {level}  anchor={anchor}  "
                  f"→ {result['days_marked']} day(s), "
                  f"{result['exercises_marked']} exercise(s) marked done")

    print("=" * 60)
    if args.dry_run:
        print(f"DRY RUN complete. {total_ex} practice submission(s) across "
              f"{len(members)} member(s) would be backfilled.")
        print("Run without --dry-run to apply.")
    else:
        print(f"DONE. Backfilled {total_ex} exercise-completions across "
              f"{len(members)} member(s).")


if __name__ == "__main__":
    main()
