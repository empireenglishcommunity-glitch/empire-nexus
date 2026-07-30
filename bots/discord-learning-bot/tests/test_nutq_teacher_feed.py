"""Nutq — teacher-feed gating tests (owner oversight channel).

The full Discord post is best-effort and covered live; here we verify the guard
rails: it no-ops (no error, no bot access) when disabled or when there's no score.
"""
import pytest

from src import api_server, config


@pytest.mark.asyncio
async def test_teacher_feed_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "NUTQ_TEACHER_FEED_CHANNEL_ID", 0)
    # channel id 0 → returns immediately (no bot import), no exception
    await api_server._post_teacher_feed("Test Student", "shadow", 1, 1,
                                        {"scored": True, "score": 90, "missed_words": [],
                                         "feedback_en": "Great!"})


@pytest.mark.asyncio
async def test_teacher_feed_noop_when_not_scored(monkeypatch):
    monkeypatch.setattr(config, "NUTQ_TEACHER_FEED_CHANNEL_ID", 123456789)
    # scored False → returns before touching the bot, no exception
    await api_server._post_teacher_feed("Test Student", "shadow", 1, 1, {"scored": False})
