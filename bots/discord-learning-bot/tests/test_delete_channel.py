"""Tests for the safe /deletechannel command.

Locks in the guardrails: it refuses load-bearing channels (rules/welcome/
announcements, the command channels, admin channels, level zones), requires an
explicit confirm, and only then deletes.
"""
from unittest.mock import AsyncMock

import pytest

from src import bot as botmod, role_gate, config


class FakeChannel:
    def __init__(self, name, cid=0, category=None):
        self.name = name
        self.id = cid
        self.category = category
        self.deleted = False

    async def delete(self, reason=None):
        self.deleted = True


# ── protected_channel_reason ─────────────────────────────────────────────────
def test_protected_channels_are_flagged():
    for name in ("rules", "welcome", "announcements", "a1-daily-tasks",
                 "c2-voice-1", "admin-chat", "bot-logs", "ghost-commands"):
        assert role_gate.protected_channel_reason(FakeChannel(name)) is not None, name


def test_command_channels_protected_by_id():
    if config.ADMIN_COMMANDS_CHANNEL_ID:
        ch = FakeChannel("some-name", cid=config.ADMIN_COMMANDS_CHANNEL_ID)
        assert role_gate.protected_channel_reason(ch) is not None


def test_ordinary_channel_is_not_protected():
    assert role_gate.protected_channel_reason(FakeChannel("general-chat")) is None
    assert role_gate.protected_channel_reason(FakeChannel("random-old-channel")) is None


# ── _do_delete_channel behavior ──────────────────────────────────────────────
@pytest.mark.asyncio
async def test_refuses_protected_channel_even_with_confirm():
    ch = FakeChannel("rules")
    msg = await botmod._do_delete_channel(guild=object(), channel=ch, confirm=True)
    assert "Refusing" in msg or "🔒" in msg
    assert ch.deleted is False


@pytest.mark.asyncio
async def test_dry_run_when_not_confirmed():
    ch = FakeChannel("old-unused-channel")
    msg = await botmod._do_delete_channel(guild=object(), channel=ch, confirm=False)
    assert "confirm" in msg.lower()
    assert ch.deleted is False       # nothing deleted without confirm


@pytest.mark.asyncio
async def test_deletes_non_protected_when_confirmed():
    ch = FakeChannel("old-unused-channel")
    msg = await botmod._do_delete_channel(guild=object(), channel=ch, confirm=True)
    assert ch.deleted is True
    assert "Deleted" in msg or "🗑️" in msg


@pytest.mark.asyncio
async def test_missing_channel_is_handled():
    msg = await botmod._do_delete_channel(guild=object(), channel=None, confirm=True)
    assert "not found" in msg.lower()


# ── registration ─────────────────────────────────────────────────────────────
def test_slash_and_prefix_registered_and_admin_gated():
    assert botmod.bot.get_command("deletechannel") is not None
    assert botmod.bot.tree.get_command("deletechannel") is not None
    # admin-gated -> appears in the /admin bridge's admin-only enumeration
    assert "deletechannel" in botmod._admin_command_names()
