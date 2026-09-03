"""Regression: a SUSPENDED student must never regain the gateway role.

Incident (2026-09-03): a suspended student showed up active in the community an
hour after being suspended. Cause: on rejoin, on_member_join →
check_existing_reaction_on_join found the student's OLD ✅ reaction still on the
#rules message and called grant_student_role — which had no suspension check —
silently re-granting access.

Fix: grant_student_role (the single chokepoint for every grant path) refuses to
grant if the member is suspended; the on-rejoin self-heal also skips suspended
members. Restore is unaffected (it clears suspended_at first and adds roles via
its own path). These tests lock that in.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import database, role_gate


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeMember:
    def __init__(self, member_id, role_names=()):
        self.id = int(member_id)
        self.display_name = f"user{member_id}"
        self.bot = False
        self.roles = [FakeRole(n) for n in role_names]
        self.guild = None

    async def add_roles(self, role, reason=None):
        self.roles.append(role)


def _mk(discord_id, level="A1"):
    database.set_feature_flag("hissar_role_gate", True)
    database.register_member(discord_id, "Regrant Target", level=level)
    return discord_id


@pytest.mark.asyncio
async def test_suspended_member_is_refused_the_gateway_role():
    did = _mk("880")
    database.suspend_member(did)
    assert database.is_suspended(did) is True

    member = FakeMember(did)   # rejoined with no roles
    fake_role = FakeRole(role_gate.STUDENT_ROLE_NAME)
    with patch.object(role_gate, "get_or_create_student_role",
                      AsyncMock(return_value=fake_role)):
        granted = await role_gate.grant_student_role(member)

    assert granted is False                                   # refused
    assert not any(r.name == role_gate.STUDENT_ROLE_NAME for r in member.roles)


@pytest.mark.asyncio
async def test_active_member_is_still_granted():
    did = _mk("881")   # never suspended
    member = FakeMember(did)
    fake_role = FakeRole(role_gate.STUDENT_ROLE_NAME)
    with patch.object(role_gate, "get_or_create_student_role",
                      AsyncMock(return_value=fake_role)):
        granted = await role_gate.grant_student_role(member)
    assert granted is True
    assert any(r.name == role_gate.STUDENT_ROLE_NAME for r in member.roles)


@pytest.mark.asyncio
async def test_restore_then_grant_works_again():
    """After /restore clears suspended_at, granting works normally again."""
    did = _mk("882")
    database.suspend_member(did)
    database.restore_member(did)              # what /restore does first
    assert database.is_suspended(did) is False

    member = FakeMember(did)
    fake_role = FakeRole(role_gate.STUDENT_ROLE_NAME)
    with patch.object(role_gate, "get_or_create_student_role",
                      AsyncMock(return_value=fake_role)):
        granted = await role_gate.grant_student_role(member)
    assert granted is True


@pytest.mark.asyncio
async def test_rejoin_self_heal_skips_suspended_member():
    """check_existing_reaction_on_join must NOT re-grant a suspended member,
    even though their old ✅ is still on the rules message."""
    did = _mk("883")
    database.suspend_member(did)
    member = FakeMember(did)

    # If it tried to heal, it would call grant_student_role. Patch it to detect.
    with patch.object(role_gate, "grant_student_role", AsyncMock()) as grant:
        await role_gate.check_existing_reaction_on_join(member)
    grant.assert_not_called()
