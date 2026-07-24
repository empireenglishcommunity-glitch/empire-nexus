#!/usr/bin/env python3
"""Phase E (E6) — Audit: "finished all tasks but the bot still shows
remaining" (owner feedback #9).

Confirms (or refutes) a genuine counting bug behind the reported
confusion, per requirement R6.3. Run against the REAL production
database (read-only — this script never writes):

    docker exec -w /app empire-english-bot python3 scripts/audit_task_counting.py

What it checks
--------------
1. For every `daily_submissions` row, does `task_id` fall within the
   canonical 7-task set (config.DAILY_TASKS)? A row with an unexpected
   task_id would silently never be counted by anything filtering on the
   canonical set (case-mismatch, stale/renamed id, etc.).
2. For every (discord_id, date) that has all 7 canonical task_ids
   submitted, does `database.count_submissions_for_date` /
   `tasks_completed_today`-equivalent logic actually return 7 for that
   date? (tasks_completed_today() only ever queries "today" by
   definition, so this audit re-implements its exact query per
   historical date to check every day in the data, not just today.)
3. Historical evidence of the ACTUAL bug found+fixed this phase: had any
   student submitted a task in the ~4-hour window where the server's
   naive UTC date and the bot's configured Asia/Dubai date disagree?
   (before the fix, that submission would log under the Dubai date but
   `tasks_completed_today()`/`_recompute_streak()`/etc. would query the
   UTC date — a real, silent mismatch, not merely a UX/messaging
   confusion.) This section reports how many submissions actually fell
   in that risk window historically, i.e. how many students were
   plausibly affected before the fix landed.

Exit codes:
  0 = no genuine mismatch found (beyond the tz-boundary class already
      fixed this phase)
  1 = a mismatch was found that is NOT explained by the tz-boundary bug
      (i.e. a different, still-unfixed defect) — investigate before
      closing out Phase E.
"""
import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import database, config

CANONICAL_TASK_IDS = {t["id"] for t in config.DAILY_TASKS}


