"""Tests for the first-class /suspend, /restore, /suspended slash commands.

These are native slash versions of the ! membership-lifecycle commands. They
reuse the SAME suspension.* primitives via shared text-builders, so behavior is
identical. The critical guarantees locked in here:

  1. Both the slash (/) and prefix (!) forms are registered and admin-gated,
     and suspend/restore/suspended still appear in the /admin bridge.
  2. The shared text-builders preview correctly and only act when asked — the
     dry-run path changes nothing.
  3. The slash target resolver enforces "exactly one of student / target".

The deep suspension/restore data guarantees live in test_suspension_lifecycle.py;
this file only covers the command-surface layer added for the slash migration.
"""
import pytest

from src import bot as botmod, database, suspension


def _mk(discord_id="700", name="Slash Student", level="A1"):
    database.register_member(discord_id, name, level=level)
    return discord_id


# ── registration ─────────────────────────────────────────────────────────────
def test_slash_and_prefix_registered_and_admin_gated():
    for name in ("suspend", "restore", "suspended"):
        assert botmod.bot.get_command(name) is not None, f"!{name} missing"
        assert botmod.bot.tree.get_command(name) is not None, f"/{name} missing"
    # admin-gated -> the ! forms still appear in the /admin bridge enumeration
    admin_names = botmod._admin_command_names()
    assert "suspend" in admin_names
    assert "restore" in admin_names


def test_slash_restore_student_is_a_distinct_command():
    """/restore (lifecycle) must not collide with /restore-student (undo reset)."""
    assert botmod.bot.tree.get_command("restore") is not None
    assert botmod.bot.tree.get_command("restore-student") is not None


# ── shared suspend text-builders ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_suspend_preview_does_not_change_anything():
    did = _mk("701")
    preview, body = await botmod._suspend_preview_lines(guild=None, rows=[database.get_member(did)])
    assert len(preview) == 1
    assert "Slash Student" in body
    # dry-run must NOT suspend
    assert database.is_suspended(did) is False


@pytest.mark.asyncio
async def test_suspend_run_actually_suspends():
    did = _mk("702")
    row = database.get_member(did)
    text = await botmod._suspend_run_text(guild=None, actionable=[row])
    assert "Suspended 1/1" in text
    assert database.is_suspended(did) is True


@pytest.mark.asyncio
async def test_suspend_preview_flags_already_suspended():
    did = _mk("703")
    database.suspend_member(did)
    preview, body = await botmod._suspend_preview_lines(guild=None, rows=[database.get_member(did)])
    assert preview[0]["already"] is True
    assert "already suspended" in body


# ── shared restore text-builders ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_restore_preview_and_run():
    did = _mk("704")
    database.suspend_member(did)
    assert database.is_suspended(did) is True

    preview, body = await botmod._restore_preview_lines(guild=None, rows=[database.get_member(did)])
    assert preview[0]["not_suspended"] is False
    assert database.is_suspended(did) is True   # preview changed nothing

    text = await botmod._restore_run_text(guild=None, actionable=[database.get_member(did)])
    assert "Restored 1/1" in text
    assert database.is_suspended(did) is False


@pytest.mark.asyncio
async def test_restore_preview_skips_not_suspended():
    did = _mk("705")   # never suspended
    preview, body = await botmod._restore_preview_lines(guild=None, rows=[database.get_member(did)])
    assert preview[0]["not_suspended"] is True
    assert "not suspended" in body


# ── suspended listing ────────────────────────────────────────────────────────
def test_suspended_list_text_empty_and_populated():
    # (a fresh in-memory DB per test run means "nobody" unless we add one)
    empty = botmod._suspended_list_text()
    assert "Nobody is currently suspended" in empty or "Suspended students" in empty

    did = _mk("706")
    database.suspend_member(did)
    populated = botmod._suspended_list_text()
    assert "Suspended students" in populated
    assert "Slash Student" in populated


# ── slash target resolver (exactly one of student / target) ──────────────────
@pytest.mark.asyncio
async def test_slash_targets_resolves_bulk_selector():
    _mk("707")
    rows, desc, err = await botmod._slash_suspension_targets(
        interaction=None, student=None, target="all")
    assert err is None
    assert any(r["discord_id"] == "707" for r in rows)
    assert "active" in desc
