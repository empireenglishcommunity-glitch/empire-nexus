"""Tests for the student history reset + consent ledger (governance).

Verifies the safe-by-design guarantees:
  - a full snapshot is captured,
  - the reset wipes learning history but KEEPS the account,
  - a consent record is written and SURVIVES further resets (append-only proof),
  - a reset is fully REVERSIBLE from the consent snapshot.
"""
from src import database


def _seed():
    database.register_member("u1", "Alice")
    d = database._today_local().isoformat()
    database.log_submission("u1", d, "accent")
    database.log_submission("u1", d, "vocab")
    database.record_practice_mastery("u1", "L0", 1, 1, "accent", today=d)
    database.add_word_to_srs("u1", "hello")
    database.update_member("u1", total_points=50, current_streak=3, longest_streak=5)


def test_snapshot_captures_student_data():
    _seed()
    snap = database.snapshot_member_data("u1")
    assert snap["members"][0]["discord_id"] == "u1"
    assert len(snap["daily_submissions"]) == 2
    assert "practice_mastery" in snap and "vocab_srs" in snap
    # The proof ledger itself is never snapshotted (avoids recursion).
    assert "reset_consent_log" not in snap


def test_reset_wipes_history_but_keeps_account():
    _seed()
    res = database.reset_member_history("u1", initiated_by="student", affirmation="RESET")
    assert res is not None and "consent_id" in res
    m = database.get_member("u1")
    assert m is not None  # account preserved
    assert m["total_points"] == 0 and m["current_streak"] == 0 and m["longest_streak"] == 0
    conn = database._connect()
    for table in ("daily_submissions", "practice_mastery", "vocab_srs"):
        c = conn.execute(f"SELECT COUNT(*) c FROM {table} WHERE discord_id='u1'").fetchone()["c"]
        assert c == 0, f"{table} should be wiped"
    conn.close()


def test_reset_records_consent_that_survives_further_resets():
    _seed()
    database.reset_member_history("u1", initiated_by="student", affirmation="RESET",
                                  reason="wants a fresh start")
    recs = database.get_reset_consent_records("u1")
    assert len(recs) == 1
    assert recs[0]["initiated_by"] == "student"
    assert recs[0]["affirmation"] == "RESET"
    assert recs[0]["reason"] == "wants a fresh start"
    # Append-only: a second reset ADDS a record, never overwrites/deletes the first.
    database.reset_member_history("u1", initiated_by="owner:999", affirmation="RESET")
    assert len(database.get_reset_consent_records("u1")) == 2


def test_reset_is_reversible_from_consent_snapshot():
    _seed()
    res = database.reset_member_history("u1", initiated_by="student", affirmation="RESET")
    conn = database._connect()
    assert conn.execute("SELECT COUNT(*) c FROM daily_submissions WHERE discord_id='u1'").fetchone()["c"] == 0
    conn.close()

    restored = database.restore_member_from_consent(res["consent_id"])
    assert restored and restored.get("daily_submissions") == 2
    conn = database._connect()
    assert conn.execute("SELECT COUNT(*) c FROM daily_submissions WHERE discord_id='u1'").fetchone()["c"] == 2
    conn.close()
    # Account fields restored from the snapshot too.
    assert database.get_member("u1")["total_points"] == 50


def test_reset_unknown_member_returns_none():
    assert database.reset_member_history("ghost-user", initiated_by="student") is None
