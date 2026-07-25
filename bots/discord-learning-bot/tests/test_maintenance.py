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


def test_auto_resume_failsafe_reports_live_and_clears():
    """If the auto-end window has elapsed, status must report live (so a
    forgotten `end` never leaves students locked out) and lazily clear."""
    maintenance.start(level="hard", window_minutes=120)
    assert maintenance.is_active() is True
    # Force the failsafe deadline into the past.
    past = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(minutes=1)).isoformat()
    database.set_setting("maintenance_auto_end_at", past)
    s = maintenance.get_status()
    assert s["state"] == "live"
    assert s.get("auto_ended") is True
    # Flag was lazily cleared.
    assert database.get_setting("maintenance_active", "0") == "0"
