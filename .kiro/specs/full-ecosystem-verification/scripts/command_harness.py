#!/usr/bin/env python3
"""Hisn H1.1-H1.3 — Discord Command Test Harness.

Invokes every registered @bot.command's underlying callback DIRECTLY
(via Command.callback, the original async function before discord.py's
dispatch/argument-parsing layer wraps it) against a faithful mock
`ctx` object. This exercises the REAL command body -- the actual
database calls, feature-flag checks, and response formatting -- without
needing a second live Discord account or a real gateway connection.

Mocks use `spec=discord.Member` / `spec=discord.Guild` so the many
`isinstance(ctx.author, discord.Member)` checks scattered through
bot.py pass correctly, matching real command behavior.

Design decisions / known limitations (read before trusting the output):
- This tests CRASH-SAFETY and BASIC RESPONSE CORRECTNESS for every
  command. It does NOT test: real audio/attachment verification (!done
  accent/shadow/speaking need a real Discord attachment), real voice
  channel presence checks (!done community), or Discord's own argument
  parsing/converters (int, discord.Member converters) -- those three
  categories are explicitly flagged NEEDS_HUMAN in the report and
  deferred to H6's live walkthrough rather than faked unreliably here.
- Runs against the LIVE production database using GHOST_TEST_ synthetic
  member IDs (per H0.6's convention) -- never touches real member data.
- Argument-parsing bypass means TRUE "wrong argument type" testing
  (e.g. `!examresult abc pass` where discord.py's `int` converter would
  normally reject "abc" before the function body even runs) isn't
  exercised here. Documented as a known gap, not silently ignored.

Run INSIDE the bot's container:
    docker cp command_harness.py empire-english-bot:/app/command_harness.py
    docker exec empire-english-bot python3 /app/command_harness.py
    docker exec empire-english-bot rm -f /app/command_harness.py
"""
import asyncio
import sys
import traceback
from unittest.mock import MagicMock, AsyncMock

sys.path.insert(0, "/app")
import discord
from src import database, config

# Import the bot module last, after src.database is initialized, since
# bot.py builds its Command objects (and the global `bot` instance) at
# import time.
database.init_db()

# ── Synthetic GHOST_TEST_ member, per H0.6's convention ──
TEST_DISCORD_ID = "900000001"
TEST_DISCORD_NAME = "GHOST_TEST_H1Runner#0001"


def make_mock_author(is_member=True):
    """Build a mock ctx.author that passes isinstance(x, discord.Member)
    checks when is_member=True (the normal in-guild case), or looks like
    a plain discord.User (DM context) when False."""
    spec = discord.Member if is_member else discord.User
    author = MagicMock(spec=spec)
    author.id = int(TEST_DISCORD_ID)
    author.display_name = TEST_DISCORD_NAME
    author.mention = f"<@{TEST_DISCORD_ID}>"
    author.bot = False
    author.send = AsyncMock()
    return author


def make_mock_guild():
    guild = MagicMock(spec=discord.Guild)
    guild.id = config.GUILD_ID
    guild.get_member = MagicMock(return_value=None)  # override per-test as needed
    guild.text_channels = []
    guild.voice_channels = []
    # !attention's buddy-load-balancing helper (features.py) iterates
    # `role.members` for every guild role to find candidates -- an
    # empty list here is enough to exercise that loop safely (0
    # iterations) without needing full synthetic role/member data.
    # Missing this caused a real "crash" on the first version of this
    # harness (confirmed to be a mocking gap, not a bot bug — see
    # defect_log.md).
    guild.roles = []
    return guild


def make_mock_ctx(content="", author=None, guild=None):
    ctx = MagicMock()
    ctx.author = author or make_mock_author()
    ctx.guild = guild or make_mock_guild()
    ctx.send = AsyncMock()
    ctx.message = MagicMock()
    ctx.message.content = content
    ctx.channel = MagicMock()
    ctx.channel.name = "bot-commands"
    ctx.channel.typing = MagicMock()
    ctx.channel.typing.return_value.__aenter__ = AsyncMock()
    ctx.channel.typing.return_value.__aexit__ = AsyncMock()
    return ctx


# Commands that need real Discord infrastructure this harness can't
# faithfully simulate (real audio attachments, real voice presence,
# discord.py's own argument converters). Flagged, not faked.
NEEDS_HUMAN = {
    "done": "needs a real #showcase audio attachment / voice presence for full verification (accent/shadow/speaking/community sub-paths)",
    "exam": "starts a real multi-step DM collection flow (recording + writing submission)",
    "examresult": "takes an `int` argument via discord.py's own converter, which this harness bypasses",
    "setlevel": "takes a `discord.Member` converter argument (@mention), which this harness bypasses",
}

# Commands that intentionally do nothing / return early when a related
# feature flag is off, or need specific pre-existing DB state to show
# their "interesting" path (still safe and correct to invoke; the goal
# here is confirming NO CRASH + a sane response, not exercising every
# internal branch).
results = []


async def run_command(bot, name, *args, ctx=None, label="", **kwargs):
    """Look up a registered command by name and invoke its raw callback
    directly with the given ctx and positional/keyword args (mirroring
    how discord.py would call it after parsing, but skipping the
    parsing step itself). Keyword-only 'rest of message' parameters
    (e.g. !join's `goal`) MUST be passed as kwargs here, not positional
    args -- see KEYWORD_ONLY_PARAM above for why."""
    cmd = bot.get_command(name)
    if cmd is None:
        results.append((name, label, "FAIL", "command not found in bot.commands"))
        return

    ctx = ctx or make_mock_ctx()
    try:
        await cmd.callback(ctx, *args, **kwargs)
        # Consider it a pass if it didn't raise. Grab whatever was sent
        # for a human-readable log, truncated.
        sent_text = ""
        if ctx.send.await_args_list:
            sent_text = str(ctx.send.await_args_list[-1])[:150]
        elif hasattr(ctx.author, "send") and ctx.author.send.await_args_list:
            sent_text = "(sent via DM) " + str(ctx.author.send.await_args_list[-1])[:150]
        results.append((name, label, "PASS", sent_text))
    except Exception as e:
        results.append((name, label, "CRASH", f"{type(e).__name__}: {e}"))


