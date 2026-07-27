"""Itqan Phase 11 — mastery-based progression gate (R16)."""
import datetime

import pytest

from src import darb, database


@pytest.fixture
def student():
    database.register_member("g1", "Gamer", "L0")
    return "g1"


def _set_join(monkeypatch, days_ago, mastery=None):
    join = (datetime.date.today() - datetime.timedelta(days=days_ago)).isoformat()
    monkeypatch.setattr(database, "level_anchor_iso", lambda m: join)
    monkeypatch.setattr(database, "get_calendar_mastery", lambda did, lvl: (mastery or {}))


def test_gate_off_is_unchanged(student, monkeypatch):
    _set_join(monkeypatch, 0)
    cal = darb.build_calendar(student)
    assert "gate" not in cal
    assert all(d["state"] != "gate_locked" for d in cal["days"])


def test_gate_new_student_locks_beyond_week1(student, monkeypatch):
    _set_join(monkeypatch, 0)                       # today_index 1 -> current week 1
    database.set_feature_flag("itqan_progression_gate", True)
    cal = darb.build_calendar(student)
    assert cal["gate"]["allowed_week"] == 1
    assert all(d["state"] == "gate_locked" for d in cal["days"] if d["week"] == 2)
    assert all(d["state"] != "gate_locked" for d in cal["days"] if d["week"] == 1)


def test_gate_opens_next_week_when_passed(student, monkeypatch):
    _set_join(monkeypatch, 0)
    database.set_feature_flag("itqan_progression_gate", True)
    database.itqan_upsert_mastery("g1", "L0", 1, False, 1)   # pass week 1
    cal = darb.build_calendar(student)
    assert cal["gate"]["allowed_week"] == 2
    # Week 2 is no longer gate-locked (it's just date-locked now).
    assert all(d["state"] != "gate_locked" for d in cal["days"] if d["week"] == 2)
    assert all(d["state"] == "gate_locked" for d in cal["days"] if d["week"] == 3)


def test_gate_grandfathers_existing_student(student, monkeypatch):
    _set_join(monkeypatch, 22)                      # ~week 4 by date, no mastery
    database.set_feature_flag("itqan_progression_gate", True)
    cal = darb.build_calendar(student)
    # Baseline = reached week (4); weeks 1-4 stay open, only week 5+ gated.
    assert cal["gate"]["allowed_week"] == 4
    assert all(d["state"] != "gate_locked" for d in cal["days"] if d["week"] <= 4)
    assert all(d["state"] == "gate_locked" for d in cal["days"] if d["week"] == 5)


def test_baseline_is_stamped_once(student, monkeypatch):
    _set_join(monkeypatch, 22)
    database.set_feature_flag("itqan_progression_gate", True)
    darb.build_calendar(student)                    # stamps baseline 4
    # Even if the student later appears "earlier", the baseline stays 4.
    assert database.itqan_gate_baseline("g1", "L0", 1) == 4
