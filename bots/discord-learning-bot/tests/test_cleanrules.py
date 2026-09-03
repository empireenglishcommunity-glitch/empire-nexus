"""Tests for /cleanrules — tidy up the #rules channel without breaking the gate.

#rules must be read-only for students (onboarding is by ✅ REACTION, never by
typing). cleanrules deletes the accumulated student messages but PRESERVES the
pinned messages and the stored role-gate ✅ message, so the reaction gate and
pin survive. Dry run by default; deletes only with confirm=True.
"""
import pytest

from src import role_gate, database


class FakeAuthorPerms:
    administrator = True


class FakeAuthor:
    guild_permissions = FakeAuthorPerms()


class FakeMsg:
    def __init__(self, mid, pinned=False):
        self.id = mid
        self.pinned = pinned
        self.deleted = False
        self.mention = f"<#{mid}>"

    async def delete(self, reason=None):
        self.deleted = True


class FakeRulesChannel:
    def __init__(self, messages, pinned):
        self._messages = messages
        self._pinned = pinned
        self.name = "rules"
        self.id = 999
        self.mention = "#rules"
        self.purged = None

    async def pins(self):
        return self._pinned

    async def history(self, limit=None):
        for m in self._messages:
            yield m

    async def purge(self, limit=None, check=None, reason=None):
        removed = [m for m in self._messages if (check is None or check(m))]
        for m in removed:
            m.deleted = True
        self.purged = removed
        return removed


class FakeGuild:
    def __init__(self, rules_channel):
        self.text_channels = [rules_channel]


class FakeCtx:
    def __init__(self, guild):
        self.author = FakeAuthor()
        self.guild = guild
        self.sent = []

    async def send(self, content, **kwargs):
        self.sent.append(content)


def _setup(messages, pinned):
    ch = FakeRulesChannel(messages, pinned)
    return FakeCtx(FakeGuild(ch)), ch


@pytest.mark.asyncio
async def test_dry_run_deletes_nothing_and_reports():
    gate = FakeMsg(1, pinned=True)
    junk = [FakeMsg(2), FakeMsg(3), FakeMsg(4)]
    database.set_setting("role_gate_message_id", "1")
    ctx, ch = _setup([gate] + junk, pinned=[gate])

    await role_gate.cmd_cleanrules(ctx, confirm=False)

    assert all(not m.deleted for m in junk)          # nothing deleted
    assert gate.deleted is False
    assert any("DRY RUN" in s for s in ctx.sent)
    assert any("3" in s for s in ctx.sent)           # 3 would be deleted


@pytest.mark.asyncio
async def test_confirm_purges_non_pinned_keeps_gate():
    gate = FakeMsg(1, pinned=True)
    junk = [FakeMsg(2), FakeMsg(3)]
    database.set_setting("role_gate_message_id", "1")
    ctx, ch = _setup([gate] + junk, pinned=[gate])

    await role_gate.cmd_cleanrules(ctx, confirm=True)

    assert gate.deleted is False                     # gate/pinned preserved
    assert all(m.deleted for m in junk)              # junk removed
    assert any("cleaned" in s.lower() for s in ctx.sent)


@pytest.mark.asyncio
async def test_keeps_stored_gate_even_if_not_pinned():
    """Belt-and-suspenders: the gate message is preserved by stored id even if
    it was never pinned."""
    gate = FakeMsg(50, pinned=False)      # NOT pinned
    junk = [FakeMsg(51)]
    database.set_setting("role_gate_message_id", "50")
    ctx, ch = _setup([gate, junk[0]], pinned=[])

    await role_gate.cmd_cleanrules(ctx, confirm=True)

    assert gate.deleted is False          # kept via stored id
    assert junk[0].deleted is True


@pytest.mark.asyncio
async def test_nothing_to_clean_reports_clean():
    gate = FakeMsg(1, pinned=True)
    database.set_setting("role_gate_message_id", "1")
    ctx, ch = _setup([gate], pinned=[gate])

    await role_gate.cmd_cleanrules(ctx, confirm=True)
    assert any("already clean" in s.lower() for s in ctx.sent)


@pytest.mark.asyncio
async def test_non_admin_refused():
    ctx, ch = _setup([FakeMsg(1)], pinned=[])
    ctx.author.guild_permissions.administrator = False
    await role_gate.cmd_cleanrules(ctx, confirm=True)
    assert any("Admin only" in s for s in ctx.sent)
    assert not ch._messages[0].deleted