async def main():
    from src import bot as bot_module
    bot = bot_module.bot

    # Register the synthetic test member so member-dependent commands
    # (!progress, !streak, etc.) exercise their "registered" branch,
    # not just their "not registered" early-return.
    database.register_member(TEST_DISCORD_ID, TEST_DISCORD_NAME, goal="Test goal for Hisn H1")

    all_commands = sorted(c.name for c in bot.commands)
    print(f"Registered commands found: {len(all_commands)}")
    print()

    # ── No-args invocation for every command (input variant 1: "none") ──
    for name in all_commands:
        if name in NEEDS_HUMAN:
            results.append((name, "none", "SKIP", f"NEEDS_HUMAN: {NEEDS_HUMAN[name]}"))
            continue
        await run_command(bot, name)

    # ── A few representative "valid args" invocations (variant 2) ──
    # NOTE: commands using a keyword-only parameter (`*, name: str = ""`
    # in their signature -- discord.py's own convention for "rest of
    # the message text" arguments) MUST be invoked with that argument
    # passed as a kwarg here, matching how discord.py's real dispatch
    # always binds them. An earlier version of this script passed
    # everything positionally and got a real TypeError for exactly
    # this reason on !join/!orient/!announce -- a harness bug, not a
    # bot bug (confirmed by reading each function's actual signature
    # before assuming otherwise). Fixed by using each command's real
    # keyword-only parameter name explicitly.
    KEYWORD_ONLY_PARAM = {
        "join": "goal",
        "orient": "date_time",
        "announce": "message",
    }
    valid_arg_tests = [
        ("join", (), {"goal": "My test goal"}),
        ("notifications", ("morning", "off"), {}),
        ("recruit", ("en",), {}),
        ("resources", ("L0",), {}),
        ("orient", (), {"date_time": "Saturday 6pm"}),
        ("announce", (), {"message": "Test announcement from Hisn H1"}),
        # !maintenance's "on"/"off" sub-paths call bot.change_presence()
        # on the real gateway singleton, which needs an actual live
        # connection this harness doesn't have -- deliberately NOT
        # exercised here (that specific side effect is deferred to H6),
        # but the flag-toggle/DB-write path IS already covered by the
        # earlier no-args run.
    ]
    for name, args, kwargs in valid_arg_tests:
        if name in [r[0] for r in results if r[1] == "none" and r[2] == "SKIP"]:
            continue
        await run_command(bot, name, *args, ctx=make_mock_ctx(), label="valid", **kwargs)

    # ── Oversized-input variant (variant 4) — the exact class of bug
    #    that broke !flag list before (Discord's 2000-char limit) ──
    oversized_goal = "x" * 3000
    await run_command(bot, "join", ctx=make_mock_ctx(), label="oversized", goal=oversized_goal)

    # ── Report FIRST, cleanup SECOND ──
    # Deliberately printed before the cleanup step below: an earlier
    # version of this script ran cleanup first and a real bug in it
    # (see the try/except below) crashed the whole script before the
    # report ever printed, hiding the actual test results behind an
    # unrelated cleanup failure. Report now always prints regardless
    # of whether cleanup succeeds.
    print("=" * 70)
    passed = [r for r in results if r[2] == "PASS"]
    crashed = [r for r in results if r[2] == "CRASH"]
    skipped = [r for r in results if r[2] == "SKIP"]
    failed = [r for r in results if r[2] == "FAIL"]
    print(f"PASS: {len(passed)}  CRASH: {len(crashed)}  SKIP (needs human): {len(skipped)}  FAIL: {len(failed)}")
    print()
    for name, label, status, detail in results:
        print(f"{status:6s} !{name:20s} [{label:10s}]  {detail}")

    # ── Restore: remove the synthetic test member's data so this run
    #    leaves no residue (H0.6 cleanup convention) ──
    conn = database._connect()
    try:
        # NOTE: conversation_sessions deliberately excluded from this
        # list -- it has no discord_id column at all (participants are
        # stored as a comma-separated participant_ids TEXT field
        # instead), and this test never creates a session row anyway.
        # An earlier version of this script blindly included it,
        # causing a real "no such column: discord_id" crash mid-cleanup
        # -- found via actually running this against the live
        # container, not by reading the schema first. Fixed by removing
        # the table from this loop rather than writing a fragile LIKE
        # match against a field this test doesn't populate.
        for table in [
            "daily_submissions", "streaks", "points_log", "notification_preferences",
            "notification_log", "voice_portfolio", "vocab_srs", "ability_milestones",
            "assessments", "advancement_exams",
            "pronunciation_scores", "link_tokens", "nour_conversations",
            "nour_study_tips", "pending_escalations", "members",
        ]:
            conn.execute(f"DELETE FROM {table} WHERE discord_id=?", (TEST_DISCORD_ID,))
        conn.commit()
        print()
        print("Cleanup: OK — all GHOST_TEST_ test data removed.")
    except Exception as e:
        print()
        print(f"Cleanup: FAILED — {type(e).__name__}: {e}")
        print(f"Manual cleanup needed for discord_id={TEST_DISCORD_ID}")
    finally:
        conn.close()

    if crashed or failed:
        sys.exit(1)


asyncio.run(main())
