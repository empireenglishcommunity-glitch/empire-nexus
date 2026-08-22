"""Community Lounge ("Majlis") Phase 6 — reward togetherness tests.

Covers:
- check_together_reward_eligible: flag off = not eligible
- check_together_reward_eligible: bonus 0 = not eligible
- check_together_reward_eligible: eligible when flag on + bonus > 0 + not yet rewarded
- check_together_reward_eligible: not eligible if already rewarded today
- grant_together_reward: grants points and records dedup
- grant_together_reward: returns 0 if not eligible
- verify_community grants reward on together-path completion
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src import database, community, verification


# ============================================================
#  HELPERS
# ============================================================

def _enable_flag(flag_name: str):
    database.set_feature_flag(flag_name, True, "", "test")


def _disable_flag(flag_name: str):
    database.set_feature_flag(flag_name, False, "", "test")


def setup_function():
    community.reset_knock_cooldown()
    verification._together_sessions.clear()


# ============================================================
#  check_together_reward_eligible
# ============================================================

def test_eligible_flag_off():
    """Not eligible when flag is OFF."""
    database.sync_flag_registry()
    _disable_flag("community_together_reward")
    assert community.check_together_reward_eligible("1") is False


def test_eligible_bonus_zero():
    """Not eligible when bonus points = 0."""
    database.sync_flag_registry()
    _enable_flag("community_together_reward")
    database.set_community_config("community_together_reward_points", 0)
    assert community.check_together_reward_eligible("1") is False


def test_eligible_all_conditions_met():
    """Eligible when flag ON, bonus > 0, not yet rewarded today."""
    database.sync_flag_registry()
    _enable_flag("community_together_reward")
    database.set_community_config("community_together_reward_points", 10)
    assert community.check_together_reward_eligible("1") is True


def test_not_eligible_already_rewarded():
    """Not eligible if already rewarded today."""
    database.sync_flag_registry()
    _enable_flag("community_together_reward")
    database.set_community_config("community_together_reward_points", 10)

    # Grant once
    database.register_member("2", "Bob")
    community.grant_together_reward("2")

    # Should not be eligible again
    assert community.check_together_reward_eligible("2") is False


# ============================================================
#  grant_together_reward
# ============================================================

def test_grant_together_reward_gives_points():
    """Grants the configured bonus points."""
    database.sync_flag_registry()
    _enable_flag("community_together_reward")
    database.set_community_config("community_together_reward_points", 15)
    database.register_member("3", "Carol")

    points = community.grant_together_reward("3")
    assert points == 15

    # Verify points were actually added
    member = database.get_member("3")
    assert member["total_points"] == 15


def test_grant_together_reward_zero_when_not_eligible():
    """Returns 0 when not eligible (flag off)."""
    database.sync_flag_registry()
    _disable_flag("community_together_reward")
    database.register_member("4", "Dave")

    points = community.grant_together_reward("4")
    assert points == 0


def test_grant_together_reward_once_per_day():
    """Second grant on the same day returns 0."""
    database.sync_flag_registry()
    _enable_flag("community_together_reward")
    database.set_community_config("community_together_reward_points", 10)
    database.register_member("5", "Eve")

    first = community.grant_together_reward("5")
    assert first == 10

    second = community.grant_together_reward("5")
    assert second == 0


# ============================================================
#  verify_community triggers reward on together-path
# ============================================================

class _FakeDiscordMember:
    def __init__(self, uid):
        self.id = int(uid)


def _make_guild_with_chat(uid):
    guild = MagicMock()
    channel = MagicMock()
    channel.name = "general-chat"
    guild.text_channels = [channel]

    msg = MagicMock()
    msg.author.id = int(uid)

    async def _history(**kwargs):
        yield msg
    channel.history = _history
    return guild


@pytest.mark.asyncio
async def test_verify_community_triggers_reward_on_together():
    """When task #7 completes via together path, reward is granted."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    _enable_flag("community_together_reward")
    database.set_community_config("community_together_reward_points", 20)
    database.register_member("10", "Frank")
    database.add_together_minutes("10", 6.0)  # over threshold
    verification._voice_sessions.clear()

    guild = _make_guild_with_chat("10")
    member = _FakeDiscordMember("10")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is True

    # Reward was granted
    m = database.get_member("10")
    assert m["total_points"] == 20


@pytest.mark.asyncio
async def test_verify_community_no_reward_on_classic_path():
    """When task #7 completes via classic 10-min path, no reward."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    _enable_flag("community_together_reward")
    database.set_community_config("community_together_reward_points", 20)
    database.register_member("11", "Grace")
    database.add_voice_minutes("11", 12.0)  # classic path
    # No together-minutes
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_chat("11")
    member = _FakeDiscordMember("11")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is True

    # No reward (together_ok was False)
    m = database.get_member("11")
    assert m["total_points"] == 0
