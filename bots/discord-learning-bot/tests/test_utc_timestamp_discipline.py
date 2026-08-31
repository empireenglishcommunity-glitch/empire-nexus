"""Stored timestamps are naive UTC. Comparing them to anything else is a bug.

WHY THIS FILE EXISTS
--------------------
On 2026-08-31 the inactivity nudge told Mai — 43-day streak, 100% weekly
completion — that she had not been active (nexus #463-#467). The cause was a
timestamp comparison, and the fix touched four call sites. This file is about
the FIFTH, SIXTH and SEVENTH, found the next day by asking "where else does this
shape appear?" rather than by anything going red.

There are two wrong ways to spell "now" next to a stored stamp, and they fail
very differently:

  * `datetime.datetime.now()` is naive LOCAL. It subtracts without complaint and
    is simply wrong by the host's offset (+4h on this deployment). With `.days`
    truncation those four hours become a whole extra day. This is the Mai bug.

  * `datetime.datetime.now(datetime.timezone.utc)` is AWARE. Subtracting a naive
    stored stamp raises TypeError. Inside a `try/except (ValueError, TypeError)`
    that does not crash the bot — it makes the feature SILENT.

The second is worse, and `ops_monitoring.check_churn_risk()` had it. The flag
`markaz_churn_alerts` went ON in production on 2026-07-15, and from that day to
2026-08-31 the alert could not fire for ANY student: every member hit the
TypeError and was skipped by `continue`, so `at_risk` was always empty. Nothing
reported it, because an alert that is never sent looks exactly like an alert that
was never needed. That is the same failure signature as the stale-streak guard
in #467 — a feature that is quietly off, not visibly broken.

These tests assert BEHAVIOUR (does the alert fire, is the week stable) rather
than which helper is called, so they keep their value if the implementation
changes again. The last test is a mechanical guard: it re-runs the AST scan that
found these three, so the class cannot silently return.
"""
import ast
import datetime
import pathlib

import pytest
from unittest.mock import AsyncMock, patch

from src import database, ops_monitoring


# ────────────────────────────────────────────────────────────────────
#  The churn alert must actually be capable of firing
# ────────────────────────────────────────────────────────────────────

