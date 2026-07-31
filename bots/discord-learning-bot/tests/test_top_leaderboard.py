"""`!top` leaderboard — personal-rank enrichment.

Regression lock for the fix to "students report they're not listed on
`!top`". The command shows only the top 10 by points, so in a 16-student
community the lower ~6 saw a board they weren't on. `cmd_top` now appends
the requester's own standing when they're outside the shown slice (mirroring
the web `/api/leaderboard`, which has always returned `your_rank`).

These tests also give the previously-uncovered `database.get_member_rank()`
its first coverage — it was written for exactly this "where do I rank
outside the top-N" case but had never been wired into a command.
"""
from unittest.mock import AsyncMock

import pytest

from src import bot as bot_mod
from src import database


class _Author:
    def __init__(self, uid, name="Tester"):
        self.id = int(uid)
        self.display_name = name


class _SimpleCtx:
    def __init__(self, uid, name="Tester"):
        self.author = _Author(uid, name)
        self.guild = object()
        self.send = AsyncMock()


def _seed(uid, name, points):
    database.register_member(uid, name)
    database.update_member(uid, total_points=points)


# ------------------------------------------------------------------
#  database.get_member_rank — the previously-unwired helper
# ------------------------------------------------------------------

def test_get_member_rank_orders_by_points():
    _seed("1", "A", 100)
    _seed("2", "B", 50)
    _seed("3", "C", 10)
    assert database.get_member_rank("1") == 1
    assert database.get_member_rank("2") == 2
    assert database.get_member_rank("3") == 3


def test_get_member_rank_none_for_unknown():
    _seed("1", "A", 100)
    assert database.get_member_rank("999999") is None


# ------------------------------------------------------------------
#  !top personal-rank line
# ------------------------------------------------------------------

@pytest.mark.asyncio
async def test_top_appends_rank_for_student_outside_top_10():
    # 10 higher-point members fill the visible board...
    for i in range(1, 11):
        _seed(str(i), f"Top{i}", 200 - i)  # 199..190, all > requester
    # ...and the requester sits just outside it.
    _seed("777", "Latecomer", 5)

    ctx = _SimpleCtx("777", "Latecomer")
    await bot_mod.cmd_top.callback(ctx)

    msg = ctx.send.await_args[0][0]
    # Their personal standing is shown even though they're off the board.
    assert "ترتيبك" in msg          # Arabic "your rank" label
    assert "#11/11" in msg          # rank / total
    assert "Latecomer" in msg
    assert "5 pts" in msg


@pytest.mark.asyncio
async def test_top_no_personal_line_when_requester_is_in_top_10():
    for i in range(1, 6):
        _seed(str(i), f"M{i}", 100 - i)
    # Requester #1 is clearly on the board.
    ctx = _SimpleCtx("1", "M1")
    await bot_mod.cmd_top.callback(ctx)

    msg = ctx.send.await_args[0][0]
    # No redundant personal-rank block for someone already visible.
    assert "ترتيبك" not in msg


@pytest.mark.asyncio
async def test_top_nudges_non_member_to_join():
    for i in range(1, 4):
        _seed(str(i), f"M{i}", 100 - i)
    # Caller has never !join'd — no member row.
    ctx = _SimpleCtx("424242", "Curious")
    await bot_mod.cmd_top.callback(ctx)

    msg = ctx.send.await_args[0][0]
    assert "!join" in msg          # nudged to join
    assert "ترتيبك" not in msg      # no personal-rank block for a non-member


@pytest.mark.asyncio
async def test_top_empty_board_prompts_first_join():
    ctx = _SimpleCtx("1", "Nobody")
    await bot_mod.cmd_top.callback(ctx)
    msg = ctx.send.await_args[0][0]
    assert "!join" in msg
