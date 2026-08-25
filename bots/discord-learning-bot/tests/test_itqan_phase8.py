"""Itqan Phase 8 — progress map + level-completion certificate."""
import pytest

from src import curriculum, darb, database, itqan_outcomes


@pytest.fixture
def student():
    database.register_member("s1", "Student", "L0")
    return "s1"


def _master(did, level, week, distinction=False):
    database.itqan_upsert_mastery(did, level, week, distinction, week)


# ---- progress -------------------------------------------------------------

def test_progress_counts_and_streak(student):
    for w in (1, 2, 3):
        _master(student, "L0", w)
    p = database.itqan_progress(student, "L0")
    assert p["mastered_count"] == 3
    assert p["total_weeks"] == curriculum.max_week_for_level("L0")  # 8
    assert p["streak"] == 3                       # contiguous from week 1
    assert p["level_complete"] is False
    assert p["pct"] == round(100 * 3 / 8, 1)


def test_progress_streak_breaks_on_gap(student):
    for w in (1, 2, 3, 5):                        # gap at 4
        _master(student, "L0", w)
    p = database.itqan_progress(student, "L0")
    assert p["mastered_count"] == 4
    assert p["streak"] == 3                       # 1,2,3 then stops


def test_progress_level_complete(student):
    total = curriculum.max_week_for_level("L0")
    for w in range(1, total + 1):
        _master(student, "L0", w)
    p = database.itqan_progress(student, "L0")
    assert p["level_complete"] is True
    assert p["streak"] == total
    assert p["pct"] == 100.0


# ---- certificate data -----------------------------------------------------

def test_certificate_not_eligible_until_complete(student):
    for w in (1, 2):
        _master(student, "L0", w)
    c = database.itqan_certificate_data(student, "L0")
    assert c["eligible"] is False
    assert c["name"] == "Student"
    assert c["total_weeks"] == curriculum.max_week_for_level("L0")


def test_certificate_eligible_on_full_mastery(student):
    total = curriculum.max_week_for_level("L0")
    for w in range(1, total + 1):
        _master(student, "L0", w, distinction=(w <= 2))
    c = database.itqan_certificate_data(student, "L0")
    assert c["eligible"] is True
    assert c["weeks_mastered"] == total
    assert c["distinction_count"] == 2
    # Phase 8: the certificate now reports the CEFR level (legacy L0 → A1),
    # and this mastery cert carries the completion statement.
    assert c["level"] == "A1"
    assert c["basis"] == "mastery"


# ---- level-complete detector (outcomes) -----------------------------------

def test_is_level_complete():
    total = curriculum.max_week_for_level("L0")
    assert itqan_outcomes._is_level_complete("L0", set(range(1, total + 1))) is True
    assert itqan_outcomes._is_level_complete("L0", {1, 2, 3}) is False


# ---- calendar gating ------------------------------------------------------

def test_calendar_progress_only_when_flag_on(student, monkeypatch):
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: {})
    # Flag off → no progress block.
    cal = darb.build_calendar(student)
    assert "itqan_progress" not in cal
    # Flag on → progress block present.
    database.set_feature_flag("itqan_weekly_assessment", True)
    cal = darb.build_calendar(student)
    assert "itqan_progress" in cal
    assert cal["itqan_progress"]["total_weeks"] == curriculum.max_week_for_level("L0")
