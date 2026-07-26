"""Itqan Phase 4 — the weekly-assessment "stop" in the personal calendar.

`darb.build_calendar` gains a per-week assessment marker with its unlock
state, but ONLY when the `itqan_weekly_assessment` flag is on — so with the
flag off (its state through Phase 8) the calendar payload is unchanged and
the dojo shows nothing new.
"""
import pytest

from src import curriculum, darb, database


@pytest.fixture
def student():
    database.register_member("s1", "Student", "L0")
    return "s1"


def _full_week(week: int) -> dict:
    core = database.PRACTICE_EXERCISES
    return {(week, d): {"day_tier": 1, "done": True,
                        "exercises": {c: 1 for c in core}} for d in range(1, 8)}


def test_no_assessments_key_when_flag_off(student, monkeypatch):
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: _full_week(1))
    cal = darb.build_calendar(student)
    assert cal is not None
    assert "assessments" not in cal  # zero new surface with the flag off


def test_assessments_present_when_flag_on(student, monkeypatch):
    database.set_feature_flag("itqan_weekly_assessment", True)
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: {})
    cal = darb.build_calendar(student)
    assert "assessments" in cal
    # One stop per content week of the level.
    assert len(cal["assessments"]) == curriculum.max_week_for_level("L0")
    # Nothing done → every week locked with all 7 days remaining.
    assert all(a["state"] == "locked" for a in cal["assessments"])
    assert cal["assessments"][0]["days_remaining"] == [1, 2, 3, 4, 5, 6, 7]


def test_week_unlocks_only_when_all_days_done(student, monkeypatch):
    database.set_feature_flag("itqan_weekly_assessment", True)
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: _full_week(2))
    cal = darb.build_calendar(student)
    by_week = {a["week"]: a for a in cal["assessments"]}
    assert by_week[2]["state"] == "available"   # week 2 fully done → unlocked
    assert by_week[1]["state"] == "locked"       # week 1 untouched → locked


def test_partial_week_stays_locked_with_remaining_days(student, monkeypatch):
    database.set_feature_flag("itqan_weekly_assessment", True)
    cal_data = _full_week(2)
    del cal_data[(2, 4)]  # day 4 not done
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: cal_data)
    cal = darb.build_calendar(student)
    by_week = {a["week"]: a for a in cal["assessments"]}
    assert by_week[2]["state"] == "locked"
    assert by_week[2]["days_remaining"] == [4]


def test_mastered_week_shows_mastered(student, monkeypatch):
    database.set_feature_flag("itqan_weekly_assessment", True)
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: _full_week(2))
    database.itqan_upsert_mastery(student, "L0", 2, False, 1)
    cal = darb.build_calendar(student)
    by_week = {a["week"]: a for a in cal["assessments"]}
    assert by_week[2]["state"] == "mastered"
