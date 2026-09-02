"""Tests for the /admin slash bridge that gives every admin prefix command a
slash entry point (students keep !).

The bridge re-dispatches to the real prefix command via bot.get_context()/
bot.invoke() — the same mechanism features.py already uses — so behavior can't
drift. These tests lock in: registration, that it targets ONLY admin commands,
autocomplete filtering, rejection of unknown/non-admin names, and that a known
admin command is actually dispatched.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import bot as botmod


# ── registration + enumeration ──────────────────────────────────────────────
def test_admin_slash_command_registered():
    assert botmod.bot.tree.get_command("admin") is not None


def test_admin_command_names_are_admin_only():
    names = botmod._admin_command_names()
    assert len(names) >= 40                      # ~46 admin commands
    # A few known admin commands present:
    for a in ("status", "flag", "announce", "setupgate", "checkadmin", "onboard"):
        assert a in names, f"{a} should be in the admin list"
    # Student commands must NOT be reachable through the bridge:
    for s in ("today", "progress", "join", "done", "help", "top", "streak"):
        assert s not in names, f"{s} (student cmd) must NOT be in the admin list"


# ── autocomplete ─────────────────────────────────────────────────────────────
class FakeInteraction:
    def __init__(self):
        self.user = object()
        self.channel = object()
        self.guild = object()
        self.id = 123
        self._state = object()
        self.response = AsyncMock()
        self.followup = AsyncMock()


@pytest.mark.asyncio
async def test_autocomplete_filters_by_typed_text():
    res = await botmod._admin_command_autocomplete(FakeInteraction(), "flag")
    vals = [c.value for c in res]
    assert "flag" in vals
    assert all("flag" in v.casefold() for v in vals)
    # empty query returns a capped list
    res_all = await botmod._admin_command_autocomplete(FakeInteraction(), "")
    assert 1 <= len(res_all) <= 25


# ── dispatch behavior ────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_unknown_command_is_rejected_without_dispatch():
    it = FakeInteraction()
    with patch.object(botmod.bot, "invoke", AsyncMock()) as inv, \
         patch.object(botmod.bot, "get_context", AsyncMock()):
        await botmod.slash_admin.callback(it, command="not_a_real_command", args="")
    inv.assert_not_called()
    it.followup.send.assert_awaited()   # sent the "unknown" message


@pytest.mark.asyncio
async def test_student_command_cannot_be_run_via_admin_bridge():
    # Even a REAL command that isn't admin-gated must be refused by the bridge.
    it = FakeInteraction()
    with patch.object(botmod.bot, "invoke", AsyncMock()) as inv, \
         patch.object(botmod.bot, "get_context", AsyncMock()):
        await botmod.slash_admin.callback(it, command="today", args="")
    inv.assert_not_called()


@pytest.mark.asyncio
async def test_known_admin_command_is_dispatched():
    it = FakeInteraction()
    fake_ctx = type("Ctx", (), {})()
    with patch.object(botmod.bot, "get_context", AsyncMock(return_value=fake_ctx)), \
         patch.object(botmod.bot, "invoke", AsyncMock()) as inv:
        await botmod.slash_admin.callback(it, command="status", args="")
    inv.assert_awaited_once()
    # the context was pointed at the real 'status' command before invoke
    assert fake_ctx.command is botmod.bot.get_command("status")
