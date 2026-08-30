"""Regression: the seasonal streak bonus must not pay for a PRE-SEASON streak.

FOUND LIVE, on day one of Season 1 (2026-08-30). A student with a 28-day full-day
streak built before the season existed immediately collected the top 28-day bonus
(600 points) on her first submission after the new award table was enabled.

The full-day streak is computed over all history, so without a cap any
long-standing student banks the maximum seasonal bonus on the season's first day.
That is exactly the "reward tenure, not work" behaviour this entire rework exists
to remove — reintroduced by me, in the one function best placed to do it, and it
survived 29 unit tests because every one of them built the streak inside a season
that was already old enough to justify it.

The fix caps the effective streak at the season's age, so a bonus can only be
earned by days actually worked inside the season.
"""
import datetime

import pytest

from src import database, ijtihad


@pytest.fixture(autouse=True)
def clean():
    conn = database._connect()
    for sql in ("DELETE FROM seasons", "DELETE FROM student_targets",
                "DELETE FROM streak_freezes", "DELETE FROM points_log",
                "DELETE FROM streaks",
                "DELETE FROM settings WHERE key LIKE 'ijtihad_%'"):
        conn.execute(sql)
    conn.commit()
    conn.close()
    yield


def _student(mid="s", name="S"):
    database.register_member(mid, name)
    database.sync_flag_registry()
    database.set_feature_flag("ijtihad_award_table", True)
    return mid


def _season_starting(days_ago: int):
    """A season whose start is `days_ago` days before today."""
    start = database._today_local() - datetime.timedelta(days=days_ago)
    database.set_ijtihad_config("ijtihad_season1_start", start.isoformat())
    return database.ijtihad_ensure_seasons()


def _full_days(mid, n, target=3):
    """n consecutive full days ending today."""
    today = database._today_local()
    conn = database._connect()
    for back in range(n):
        d = (today - datetime.timedelta(days=back)).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO streaks (discord_id,date,tasks_completed,all_seven) "
            "VALUES (?,?,?,0)", (mid, d, target))
    conn.commit()
    conn.close()


# ============================================================
#  The bug
# ============================================================

def test_a_long_pre_season_streak_pays_nothing_on_day_one():
    """THE EXACT LIVE BUG. 28-day streak, season is 1 day old → no bonus."""
    mid = _student()
    s = _season_starting(0)              # season starts TODAY
    database.ijtihad_set_target(mid, 3, s)
    _full_days(mid, 28)                  # streak built entirely before the season
    assert database.ijtihad_full_day_streak(
        mid, consume_freezes=False)["streak"] == 28
    assert ijtihad.award_streak_bonus(mid) == (0, 0), \
        "a streak built before the season must not pay a seasonal bonus"


def test_no_points_are_written_for_a_pre_season_streak():
    mid = _student()
    s = _season_starting(0)
    database.ijtihad_set_target(mid, 3, s)
    _full_days(mid, 28)
    before = database.get_member(mid)["total_points"]
    ijtihad.award_streak_bonus(mid)
    assert database.get_member(mid)["total_points"] == before


@pytest.mark.parametrize("season_age,expected", [
    (0, (0, 0)),        # day 1  -> nothing
    (5, (0, 0)),        # day 6  -> still below the 7 threshold
    (6, (7, 100)),      # day 7  -> first bonus unlocks
    (13, (14, 200)),    # day 14
    (20, (21, 350)),    # day 21
    (27, (28, 600)),    # day 28 -> top bonus, legitimately earned
])
def test_bonus_unlocks_only_as_the_season_ages(season_age, expected):
    """With a 28-day streak available the whole time, the payout is governed by
    how long the SEASON has run — not by how long the student has been here."""
    mid = _student(f"s{season_age}")
    s = _season_starting(season_age)
    database.ijtihad_set_target(mid, 3, s)
    _full_days(mid, 28)
    assert ijtihad.award_streak_bonus(mid) == expected


def test_a_streak_earned_inside_the_season_still_pays():
    """The cap must not break the legitimate case."""
    mid = _student()
    s = _season_starting(10)
    database.ijtihad_set_target(mid, 3, s)
    _full_days(mid, 8)
    assert ijtihad.award_streak_bonus(mid) == (7, 100)


def test_cap_uses_the_smaller_of_streak_and_season_age():
    """Season is old, but the student only just started working."""
    mid = _student()
    s = _season_starting(27)
    database.ijtihad_set_target(mid, 3, s)
    _full_days(mid, 7)                   # only 7 days of work
    assert ijtihad.award_streak_bonus(mid) == (7, 100), \
        "should pay the 7-day tier, not the 28-day tier"


def test_still_pays_only_once_per_threshold_per_season():
    mid = _student()
    s = _season_starting(10)
    database.ijtihad_set_target(mid, 3, s)
    _full_days(mid, 8)
    assert ijtihad.award_streak_bonus(mid) == (7, 100)
    assert ijtihad.award_streak_bonus(mid) == (0, 0)


def test_no_season_pays_nothing():
    mid = _student()
    database.set_ijtihad_config("ijtihad_season1_start", "2099-01-02")
    assert ijtihad.award_streak_bonus(mid) == (0, 0)
