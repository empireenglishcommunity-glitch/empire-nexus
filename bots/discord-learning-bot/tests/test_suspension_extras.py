"""Tests for two suspension add-ons:

  1. Pre-flight role-hierarchy check — /suspend must WARN when the bot's own
     role sits at or below a student's access role, because Discord will refuse
     to remove it (suspension would otherwise appear to work and silently leave
     the student with access).
  2. The warm farewell DM sent on suspension — thanks the student, gives the
     renewal contact, reassures them their record is kept, and leaves them
     practice tips. It must be sent on a real first-time suspension only (not on
     the re-enforce repair path, not on dry-run).

These use position-aware fake roles so `role >= bot_top_role` behaves like
discord.py's real hierarchy comparison.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import database, suspension, role_gate, config


GATEWAY = role_gate.STUDENT_ROLE_NAME
A1_ROLE = config.level_role_name("A1")


class PosRole:
    """A fake role that supports discord.py-style position comparison."""
    def __init__(self, name, position):
        self.name = name
        self.position = position

    def __ge__(self, other):
        return self.position >= other.position

    def __gt__(self, other):
        return self.position > other.position

    def __repr__(self):
        return f"PosRole({self.name!r}, {self.position})"


class PosMember:
    def __init__(self, member_id, roles):
        self.id = int(member_id)
        self.display_name = f"user{member_id}"
        self.roles = list(roles)
        self.sent = []

    async def add_roles(self, role, reason=None):
        if role.name not in [r.name for r in self.roles]:
            self.roles.append(role)

    async def remove_roles(self, role, reason=None):
        self.roles = [r for r in self.roles if r.name != role.name]

    async def send(self, content):
        self.sent.append(content)

    def role_names(self):
        return {r.name for r in self.roles}


class PosGuild:
    def __init__(self, member, bot_top_position):
        self._member = member
        self.me = PosMember("999999", [PosRole("Empire Bot", bot_top_position)])
        # give guild.me a top_role attribute like discord.Member
        self.me.top_role = PosRole("Empire Bot", bot_top_position)
        self.roles = [PosRole(GATEWAY, 5), PosRole(A1_ROLE, 6)]

    def get_member(self, mid):
        if int(mid) == self._member.id:
            return self._member
        if int(mid) == self.me.id:
            return self.me
        return None

    async def create_role(self, **kwargs):
        r = PosRole(kwargs.get("name", "role"), 1)
        self.roles.append(r)
        return r


def _mk(discord_id, level="A1"):
    database.register_member(discord_id, "Farewell Target", level=level)
    database.set_level(discord_id, level)
    return discord_id


# ── 1. Pre-flight hierarchy check ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_hierarchy_blocks_flagged_when_bot_role_is_below():
    """Bot's top role (position 4) is BELOW the level role (6) and gateway (5),
    so both are unremovable → both reported as blocked."""
    did = _mk("901")
    member = PosMember(did, [PosRole(GATEWAY, 5), PosRole(A1_ROLE, 6)])
    guild = PosGuild(member, bot_top_position=4)

    res = await suspension.suspend_one(guild, database.get_member(did), dry_run=True)

    assert set(res["blocked_roles"]) == {GATEWAY, A1_ROLE}


@pytest.mark.asyncio
async def test_hierarchy_clear_when_bot_role_is_above():
    """Bot's top role (position 99) is ABOVE both access roles → nothing blocked."""
    did = _mk("902")
    member = PosMember(did, [PosRole(GATEWAY, 5), PosRole(A1_ROLE, 6)])
    guild = PosGuild(member, bot_top_position=99)

    res = await suspension.suspend_one(guild, database.get_member(did), dry_run=True)

    assert res["blocked_roles"] == []


def test_roles_bot_cannot_remove_direct():
    did = _mk("903")
    member = PosMember(did, [PosRole(GATEWAY, 5), PosRole(A1_ROLE, 6)])
    guild = PosGuild(member, bot_top_position=5)   # equal to gateway → gateway blocked
    blocked = suspension._roles_bot_cannot_remove(guild, did)
    # gateway (5) is equal to bot top (5) → blocked; level (6) > 5 → blocked too
    assert GATEWAY in blocked and A1_ROLE in blocked


def test_hierarchy_check_no_false_alarm_without_guild():
    assert suspension._roles_bot_cannot_remove(None, "1") == []


# ── 2. Farewell DM ───────────────────────────────────────────────────────────
def test_farewell_dm_content():
    msg = suspension.farewell_dm("Abeer Hassan")
    assert "Abeer" in msg                      # personalized (first name)
    assert "محمود عشري" in msg                  # renewal contact / owner name
    assert config.OWNER_WHATSAPP_URL in msg     # tappable renewal link
    assert config.OWNER_TELEGRAM in msg
    assert str(database.RETENTION_DAYS) in msg  # reassurance data is kept
    # keep-practicing tips present
    assert "💡" in msg


@pytest.mark.asyncio
async def test_dm_suspended_sends_on_real_suspension():
    did = _mk("904")
    member = PosMember(did, [PosRole(GATEWAY, 5), PosRole(A1_ROLE, 6)])
    guild = PosGuild(member, bot_top_position=99)

    ok = await suspension.dm_suspended(guild, did, "Abeer Hassan")
    assert ok is True
    assert len(member.sent) == 1
    assert "شكراً" in member.sent[0]           # the farewell greeting


@pytest.mark.asyncio
async def test_dm_suspended_tolerates_closed_dms():
    did = _mk("905")

    class ClosedDMMember(PosMember):
        async def send(self, content):
            raise RuntimeError("Cannot send messages to this user")

    member = ClosedDMMember(did, [PosRole(GATEWAY, 5)])
    guild = PosGuild(member, bot_top_position=99)
    ok = await suspension.dm_suspended(guild, did, "X")
    assert ok is False                          # never raises, just reports False


@pytest.mark.asyncio
async def test_reenforce_does_not_send_farewell_dm():
    """Repairing an already-suspended student must NOT re-send the goodbye DM
    (they already got it at first suspension). The re-enforce path returns
    before the DM step; assert dm_suspended is never invoked."""
    from src import bot as botmod

    did = _mk("906")
    database.suspend_member(did)
    member = PosMember(did, [PosRole(GATEWAY, 5), PosRole(A1_ROLE, 6)])
    guild = PosGuild(member, bot_top_position=99)

    with patch.object(suspension, "dm_suspended", AsyncMock()) as dm:
        text = await botmod._suspend_run_text(guild, [database.get_member(did)], reenforce=True)
    dm.assert_not_called()
    assert "Re-applied access removal" in text
