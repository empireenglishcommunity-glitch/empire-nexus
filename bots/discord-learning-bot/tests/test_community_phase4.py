"""Community Lounge ("Majlis") Phase 4 — opt-in pings + Knock tests.

Covers:
- has_pings_role: checks role presence on member
- toggle_pings_role: adds/removes role (mocked Discord)
- toggle_pings_role: flag OFF returns 'disabled'
- build_beacon_mention: returns role mention when flag ON + role exists
- build_beacon_mention: returns empty when flag OFF
- can_knock / record_knock: rate-limiting
- do_knock: sends, rate-limited, quiet-hours, not-in-majlis check
"""
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src import database, community


# ============================================================
#  HELPERS
# ============================================================

def _enable_flag(flag_name: str):
    database.set_feature_flag(flag_name, True, "", "test")


def _disable_flag(flag_name: str):
    database.set_feature_flag(flag_name, False, "", "test")


def setup_function():
    community.reset_knock_cooldown()


class _FakeRole:
    def __init__(self, name, role_id="800"):
        self.name = name
        self.id = int(role_id)


class _FakeMember:
    def __init__(self, uid, roles=None, display_name="Tester", bot=False):
        self.id = int(uid)
        self.roles = roles or []
        self.display_name = display_name
        self.bot = bot
        self.add_roles = AsyncMock()
        self.remove_roles = AsyncMock()


class _FakeVC:
    def __init__(self, name, cid, members=None):
        self.name = name
        self.id = int(cid)
        self.members = members or []


class _FakeGuild:
    def __init__(self, vcs=None, roles=None):
        self.voice_channels = vcs or []
        self.roles = roles or []
        self.create_role = AsyncMock()

    def get_role(self, rid):
        for r in self.roles:
            if r.id == rid:
                return r
        return None


# ============================================================
#  has_pings_role
# ============================================================

def test_has_pings_role_true():
    role = _FakeRole("community-pings")
    member = _FakeMember("1", roles=[role])
    assert community.has_pings_role(member) is True


def test_has_pings_role_false():
    member = _FakeMember("1", roles=[_FakeRole("other")])
    assert community.has_pings_role(member) is False


# ============================================================
#  toggle_pings_role
# ============================================================

@pytest.mark.asyncio
async def test_toggle_adds_role():
    """Toggling when not opted in adds the role."""
    database.sync_flag_registry()
    _enable_flag("community_pings_optin")

    role = _FakeRole("community-pings", "800")
    member = _FakeMember("1", roles=[])
    guild = _FakeGuild(roles=[role])
    database.set_setting("community_pings_role_id", "800")

    result = await community.toggle_pings_role(member, guild)
    assert result == "added"
    member.add_roles.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_removes_role():
    """Toggling when opted in removes the role."""
    database.sync_flag_registry()
    _enable_flag("community_pings_optin")

    role = _FakeRole("community-pings", "800")
    member = _FakeMember("1", roles=[role])
    guild = _FakeGuild(roles=[role])
    database.set_setting("community_pings_role_id", "800")

    result = await community.toggle_pings_role(member, guild)
    assert result == "removed"
    member.remove_roles.assert_called_once()


@pytest.mark.asyncio
async def test_toggle_flag_off_returns_disabled():
    """With flag OFF, toggle returns 'disabled'."""
    database.sync_flag_registry()
    _disable_flag("community_pings_optin")

    member = _FakeMember("1")
    guild = _FakeGuild()

    result = await community.toggle_pings_role(member, guild)
    assert result == "disabled"


# ============================================================
#  build_beacon_mention
# ============================================================

def test_build_beacon_mention_flag_on():
    """Returns role mention when flag is ON and role ID is stored."""
    database.sync_flag_registry()
    _enable_flag("community_pings_optin")
    database.set_setting("community_pings_role_id", "800")

    mention = community.build_beacon_mention(MagicMock())
    assert mention == "<@&800> "


def test_build_beacon_mention_flag_off():
    """Returns empty string when flag is OFF."""
    database.sync_flag_registry()
    _disable_flag("community_pings_optin")

    mention = community.build_beacon_mention(MagicMock())
    assert mention == ""


# ============================================================
#  can_knock / record_knock
# ============================================================

def test_can_knock_initially():
    """First knock is always allowed."""
    allowed, remaining = community.can_knock("1")
    assert allowed is True
    assert remaining == 0


def test_can_knock_after_record():
    """Immediately after a knock, next one is blocked."""
    community.record_knock("1")
    allowed, remaining = community.can_knock("1")
    assert allowed is False
    assert remaining > 0


def test_can_knock_after_cooldown():
    """After cooldown expires, can knock again."""
    community._knock_cooldown["1"] = time.time() - 400  # 400s > 300s cooldown
    allowed, remaining = community.can_knock("1")
    assert allowed is True


# ============================================================
#  do_knock
# ============================================================

@pytest.mark.asyncio
async def test_do_knock_sends():
    """Knock sends a message when all conditions met."""
    database.sync_flag_registry()
    _enable_flag("community_pings_optin")
    database.set_setting("community_pings_role_id", "800")

    member = _FakeMember("1", display_name="Ali")
    vc = _FakeVC("voice-lounge", "100", [member])
    guild = _FakeGuild(vcs=[vc])

    fake_live = MagicMock()
    fake_live.send = AsyncMock()

    with patch.object(community, 'get_or_create_community_live', new=AsyncMock(return_value=fake_live)):
        with patch.object(community, '_is_global_quiet_hours', return_value=False):
            result = await community.do_knock(member, guild)

    assert result == "sent"
    fake_live.send.assert_called_once()
    sent_text = fake_live.send.call_args[0][0]
    assert "Ali" in sent_text
    assert "👋" in sent_text


@pytest.mark.asyncio
async def test_do_knock_not_in_majlis():
    """Knock fails if member isn't in a Majlis."""
    database.sync_flag_registry()
    _enable_flag("community_pings_optin")

    member = _FakeMember("1")
    vc = _FakeVC("l0-voice-1", "200", [member])  # not a Majlis
    guild = _FakeGuild(vcs=[vc])

    result = await community.do_knock(member, guild)
    assert result == "not_in_majlis"


@pytest.mark.asyncio
async def test_do_knock_quiet_hours():
    """Knock blocked during quiet hours."""
    database.sync_flag_registry()
    _enable_flag("community_pings_optin")

    member = _FakeMember("1")
    vc = _FakeVC("voice-lounge", "100", [member])
    guild = _FakeGuild(vcs=[vc])

    with patch.object(community, '_is_global_quiet_hours', return_value=True):
        result = await community.do_knock(member, guild)

    assert result == "quiet_hours"


@pytest.mark.asyncio
async def test_do_knock_rate_limited():
    """Knock rate-limited after recent use."""
    database.sync_flag_registry()
    _enable_flag("community_pings_optin")

    community.record_knock("1")
    member = _FakeMember("1")
    vc = _FakeVC("voice-lounge", "100", [member])
    guild = _FakeGuild(vcs=[vc])

    with patch.object(community, '_is_global_quiet_hours', return_value=False):
        result = await community.do_knock(member, guild)

    assert result.startswith("cooldown:")
