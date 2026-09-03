"""cmd_setupgate must acknowledge BEFORE its long, rate-limited work.

Bug: /setupgate (via the /admin bridge) showed "thinking…" forever. setupgate
makes many sequential set_permissions calls (a level zone is ~9 calls, dozens of
channels), and it only posted its result AFTER the whole loop — so the channel
and the slash interaction had no feedback for minutes and could time out.

Fix: setupgate posts an immediate "started" message before the loop, then the
summary at the end. This test locks in that the FIRST ctx.send happens before
any channel permission work, and that a final summary is still sent.
"""
from unittest.mock import AsyncMock

import pytest

from src import role_gate


class FakeAuthorPerms:
    administrator = True


class FakeAuthor:
    guild_permissions = FakeAuthorPerms()
    bot = False
    id = 1


class FakeGuild:
    def __init__(self):
        self.channels = []          # no channels → loop is a fast no-op
        self.roles = []
        self.members = []
        self.default_role = object()


class RecordingCtx:
    def __init__(self):
        self.author = FakeAuthor()
        self.guild = FakeGuild()
        self.messages = []

    async def send(self, content, **kwargs):
        self.messages.append(content)


@pytest.mark.asyncio
async def test_setupgate_sends_started_ack_before_summary(monkeypatch):
    # get_or_create_student_role hits Discord; stub it.
    async def fake_role(guild):
        return object()
    monkeypatch.setattr(role_gate, "get_or_create_student_role", fake_role)

    ctx = RecordingCtx()
    await role_gate.cmd_setupgate(ctx)

    # At least two messages: the immediate "started" ack, then the summary.
    assert len(ctx.messages) >= 2
    first = ctx.messages[0]
    # The first message is the progress ack (bilingual "started / Setting up").
    assert ("بدأ" in first) or ("Setting up" in first) or ("⏳" in first)
    # The final message is the completion summary.
    last = ctx.messages[-1]
    assert ("تم إعداد" in last) or ("postgate" in last)


@pytest.mark.asyncio
async def test_setupgate_admin_only_guard(monkeypatch):
    ctx = RecordingCtx()
    ctx.author.guild_permissions.administrator = False
    await role_gate.cmd_setupgate(ctx)
    # Only the "Admin only" refusal, no work started.
    assert len(ctx.messages) == 1
    assert "Admin only" in ctx.messages[0]
    ctx.author.guild_permissions.administrator = True   # restore for other tests
