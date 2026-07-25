"""Progress reconciliation audit (read-only).

Cross-checks the ecosystem's two completion ledgers for consistency:

  * ``daily_submissions`` — the DATE-based 7-task Discord ledger that drives
    ``!progress``, the streak and points.
  * ``practice_mastery`` — the CONTENT-DAY calendar that drives the practice
    page's "green" days and per-exercise tiers.

Both are meant to be updated together (``tasks.process_submission`` +
``database.record_practice_mastery`` are paired on every completion path —
the page's ``/api/practice-complete`` & ``/api/submit-recording`` and the
Discord ``!done`` / reaction handlers). For any given day, every one of the
5 practice exercises (``CALENDAR_EXERCISES``) logged in ``daily_submissions``
that day should also have a ``practice_mastery`` row updated that day — and
vice versa. A student may legitimately be catching up on a PAST content-day,
so we match on "was mastery recorded that day at all" (any week/day), NOT on
today's content-day specifically.

Anything that doesn't line up is reported as "drift". This module is
READ-ONLY — it never writes to the database.

Usage:
    python -m src.reconcile                 # audit today, last 10 active days
    python -m src.reconcile --date 2026-07-25
    python -m src.reconcile --days 30
"""
from __future__ import annotations

import argparse

from .database import _connect, _today_local, CALENDAR_EXERCISES


def reconcile(date: str | None = None, lookback_days: int = 10) -> dict:
    """Reconcile the two ledgers for `date` (default: today, bot-local).

    Returns a report dict:
        {
          "date": str,
          "active_students": int,      # submitted anything in the lookback window
          "checked": int,              # practice-task completions examined on `date`
          "all5": int,                 # students whose `date` submissions cover all 5 practice
          "all7": int,                 # students with all 7 daily tasks submitted on `date`
          "forward_drift": [(discord_id, exercise), ...],  # in ledger, no mastery that day
          "reverse_drift": [(discord_id, exercise), ...],  # mastery that day, not in ledger
        }
    """
    date = date or _today_local().isoformat()
    practice = set(CALENDAR_EXERCISES)  # accent, vocab, shadow, listening, speaking

    conn = _connect()
    try:
        students = [
            r["discord_id"]
            for r in conn.execute(
                "SELECT DISTINCT discord_id FROM daily_submissions "
                "WHERE date >= date(?, ?)",
                (date, f"-{int(lookback_days)} day"),
            ).fetchall()
        ]

        forward_drift: list[tuple[str, str]] = []
        reverse_drift: list[tuple[str, str]] = []
        checked = all5 = all7 = 0

        for did in students:
            subs = {
                r["task_id"]
                for r in conn.execute(
                    "SELECT task_id FROM daily_submissions WHERE discord_id=? AND date=?",
                    (did, date),
                ).fetchall()
            }
            if len(subs) >= 7:
                all7 += 1
            practice_subs = subs & practice
            if practice_subs.issuperset(practice):
                all5 += 1

            mastered_that_day = {
                r["exercise"]
                for r in conn.execute(
                    "SELECT DISTINCT exercise FROM practice_mastery "
                    "WHERE discord_id=? AND last_completed_date=?",
                    (did, date),
                ).fetchall()
            }

            for ex in practice_subs:
                checked += 1
                if ex not in mastered_that_day:
                    forward_drift.append((did, ex))
            for ex in mastered_that_day & practice:
                if ex not in subs:
                    reverse_drift.append((did, ex))

        return {
            "date": date,
            "active_students": len(students),
            "checked": checked,
            "all5": all5,
            "all7": all7,
            "forward_drift": forward_drift,
            "reverse_drift": reverse_drift,
        }
    finally:
        conn.close()


def format_report(report: dict) -> str:
    lines = [
        "=== Progress reconciliation ===",
        f"Date:                     {report['date']}",
        f"Active students (window): {report['active_students']}",
        f"Practice completions:     {report['checked']}",
        f"Did all 5 practice:       {report['all5']}",
        f"Did all 7 daily tasks:    {report['all7']}",
        f"Forward drift (ledger→no mastery): {len(report['forward_drift'])}",
        f"Reverse drift (mastery→no ledger): {len(report['reverse_drift'])}",
    ]
    for did, ex in report["forward_drift"][:50]:
        lines.append(f"  [forward] {did}: '{ex}' logged in daily_submissions but no mastery recorded that day")
    for did, ex in report["reverse_drift"][:50]:
        lines.append(f"  [reverse] {did}: '{ex}' mastery recorded but not in daily_submissions that day")
    ok = not report["forward_drift"] and not report["reverse_drift"]
    lines.append("RESULT: ✅ ledgers consistent" if ok else "RESULT: ⚠️ drift found — investigate above")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=None, help="Date to audit (YYYY-MM-DD). Default: today.")
    parser.add_argument("--days", type=int, default=10, help="Active-window lookback in days (default 10).")
    args = parser.parse_args()
    print(format_report(reconcile(date=args.date, lookback_days=args.days)))


if __name__ == "__main__":
    main()
