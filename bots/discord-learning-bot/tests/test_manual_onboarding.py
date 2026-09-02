"""Tests for team-run manual onboarding (replaces student self-onboarding).

Owner decision: the team trains + onboards each student in person via
!onboard @student <level>. The self-serve rules gate (✅-react / !agree) is
disabled by the `manual_onboarding` flag. Channel security (the gateway role +
channel overwrites) is UNCHANGED — only the self-grant paths are turned off.

Nour was retired (2026-09-03): there is no longer an automated onboarding
journey, so `grant_student_role` never kicks one off (the `start_journey`
parameter is retained only for backward compatibility and is now inert).

These tests lock in:
  1. grant_student_role grants the gateway role and starts NO journey,
     regardless of the (deprecated) start_journey argument.
  2. manual_onboarding ON => handle_reaction_gate and cmd_agree no-op (so a
     student cannot self-onboard).
  3. self-serve still works when manual_onboarding is OFF (no regression).
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import database, role_gate, community


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


# ── 1. grant_student_role grants the gateway role, starts no journey ────────
@pytest.mark.asyncio
async def test_grant_grants_role_but_no_journey():
    _set_manual(False)
    member = FakeMember("501")
    fake_role = FakeRole(role_gate.STUDENT_ROLE_NAME)
    with patch.object(role_gate, "get_or_create_student_role",
                      AsyncMock(return_value=fake_role)):
        granted = await role_gate.grant_student_role(member, start_journey=False)
    assert granted is True
    assert any(r.name == role_gate.STUDENT_ROLE_NAME for r in member.roles)


@pytest.mark.asyncio
async def test_grant_starts_no_journey_even_when_start_journey_true():
    """Nour retired: the deprecated start_journey=True argument is inert — the
    role is still granted, and no onboarding journey is ever started."""
    _set_manual(False)
    member = FakeMember("502")
    fake_role = FakeRole(role_gate.STUDENT_ROLE_NAME)
    with patch.object(role_gate, "get_or_create_student_role",
                      AsyncMock(return_value=fake_role)):
        granted = await role_gate.grant_student_role(member, start_journey=True)
    assert granted is True
    assert any(r.name == role_gate.STUDENT_ROLE_NAME for r in member.roles)
    # role_gate no longer imports or references any journey module.
    assert not hasattr(role_gate, "nour_journey")


@pytest.mark.asyncio
async def test_grant_noop_when_already_has_role():
    _set_manual(False)
    member = FakeMember("504", role_names=[role_gate.STUDENT_ROLE_NAME])
    granted = await role_gate.grant_student_role(member, start_journey=False)
    assert granted is False


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



# ── 5. /onboard member picker lists guild members (works in admin channel) ──
@pytest.mark.asyncio
async def test_member_autocomplete_lists_guild_members():
    """The bot-supplied picker for /onboard must list guild members regardless
    of channel visibility (the native picker didn't, from #admin-commands)."""
    from src import bot as botmod

    class FakeM:
        def __init__(self, mid, name, is_bot=False):
            self.id = mid
            self.display_name = name
            self.name = name
            self.bot = is_bot

    class FakeGuild:
        members = [FakeM(1, "Nada Ibrahim"), FakeM(2, "Ahmed"),
                   FakeM(3, "Empire Bot", is_bot=True)]

    class FakeInteraction:
        guild = FakeGuild()

    # No filter → both humans, no bots.
    res = await botmod._member_autocomplete(FakeInteraction(), "")
    names = [c.name for c in res]
    values = [c.value for c in res]
    assert "Nada Ibrahim" in names and "Ahmed" in names
    assert "Empire Bot" not in names          # bots excluded
    assert "1" in values                        # value is the member id

    # Filter by partial name.
    res2 = await botmod._member_autocomplete(FakeInteraction(), "nada")
    assert [c.name for c in res2] == ["Nada Ibrahim"]
    assert res2[0].value == "1"
