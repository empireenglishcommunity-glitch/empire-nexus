"""Tests for /repost-rules — refresh the pinned #rules content safely.

Reposts config.RULES_MESSAGE (chunked to Discord's 2000-char limit), pins the
FIRST chunk, removes any previous bot-posted rules message, and NEVER touches
the onboarding ✅ gate message. Dry run by default; posts only with confirm.
"""
import pytest

from src import role_gate, config, database


class FakeAuthorPerms:
    administrator = True


class FakeAuthor:
    guild_permissions = FakeAuthorPerms()


class FakeBotUser:
    id = 42


class FakeMsg:
    def __init__(self, mid, content="", author=None, pinned=False):
        self.id = mid
        self.content = content
        self.author = author
        self.pinned = pinned
        self.deleted = False

    async def delete(self, reason=None):
        self.deleted = True

    async def pin(self, reason=None):
        self.pinned = True


class FakeRulesChannel:
    def __init__(self, existing, bot_user):
        self._existing = existing
        self._bot_user = bot_user
        self.name = "rules"
        self.id = 999
        self.mention = "#rules"
        self.sent = []          # messages posted during the test

    async def history(self, limit=None):
        for m in self._existing:
            yield m

    async def send(self, content):
        msg = FakeMsg(1000 + len(self.sent), content=content, author=self._bot_user)
        self.sent.append(msg)
        return msg


class FakeGuild:
    def __init__(self, ch):
        self.text_channels = [ch]


class FakeBot:
    def __init__(self, user):
        self.user = user


class FakeCtx:
    def __init__(self, guild, bot):
        self.author = FakeAuthor()
        self.guild = guild
        self.bot = bot
        self.sent = []

    async def send(self, content, **kwargs):
        self.sent.append(content)


def _setup(existing):
    bot_user = FakeBotUser()
    ch = FakeRulesChannel(existing, bot_user)
    ctx = FakeCtx(FakeGuild(ch), FakeBot(bot_user))
    return ctx, ch, bot_user


@pytest.mark.asyncio
async def test_dry_run_posts_nothing():
    ctx, ch, _ = _setup(existing=[])
    await role_gate.cmd_repost_rules(ctx, confirm=False)
    assert ch.sent == []                       # nothing posted
    assert any("DRY RUN" in s for s in ctx.sent)


@pytest.mark.asyncio
async def test_confirm_posts_chunks_and_pins_first():
    ctx, ch, _ = _setup(existing=[])
    await role_gate.cmd_repost_rules(ctx, confirm=True)

    expected_chunks = config.chunk_message(config.RULES_MESSAGE)
    assert len(ch.sent) == len(expected_chunks)     # posted every chunk
    assert ch.sent[0].pinned is True                # first chunk pinned
    assert all(not m.pinned for m in ch.sent[1:])   # only the first
    assert "RULE 8" in "".join(m.content for m in ch.sent)  # enriched content


@pytest.mark.asyncio
async def test_replaces_old_rules_but_keeps_gate():
    bot_user = FakeBotUser()
    header = config.RULES_MESSAGE.splitlines()[0]
    old_rules = FakeMsg(1, content=header + "\n...old rules...", author=bot_user)
    gate = FakeMsg(7, content="🔒 للدخول إلى المجتمع — react ✅", author=bot_user)
    database.set_setting("role_gate_message_id", "7")

    ch = FakeRulesChannel([old_rules, gate], bot_user)
    ctx = FakeCtx(FakeGuild(ch), FakeBot(bot_user))

    await role_gate.cmd_repost_rules(ctx, confirm=True)

    assert old_rules.deleted is True      # previous rules post removed
    assert gate.deleted is False          # ✅ gate message preserved
    assert len(ch.sent) >= 1              # fresh rules posted


@pytest.mark.asyncio
async def test_does_not_delete_a_non_rules_bot_message():
    bot_user = FakeBotUser()
    other = FakeMsg(3, content="Daily digest 📊", author=bot_user)
    ch = FakeRulesChannel([other], bot_user)
    ctx = FakeCtx(FakeGuild(ch), FakeBot(bot_user))

    await role_gate.cmd_repost_rules(ctx, confirm=True)
    assert other.deleted is False         # only rules-header posts are removed


@pytest.mark.asyncio
async def test_non_admin_refused():
    ctx, ch, _ = _setup(existing=[])
    ctx.author.guild_permissions.administrator = False
    await role_gate.cmd_repost_rules(ctx, confirm=True)
    assert any("Admin only" in s for s in ctx.sent)
    assert ch.sent == []
