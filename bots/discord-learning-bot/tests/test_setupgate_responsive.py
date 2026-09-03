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



# ── setupgate retroactive grant must SKIP suspended members ──────────────────
# Incident (2026-09-03): re-running /setupgate re-granted the Student role to
# EVERY member without it — including suspended students — silently undoing all
# active suspensions and putting them all back in the community at once.

class _RetroMember:
    def __init__(self, mid, has_role=False):
        from src import role_gate as rg
        self.id = int(mid)
        self.display_name = f"user{mid}"
        self.bot = False
        self.roles = [type("R", (), {"name": rg.STUDENT_ROLE_NAME})()] if has_role else []
        self.granted = False

    async def add_roles(self, role, reason=None):
        self.granted = True
        self.roles.append(role)


class _RetroGuild:
    def __init__(self, members):
        self.channels = []          # skip the permission loop
        self.roles = []
        self.members = members
        self.default_role = object()


class _RetroCtx:
    def __init__(self, guild):
        self.author = FakeAuthor()
        self.guild = guild
        self.messages = []

    async def send(self, content, **kwargs):
        self.messages.append(content)


@pytest.mark.asyncio
async def test_setupgate_retroactive_skips_suspended_members(monkeypatch):
    from src import database, role_gate

    active_id, susp_id = "9101", "9102"
    database.register_member(active_id, "Active One", level="A1")
    database.register_member(susp_id, "Suspended One", level="A1")
    database.suspend_member(susp_id)
    assert database.is_suspended(susp_id) is True

    active = _RetroMember(active_id, has_role=False)
    suspended = _RetroMember(susp_id, has_role=False)
    ctx = _RetroCtx(_RetroGuild([active, suspended]))

    fake_role = type("R", (), {"name": role_gate.STUDENT_ROLE_NAME})()

    async def fake_get_or_create(guild):
        return fake_role
    monkeypatch.setattr(role_gate, "get_or_create_student_role", fake_get_or_create)

    await role_gate.cmd_setupgate(ctx)

    assert active.granted is True        # active member retro-granted
    assert suspended.granted is False    # suspended member SKIPPED
