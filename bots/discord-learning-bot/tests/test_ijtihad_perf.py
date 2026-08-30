"""Ijtihad — query-count guards for the hot paths.

Found by measurement AFTER the boards went live, not by review: building the
consistency board for 17 students took **5.4 seconds and 12,972 SQLite
connections**, because the streak walk called helpers that each re-read the
config and opened their own connection, once per day of history.

A student typing `!consistency` waited 5.4s, and the same call runs in the
nightly post. That also failed this project's own "5-year / 10x scale" rule —
at 100 students it would have been ~30s.

These tests assert query COUNTS rather than wall-clock time, because timing is
flaky in CI while a count regression is exactly the mistake that caused this:
an inner-loop helper that quietly opens a connection. The numbers are ceilings
with headroom, not targets to tune.
"""
import datetime

import pytest

from src import database


@pytest.fixture(autouse=True)
def clean():
    conn = database._connect()
    for sql in ("DELETE FROM seasons", "DELETE FROM student_targets",
                "DELETE FROM streak_freezes", "DELETE FROM streaks",
                "DELETE FROM points_log",
                "DELETE FROM settings WHERE key LIKE 'ijtihad_%'"):
        conn.execute(sql)
    conn.commit()
    conn.close()
    yield


class _CountingConnect:
    """Wraps database._connect to count how many connections a call opens."""

    def __init__(self):
        self._orig = database._connect
        self.count = 0

    def __enter__(self):
        def counting():
            self.count += 1
            return self._orig()
        database._connect = counting
        return self

    def __exit__(self, *exc):
        database._connect = self._orig
        return False


def _populate(members: int, days: int, target: int = 5):
    database.set_ijtihad_config("ijtihad_season1_start", "2026-01-03")
    season = database.ijtihad_ensure_seasons()
    today = database._today_local()

    # Register everyone FIRST: register_member opens its own connection, and doing
    # that while holding an uncommitted write transaction below deadlocks SQLite.
    for i in range(members):
        database.register_member(f"perf{i}", f"P{i}")

    conn = database._connect()
    try:
        for i in range(members):
            mid = f"perf{i}"
            conn.execute(
                "INSERT OR REPLACE INTO student_targets (discord_id, season_id, target) "
                "VALUES (?,?,?)", (mid, season["id"], target))
            for back in range(days):
                d = (today - datetime.timedelta(days=back)).isoformat()
                conn.execute(
                    "INSERT OR REPLACE INTO streaks (discord_id,date,tasks_completed,all_seven) "
                    "VALUES (?,?,?,0)", (mid, d, target))
        conn.commit()
    finally:
        conn.close()
    return season


def test_full_day_streak_does_not_scale_with_history_length():
    """THE REGRESSION. The streak walk must load a student's history once and walk
    it in memory -- not open connections per day. A 60-day streak must not cost
    ~10x what a 6-day streak costs."""
    _populate(members=1, days=60)
    with _CountingConnect() as c:
        out = database.ijtihad_full_day_streak("perf0", consume_freezes=False)
    assert out["streak"] == 60
    assert c.count <= 15, (
        f"streak walk opened {c.count} connections for 60 days of history — "
        "an inner-loop helper is opening its own connection again")


def test_consistency_board_is_bounded_per_member():
    """Nightly post + !consistency. Was 12,972 connections for 17 students."""
    _populate(members=17, days=60)
    with _CountingConnect() as c:
        rows = database.ijtihad_consistency_board(limit=5)
    assert len(rows) == 5
    assert c.count <= 400, (
        f"consistency board opened {c.count} connections for 17 students "
        "(pre-fix: 12,972)")


def test_full_days_on_is_a_constant_number_of_queries():
    """The nightly roll must not scale queries with members."""
    _populate(members=17, days=3)
    today = database._today_local().isoformat()
    with _CountingConnect() as c:
        rows = database.ijtihad_full_days_on(today)
    assert len(rows) == 17
    assert c.count <= 12, (
        f"full_days_on opened {c.count} connections — it should batch, "
        "not query per member")


def test_config_read_is_one_query():
    """get_ijtihad_config is called inside loops; it must not cost one
    connection per key."""
    with _CountingConnect() as c:
        database.get_ijtihad_config()
    assert c.count <= 2, f"config read opened {c.count} connections"


def test_season_points_is_a_single_query():
    _populate(members=1, days=3)
    season = database.ijtihad_current_season()
    with _CountingConnect() as c:
        database.ijtihad_season_points("perf0", season)
    assert c.count <= 2
