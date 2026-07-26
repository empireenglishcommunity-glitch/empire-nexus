"""Session-33 — onboarding safety-net tests (role_gate reconciliation).

Covers the read-only audit that detects onboarding-gate bypasses, plus the
Empire Ops reconciliation alert with its change-only (fingerprint) de-dup.
These lock in the behavior that would have automatically caught the
session-23 gap (14/15 students with NO_JOURNEY).
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import database, role_gate


# ============================================================
#  Minimal discord.Guild / Member / Role doubles
# ============================================================

class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeMember:
    def __init__(self, member_id, role_names):
        self.id = int(member_id)
        self.roles = [FakeRole(n) for n in role_names]


class FakeGuild:
    def __init__(self, members):
        # members: dict of {discord_id: FakeMember or None}
        self._by_id = {int(k): v for k, v in members.items()}

    def get_member(self, mid):
        return self._by_id.get(int(mid))


STUDENT = role_gate.STUDENT_ROLE_NAME


def _add_journey(discord_id):
    conn = database._connect()
    conn.execute(
        "INSERT OR IGNORE INTO student_journey (discord_id) VALUES (?)",
        (str(discord_id),),
    )
    conn.commit()
    conn.close()


def _register(discord_id, name):
    database.register_member(str(discord_id), name)


# ============================================================
#  audit_onboarding — classification
# ============================================================

def test_audit_classifies_all_four_states():
    # A: role + journey (fully onboarded)
    # B: role, no journey (legacy/grandfathered)
    # C: in guild, no role (a real bypass)
    # D: active in DB but not currently in the guild
    _register("100", "Ahmed"); _add_journey("100")
    _register("200", "Basma")               # role, no journey
    _register("300", "Cadi")                # no role
    _register("400", "Dina")                # not in guild

    guild = FakeGuild({
        "100": FakeMember("100", [STUDENT, "@everyone"]),
        "200": FakeMember("200", [STUDENT]),
        "300": FakeMember("300", ["@everyone"]),   # no Student role
        "400": None,                                # left the guild
    })

    audit = role_gate.audit_onboarding(guild)

    assert audit["total"] == 4
    assert [m["discord_id"] for m in audit["ok"]] == ["100"]
    assert [m["discord_id"] for m in audit["gated_no_journey"]] == ["200"]
    assert [m["discord_id"] for m in audit["no_gate"]] == ["300"]
    assert [m["discord_id"] for m in audit["not_in_guild"]] == ["400"]


def test_audit_all_clean():
    for i, name in enumerate(["A", "B"]):
        did = str(500 + i)
        _register(did, name); _add_journey(did)
    guild = FakeGuild({
        "500": FakeMember("500", [STUDENT]),
        "501": FakeMember("501", [STUDENT]),
    })
    audit = role_gate.audit_onboarding(guild)
    assert len(audit["ok"]) == 2
    assert audit["no_gate"] == [] and audit["gated_no_journey"] == []


# ============================================================
#  format_onboarding_audit
# ============================================================

def test_format_flags_bypass_and_legacy():
    _register("300", "Cadi")
    _register("200", "Basma"); 
    guild = FakeGuild({
        "300": FakeMember("300", ["@everyone"]),
        "200": FakeMember("200", [STUDENT]),
    })
    audit = role_gate.audit_onboarding(guild)
    text = role_gate.format_onboarding_audit(audit)
    assert "WITHOUT the gate role" in text
    assert "Cadi" in text            # the bypass member is named
    assert "no guided journey" in text
    assert "Basma" in text


def test_format_clean_reports_ok():
    _register("500", "A"); _add_journey("500")
    guild = FakeGuild({"500": FakeMember("500", [STUDENT])})
    audit = role_gate.audit_onboarding(guild)
    text = role_gate.format_onboarding_audit(audit)
    assert "every active student passed the gate" in text


# ============================================================
#  run_onboarding_reconciliation — alert + fingerprint de-dup
# ============================================================

@pytest.mark.asyncio
async def test_reconciliation_alerts_then_dedups_then_realerts():
    database.set_feature_flag("hissar_role_gate", True)
    _register("300", "Cadi")                       # no_gate -> critical
    _register("200", "Basma")                      # gated_no_journey
    guild = FakeGuild({
        "300": FakeMember("300", ["@everyone"]),
        "200": FakeMember("200", [STUDENT]),
    })

    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        # 1st run: something is wrong -> alert once, critical (a no_gate exists)
        await role_gate.run_onboarding_reconciliation(guild)
        assert alert.await_count == 1
        assert alert.await_args.kwargs.get("severity") == "critical"

        # 2nd run: nothing changed -> no new alert (de-dup)
        await role_gate.run_onboarding_reconciliation(guild)
        assert alert.await_count == 1

        # A NEW bypass appears -> fingerprint changes -> alert again
        _register("301", "Cadi2")
        guild._by_id[301] = FakeMember("301", ["@everyone"])
        await role_gate.run_onboarding_reconciliation(guild)
        assert alert.await_count == 2


@pytest.mark.asyncio
async def test_reconciliation_silent_when_clean():
    database.set_feature_flag("hissar_role_gate", True)
    _register("500", "A"); _add_journey("500")
    guild = FakeGuild({"500": FakeMember("500", [STUDENT])})
    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        audit = await role_gate.run_onboarding_reconciliation(guild)
        assert alert.await_count == 0
        assert audit["no_gate"] == []


@pytest.mark.asyncio
async def test_reconciliation_noop_when_flag_off():
    database.set_feature_flag("hissar_role_gate", False)
    _register("300", "Cadi")
    guild = FakeGuild({"300": FakeMember("300", ["@everyone"])})
    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        result = await role_gate.run_onboarding_reconciliation(guild)
        assert result is None
        assert alert.await_count == 0


@pytest.mark.asyncio
async def test_force_reports_even_when_clean():
    database.set_feature_flag("hissar_role_gate", True)
    _register("500", "A"); _add_journey("500")
    guild = FakeGuild({"500": FakeMember("500", [STUDENT])})
    with patch("src.ops_hub.send_ops_alert", new=AsyncMock()) as alert:
        await role_gate.run_onboarding_reconciliation(guild, force=True)
        assert alert.await_count == 1
        # clean state -> not critical
        assert alert.await_args.kwargs.get("severity") == "warning"
