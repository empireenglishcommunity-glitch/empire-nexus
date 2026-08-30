"""Ijtihad Phase 4 — Personal Daily Target, Full-Day streaks, streak freezes.

Two problems are fixed here.

1. THE BUSY-ADULT PROBLEM. A fixed bar of 7 tasks/day means a student with a job
   and a family is permanently 4 tasks short of "complete", no matter how
   faithfully they work. Their target is now 3, 5 or 7, and hitting THEIR target
   is a Full Day. Absolute volume still scales, so 7/7 still earns more points
   than 3/3 -- the target changes what counts as *complete*, never what counts as
   *more*.

2. STREAKS MEASURED ATTENDANCE, NOT WORK. The legacy streak counted any day with
   >= 1 task, so one 30-second task looked identical to 7/7 -- and that number was
   what the nightly public post ranked people by.

Freezes exist because loss aversion motivates but an unforgiving streak turns one
sick day into a quit, and the people most likely to be hit are exactly the adults
this rework is meant to keep.

See .kiro/specs/ijtihad-effort-economy/ design §2.3 / §2.5.
"""
import datetime

import pytest

from src import database, flag_registry


FLAG = "ijtihad_personal_target"


@pytest.fixture(autouse=True)
def clean_ijtihad():
    conn = database._connect()
    for sql in ("DELETE FROM seasons", "DELETE FROM student_targets",
                "DELETE FROM streak_freezes",
                "DELETE FROM settings WHERE key LIKE 'ijtihad_%'",
                "DELETE FROM settings WHERE key = 'maintenance_days'"):
        conn.execute(sql)
    conn.commit()
    conn.close()
    yield


def _student(mid: str = "t1", name: str = "Student"):
    database.register_member(mid, name)
    return mid


def _season():
    return database.ijtihad_ensure_seasons()


def _season_covering_history():
    """A season whose window already covers the recent past.

    Streak tests walk backwards over ~a week, and a season anchored on *today*
    would put most of that history outside any season -- which is a real boundary
    case, but a separate one (see the dedicated pre-season test). Anchoring the
    season well before today keeps the freeze-mechanism tests deterministic
    regardless of which weekday the suite happens to run on.
    """
    database.set_ijtihad_config("ijtihad_season1_start", "2026-01-03")  # a Saturday
    return database.ijtihad_ensure_seasons()


def _did_tasks(mid: str, day: datetime.date, n: int):
    """Record n tasks completed on a date (streaks table is the source of truth
    for 'how much did they do that day')."""
    conn = database._connect()
    conn.execute(
        "INSERT OR REPLACE INTO streaks (discord_id, date, tasks_completed, all_seven) "
        "VALUES (?,?,?,?)",
        (mid, day.isoformat(), n, 1 if n >= 7 else 0),
    )
    conn.commit()
    conn.close()


# ============================================================
#  Flag + config
# ============================================================

def test_flag_registered_and_off_by_default():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == FLAG), None)
    assert entry is not None
    assert entry[3] is False


def test_config_defaults():
    cfg = database.get_ijtihad_config()
    assert cfg["ijtihad_target_default"] == 5
    assert cfg["ijtihad_freezes_per_season"] == 2


def test_target_choices_are_coarse_on_purpose():
    """A free-text number would invite optimising the denominator instead of
    doing the work."""
    assert database.IJTIHAD_TARGET_CHOICES == (3, 5, 7)


# ============================================================
#  Setting and reading a target
# ============================================================

def test_default_target_when_never_chosen():
    mid = _student()
    _season()
    assert database.ijtihad_get_target(mid) == 5
    assert database.ijtihad_target_is_set(mid) is False


def test_set_and_read_target():
    mid = _student()
    s = _season()
    ok, reason = database.ijtihad_set_target(mid, 3, s)
    assert (ok, reason) == (True, "ok")
    assert database.ijtihad_get_target(mid, s) == 3
    assert database.ijtihad_target_is_set(mid, s) is True


@pytest.mark.parametrize("bad", [0, 1, 2, 4, 6, 8, 99, -3])
def test_invalid_targets_are_rejected(bad):
    mid = _student()
    s = _season()
    ok, reason = database.ijtihad_set_target(mid, bad, s)
    assert ok is False
    assert reason == "bad_target"


def test_target_is_changeable_only_once_per_season():
    """Real life changes, but the target must not be a dial someone spins
    mid-race to make a bad week look complete."""
    mid = _student()
    s = _season()
    assert database.ijtihad_set_target(mid, 7, s)[0] is True
    ok, reason = database.ijtihad_set_target(mid, 3, s)
    assert ok is False
    assert reason == "already_set"
    assert database.ijtihad_get_target(mid, s) == 7


