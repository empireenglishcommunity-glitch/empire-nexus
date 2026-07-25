"""Tests for the owner-approval gate on student-initiated resets.

Guarantees: a pending request wipes NOTHING until approved; approve executes
the (logged, reversible) reset; deny leaves data intact; a new request
supersedes an older pending one; stale requests expire.
"""
from src import database


def _seed():
    database.register_member("u1", "Alice")
    d = database._today_local().isoformat()
    database.log_submission("u1", d, "accent")
    database.record_practice_mastery("u1", "L0", 1, 1, "accent", today=d)
    database.update_member("u1", total_points=30)


def _subs(discord_id="u1"):
    conn = database._connect()
    n = conn.execute("SELECT COUNT(*) c FROM daily_submissions WHERE discord_id=?",
                     (discord_id,)).fetchone()["c"]
    conn.close()
    return n


def test_pending_request_wipes_nothing():
    _seed()
    rid = database.create_pending_reset("u1", "Alice", "consent text", "RESET", "fresh start")
    assert rid > 0
    pend = database.get_pending_reset(rid)
    assert pend["status"] == "pending"
    # Data is untouched while pending.
    assert _subs() == 1
    assert database.get_member("u1")["total_points"] == 30
    assert len(database.list_pending_resets()) == 1


def test_approve_executes_reset_and_logs_consent():
    _seed()
    rid = database.create_pending_reset("u1", "Alice", "consent text", "RESET", "")
    res = database.approve_pending_reset(rid, decided_by="owner:owner123")
    assert res and res["consent_id"]
    # History wiped, account kept.
    assert _subs() == 0
    assert database.get_member("u1") is not None
    # Pending row marked approved + linked to the consent record.
    pend = database.get_pending_reset(rid)
    assert pend["status"] == "approved" and pend["decided_by"] == "owner:owner123"
    assert pend["consent_id"] == res["consent_id"]
    # Consent ledger has the record, marked student-approved.
    recs = database.get_reset_consent_records("u1")
    assert len(recs) == 1 and recs[0]["initiated_by"].startswith("student-approved:")


def test_deny_leaves_data_intact():
    _seed()
    rid = database.create_pending_reset("u1", "Alice", "consent text", "RESET", "")
    res = database.deny_pending_reset(rid, decided_by="owner:owner123")
    assert res and res["discord_id"] == "u1"
    assert _subs() == 1  # nothing deleted
    assert database.get_pending_reset(rid)["status"] == "denied"
    # No consent record written (nothing was reset).
    assert database.get_reset_consent_records("u1") == []


def test_cannot_decide_twice():
    _seed()
    rid = database.create_pending_reset("u1", "Alice", "c", "RESET", "")
    database.approve_pending_reset(rid, "owner:x")
    again = database.approve_pending_reset(rid, "owner:x")
    assert again == {"error": "not_pending", "status": "approved"}


def test_new_request_supersedes_old_pending():
    _seed()
    r1 = database.create_pending_reset("u1", "Alice", "c", "RESET", "")
    r2 = database.create_pending_reset("u1", "Alice", "c", "RESET", "")
    assert database.get_pending_reset(r1)["status"] == "superseded"
    assert database.get_pending_reset(r2)["status"] == "pending"
    assert len(database.list_pending_resets()) == 1


def test_expire_old_pending():
    _seed()
    rid = database.create_pending_reset("u1", "Alice", "c", "RESET", "")
    # Backdate the request beyond the TTL.
    conn = database._connect()
    conn.execute("UPDATE pending_resets SET requested_at=datetime('now','-30 days') WHERE id=?", (rid,))
    conn.commit()
    conn.close()
    assert database.expire_old_pending_resets(ttl_days=7) == 1
    assert database.get_pending_reset(rid)["status"] == "expired"


def test_approve_unknown_request_returns_none():
    assert database.approve_pending_reset(99999, "owner:x") is None