def _student(discord_id: str, name: str, *, silent_for: str, longest: int = 7):
    """A member whose last_active_at is written the way SQLite writes it —
    naive UTC, space separator — which is what production actually contains."""
    database.register_member(discord_id, name)
    conn = database._connect()
    conn.execute(
        "UPDATE members SET last_active_at=datetime('now', ?), longest_streak=?, "
        "current_streak=0 WHERE discord_id=?",
        (silent_for, longest, discord_id),
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_churn_alert_fires_for_a_genuinely_silent_student():
    """THE REGRESSION. Before the fix this sent zero alerts for any input.

    Fails on the old code with an aware/naive TypeError swallowed by `continue`,
    which is invisible from the outside — hence asserting on the alert, not on
    an intermediate value.
    """
    database.set_feature_flag("markaz_churn_alerts", True)
    _student("silent1", "Silent Student", silent_for="-5 days", longest=9)

    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        await ops_monitoring.check_churn_risk()

    assert alert.await_count == 1, (
        "churn alert did not fire for a student silent 5 days — this is the "
        "2026-07-15..08-31 production defect, where every member was skipped "
        "by a swallowed TypeError"
    )
    body = alert.await_args.args[1] if alert.await_args.args else ""
    assert "5 days" in body


@pytest.mark.asyncio
async def test_churn_alert_stays_silent_for_a_student_who_worked_today():
    """Negative control — the fix must not make the alert fire for everyone.

    A test that only proves "it sends something" would pass on code that alerts
    the whole roster, which is a worse defect than sending nothing.
    """
    database.set_feature_flag("markaz_churn_alerts", True)
    _student("active1", "Active Student", silent_for="-2 hours", longest=9)

    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        await ops_monitoring.check_churn_risk()

    assert alert.await_count == 0


@pytest.mark.asyncio
async def test_churn_alert_ignores_a_student_with_no_real_history():
    """`longest_streak < 3` is the "was ever engaged" gate and must survive."""
    database.set_feature_flag("markaz_churn_alerts", True)
    _student("newbie1", "Barely Started", silent_for="-30 days", longest=1)

    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        await ops_monitoring.check_churn_risk()

    assert alert.await_count == 0


# ────────────────────────────────────────────────────────────────────
#  The helper itself
# ────────────────────────────────────────────────────────────────────

def test_utcnow_is_naive_so_a_stored_stamp_can_be_subtracted_from_it():
    """The whole point. An AWARE now is what killed the churn alert."""
    now = database.utcnow()
    assert now.tzinfo is None
    stored = database.parse_stamp("2026-08-30 22:39:00")
    (now - stored)  # must not raise TypeError


@pytest.mark.parametrize("raw", [
    "2026-08-30 22:39:00",          # SQLite datetime('now') — space
    "2026-08-30T22:39:00",          # Python .isoformat() — "T"
    "2026-08-30T22:39:00.123456",   # with microseconds
    "2026-08-30T22:39:00Z",         # trailing Z
    "  2026-08-30 22:39:00  ",      # padded
])
def test_parse_stamp_accepts_every_format_the_database_actually_contains(raw):
    """Tolerant on READ, because production genuinely holds more than one
    format and always will — old rows are not going to rewrite themselves.

    Microseconds are preserved rather than truncated, so compare to the second.
    """
    parsed = database.parse_stamp(raw)
    assert parsed is not None, f"could not parse {raw!r}"
    assert parsed.replace(microsecond=0) == datetime.datetime(2026, 8, 30, 22, 39, 0)


def test_parse_stamp_converts_an_aware_stamp_instead_of_stripping_its_offset():
    """Stripping tzinfo keeps the LOCAL wall clock and silently reintroduces
    the original bug. 22:39+04:00 is 18:39 UTC, not 22:39 UTC."""
    assert database.parse_stamp("2026-08-30T22:39:00+04:00") == \
        datetime.datetime(2026, 8, 30, 18, 39, 0)


@pytest.mark.parametrize("raw", [None, "", "not-a-date", "2026-13-45 99:99:99"])
def test_days_since_returns_none_not_zero_for_an_unusable_value(raw):
    """None means "unknown". Returning 0 would mean "active today", which is
    how a re-engagement job ends up messaging exactly the wrong people."""
    assert database.days_since(raw) is None


def test_days_since_measures_whole_days_in_utc():
    now = datetime.datetime(2026, 8, 31, 12, 0, 0)
    assert database.days_since("2026-08-31 11:00:00", now) == 0
    assert database.days_since("2026-08-30 11:00:00", now) == 1
    assert database.days_since("2026-08-24 13:00:00", now) == 6   # 6d23h, not 7
    assert database.days_since("2026-08-24 11:00:00", now) == 7


# ────────────────────────────────────────────────────────────────────
#  level_started_at was written in two zones and two formats
# ────────────────────────────────────────────────────────────────────

def test_set_level_writes_a_stamp_sqlite_can_compare():
    """`level_started_at` had TWO writers: SQL datetime('now') (UTC, space) and
    Python .now().isoformat() (LOCAL, "T"). Same column, two zones — the exact
    shape of the Mai defect, in the column that anchors a student's calendar.

    Asserted through julianday() because that is what the queries use: a value
    SQLite cannot parse comes back NULL and every comparison against it is
    silently false.
    """
    database.register_member("promoted", "Promoted Student")
    database.set_level("promoted", "A2")

    stored = database.get_member("promoted")["level_started_at"]
    assert "T" not in stored, f"level_started_at must match the SQL format, got {stored!r}"

    conn = database._connect()
    jd, drift = conn.execute(
        "SELECT julianday(?), ABS(julianday(?) - julianday('now')) * 86400.0", (stored, stored)
    ).fetchone()
    conn.close()

    assert jd is not None, f"SQLite cannot parse {stored!r}"
    assert drift < 120, (
        f"level_started_at is {drift:.0f}s from SQLite's own 'now' — that is a "
        f"timezone offset written into the column, not clock skew"
    )


def test_member_week_number_survives_an_offset_aware_anchor():
    """Discriminating case: an anchor carrying an explicit offset.

    The old code did `datetime.datetime.now() - fromisoformat(anchor)` — naive
    minus aware — which raises TypeError with nothing catching it, so a single
    such row took down `!progress` for that student. Now it is converted.
    """
    database.register_member("offsetkid", "Offset Anchor")
    anchor = (database.utcnow() - datetime.timedelta(days=8)).replace(microsecond=0)
    database.update_member("offsetkid", level_started_at=anchor.isoformat() + "+00:00")

    assert database.member_week_number("offsetkid") == 2


def test_member_week_number_is_1_when_the_anchor_is_unreadable():
    """Never 0, never negative, never an exception — week 1 is the safe floor."""
    database.register_member("junkanchor", "Junk Anchor")
    database.update_member("junkanchor", level_started_at="garbage")
    assert database.member_week_number("junkanchor") == 1


# ────────────────────────────────────────────────────────────────────
#  Mechanical guard — this class must not come back silently
# ────────────────────────────────────────────────────────────────────

# Functions allowed to mix an aware "now" with a naive parse, with the reason.
_ALLOWED = {
    # Converts explicitly via parse_stamp/astimezone; that IS the fix.
    ("database.py", "parse_stamp"),
}


def _calls_an_aware_now(node) -> bool:
    """True if this function calls a `now()` that returns an AWARE datetime.

    Detected structurally rather than by substring, because a substring check
    gets this wrong in both directions. `assessment._utcnow()` is spelled with
    `timezone.utc` yet returns NAIVE UTC (it strips tzinfo on the way out), so
    matching on the text flags every one of its callers — which it did, on
    `finish_attempt`, which is correct code. The distinguishing fact is the
    ARGUMENT: `datetime.now()` is naive local, `datetime.now(anything)` is aware.
    `datetime.utcnow()` is deprecated but naive, so it is not this bug either.
    """
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        func = ast.unparse(inner.func)
        if func.split(".")[-1] == "now" and (inner.args or inner.keywords):
            return True
    return False


def test_no_function_mixes_an_aware_now_with_a_naive_stored_stamp():
    """The scan that found the churn defect, kept as a gate.

    A green suite did not catch the original three, because none of them had a
    test at all — the code simply never ran in CI with a real member row. A
    static check does not need the code to run.
    """
    offenders = []
    for path in sorted(pathlib.Path("src").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (path.name, node.name) in _ALLOWED:
                continue
            src = ast.unparse(node)
            if not (_calls_an_aware_now(node) and "fromisoformat" in src):
                continue
            if not any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Sub)
                       for n in ast.walk(node)):
                continue
            # Attaching or converting a timezone makes the mix deliberate.
            if "tzinfo" in src or "astimezone" in src or "parse_stamp" in src:
                continue
            offenders.append(f"{path.name}:{node.lineno} {node.name}()")

    assert not offenders, (
        "these functions subtract a naive fromisoformat() result against an "
        "aware 'now' — a TypeError that a broad except turns into silence:\n  "
        + "\n  ".join(offenders)
        + "\nUse database.utcnow() / database.parse_stamp() / database.days_since()."
    )


def test_no_module_writes_a_timestamp_column_with_naive_local_time():
    """`datetime.datetime.now().isoformat()` into a timestamp column is how a
    column ends up holding two zones. Every writer must be UTC.
    """
    bad = []
    columns = ("level_started_at", "joined_at", "last_active_at", "submitted_at",
               "created_at", "completed_at", "suspended_at", "updated_at")
    for path in sorted(pathlib.Path("src").glob("*.py")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            stripped = line.lstrip()
            if stripped.startswith("#") or "datetime.now().isoformat()" not in line:
                continue
            if any(c in line for c in columns):
                bad.append(f"{path.name}:{lineno}: {stripped[:90]}")

    assert not bad, (
        "naive LOCAL time being written into a UTC timestamp column:\n  "
        + "\n  ".join(bad)
        + "\nUse database.utcnow().isoformat(sep=' ', timespec='seconds')."
    )