def test_target_can_be_set_again_in_a_new_season():
    mid = _student()
    s1 = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    database.ijtihad_set_target(mid, 7, s1)
    s2 = database.ijtihad_ensure_seasons(datetime.date(2026, 9, 27))
    assert s2["id"] != s1["id"]
    ok, _ = database.ijtihad_set_target(mid, 3, s2)
    assert ok is True
    assert database.ijtihad_get_target(mid, s2) == 3
    # The old season's commitment is untouched.
    assert database.ijtihad_get_target(mid, s1) == 7


def test_setting_a_target_with_no_season_is_refused_cleanly():
    mid = _student()
    database.set_ijtihad_config("ijtihad_season1_start", "2027-01-02")
    ok, reason = database.ijtihad_set_target(mid, 5, None)
    assert ok is False
    assert reason == "no_season"


# ============================================================
#  Full Day — the busy-adult fix
# ============================================================

def test_three_of_three_is_a_full_day_for_a_target_of_three():
    """THE FIX. 3/3 is a complete day for someone who committed to 3."""
    mid = _student()
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    _did_tasks(mid, today, 3)
    assert database.ijtihad_is_full_day(mid, today.isoformat()) is True


def test_three_of_seven_is_not_a_full_day():
    """...but 3 tasks against a target of 7 is not complete. Partial effort does
    not become full effort just because targets exist."""
    mid = _student()
    s = _season()
    database.ijtihad_set_target(mid, 7, s)
    today = database._today_local()
    _did_tasks(mid, today, 3)
    assert database.ijtihad_is_full_day(mid, today.isoformat()) is False


def test_one_task_is_not_a_full_day_under_any_target():
    """The legacy streak counted a 1-task day as a full streak day. That is
    exactly what this replaces."""
    mid = _student()
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    _did_tasks(mid, today, 1)
    assert database.ijtihad_is_full_day(mid, today.isoformat()) is False


def test_exceeding_the_target_is_still_a_full_day():
    mid = _student()
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    _did_tasks(mid, today, 7)
    assert database.ijtihad_is_full_day(mid, today.isoformat()) is True


# ============================================================
#  Full-day streaks
# ============================================================

def test_full_day_streak_counts_consecutive_complete_days():
    mid = _student()
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    for back in range(5):
        _did_tasks(mid, today - datetime.timedelta(days=back), 3)
    assert database.ijtihad_full_day_streak(mid)["streak"] == 5


def test_partial_days_do_not_extend_the_streak():
    mid = _student()
    s = _season()
    database.ijtihad_set_target(mid, 5, s)
    today = database._today_local()
    _did_tasks(mid, today, 5)
    _did_tasks(mid, today - datetime.timedelta(days=1), 2)   # partial → breaks
    _did_tasks(mid, today - datetime.timedelta(days=2), 5)
    out = database.ijtihad_full_day_streak(mid, consume_freezes=False)
    assert out["streak"] == 1


def test_an_incomplete_today_does_not_break_the_streak_at_breakfast():
    """Today isn't over. A streak built through yesterday must survive until the
    day actually ends."""
    mid = _student()
    s = _season()
    database.ijtihad_set_target(mid, 5, s)
    today = database._today_local()
    for back in range(1, 4):
        _did_tasks(mid, today - datetime.timedelta(days=back), 5)
    _did_tasks(mid, today, 1)  # started today, not done
    assert database.ijtihad_full_day_streak(mid, consume_freezes=False)["streak"] == 3


def test_streak_is_zero_with_no_activity():
    mid = _student()
    _season()
    assert database.ijtihad_full_day_streak(mid)["streak"] == 0


def test_target_change_next_season_does_not_rewrite_history():
    """A day is judged against the target that was in force THAT day, so raising
    your target later cannot retroactively delete past Full Days."""
    mid = _student()
    s1 = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    database.ijtihad_set_target(mid, 3, s1)
    day = datetime.date(2026, 8, 30)
    _did_tasks(mid, day, 3)
    assert database.ijtihad_is_full_day(mid, day.isoformat()) is True
    # Next season they commit to 7; the old day is still a Full Day.
    s2 = database.ijtihad_ensure_seasons(datetime.date(2026, 9, 27))
    database.ijtihad_set_target(mid, 7, s2)
    assert database.ijtihad_is_full_day(mid, day.isoformat()) is True


# ============================================================
#  Freezes
# ============================================================

def test_a_freeze_bridges_one_missed_day():
    mid = _student()
    s = _season_covering_history()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    _did_tasks(mid, today, 3)
    # yesterday missed entirely
    _did_tasks(mid, today - datetime.timedelta(days=2), 3)
    _did_tasks(mid, today - datetime.timedelta(days=3), 3)
    out = database.ijtihad_full_day_streak(mid)
    assert out["streak"] == 3
    assert out["freezes_used"] == 1


