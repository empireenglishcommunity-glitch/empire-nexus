"""Darb (درب) Phase 1 backend tests — claim codes, device sessions,
signed session tokens, content-day mastery/tiers, and the personal
calendar. Pure/sync + a couple of async orchestration tests. Uses the
shared temp_db fixture (fresh SQLite per test)."""
import datetime

import pytest

from src import config, database, darb


def _member(discord_id="u1", name="Alice", level="L0", joined_at=None):
    database.register_member(discord_id, name)
    fields = {"level": level}
    if joined_at:
        fields["joined_at"] = joined_at
    database.update_member(discord_id, **fields)
    return discord_id


# ============================================================
#  CLAIM CODES
# ============================================================

def test_claim_code_create_and_consume():
    _member()
    code = database.create_claim_code("u1")
    assert code and len(code) == 8
    # Consuming a valid code returns the owner and marks it consumed.
    assert database.consume_claim_code(code) == "u1"
    # A second consume of the same code fails (single-use).
    assert database.consume_claim_code(code) is None


def test_claim_code_new_invalidates_prior_unconsumed():
    _member()
    first = database.create_claim_code("u1")
    second = database.create_claim_code("u1")
    assert first != second
    # The first (never consumed) is now invalid; only the newest works.
    assert database.consume_claim_code(first) is None
    assert database.consume_claim_code(second) == "u1"


def test_claim_code_expired_cannot_be_consumed():
    _member()
    code = database.create_claim_code("u1")
    # Force it into the past.
    conn = database._connect()
    conn.execute("UPDATE claim_codes SET expires_at=datetime('now','-1 minute') WHERE code=?", (code,))
    conn.commit()
    conn.close()
    assert database.consume_claim_code(code) is None


def test_claim_code_rate_limited():
    _member()
    # With a cap of 3/hour, the 4th issue is refused.
    assert database.create_claim_code("u1", max_per_hour=3) is not None
    assert database.create_claim_code("u1", max_per_hour=3) is not None
    assert database.create_claim_code("u1", max_per_hour=3) is not None
    assert database.create_claim_code("u1", max_per_hour=3) is None


def test_consume_unknown_code_returns_none():
    assert database.consume_claim_code("NOPE") is None
    assert database.consume_claim_code("") is None


# ============================================================
#  DEVICE SESSIONS + CAP
# ============================================================

def test_device_session_create_active_revoke():
    _member()
    database.create_device_session("u1", "dev1", ip="1.1.1.1", user_agent="ua")
    assert database.is_device_session_active("dev1") is True
    assert len(database.active_device_sessions("u1")) == 1
    database.revoke_device_session("dev1")
    assert database.is_device_session_active("dev1") is False
    assert len(database.active_device_sessions("u1")) == 0


def test_enforce_device_cap_revokes_oldest():
    _member()
    # Three sessions; created_at ordering is insertion order.
    for d in ("dev1", "dev2", "dev3"):
        database.create_device_session("u1", d)
    revoked = database.enforce_device_cap("u1", cap=2)
    assert revoked == ["dev1"]  # oldest evicted
    active_ids = {s["device_id"] for s in database.active_device_sessions("u1")}
    assert active_ids == {"dev2", "dev3"}


def test_revoke_all_device_sessions():
    _member()
    database.create_device_session("u1", "dev1")
    database.create_device_session("u1", "dev2")
    assert database.revoke_all_device_sessions("u1") == 2
    assert database.active_device_sessions("u1") == []


# ============================================================
#  SIGNED SESSION TOKENS
# ============================================================

def test_session_mint_verify_roundtrip(monkeypatch):
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "test-secret-abc")
    tok = darb.mint_session("u1", "L0", "dev1")
    payload = darb.verify_session(tok)
    assert payload is not None
    assert payload["did"] == "u1"
    assert payload["lvl"] == "L0"
    assert payload["sid"] == "dev1"


def test_session_tampered_signature_fails(monkeypatch):
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "test-secret-abc")
    tok = darb.mint_session("u1", "L0", "dev1")
    body, sig = tok.split(".", 1)
    tampered = body + ".AAAA" + sig[4:]
    assert darb.verify_session(tampered) is None


def test_session_wrong_secret_fails(monkeypatch):
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "secret-one")
    tok = darb.mint_session("u1", "L0", "dev1")
    # A different secret must not validate a token signed with the first.
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "secret-two")
    assert darb.verify_session(tok) is None


def test_session_expired_fails(monkeypatch):
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "test-secret-abc")
    tok = darb.mint_session("u1", "L0", "dev1", ttl_days=-1)  # already expired
    assert darb.verify_session(tok) is None


def test_session_empty_secret_is_failsafe(monkeypatch):
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "")
    with pytest.raises(RuntimeError):
        darb.mint_session("u1", "L0", "dev1")
    assert darb.verify_session("anything.anything") is None


# ============================================================
#  PRACTICE MASTERY / TIERS
# ============================================================

