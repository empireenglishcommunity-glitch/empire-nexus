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


# Soft gate (owner decision 2026-07-28): the progression gate NO LONGER freezes
# daily practice — no day is ever "gate_locked". The gate still computes
# `allowed_week` (informational, for the progress map / messaging), and mastery
# rewards (Champions, certificate) still require passing each week's test. These
# tests assert the allowed_week math is intact AND that daily tasks are never
# frozen.


def test_gate_new_student_allowed_week_is_current(student, monkeypatch):
    _set_join(monkeypatch, 0)                       # today_index 1 -> current week 1
    database.set_feature_flag("itqan_progression_gate", True)
    cal = darb.build_calendar(student)
    assert cal["gate"]["allowed_week"] == 1
    assert all(d["state"] != "gate_locked" for d in cal["days"])   # never frozen


def test_gate_allowed_week_advances_when_passed(student, monkeypatch):
    _set_join(monkeypatch, 0)
    database.set_feature_flag("itqan_progression_gate", True)
    database.itqan_upsert_mastery("g1", "L0", 1, False, 1)   # pass week 1
    cal = darb.build_calendar(student)
    assert cal["gate"]["allowed_week"] == 2
    assert all(d["state"] != "gate_locked" for d in cal["days"])   # never frozen


def test_gate_grandfathers_existing_student(student, monkeypatch):
    _set_join(monkeypatch, 22)                      # ~week 4 by date, no mastery
    database.set_feature_flag("itqan_progression_gate", True)
    cal = darb.build_calendar(student)
    # Baseline = reached week (4); allowed_week reported as 4, and NO day is
    # frozen — the student keeps full access to their daily practice.
    assert cal["gate"]["allowed_week"] == 4
    assert all(d["state"] != "gate_locked" for d in cal["days"])


def test_baseline_is_stamped_once(student, monkeypatch):
    _set_join(monkeypatch, 22)
    database.set_feature_flag("itqan_progression_gate", True)
    darb.build_calendar(student)                    # stamps baseline 4
    # Even if the student later appears "earlier", the baseline stays 4.
    assert database.itqan_gate_baseline("g1", "L0", 1) == 4
