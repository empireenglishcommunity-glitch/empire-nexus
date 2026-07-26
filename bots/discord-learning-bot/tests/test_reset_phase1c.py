"""Empire Reset (session-33) — Phase 1c.

- !systemstatus removed.
- !assess is no longer needed: the weekly_assessment Sunday job now scores
  each student AUTOMATICALLY (build_weekly_assessment → save_assessment →
  points once), and DMs them the result. Students with no data get an
  encouraging nudge instead of a 0%.
"""
import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest

from src import bot as bot_mod
from src import database


def test_systemstatus_command_removed():
    assert not hasattr(bot_mod, "cmd_systemstatus")


def _wire_common(monkeypatch, submitted):
    """Point the Sunday job at a single fake member + fake guild, and stub
    build_weekly_assessment. Returns (member_send_mock, calls dict)."""
    # 2026-07-26 is a Sunday, so the weekday guard passes.
    monkeypatch.setattr(bot_mod, "_now", lambda: dt.datetime(2026, 7, 26))
    member = MagicMock()
    member.send = AsyncMock()
    guild = MagicMock()
    guild.get_member = MagicMock(return_value=member)
    monkeypatch.setattr(bot_mod.bot, "get_guild", lambda gid: guild)
    monkeypatch.setattr(bot_mod.database, "all_active_members", lambda: [{"discord_id": "700"}])
    monkeypatch.setattr(bot_mod.database, "member_week_number", lambda did: 3)
    monkeypatch.setattr(bot_mod.task_engine, "build_weekly_assessment", lambda did: {
        "scores": {}, "overall": 82.0, "rating": "Strong", "submitted_tasks": submitted,
    })
    calls = {"saved": False, "points": False}
    monkeypatch.setattr(bot_mod.database, "get_assessment_for_week", lambda did, w: None)
    monkeypatch.setattr(bot_mod.database, "save_assessment",
                        lambda *a, **k: calls.__setitem__("saved", True))
    monkeypatch.setattr(bot_mod.database, "add_points",
                        lambda *a, **k: calls.__setitem__("points", True))
    return member, calls


@pytest.mark.asyncio
async def test_weekly_job_autoscores_when_data_present(monkeypatch):
    member, calls = _wire_common(monkeypatch, submitted=["writing", "vocab"])
    await bot_mod.weekly_assessment.coro()
    assert calls["saved"] is True
    assert calls["points"] is True
    member.send.assert_awaited()
    assert "82%" in member.send.await_args[0][0]


@pytest.mark.asyncio
async def test_weekly_job_encourages_when_no_data(monkeypatch):
    member, calls = _wire_common(monkeypatch, submitted=[])
    await bot_mod.weekly_assessment.coro()
    # No score saved, no points, and the DM is the encouraging nudge.
    assert calls["saved"] is False
    assert calls["points"] is False
    member.send.assert_awaited()
    assert "!link" in member.send.await_args[0][0]