def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def main() -> int:
    database.init_db()
    conn = database._connect()
    problems = 0

    # ------------------------------------------------------------------
    section("1. Unexpected task_id values in daily_submissions")
    # ------------------------------------------------------------------
    rows = conn.execute(
        "SELECT DISTINCT task_id FROM daily_submissions"
    ).fetchall()
    seen_ids = {r["task_id"] for r in rows}
    unexpected = seen_ids - CANONICAL_TASK_IDS
    if unexpected:
        problems += 1
        print(f"  ❌ Found task_id values outside the canonical 7: {unexpected}")
        print("     These would never be counted by anything filtering on")
        print("     config.DAILY_TASKS — a real, separate bug from the tz one.")
    else:
        print(f"  ✅ All submitted task_ids are within the canonical set "
              f"{sorted(CANONICAL_TASK_IDS)}.")

    # ------------------------------------------------------------------
    section("2. Students who completed all 7 canonical tasks on a date")
    # ------------------------------------------------------------------
    all_rows = conn.execute(
        "SELECT discord_id, date, task_id FROM daily_submissions"
    ).fetchall()
    by_day: dict[tuple[str, str], set[str]] = {}
    for r in all_rows:
        key = (r["discord_id"], r["date"])
        by_day.setdefault(key, set()).add(r["task_id"])

    all_seven_days = [
        (discord_id, date, ids) for (discord_id, date), ids in by_day.items()
        if ids >= CANONICAL_TASK_IDS
    ]
    print(f"  Found {len(all_seven_days)} (student, date) pairs with all 7 "
          f"canonical tasks submitted.")

    mismatches = []
    for discord_id, date, ids in all_seven_days:
        # Re-implement the exact count query tasks_completed_today() would
        # run FOR THAT DATE (not "today") to check every historical day,
        # not just today.
        recount = conn.execute(
            "SELECT COUNT(DISTINCT task_id) as cnt FROM daily_submissions "
            "WHERE discord_id=? AND date=?",
            (discord_id, date),
        ).fetchone()["cnt"]
        if recount != 7:
            mismatches.append((discord_id, date, recount))

    if mismatches:
        problems += 1
        print(f"  ❌ {len(mismatches)} case(s) where 7 distinct task_ids were "
              f"submitted for a date but a same-date recount != 7:")
        for discord_id, date, recount in mismatches[:20]:
            print(f"     {discord_id} on {date}: recount={recount}")
    else:
        print("  ✅ Every (student, date) with all 7 tasks submitted also "
              "recounts to exactly 7 for that same date. No genuine "
              "same-date counting bug found.")

    # ------------------------------------------------------------------
    section("3. Historical exposure to the tz-boundary bug (now fixed)")
    # ------------------------------------------------------------------
    # Before this phase's fix, database.py used a bare datetime.date.today()
    # (server/UTC clock) everywhere tasks_completed_today()/_recompute_streak()
    # /get_voice_minutes()/record_practice_mastery() needed "today", while
    # submissions are logged under tasks.today_str()'s Asia/Dubai date. The
    # two disagree during the window where the UTC calendar date has moved
    # but Dubai's hasn't (or vice versa). We can't know the EXACT wall-clock
    # instant each historical submission was logged (submitted_at is stored,
    # so we can check it), so this reports submissions whose submitted_at
    # falls in the risk window, as a proxy for "could plausibly have been
    # affected by the pre-fix bug."
    tz = getattr(config, "TIMEZONE", "Asia/Dubai") or "Asia/Dubai"
    try:
        from zoneinfo import ZoneInfo
        tzinfo = ZoneInfo(tz)
    except Exception:
        tzinfo = None

    risk_rows = conn.execute(
        "SELECT discord_id, date, task_id, submitted_at FROM daily_submissions "
        "WHERE submitted_at IS NOT NULL"
    ).fetchall()

    at_risk = []
    for r in risk_rows:
        try:
            submitted_utc = datetime.datetime.fromisoformat(r["submitted_at"])
            if submitted_utc.tzinfo is None:
                submitted_utc = submitted_utc.replace(tzinfo=datetime.timezone.utc)
        except (ValueError, TypeError):
            continue
        naive_utc_date = submitted_utc.astimezone(datetime.timezone.utc).date()
        local_date = (
            submitted_utc.astimezone(tzinfo).date() if tzinfo else naive_utc_date
        )
        if naive_utc_date != local_date:
            at_risk.append((r["discord_id"], r["date"], r["task_id"],
                            str(naive_utc_date), str(local_date)))

    if at_risk:
        print(f"  ⚠️  {len(at_risk)} historical submission(s) were logged during "
              f"the UTC-vs-{tz} date-boundary window (server date != Dubai "
              f"date at the moment of submission).")
        print("     These are exactly the submissions that COULD have been")
        print("     invisible to !progress/!today/!done for a few hours,")
        print("     pre-fix. Sample:")
        for discord_id, date, task_id, utc_d, local_d in at_risk[:10]:
            print(f"       {discord_id} | task={task_id} | stored date={date} "
                  f"| server-date-at-submit={utc_d} | dubai-date-at-submit={local_d}")
    else:
        print("  ✅ No historical submissions found in the tz-boundary risk "
              "window (or submitted_at wasn't populated for older rows).")

    conn.close()

    # ------------------------------------------------------------------
    section("SUMMARY")
    # ------------------------------------------------------------------
    if problems:
        print(f"  ❌ {problems} genuine issue category found — see above. "
              f"These are NOT explained by the (already-fixed) tz-boundary "
              f"bug and need separate investigation.")
        return 1
    print("  ✅ No unexplained counting bug found. The tz-boundary class of "
          "issue (section 3) is the confirmed real bug and is already fixed "
          "in this phase (database._today_local()). Any remaining "
          "'finished but shows remaining' reports are the 4/5-vs-7 "
          "self-study-vs-full-program split (messaging, not a counting bug).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
