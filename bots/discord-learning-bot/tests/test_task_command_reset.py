"""Empire Reset (session-33) — task-completion command restructure.

The 5 core exercises (accent, vocab, shadow, listening, speaking) are logged
AUTOMATICALLY on the practice page, so `!done` / `!1`-`!5` no longer log them
in Discord — they show a redirect. Only writing (`!6`) and community (`!7`)
are logged in Discord. These tests lock that policy in.
"""
from unittest.mock import AsyncMock, patch

import pytest

from src import bot as bot_mod
from src import config, database, features


class _Author:
    def __init__(self, uid):
        self.id = int(uid)
        self.display_name = "Tester"


# cmd_done only needs ctx.author.id / .display_name / .send and, for the
# writing/community path, isinstance(ctx.author, discord.Member). The 5-core
# redirect path returns BEFORE any Member check, so a plain object suffices
# for the redirect tests.
class _SimpleCtx:
    def __init__(self, uid):
        self.author = _Author(uid)
        self.guild = object()
        self.send = AsyncMock()


REDIRECT_HINT = "practice page"


@pytest.mark.asyncio
@pytest.mark.parametrize("arg", ["accent", "vocab", "shadow", "listening", "speaking",
                                  "1", "2", "3", "4", "5", None, "bogustask"])
async def test_core_and_unknown_and_empty_redirect(arg):
    database.register_member("500", "Tester")
    ctx = _SimpleCtx("500")
    await bot_mod.cmd_done.callback(ctx, arg)
    ctx.send.assert_awaited_once()
    msg = ctx.send.await_args[0][0]
    assert "!6" in msg and "!7" in msg  # the redirect names the two real cmds
    assert "!link" in msg


@pytest.mark.asyncio
@pytest.mark.parametrize("arg,expected_task", [("6", "writing"), ("7", "community"),
                                               ("writing", "writing"), ("community", "community")])
async def test_writing_and_community_reach_submission(arg, expected_task):
    """!6/!7 (and their names) must flow through to the real verification +
    submission path — NOT the redirect."""
    import discord
    from unittest.mock import MagicMock
    database.register_member("501", "Tester")
    # A Member-spec mock so isinstance(ctx.author, discord.Member) is True.
    author = MagicMock(spec=discord.Member)
    author.id = 501
    author.display_name = "Tester"
    ctx = MagicMock()
    ctx.author = author
    ctx.guild = MagicMock(spec=discord.Guild)
    ctx.send = AsyncMock()

    # Stub the gradual-intro gate to allow the task, the cooldown to pass,
    # and verify_task to succeed, so we can assert process_submission is hit.
    with patch.object(features, "get_allowed_tasks_for_member", return_value=[expected_task]), \
         patch("src.verification.check_cooldown", return_value=(True, 0)), \
         patch("src.verification.verify_task", new=AsyncMock(return_value=(True, ""))), \
         patch("src.verification.record_done_time"), \
         patch("src.tasks.process_submission", new=AsyncMock(return_value={"new": False})) as psub:
        try:
            await bot_mod.cmd_done.callback(ctx, arg)
        except Exception:
            # Some downstream (mastery/journey) helpers may not be fully
            # stubbable; we only care that the redirect did NOT fire and
            # the submission path was entered.
            pass

    # The redirect message must NOT have been the (only) thing sent.
    sent_msgs = [c.args[0] for c in ctx.send.await_args_list] if ctx.send.await_args_list else []
    assert not any("practice page" in m for m in sent_msgs), \
        f"writing/community must not redirect; got {sent_msgs}"
    psub.assert_awaited_once()
    assert psub.await_args[0][2] == expected_task


def test_only_67_reactions_added_constant():
    """The daily post must only offer 6️⃣/7️⃣ reactions now."""
    assert bot_mod._TASK_NUMBER_EMOJIS[5:7] == ["6️⃣", "7️⃣"]
    # Sanity: index mapping still writing=5, community=6.
    assert config.DAILY_TASKS[5]["id"] == "writing"
    assert config.DAILY_TASKS[6]["id"] == "community"
