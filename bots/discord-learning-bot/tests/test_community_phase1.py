"""Community Lounge ("Majlis") Phase 1 — company-aware task #7 credit tests.

Covers:
- verify_community: flag OFF = identical to today (10 min any voice required)
- verify_community: flag ON + together-time >= threshold = voice half done
- verify_community: #general-chat still required even with together-time
- verify_community: solo student still needs 10 min even with flag ON
- together-time tracking: on_together_check accrues when 2+ in Majlis
- together-time tracking: persists on leave, clears session
- together-time tracking: no accrual when alone in Majlis
- get_together_minutes_today: combines persisted + ongoing
- reset_daily_together: clears sessions
- Checklist copy: shows together path when closer, classic path when no together-time
- bidi-safe copy check
"""
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src import database, verification, community


# ============================================================
#  HELPERS
# ============================================================

def _enable_flag(flag_name: str):
    """Enable a flag for everyone (empty allowlist)."""
    database.set_feature_flag(flag_name, True, "", "test")


def _disable_flag(flag_name: str):
    """Disable a flag."""
    database.set_feature_flag(flag_name, False, "", "test")


class _FakeMember:
    def __init__(self, uid: str, bot: bool = False):
        self.id = int(uid)
        self.bot = bot


class _FakeVC:
    def __init__(self, name: str, channel_id: str, members: list):
        self.name = name
        self.id = int(channel_id)
        self.members = members


class _FakeGuild:
    def __init__(self, voice_channels: list):
        self.voice_channels = voice_channels


class _FakeDiscordMember:
    """For verify_community (needs .id as int)."""
    def __init__(self, uid: str):
        self.id = int(uid)


def _make_guild_with_general_chat(has_message_from: str = None):
    """Create a mock guild + #general-chat channel for verify_community."""
    guild = MagicMock()
    channel = MagicMock()
    channel.name = "general-chat"
    guild.text_channels = [channel]

    if has_message_from:
        msg = MagicMock()
        msg.author.id = int(has_message_from)

        async def _history(**kwargs):
            yield msg
        channel.history = _history
    else:
        async def _empty_history(**kwargs):
            return
            yield  # make it an async generator
        channel.history = _empty_history

    return guild


# ============================================================
#  TOGETHER-TIME TRACKING (on_together_check)
# ============================================================

def test_on_together_check_starts_session_with_company():
    """When 2+ non-bot members are in a Majlis, both get a together_start."""
    verification._together_sessions.clear()
    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1"), _FakeMember("2")])
    guild = _FakeGuild([vc])

    verification.on_together_check(guild)

    assert verification._together_sessions["1"]["together_start"] is not None
    assert verification._together_sessions["2"]["together_start"] is not None


def test_on_together_check_no_session_when_alone():
    """A solo member in a Majlis does NOT get a together session."""
    verification._together_sessions.clear()
    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1")])
    guild = _FakeGuild([vc])

    verification.on_together_check(guild)

    session = verification._together_sessions.get("1", {})
    assert not session or not session.get("together_start")


def test_on_together_check_persists_on_leave():
    """When a member loses company, their elapsed time is persisted."""
    verification._together_sessions.clear()
    database.register_member("1", "Alice")

    # First: two people together
    vc = _FakeVC("voice-lounge", "100", [_FakeMember("1"), _FakeMember("2")])
    guild = _FakeGuild([vc])
    verification.on_together_check(guild)

    # Simulate 3 minutes passing
    verification._together_sessions["1"]["together_start"] = (
        datetime.datetime.now() - datetime.timedelta(minutes=3)
    )

    # Now member 2 leaves → member 1 is alone
    vc_alone = _FakeVC("voice-lounge", "100", [_FakeMember("1")])
    guild_alone = _FakeGuild([vc_alone])
    verification.on_together_check(guild_alone)

    # Together session cleared
    assert verification._together_sessions["1"]["together_start"] is None
    # Minutes persisted to DB
    stored = database.get_together_minutes("1")
    assert stored >= 2.9  # ~3 min (allow small float variance)


def test_on_together_check_ignores_non_majlis():
    """Level practice rooms don't trigger together-time."""
    verification._together_sessions.clear()
    vc = _FakeVC("l0-voice-1", "200", [_FakeMember("1"), _FakeMember("2")])
    guild = _FakeGuild([vc])

    verification.on_together_check(guild)

    assert "1" not in verification._together_sessions or \
           not verification._together_sessions.get("1", {}).get("together_start")


# ============================================================
#  get_together_minutes_today
# ============================================================

def test_get_together_minutes_today_persisted_only():
    """Returns persisted minutes when no active session."""
    verification._together_sessions.clear()
    database.register_member("10", "Bob")
    database.add_together_minutes("10", 4.0)

    assert verification.get_together_minutes_today("10") == 4.0


def test_get_together_minutes_today_with_ongoing():
    """Includes ongoing session time."""
    verification._together_sessions.clear()
    database.register_member("11", "Carol")
    database.add_together_minutes("11", 2.0)

    # Simulate an ongoing session of ~1 min
    verification._together_sessions["11"] = {
        "together_start": datetime.datetime.now() - datetime.timedelta(minutes=1)
    }
    total = verification.get_together_minutes_today("11")
    assert total >= 2.9  # 2.0 persisted + ~1.0 ongoing


