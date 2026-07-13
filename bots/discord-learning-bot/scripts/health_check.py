#!/usr/bin/env python3
"""
Health check for the Empire English Community Bot — Aegis Phase 2
(production-safe-deploys spec, .kiro/specs/production-safe-deploys/).

Checks concrete, specific facts about the running bot rather than just
"is the container running" (Requirement 2.4's explicit rejection of that
as sufficient evidence — a container can be "Up" while the bot inside it
crashed on startup, never connected to Discord, or loaded a broken
curriculum):

  1. Database reachable  — a real query succeeds, not just "file exists"
  2. Curriculum loaded    — exactly 38 weeks across all 4 levels, not
                             just "some number greater than zero"
  3. Commands registered  — at least MIN_EXPECTED_COMMANDS, catching an
                             import error that silently drops a whole
                             command's registration without crashing
                             the bot outright
  4. Gateway connected    — via the heartbeat loop in bot.py (see that
                             loop's own docstring for why this can't be
                             checked directly from an external process):
                             fresh if updated within HEARTBEAT_STALE_AFTER

Usage:
    python3 scripts/health_check.py
    docker exec empire-english-bot python3 scripts/health_check.py

Exit codes:
    0 = healthy (all checks passed)
    1 = unhealthy (at least one check failed)

Called by scripts/deploy.py right after a deploy (gates whether the
deploy is considered successful or triggers rollback instructions), and
safe to run standalone at any time for a manual spot-check — this is
the SAME script either way, not a separate "deploy-time" vs.
"on-demand" implementation that could silently drift apart.
"""
import os
import sys
import datetime

# Make src/ importable regardless of the current working directory this
# script is invoked from (project root, or the scripts/ dir itself),
# same pattern as scripts/backup.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config, database, curriculum  # noqa: E402

EXPECTED_WEEKS = 38  # L0=8 + L1=10 + L2=12 + L3=8, per curriculum.py's LEVEL_WEEK_COUNTS
MIN_EXPECTED_COMMANDS = 24  # as of Aegis Phase 1 (!flag/!systemstatus added); bump this
                            # deliberately whenever a real new command is added, so it
                            # stays a meaningful floor rather than a stale number nobody
                            # ever revisits
HEARTBEAT_STALE_AFTER_MINUTES = 5  # heartbeat loop fires every 2 min; 5 min gives one
                                    # missed beat of slack before calling it stale


def check_database() -> tuple[bool, str]:
    try:
        count = database.member_count()
        return True, f"Database reachable ({count} member(s))"
    except Exception as e:
        return False, f"Database check failed: {e}"


def check_curriculum() -> tuple[bool, str]:
    try:
        curriculum.load_all()
        stats = curriculum.stats()
        weeks = stats.get("weeks_loaded", 0)
        if weeks == EXPECTED_WEEKS:
            return True, f"Curriculum loaded ({weeks}/{EXPECTED_WEEKS} weeks)"
        return False, f"Curriculum incomplete ({weeks}/{EXPECTED_WEEKS} weeks loaded)"
    except Exception as e:
        return False, f"Curriculum check failed: {e}"


def check_commands() -> tuple[bool, str]:
    """Import bot.py and count its registered commands, WITHOUT
    connecting to Discord (bot.run() is never called here) -- this
    catches an import-time error that would silently drop a command's
    registration, the exact failure mode this check exists for, without
    needing a second live gateway connection competing with the real
    running bot's session."""
    try:
        from src.bot import bot
        count = len(bot.commands)
        if count >= MIN_EXPECTED_COMMANDS:
            return True, f"{count} commands registered (>= {MIN_EXPECTED_COMMANDS} expected)"
        return False, f"Only {count} commands registered (expected >= {MIN_EXPECTED_COMMANDS} -- a command may have failed to register)"
    except Exception as e:
        return False, f"Command registration check failed: {e}"


def check_heartbeat() -> tuple[bool, str]:
    """Read the heartbeat timestamp bot.py's own heartbeat loop writes
    every 2 minutes. Stale/missing means the bot's event loop isn't
    actually running (crashed, never started, or disconnected) even if
    the container itself shows as "Up" -- see bot.py's heartbeat loop
    docstring for the full rationale on why this indirection is
    necessary from an external process."""
    try:
        raw = database.get_setting("last_heartbeat", "")
    except Exception as e:
        # A database file can exist without being fully initialized yet
        # (e.g. right at container startup, or a corrupted/half-migrated
        # file) -- get_setting()'s bare "no such table" would otherwise
        # crash this whole script instead of reporting a clean, gradeable
        # failure, which defeats the point of a health check.
        return False, f"Could not read heartbeat (database not fully initialized?): {e}"
    if not raw:
        return False, "No heartbeat recorded yet (bot may not have started, or predates this check)"
    try:
        last = datetime.datetime.fromisoformat(raw)
    except ValueError:
        return False, f"Heartbeat value unparseable: {raw!r}"
    now = last.__class__.now(last.tzinfo) if last.tzinfo else datetime.datetime.now()
    age = (now - last).total_seconds() / 60
    if age <= HEARTBEAT_STALE_AFTER_MINUTES:
        return True, f"Heartbeat fresh ({age:.1f} min ago)"
    return False, f"Heartbeat stale ({age:.1f} min ago, expected <= {HEARTBEAT_STALE_AFTER_MINUTES})"


def main() -> int:
    checks = [
        ("Database", check_database),
        ("Curriculum", check_curriculum),
        ("Commands", check_commands),
        ("Gateway (heartbeat)", check_heartbeat),
    ]

    all_ok = True
    print(f"🩺 Health check — {config.DB_PATH}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    for label, check_fn in checks:
        ok, message = check_fn()
        icon = "✅" if ok else "❌"
        print(f"{icon} {label}: {message}")
        all_ok = all_ok and ok

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if all_ok:
        print("✅ HEALTHY")
        return 0
    else:
        print("❌ UNHEALTHY")
        return 1


if __name__ == "__main__":
    sys.exit(main())
