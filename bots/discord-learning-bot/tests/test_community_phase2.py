"""Community Lounge ("Majlis") Phase 2 — presence beacon tests.

Covers:
- should_beacon: fires in band [1, max_occupancy], not when healthy, not when empty
- should_beacon: dedup (cooldown per lounge)
- should_beacon: quiet hours respected
- record_beacon / get_active_beacon / clear_beacon state management
- get_expired_beacons: TTL expiry
- build_beacon_text: correct format for 1 person and multiple people
- reset_beacons: clears all state
- maybe_post_beacon: flag-gated, posts when conditions met
- maybe_clear_beacon: deletes message when lounge empties
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
    """Reset beacon state before each test."""
    community.reset_beacons()


# ============================================================
#  should_beacon — BAND LOGIC
# ============================================================

def test_should_beacon_fires_at_occupancy_1():
    """Beacon should fire when 1 person is waiting (lonely)."""
    assert community.should_beacon("100", occupancy=1) is True


def test_should_beacon_fires_at_max_occupancy():
    """Beacon fires at the max_occupancy boundary (default 4)."""
    assert community.should_beacon("100", occupancy=4) is True


def test_should_beacon_not_when_healthy():
    """Beacon does NOT fire when occupancy exceeds max (room is lively enough)."""
    assert community.should_beacon("100", occupancy=5) is False


def test_should_beacon_not_when_empty():
    """Beacon does NOT fire when the lounge is empty."""
    assert community.should_beacon("100", occupancy=0) is False


# ============================================================
#  should_beacon — DEDUP / COOLDOWN
# ============================================================

def test_should_beacon_deduped_within_cooldown():
    """A recent beacon for this lounge blocks a new one (cooldown)."""
    community.record_beacon("100", message_id=999, text_channel_id=200)
    assert community.should_beacon("100", occupancy=2) is False


def test_should_beacon_fires_after_cooldown():
    """Once the cooldown expires, a new beacon can fire."""
    community.record_beacon("100", message_id=999, text_channel_id=200)
    # Fake the posted_at to be well past the cooldown (41 min ago)
    community._active_beacons["100"]["posted_at"] = time.time() - (41 * 60)
    assert community.should_beacon("100", occupancy=2) is True


def test_should_beacon_different_lounge_not_blocked():
    """A beacon for lounge A doesn't block lounge B."""
    community.record_beacon("100", message_id=999, text_channel_id=200)
    assert community.should_beacon("200", occupancy=2) is True


# ============================================================
#  should_beacon — QUIET HOURS
# ============================================================

def test_should_beacon_blocked_in_quiet_hours():
    """Beacon does NOT fire during quiet hours."""
    with patch.object(community, '_is_global_quiet_hours', return_value=True):
        assert community.should_beacon("100", occupancy=2) is False


def test_should_beacon_fires_outside_quiet_hours():
    """Beacon fires when NOT in quiet hours."""
    with patch.object(community, '_is_global_quiet_hours', return_value=False):
        assert community.should_beacon("100", occupancy=2) is True


# ============================================================
#  STATE MANAGEMENT
# ============================================================

def test_record_and_get_beacon():
    """record_beacon stores state retrievable by get_active_beacon."""
    community.record_beacon("100", message_id=555, text_channel_id=200)
    state = community.get_active_beacon("100")
    assert state is not None
    assert state["message_id"] == 555
    assert state["channel_id"] == 200
    assert state["posted_at"] > 0


def test_clear_beacon_returns_and_removes():
    """clear_beacon returns the state and removes it."""
    community.record_beacon("100", message_id=555, text_channel_id=200)
    state = community.clear_beacon("100")
    assert state["message_id"] == 555
    assert community.get_active_beacon("100") is None


def test_clear_beacon_returns_none_if_not_present():
    """clear_beacon returns None for an unknown lounge."""
    assert community.clear_beacon("999") is None


def test_reset_beacons_clears_all():
    """reset_beacons removes all beacon state."""
    community.record_beacon("100", 1, 200)
    community.record_beacon("200", 2, 200)
    community.reset_beacons()
    assert community.get_active_beacon("100") is None
    assert community.get_active_beacon("200") is None


# ============================================================
#  EXPIRY
# ============================================================

def test_get_expired_beacons_empty_when_fresh():
    """Fresh beacons are not expired."""
    community.record_beacon("100", message_id=1, text_channel_id=200)
    assert community.get_expired_beacons() == []


def test_get_expired_beacons_returns_old():
    """Beacons past their TTL are returned as expired."""
    community.record_beacon("100", message_id=1, text_channel_id=200)
    # Fake to 21 minutes ago (default TTL is 20)
    community._active_beacons["100"]["posted_at"] = time.time() - (21 * 60)
    expired = community.get_expired_beacons()
    assert len(expired) == 1
    assert expired[0]["lounge_id"] == "100"
    assert expired[0]["message_id"] == 1


