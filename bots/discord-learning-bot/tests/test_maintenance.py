"""Tests for maintenance mode (src/maintenance.py) — Phase 1."""
import datetime

from src import maintenance, database


def _reset():
    database.set_setting("maintenance_active", "0")


def test_default_is_live():
    _reset()
    assert maintenance.get_status() == {"state": "live"}
    assert maintenance.is_active() is False


def test_start_soft_sets_all_fields():
    maintenance.start(level="soft", reason="deploying #123", eta="~20 min")
    s = maintenance.get_status()
    assert s["state"] == "maintenance"
    assert s["level"] == "soft"
    assert s["reason"] == "deploying #123"
    assert s["eta"] == "~20 min"
    assert s["started_at"]
    assert maintenance.is_active() is True
    maintenance.end()


def test_start_hard():
    maintenance.start(level="hard")
    assert maintenance.get_status()["level"] == "hard"
    maintenance.end()


def test_invalid_level_defaults_to_soft():
    maintenance.start(level="banana")
    assert maintenance.get_status()["level"] == "soft"
    maintenance.end()


def test_end_returns_to_live():
    maintenance.start(level="hard")
    maintenance.end()
    assert maintenance.get_status()["state"] == "live"
    assert maintenance.is_active() is False


def test_custom_message_overrides():
    maintenance.start(level="soft", reason="r", message="custom text")
    assert maintenance.get_status()["message"] == "custom text"
    maintenance.end()


def test_auto_resume_window_reports_live_without_clearing():
    """If the auto-end window has elapsed, status reports live immediately
    (so a forgotten `end` never leaves students locked out) — but it does NOT
    clear the flag; the heartbeat's check_and_handle_auto_resume does the
    clear + 'we're back' broadcast exactly once."""
    maintenance.start(level="hard", window_minutes=120)
    assert maintenance.is_active() is True
    past = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=1)).isoformat()
    database.set_setting("maintenance_auto_end_at", past)
    s = maintenance.get_status()
    assert s["state"] == "live"
    assert s.get("auto_ended") is True
    # Still flagged active (not cleared here) — cleared by the auto-resume handler.
    assert database.get_setting("maintenance_active", "0") == "1"
    maintenance.end()



# ============================================================
#  Phase 2 — broadcast + messages + legacy-key unification
# ============================================================

import asyncio
import types

import pytest

from src import config


def test_legacy_maintenance_mode_is_honored():
    """deploy.py sets maintenance_mode=on before a deploy — get_status must
    treat that as maintenance (so the page banner + presence reflect it)."""
    _reset()
    database.set_setting("maintenance_mode", "off")
    assert maintenance.get_status()["state"] == "live"
    database.set_setting("maintenance_mode", "on")
    try:
        assert maintenance.get_status()["state"] == "maintenance"
        assert maintenance.is_active() is True
    finally:
        database.set_setting("maintenance_mode", "off")


def test_start_end_keep_both_keys_in_sync():
    maintenance.start(level="soft")
    assert database.get_setting("maintenance_active", "0") == "1"
    assert database.get_setting("maintenance_mode", "off") == "on"
    maintenance.end()
    assert database.get_setting("maintenance_active", "0") == "0"
    assert database.get_setting("maintenance_mode", "off") == "off"


def test_messages_are_bilingual_and_safe():
    m = maintenance.start_message({"level": "hard", "reason": "deploy", "eta": "~20 min"})
    assert "🔒" in m and "safe" in m.lower()
    assert "صيانة" in m  # Arabic present
    # No promised time in the student-facing broadcast, even when an ETA is set.
    assert "~20 min" not in m
    assert "Expected back" not in m
    # No duration-implying words (agreed: never imply how long it takes).
    assert "Quick" not in m and "quick" not in m
    assert "سريعة" not in m
    # A soft notice must not say the page is 'paused'.
    soft = maintenance.start_message({"level": "soft"})
    assert "keep practicing" in soft.lower()
    e = maintenance.end_message("Faster vocab quiz")
    assert "back" in e.lower()
    assert "Faster vocab quiz" in e
    assert "رجعنا" in e  # Arabic present