# ============================================================
#  reset_daily_together
# ============================================================

def test_reset_daily_together_clears_sessions():
    verification._together_sessions["x"] = {"together_start": datetime.datetime.now()}
    verification.reset_daily_together()
    assert verification._together_sessions == {}


# ============================================================
#  verify_community — FLAG OFF (backwards-compatible)
# ============================================================

@pytest.mark.asyncio
async def test_verify_community_flag_off_10min_voice_passes():
    """Flag OFF: 10 min voice + chat message = pass (unchanged behavior)."""
    database.sync_flag_registry()
    _disable_flag("community_together_credit")
    database.register_member("20", "Dave")
    database.add_voice_minutes("20", 12.0)
    verification._voice_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from="20")
    member = _FakeDiscordMember("20")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is True
    assert msg == ""


@pytest.mark.asyncio
async def test_verify_community_flag_off_under_10min_fails():
    """Flag OFF: under 10 min voice = fail (even if together-time exists)."""
    database.sync_flag_registry()
    _disable_flag("community_together_credit")
    database.register_member("21", "Eve")
    database.add_voice_minutes("21", 4.0)
    database.add_together_minutes("21", 8.0)  # plenty of together-time
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from="21")
    member = _FakeDiscordMember("21")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is False
    assert "10" in msg  # shows the 10-min requirement


# ============================================================
#  verify_community — FLAG ON (company-aware)
# ============================================================

@pytest.mark.asyncio
async def test_verify_community_flag_on_together_path_passes():
    """Flag ON: 5+ min together-time + chat = pass (fast path)."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    database.register_member("30", "Frank")
    database.add_voice_minutes("30", 3.0)  # under 10 — classic would fail
    database.add_together_minutes("30", 6.0)  # over threshold
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from="30")
    member = _FakeDiscordMember("30")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is True
    assert msg == ""


@pytest.mark.asyncio
async def test_verify_community_flag_on_still_needs_chat():
    """Flag ON + together-time met but NO chat message = fail."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    database.register_member("31", "Grace")
    database.add_together_minutes("31", 10.0)
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from=None)  # no message
    member = _FakeDiscordMember("31")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is False
    assert "general-chat" in msg


@pytest.mark.asyncio
async def test_verify_community_flag_on_solo_still_needs_10():
    """Flag ON but no together-time: solo student still needs 10 min."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    database.register_member("32", "Hank")
    database.add_voice_minutes("32", 7.0)  # under 10
    # No together-minutes at all
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from="32")
    member = _FakeDiscordMember("32")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is False
    assert "10" in msg


@pytest.mark.asyncio
async def test_verify_community_flag_on_classic_path_still_works():
    """Flag ON: the classic 10-min any-voice path still works (OR, not AND)."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    database.register_member("33", "Iris")
    database.add_voice_minutes("33", 15.0)  # over 10
    # No together-minutes
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from="33")
    member = _FakeDiscordMember("33")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is True
    assert msg == ""


# ============================================================
#  CHECKLIST COPY
# ============================================================

@pytest.mark.asyncio
async def test_checklist_shows_together_path_when_closer():
    """When student has some together-time, checklist shows Majlis path."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    database.register_member("40", "Jack")
    database.add_voice_minutes("40", 2.0)
    database.add_together_minutes("40", 3.0)  # has SOME, but not enough
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from="40")
    member = _FakeDiscordMember("40")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is False
    assert "المجلس" in msg  # shows Majlis path
    assert "3/5" in msg or "3/" in msg  # progress toward threshold


@pytest.mark.asyncio
async def test_checklist_shows_classic_path_when_no_together():
    """When no together-time at all, checklist shows classic 10-min path."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    database.register_member("41", "Kate")
    database.add_voice_minutes("41", 4.0)
    # No together-minutes
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from="41")
    member = _FakeDiscordMember("41")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is False
    assert "10 دقائق" in msg  # classic path
    assert "المجلس" not in msg


# ============================================================
#  BIDI SAFETY
# ============================================================

@pytest.mark.asyncio
async def test_checklist_bidi_safe():
    """The checklist copy doesn't trip the bidi checker's worst-case
    (Arabic sandwiched between multi-word LTR runs). Verify the Arabic
    lines are Arabic-dominant."""
    database.sync_flag_registry()
    _enable_flag("community_together_credit")
    database.register_member("50", "Liam")
    database.add_together_minutes("50", 2.0)
    verification._voice_sessions.clear()
    verification._together_sessions.clear()

    guild = _make_guild_with_general_chat(has_message_from="50")
    member = _FakeDiscordMember("50")

    ok, msg = await verification.verify_community(member, guild)
    assert ok is False
    # The Arabic lines should start with Arabic text (after the emoji)
    lines = msg.split("\n")
    # First line is Arabic-first
    assert lines[0].startswith("مهمة")