def test_mastery_first_completion_is_bronze():
    _member()
    r = database.record_practice_mastery("u1", "L0", 1, 1, "accent", today="2026-07-10")
    assert r["exercise_tier"] == 1
    assert r["incremented"] is True


def test_mastery_same_day_repeat_does_not_increment():
    _member()
    database.record_practice_mastery("u1", "L0", 1, 1, "accent", today="2026-07-10")
    r = database.record_practice_mastery("u1", "L0", 1, 1, "accent", today="2026-07-10")
    assert r["exercise_tier"] == 1
    assert r["incremented"] is False


def test_mastery_increments_once_per_new_day_and_caps_at_5():
    _member()
    days = ["2026-07-10", "2026-07-11", "2026-07-12", "2026-07-13",
            "2026-07-14", "2026-07-15", "2026-07-16"]
    tiers = [database.record_practice_mastery("u1", "L0", 1, 1, "accent", today=d)["exercise_tier"]
             for d in days]
    assert tiers == [1, 2, 3, 4, 5, 5, 5]  # caps at 5 (Diamond)


def test_day_tier_is_min_across_four_and_done_needs_all_four():
    _member()
    # Only 3 of 4 exercises done → day not done, tier 0.
    for ex in ("accent", "vocab", "shadow"):
        database.record_practice_mastery("u1", "L0", 1, 1, ex, today="2026-07-10")
    cal = database.get_calendar_mastery("u1", "L0")
    assert cal[(1, 1)]["done"] is False
    assert cal[(1, 1)]["day_tier"] == 0
    # Complete the 4th → done, day tier = min (all at 1 = bronze).
    database.record_practice_mastery("u1", "L0", 1, 1, "listening", today="2026-07-10")
    cal = database.get_calendar_mastery("u1", "L0")
    assert cal[(1, 1)]["done"] is True
    assert cal[(1, 1)]["day_tier"] == 1
    # Push accent to silver on a new day → day tier stays min (1).
    database.record_practice_mastery("u1", "L0", 1, 1, "accent", today="2026-07-11")
    cal = database.get_calendar_mastery("u1", "L0")
    assert cal[(1, 1)]["day_tier"] == 1


# ============================================================
#  PERSONAL CALENDAR
# ============================================================

def test_calendar_states(monkeypatch):
    _member(level="L0", joined_at="2026-07-10")
    # Fix "today" to 3 days after join → today_index == 3.
    monkeypatch.setattr(darb, "_today_local", lambda: datetime.date(2026, 7, 12))
    # Complete all 4 of week1/day1 → that day should be green (done).
    for ex in database.PRACTICE_EXERCISES:
        database.record_practice_mastery("u1", "L0", 1, 1, ex, today="2026-07-10")

    cal = darb.build_calendar("u1")
    assert cal["level"] == "L0"
    assert cal["join_date"] == "2026-07-10"
    assert cal["today_index"] == 3
    assert cal["level_total_days"] == 56  # L0 = 8 weeks

    by_index = {d["index"]: d for d in cal["days"]}
    assert by_index[1]["state"] == "done"      # completed
    assert by_index[1]["date"] == "2026-07-10"
    assert by_index[2]["state"] == "missed"    # past, not done
    assert by_index[3]["state"] == "today"     # today, not done
    assert by_index[4]["state"] == "locked"    # future
    assert by_index[1]["day_tier"] == 1


def test_calendar_unknown_member_returns_none():
    assert darb.build_calendar("ghost") is None


# ============================================================
#  CLAIM ORCHESTRATION (async)
# ============================================================

@pytest.mark.asyncio
async def test_claim_flow_mints_valid_session(monkeypatch):
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "test-secret-abc")
    _member(level="L1")
    code = database.create_claim_code("u1")
    result = await darb.claim(code, ip="9.9.9.9", user_agent="ua")
    assert result is not None
    assert result["level"] == "L1"
    # The minted token verifies and its device session is active.
    payload = darb.verify_session(result["token"])
    assert payload["did"] == "u1"
    assert payload["sid"] == result["device_id"]
    assert database.is_device_session_active(result["device_id"]) is True


@pytest.mark.asyncio
async def test_claim_flow_enforces_two_device_cap(monkeypatch):
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "test-secret-abc")
    # Silence the owner alert (no network in tests).
    async def _noop(*a, **k):
        return None
    monkeypatch.setattr(darb, "_alert_owner_device_cap", _noop)
    _member()

    devices = []
    for _ in range(3):
        code = database.create_claim_code("u1")
        res = await darb.claim(code)
        devices.append(res["device_id"])

    # Only the 2 most recent remain active; the oldest was evicted.
    active = {s["device_id"] for s in database.active_device_sessions("u1")}
    assert active == {devices[1], devices[2]}
    assert database.is_device_session_active(devices[0]) is False


@pytest.mark.asyncio
async def test_claim_invalid_code_returns_none(monkeypatch):
    monkeypatch.setattr(config, "DARB_SESSION_SECRET", "test-secret-abc")
    assert await darb.claim("BADCODE") is None
