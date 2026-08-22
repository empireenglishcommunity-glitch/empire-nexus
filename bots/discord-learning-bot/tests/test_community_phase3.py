"""Community Lounge ("Majlis") Phase 3 — dynamic pods tests.

Covers:
- next_majlis_number: returns correct number based on registry
- is_majlis_hub: identifies the hub channel
- handle_hub_join: spawns a room, moves member, registers (mocked Discord)
- handle_hub_join: flag OFF does nothing
- reap_empty_majlis_rooms: reaps after grace, never reaps anchor
- reap_empty_majlis_rooms: doesn't reap within grace period
- reap_empty_majlis_rooms: cleans up deleted channels from registry
- find_best_lounge: returns lively-not-full lounge
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
    """Reset state before each test."""
    community.reset_beacons()
    community.reset_empty_since()
    database.set_setting("majlis_rooms", "[]")


class _FakeMember:
    def __init__(self, uid, bot=False):
        self.id = int(uid)
        self.bot = bot
        self.move_to = AsyncMock()


class _FakeVC:
    def __init__(self, name, cid, members=None, user_limit=0):
        self.name = name
        self.id = int(cid)
        self.members = members or []
        self.user_limit = user_limit
        self.category = None
        self.delete = AsyncMock()
        self.edit = AsyncMock()


class _FakeGuild:
    def __init__(self, vcs=None, text_channels=None):
        self.voice_channels = vcs or []
        self.text_channels = text_channels or []
        self.create_voice_channel = AsyncMock()
        self.create_text_channel = AsyncMock()

    def get_channel(self, cid):
        for ch in self.voice_channels + self.text_channels:
            if ch.id == cid:
                return ch
        return None


# ============================================================
#  next_majlis_number
# ============================================================

def test_next_majlis_number_empty_registry():
    """With no dynamic rooms, next number is 2 (anchor is conceptually 1)."""
    assert community.next_majlis_number() == 2


def test_next_majlis_number_with_existing():
    """With 2 registered rooms, next is 4."""
    community.register_majlis_room("100")
    community.register_majlis_room("200")
    assert community.next_majlis_number() == 4


# ============================================================
#  is_majlis_hub
# ============================================================

def test_is_majlis_hub_true():
    ch = _FakeVC(community.MAJLIS_HUB_NAME, "999")
    assert community.is_majlis_hub(ch) is True


def test_is_majlis_hub_false_for_lounge():
    ch = _FakeVC("voice-lounge", "100")
    assert community.is_majlis_hub(ch) is False


# ============================================================
#  handle_hub_join
# ============================================================

@pytest.mark.asyncio
async def test_handle_hub_join_spawns_and_moves():
    """Hub join spawns a capped room and moves the member."""
    database.sync_flag_registry()
    _enable_flag("community_dynamic_rooms")

    member = _FakeMember("1")
    anchor = _FakeVC("voice-lounge", "100")
    anchor.category = MagicMock()
    new_room = _FakeVC("Majlis 2", "500", user_limit=6)
    new_room.id = 500

    guild = _FakeGuild([anchor])
    guild.create_voice_channel = AsyncMock(return_value=new_room)

    with patch("src.community.MAJLIS_ANCHOR_NAME", "voice-lounge"):
        await community.handle_hub_join(member, guild)

    # Room was created
    guild.create_voice_channel.assert_called_once()
    call_kwargs = guild.create_voice_channel.call_args
    assert call_kwargs[0][0] == "Majlis 2"  # name
    assert call_kwargs[1]["user_limit"] == 6

    # Member was moved
    member.move_to.assert_called_once_with(new_room)

    # Room was registered
    assert "500" in community.get_majlis_room_ids()


@pytest.mark.asyncio
async def test_handle_hub_join_flag_off_does_nothing():
    """With the flag OFF, hub join does nothing."""
    database.sync_flag_registry()
    _disable_flag("community_dynamic_rooms")

    member = _FakeMember("1")
    guild = _FakeGuild()

    await community.handle_hub_join(member, guild)

    guild.create_voice_channel.assert_not_called()


# ============================================================
#  reap_empty_majlis_rooms
# ============================================================

@pytest.mark.asyncio
async def test_reap_after_grace():
    """Rooms empty past the grace period are deleted and unregistered."""
    database.sync_flag_registry()
    _enable_flag("community_dynamic_rooms")

    empty_room = _FakeVC("Majlis 2", "500", members=[])
    community.register_majlis_room("500")
    # Fake: empty since 5 minutes ago (grace default is 3)
    community._empty_since["500"] = time.time() - 300

    guild = _FakeGuild([empty_room])

    await community.reap_empty_majlis_rooms(guild)

    empty_room.delete.assert_called_once()
    assert "500" not in community.get_majlis_room_ids()


@pytest.mark.asyncio
async def test_reap_within_grace_not_deleted():
    """Rooms empty within the grace period are NOT deleted."""
    database.sync_flag_registry()
    _enable_flag("community_dynamic_rooms")

    empty_room = _FakeVC("Majlis 2", "500", members=[])
    community.register_majlis_room("500")
    # Fake: empty since 1 minute ago (grace is 3)
    community._empty_since["500"] = time.time() - 60

    guild = _FakeGuild([empty_room])

    await community.reap_empty_majlis_rooms(guild)

    empty_room.delete.assert_not_called()
    assert "500" in community.get_majlis_room_ids()


@pytest.mark.asyncio
async def test_reap_never_deletes_anchor():
    """The anchor voice-lounge is NEVER reaped (it's not in the registry)."""
    database.sync_flag_registry()
    _enable_flag("community_dynamic_rooms")

    anchor = _FakeVC("voice-lounge", "100", members=[])
    guild = _FakeGuild([anchor])

    # Anchor is NOT in majlis_rooms (by design — it's identified by name)
    await community.reap_empty_majlis_rooms(guild)

    anchor.delete.assert_not_called()


@pytest.mark.asyncio
async def test_reap_cleans_registry_for_deleted_channels():
    """If a channel was manually deleted, the registry is cleaned up."""
    database.sync_flag_registry()
    _enable_flag("community_dynamic_rooms")

    # Register a room that doesn't exist in the guild anymore
    community.register_majlis_room("999")
    guild = _FakeGuild([])  # no voice channels at all

    await community.reap_empty_majlis_rooms(guild)

    # Registry cleaned
    assert "999" not in community.get_majlis_room_ids()


@pytest.mark.asyncio
async def test_reap_occupied_room_not_touched():
    """A room with people in it is never reaped."""
    database.sync_flag_registry()
    _enable_flag("community_dynamic_rooms")

    occupied = _FakeVC("Majlis 2", "500", members=[_FakeMember("1")])
    community.register_majlis_room("500")
    community._empty_since["500"] = time.time() - 9999  # would be past grace

    guild = _FakeGuild([occupied])

    await community.reap_empty_majlis_rooms(guild)

    occupied.delete.assert_not_called()
    # empty_since timer should be cleared (room has people now)
    assert "500" not in community._empty_since


# ============================================================
#  find_best_lounge
# ============================================================

def test_find_best_lounge_picks_lively_not_full():
    """find_best_lounge returns the lounge with the most people under capacity."""
    vc1 = _FakeVC("voice-lounge", "100", [_FakeMember("1"), _FakeMember("2")])
    vc2 = _FakeVC("Majlis 2", "200", [_FakeMember("3"), _FakeMember("4"), _FakeMember("5")])
    community.register_majlis_room("200")

    guild = _FakeGuild([vc1, vc2])

    best = community.find_best_lounge(guild)
    assert best == "200"  # 3 people (more lively, still under cap 6)


def test_find_best_lounge_none_when_all_full():
    """Returns None when all lounges are at capacity."""
    members = [_FakeMember(str(i)) for i in range(6)]
    vc1 = _FakeVC("voice-lounge", "100", members)
    guild = _FakeGuild([vc1])

    best = community.find_best_lounge(guild)
    assert best is None


def test_find_best_lounge_none_when_all_empty():
    """Returns None when all lounges are empty."""
    vc1 = _FakeVC("voice-lounge", "100", [])
    guild = _FakeGuild([vc1])

    best = community.find_best_lounge(guild)
    assert best is None
