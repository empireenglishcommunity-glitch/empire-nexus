"""Tests for the read-only progress reconciliation audit (src/reconcile.py).

Verifies it correctly reports consistency between the date-based Discord
ledger (daily_submissions) and the content-day calendar (practice_mastery),
including the legitimate "catch-up on a past day" case that must NOT be
flagged as drift."""
from src import database, reconcile


def _today():
    return database._today_local().isoformat()


def test_reconcile_consistent_no_drift():
    database.register_member("u1", "Alice")
    d = _today()
    for ex in ("accent", "vocab", "shadow", "listening", "speaking"):
        database.log_submission("u1", d, ex)
        database.record_practice_mastery("u1", "L0", 1, 1, ex, today=d)
    rep = reconcile.reconcile(date=d)
    assert rep["forward_drift"] == []
    assert rep["reverse_drift"] == []
    assert rep["all5"] == 1
    assert rep["checked"] == 5
    assert rep["active_students"] == 1


def test_reconcile_flags_forward_drift():
    """Logged in the 7-ledger but no mastery recorded that day."""
    database.register_member("u1", "Alice")
    d = _today()
    database.log_submission("u1", d, "accent")  # ledger only, no mastery
    rep = reconcile.reconcile(date=d)
    assert ("u1", "accent") in rep["forward_drift"]


def test_reconcile_flags_reverse_drift():
    """Mastery recorded that day but the task never hit the 7-ledger."""
    database.register_member("u1", "Alice")
    d = _today()
    database.log_submission("u1", d, "accent")               # keeps the student "active"
    database.record_practice_mastery("u1", "L0", 1, 1, "accent", today=d)
    database.record_practice_mastery("u1", "L0", 1, 1, "vocab", today=d)  # no vocab submission
    rep = reconcile.reconcile(date=d)
    assert ("u1", "vocab") in rep["reverse_drift"]
    assert ("u1", "accent") not in rep["reverse_drift"]


def test_reconcile_catchup_on_past_day_is_not_drift():
    """A student catching up on a PAST content-day (mastery on w1d2 while the
    submission is logged for the same real date) must be consistent — the
    match is on 'recorded that day', not today's content-day."""
    database.register_member("u1", "Alice")
    d = _today()
    database.log_submission("u1", d, "accent")
    database.record_practice_mastery("u1", "L0", 1, 2, "accent", today=d)
    rep = reconcile.reconcile(date=d)
    assert rep["forward_drift"] == []
    assert rep["reverse_drift"] == []