class _FakeChannel:
    def __init__(self): self.name = "announcements"; self.sent = []
    async def send(self, text): self.sent.append(text)


class _FakeGuild:
    def __init__(self, ch): self.text_channels = [ch]


class _FakeBot:
    def __init__(self, ch):
        self._guild = _FakeGuild(ch)
        self.presence = None
    def get_guild(self, gid): return self._guild
    async def change_presence(self, **kwargs): self.presence = kwargs


@pytest.mark.asyncio
async def test_broadcast_start_posts_to_announcements_and_sets_presence(monkeypatch):
    ch = _FakeChannel()
    bot = _FakeBot(ch)
    monkeypatch.setattr(config, "GUILD_ID", 123456789)
    monkeypatch.setattr(config, "MAINTENANCE_TG_CHAT_IDS", [])  # no TG groups
    maintenance.start(level="hard", reason="test", eta="~5 min")
    result = await maintenance.broadcast_start(bot, maintenance.get_status())
    maintenance.end()
    assert result["discord"] is True
    assert len(ch.sent) == 1
    assert "🔒" in ch.sent[0]
    assert bot.presence is not None  # presence was set


@pytest.mark.asyncio
async def test_broadcast_end_announces_and_restores(monkeypatch):
    ch = _FakeChannel()
    bot = _FakeBot(ch)
    monkeypatch.setattr(config, "GUILD_ID", 123456789)
    monkeypatch.setattr(config, "MAINTENANCE_TG_CHAT_IDS", [])
    result = await maintenance.broadcast_end(bot, "New feature X")
    assert result["discord"] is True
    assert "New feature X" in ch.sent[0]



# ============================================================
#  Phase 3 — auto-resume announcement + streak protection
# ============================================================

@pytest.mark.asyncio
async def test_check_auto_resume_ends_and_announces_once(monkeypatch):
    ch = _FakeChannel()
    bot = _FakeBot(ch)
    monkeypatch.setattr(config, "GUILD_ID", 123456789)
    monkeypatch.setattr(config, "MAINTENANCE_TG_CHAT_IDS", [])
    maintenance.start(level="hard", window_minutes=120)
    # Force the window into the past.
    past = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=1)).isoformat()
    database.set_setting("maintenance_auto_end_at", past)

    resumed = await maintenance.check_and_handle_auto_resume(bot)
    assert resumed is True
    assert maintenance.is_active() is False
    assert database.get_setting("maintenance_active", "0") == "0"
    assert len(ch.sent) == 1                      # "we're back" announced once
    assert "back" in ch.sent[0].lower()
    # Idempotent: a second check does nothing (no double announcement).
    assert await maintenance.check_and_handle_auto_resume(bot) is False


def test_maintenance_day_bridges_a_missed_day_in_streak():
    """A day the platform was under maintenance must not break a streak."""
    import json
    uid = "streak_bridge_user"
    database.register_member(uid, "Bridge User")
    today = database._today_local()
    day = datetime.timedelta(days=1)

    # Practiced today and 2 days ago, but MISSED yesterday.
    database.set_setting("maintenance_days", "[]")
    database.update_streak(uid, today.isoformat(), 7)
    database.update_streak(uid, (today - 2 * day).isoformat(), 7)

    # Without maintenance, yesterday's gap breaks the streak at 1 (today only).
    cur, _ = database.get_streak(uid)
    assert cur == 1

    # Now mark YESTERDAY as a maintenance day → it bridges: today counts,
    # yesterday is forgiven (not counted, not breaking), 2-days-ago counts.
    database.set_setting("maintenance_days", json.dumps([(today - day).isoformat()]))
    database._recompute_streak(uid)
    cur, _ = database.get_streak(uid)
    assert cur == 2

    database.set_setting("maintenance_days", "[]")  # cleanup shared setting
