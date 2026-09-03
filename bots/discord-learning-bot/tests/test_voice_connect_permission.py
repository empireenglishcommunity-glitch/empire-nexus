"""Students must be able to JOIN community/level VOICE channels, not just see them.

Bug: setupgate (and the community helper) granted the student/level role
view_channel + send_messages. For a VOICE channel, send_messages is meaningless
and the gate to actually JOIN is `connect` (+`speak`). So students could SEE the
community voice lounge / their level voice channel but got 'no access' on join.

Fix: role_gate._access_kwargs(channel, allow=...) returns view+send for text and
view+connect+speak for voice, used everywhere a student is granted/denied a
channel. These tests lock that in.
"""
import discord
import pytest

from src import role_gate, community


class FakeText(discord.TextChannel):
    def __init__(self, name="general-chat"):
        self.name = name


class FakeVoice(discord.VoiceChannel):
    def __init__(self, name="voice-lounge"):
        self.name = name


# ── _access_kwargs ───────────────────────────────────────────────────────────
def test_text_channel_grant_is_view_and_send():
    assert role_gate._access_kwargs(FakeText(), allow=True) == {
        "view_channel": True, "send_messages": True}


def test_voice_channel_grant_includes_connect_and_speak():
    kw = role_gate._access_kwargs(FakeVoice(), allow=True)
    assert kw["view_channel"] is True
    assert kw["connect"] is True          # <-- JOIN permission
    assert kw["speak"] is True
    # use_voice_activation lets a student talk hands-free; without it Discord
    # forces "Push to Talk Required".
    assert kw["use_voice_activation"] is True
    assert "send_messages" not in kw


def test_voice_channel_deny_blocks_connect():
    kw = role_gate._access_kwargs(FakeVoice(), allow=False)
    assert kw == {"view_channel": False, "connect": False, "speak": False,
                  "use_voice_activation": False}


def test_is_voice_detection():
    assert role_gate._is_voice(FakeVoice()) is True
    assert role_gate._is_voice(FakeText()) is False


# ── community._grant_student_access uses connect for voice ────────────────────
class RecordingChannel:
    """A channel double that records the kwargs set_permissions was called with,
    and reports as text or voice via isinstance by subclassing the discord type."""
    pass


class RecordingVoice(discord.VoiceChannel):
    def __init__(self):
        self.name = "voice-lounge"
        self.calls = {}

    async def set_permissions(self, target, reason=None, **kwargs):
        self.calls[getattr(target, "name", "?")] = kwargs


class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeGuild:
    def __init__(self):
        self.default_role = FakeRole("@everyone")
        self._student = FakeRole(role_gate.STUDENT_ROLE_NAME)


@pytest.mark.asyncio
async def test_community_voice_grant_includes_connect(monkeypatch):
    guild = FakeGuild()
    ch = RecordingVoice()

    async def fake_get_or_create(g):
        return guild._student
    monkeypatch.setattr(role_gate, "get_or_create_student_role", fake_get_or_create)

    await community._grant_student_access(guild, ch)

    student = ch.calls[role_gate.STUDENT_ROLE_NAME]
    assert student["view_channel"] is True
    assert student["connect"] is True     # students can JOIN the voice lounge
    assert student["speak"] is True