def test_freezes_are_finite_per_season():
    mid = _student()
    s = _season_covering_history()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    # complete today, then miss 3 separate days with only 2 freezes available
    _did_tasks(mid, today, 3)
    _did_tasks(mid, today - datetime.timedelta(days=2), 3)
    _did_tasks(mid, today - datetime.timedelta(days=4), 3)
    _did_tasks(mid, today - datetime.timedelta(days=6), 3)
    out = database.ijtihad_full_day_streak(mid)
    assert out["freezes_used"] == 2
    assert database.ijtihad_freezes_remaining(mid, s) == 0
    # The third gap is not bridged, so the streak stops there.
    assert out["streak"] == 3


def test_freezes_are_persisted_so_recomputation_is_stable():
    """The same gap must resolve the same way every time the streak is
    recalculated -- otherwise a student's streak would flicker."""
    mid = _student()
    s = _season_covering_history()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    _did_tasks(mid, today, 3)
    _did_tasks(mid, today - datetime.timedelta(days=2), 3)

    first = database.ijtihad_full_day_streak(mid)
    used_after_first = database.ijtihad_freezes_used(mid, s)
    second = database.ijtihad_full_day_streak(mid)
    assert first["streak"] == second["streak"]
    assert database.ijtihad_freezes_used(mid, s) == used_after_first  # not double-spent


def test_freeze_is_not_spent_before_a_streak_exists():
    """A student with no streak yet shouldn't silently burn freezes on ancient
    empty days."""
    mid = _student()
    s = _season_covering_history()
    database.ijtihad_set_target(mid, 3, s)
    database.ijtihad_full_day_streak(mid)
    assert database.ijtihad_freezes_used(mid, s) == 0


def test_consume_freezes_false_is_a_pure_read():
    mid = _student()
    s = _season_covering_history()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    _did_tasks(mid, today, 3)
    _did_tasks(mid, today - datetime.timedelta(days=2), 3)
    out = database.ijtihad_full_day_streak(mid, consume_freezes=False)
    assert out["streak"] == 1
    assert database.ijtihad_freezes_used(mid, s) == 0


def test_freezes_remaining_reflects_config():
    mid = _student()
    s = _season()
    database.set_ijtihad_config("ijtihad_freezes_per_season", 5)
    assert database.ijtihad_freezes_remaining(mid, s) == 5


def test_a_gap_before_season_1_is_still_chargeable():
    """Regression for a real gap found while writing these tests.

    A student's history predates Season 1, so a missed day being bridged may
    belong to NO season. The first implementation required the gap day to have a
    season and therefore refused to bridge it, silently ending the streak at the
    season boundary. Freezes are a CURRENT allowance, so such a day is charged to
    the current season -- otherwise pre-season gaps would bridge for free,
    without limit.
    """
    mid = _student()
    # Season 1 starts today, so everything before today has no season.
    today = database._today_local()
    database.set_ijtihad_config("ijtihad_season1_start", today.isoformat())
    s = database.ijtihad_ensure_seasons(today)
    database.ijtihad_set_target(mid, 3, s)

    _did_tasks(mid, today, 3)
    # yesterday missed (no season of its own), day before complete
    _did_tasks(mid, today - datetime.timedelta(days=2), 3)

    out = database.ijtihad_full_day_streak(mid)
    assert out["streak"] == 2, "the pre-season gap must be bridgeable"
    assert out["freezes_used"] == 1
    assert database.ijtihad_freezes_used(mid, s) == 1, "charged to the current season"


def test_maintenance_days_bridge_for_free():
    """Server maintenance is our fault, not the student's -- it must not cost
    them a freeze."""
    import json
    mid = _student()
    s = _season_covering_history()
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    gap = (today - datetime.timedelta(days=1)).isoformat()
    database.set_setting("maintenance_days", json.dumps([gap]))
    _did_tasks(mid, today, 3)
    _did_tasks(mid, today - datetime.timedelta(days=2), 3)
    out = database.ijtihad_full_day_streak(mid)
    assert out["streak"] == 2
    assert out["freezes_used"] == 0
    assert database.ijtihad_freezes_used(mid, s) == 0


# ============================================================
#  Non-destructiveness — the legacy streak is untouched
# ============================================================

def test_legacy_streak_engine_is_not_modified():
    """Phase 4 is additive. members.current_streak and the legacy >=1-task
    streak keep working exactly as before, because DMs, alerts, bonuses and the
    nightly post all still read them. Two coexisting notions is deliberate: a
    gentle 'you showed up' streak may exist, it just must not be what we
    publicly rank."""
    mid = _student()
    s = _season()
    database.ijtihad_set_target(mid, 7, s)
    today = database._today_local()
    # One task today: legacy streak counts the day, full-day streak does not.
    database.update_streak(mid, today.isoformat(), 1)
    legacy_current, _ = database.get_streak(mid)
    assert legacy_current == 1, "legacy active-day streak must still count this"
    assert database.ijtihad_full_day_streak(mid, consume_freezes=False)["streak"] == 0
