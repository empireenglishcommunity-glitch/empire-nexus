"""Tests for team-run manual onboarding (replaces student self-onboarding).

Owner decision: the team trains + onboards each student in person via
!onboard @student <level>. The self-serve rules gate (✅-react / !agree) and the
automated Nour journey are disabled by the `manual_onboarding` flag. Channel
security (the gateway role + channel overwrites) is UNCHANGED — only the
self-grant paths and the journey DMs are turned off.

These tests lock in:
  1. grant_student_role(start_journey=False) grants the gateway role but does
     NOT kick off the journey.
  2. manual_onboarding ON => handle_reaction_gate and cmd_agree no-op (so a
     student cannot self-onboard).
  3. nour_journey.start_journey bails when manual_onboarding is on.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import database, role_gate, nour_journey, community


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeMember:
    def __init__(self, member_id, role_names=(), bot=False):
        self.id = int(member_id)
        self.display_name = f"user{member_id}"
        self.bot = bot
        self.roles = [FakeRole(n) for n in role_names]
        self.guild = None
        self.added = []

    async def add_roles(self, role, reason=None):
        self.added.append(role)
        self.roles.append(role)


def _set_manual(on: bool):
    database.set_feature_flag("hissar_role_gate", True)
    database.set_feature_flag("manual_onboarding", on)


# ── 1. grant_student_role(start_journey=False) ──────────────────────────────
@pytest.mark.asyncio
async def test_grant_without_journey_grants_role_but_no_journey():
    _set_manual(False)  # isolate: prove start_journey=False alone suppresses it
    member = FakeMember("501")
    fake_role = FakeRole(role_gate.STUDENT_ROLE_NAME)
    with patch.object(role_gate, "get_or_create_student_role",
                      AsyncMock(return_value=fake_role)), \
         patch.object(nour_journey, "start_journey", AsyncMock()) as journey:
        granted = await role_gate.grant_student_role(member, start_journey=False)
    assert granted is True
    assert any(r.name == role_gate.STUDENT_ROLE_NAME for r in member.roles)
    journey.assert_not_called()


@pytest.mark.asyncio
async def test_grant_with_journey_starts_journey():
    _set_manual(False)
    member = FakeMember("502")
    fake_role = FakeRole(role_gate.STUDENT_ROLE_NAME)
    with patch.object(role_gate, "get_or_create_student_role",
                      AsyncMock(return_value=fake_role)), \
         patch.object(nour_journey, "start_journey", AsyncMock()) as journey:
        await role_gate.grant_student_role(member, start_journey=True)
    journey.assert_called_once()


# ── 2. manual_onboarding disables the self-serve gate ───────────────────────
@pytest.mark.asyncio
async def test_reaction_gate_noop_when_manual_onboarding_on():
    _set_manual(True)

    class FakePayload:
        emoji = role_gate.GATE_EMOJI
        channel_id = 1
        user_id = 999

    # Should return False (not handled) and never grant a role.
    with patch.object(role_gate, "grant_student_role", AsyncMock()) as grant:
        handled = await role_gate.handle_reaction_gate(FakePayload(), guild=object())
    assert handled is False
    grant.assert_not_called()


@pytest.mark.asyncio
async def test_agree_noop_when_manual_onboarding_on():
    _set_manual(True)
    ctx = AsyncMock()
    handled = await role_gate.cmd_agree(ctx)
    assert handled is False
    ctx.send.assert_not_called()   # silent — no prompt to the student


@pytest.mark.asyncio
async def test_journey_bails_when_manual_onboarding_on():
    _set_manual(True)
    database.set_feature_flag("nour_journey", True)  # even with journey ON
    member = FakeMember("503")
    # _get_journey should never be reached; patch it to blow up if it is.
    with patch.object(nour_journey, "_get_journey",
                      side_effect=AssertionError("journey must not start")):
        await nour_journey.start_journey(member)   # must simply return


# ── 3. self-serve still works when manual_onboarding OFF (no regression) ────
@pytest.mark.asyncio
async def test_agree_active_when_manual_onboarding_off():
    _set_manual(False)

    # Wrong channel path is fine — we only assert it did NOT early-return on the
    # manual-onboarding guard (it proceeds to the channel check and responds).
    ctx = AsyncMock()
    ctx.channel.name = "not-rules"
    handled = await role_gate.cmd_agree(ctx)
    # In a non-#rules channel it sends the "only in #rules" notice and returns.
    assert ctx.send.await_count >= 1



# ── 4. community-pings role is granted (grant-only, idempotent) ─────────────
@pytest.mark.asyncio
async def test_ensure_pings_role_grants_when_missing():
    member = FakeMember("601")
    fake_role = FakeRole(community.COMMUNITY_PINGS_ROLE)
    with patch.object(community, "get_or_create_pings_role",
                      AsyncMock(return_value=fake_role)):
        added = await community.ensure_pings_role(member, guild=object())
    assert added is True
    assert any(r.name == community.COMMUNITY_PINGS_ROLE for r in member.roles)


@pytest.mark.asyncio
async def test_ensure_pings_role_noop_when_already_has_it():
    member = FakeMember("602", role_names=[community.COMMUNITY_PINGS_ROLE])
    with patch.object(community, "get_or_create_pings_role",
                      AsyncMock()) as getrole:
        added = await community.ensure_pings_role(member, guild=object())
    assert added is False
    getrole.assert_not_called()   # short-circuits before touching the role