# ============================================================
#  build_beacon_text
# ============================================================

def test_build_beacon_text_one_person():
    """Text for one person uses singular Arabic phrasing."""
    text = community.build_beacon_text(["123"], "voice-lounge", "100")
    assert "في حد" in text  # "someone's in"
    assert "<#100>" in text  # jump link
    assert "voice-lounge" in text


def test_build_beacon_text_multiple():
    """Text for multiple people shows the count."""
    text = community.build_beacon_text(["1", "2", "3"], "voice-lounge", "100")
    assert "3" in text
    assert "<#100>" in text


# ============================================================
#  maybe_post_beacon (async, mocked Discord)
# ============================================================

class _FakeMember:
    def __init__(self, uid, bot=False):
        self.id = int(uid)
        self.bot = bot


class _FakeVC:
    def __init__(self, name, cid, members):
        self.name = name
        self.id = int(cid)
        self.members = members


class _FakeGuild:
    def __init__(self, vcs, text_channels=None):
        self.voice_channels = vcs
        self.text_channels = text_channels or []

    def get_channel(self, cid):
        for ch in self.text_channels + self.voice_channels:
            if ch.id == cid:
                return ch
        return None


@pytest.mark.asyncio
async def test_maybe_post_beacon_flag_off_does_nothing():
    """With the flag OFF, nothing is posted."""
    database.sync_flag_registry()
    _disable_flag("community_lounge_beacon")

    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1")])
    guild = _FakeGuild([vc])

    # Should not raise or post
    await community.maybe_post_beacon(guild, vc)
    assert community.get_active_beacon("100") is None


@pytest.mark.asyncio
async def test_maybe_post_beacon_posts_when_conditions_met():
    """With flag ON and conditions met, posts and records."""
    database.sync_flag_registry()
    _enable_flag("community_lounge_beacon")

    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1"), _FakeMember("2")])
    guild = _FakeGuild([vc])

    # Mock get_or_create_community_live to return a fake channel
    fake_live = MagicMock()
    fake_msg = MagicMock()
    fake_msg.id = 777
    fake_live.send = AsyncMock(return_value=fake_msg)
    fake_live.id = 300

    with patch.object(community, 'get_or_create_community_live', new=AsyncMock(return_value=fake_live)):
        with patch.object(community, '_is_global_quiet_hours', return_value=False):
            await community.maybe_post_beacon(guild, vc)

    # Beacon was recorded
    state = community.get_active_beacon("100")
    assert state is not None
    assert state["message_id"] == 777
    # Message was sent
    fake_live.send.assert_called_once()


@pytest.mark.asyncio
async def test_maybe_post_beacon_skips_when_healthy():
    """When occupancy exceeds max, no beacon is posted."""
    database.sync_flag_registry()
    _enable_flag("community_lounge_beacon")

    members = [_FakeMember(str(i)) for i in range(6)]  # 6 > default max 4
    vc = _FakeVC("voice-lounge", "100", members)
    guild = _FakeGuild([vc])

    fake_live = MagicMock()
    fake_live.send = AsyncMock()

    with patch.object(community, 'get_or_create_community_live', new=AsyncMock(return_value=fake_live)):
        with patch.object(community, '_is_global_quiet_hours', return_value=False):
            await community.maybe_post_beacon(guild, vc)

    fake_live.send.assert_not_called()
    assert community.get_active_beacon("100") is None


# ============================================================
#  maybe_clear_beacon (async, mocked Discord)
# ============================================================

@pytest.mark.asyncio
async def test_maybe_clear_beacon_deletes_on_empty():
    """When a lounge empties, its beacon message is deleted."""
    database.sync_flag_registry()
    _enable_flag("community_lounge_beacon")

    # Record an active beacon
    community.record_beacon("100", message_id=888, text_channel_id=300)

    # Lounge is now empty
    vc = _FakeVC("voice-lounge", "100", [])
    fake_msg = AsyncMock()
    fake_ch = MagicMock()
    fake_ch.id = 300
    fake_ch.fetch_message = AsyncMock(return_value=fake_msg)
    guild = _FakeGuild([vc], text_channels=[fake_ch])

    await community.maybe_clear_beacon(guild, vc)

    # Beacon cleared from state
    assert community.get_active_beacon("100") is None
    # Message was deleted
    fake_msg.delete.assert_called_once()


@pytest.mark.asyncio
async def test_maybe_clear_beacon_no_op_when_not_empty():
    """When there are still people in the lounge, beacon is NOT cleared."""
    database.sync_flag_registry()
    _enable_flag("community_lounge_beacon")

    community.record_beacon("100", message_id=888, text_channel_id=300)

    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1")])
    guild = _FakeGuild([vc])

    await community.maybe_clear_beacon(guild, vc)

    # Beacon still active (not cleared — someone's still there)
    assert community.get_active_beacon("100") is not None
