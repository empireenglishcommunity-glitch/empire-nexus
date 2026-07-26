"""Empire Reset (session-33) — Phase 1c + assessment removal.

- !systemstatus removed.
- The old weekly "assessment" scoring (attendance dressed up as a skill grade,
  Excellent…Critical labels) was misleading/unprofessional and is GONE. The
  Sunday job is now an honest `weekly_recap`: real activity only (exercises
  done, days practiced, streak) — no scores, no saved assessment, no points.
"""
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest

from src import bot as bot_mod


def test_systemstatus_command_removed():
    assert not hasattr(bot_mod, "cmd_systemstatus")


def test_assess_command_removed():
    assert not hasattr(bot_mod, "cmd_assess")


def _wire(monkeypatch, subs):
    """Point the Sunday recap at one fake member + guild. Returns
    (member_send_mock, calls dict) — calls tracks that NO scoring happens."""
    monkeypatch.setattr(bot_mod, "_now", lambda: dt.datetime(2026, 7, 26))  # Sunday
    monkeypatch.setattr(bot_mod.config, "IS_GHOST_INSTANCE", False)
    member = MagicMock()
    member.send = AsyncMock()
    guild = MagicMock()
    guild.get_member = MagicMock(return_value=member)
    monkeypatch.setattr(bot_mod.bot, "get_guild", lambda gid: guild)
    monkeypatch.setattr(bot_mod.database, "all_active_members", lambda: [{"discord_id": "700"}])
    monkeypatch.setattr(bot_mod.database, "member_week_number", lambda did: 3)
    monkeypatch.setattr(bot_mod.database, "get_submissions_since", lambda did, days=7: subs)
    monkeypatch.setattr(bot_mod.database, "get_streak", lambda did: (4, 9))
    calls = {"saved": False, "points": False}
    monkeypatch.setattr(bot_mod.database, "save_assessment",
                        lambda *a, **k: calls.__setitem__("saved", True))
    monkeypatch.setattr(bot_mod.database, "add_points",
                        lambda *a, **k: calls.__setitem__("points", True))
    return member, calls


@pytest.mark.asyncio
async def test_weekly_recap_shows_real_numbers_no_grade(monkeypatch):
    subs = [
        {"date": "2026-07-20", "task_id": "accent"},
        {"date": "2026-07-20", "task_id": "vocab"},
        {"date": "2026-07-21", "task_id": "shadow"},
    ]
    member, calls = _wire(monkeypatch, subs)
    await bot_mod.weekly_recap.coro()
    member.send.assert_awaited()
    msg = member.send.await_args[0][0]
    assert "Exercises completed: **3**" in msg
    assert "Days practiced: **2/7**" in msg
    assert "**4** days" in msg  # current streak
    # No grade/score and no scoring side effects.
    assert "%" not in msg
    assert calls["saved"] is False and calls["points"] is False


@pytest.mark.asyncio
async def test_weekly_recap_encourages_when_no_activity(monkeypatch):
    member, calls = _wire(monkeypatch, [])
    await bot_mod.weekly_recap.coro()
    msg = member.send.await_args[0][0]
    assert "!link" in msg
    assert "%" not in msg
    assert calls["saved"] is False and calls["points"] is False
