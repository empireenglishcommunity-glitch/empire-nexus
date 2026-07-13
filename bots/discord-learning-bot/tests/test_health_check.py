"""Tests for scripts/health_check.py — Aegis Phase 2 (production-safe-deploys)."""
import datetime
import importlib.util
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

from src import database

# health_check.py lives in scripts/, outside the src/ package, so it's
# loaded the same way scripts/backup.py's own tests do -- by file path,
# not a normal import.
_SPEC = importlib.util.spec_from_file_location(
    "health_check", Path(__file__).resolve().parent.parent / "scripts" / "health_check.py"
)
health_check = importlib.util.module_from_spec(_SPEC)
sys.modules["health_check"] = health_check
_SPEC.loader.exec_module(health_check)


def test_check_database_ok_on_initialized_db():
    ok, message = health_check.check_database()
    assert ok is True
    assert "Database reachable" in message


def test_check_curriculum_ok_when_all_38_weeks_loaded():
    ok, message = health_check.check_curriculum()
    assert ok is True
    assert "38/38" in message


def test_check_commands_ok_when_above_minimum():
    ok, message = health_check.check_commands()
    assert ok is True
    assert "commands registered" in message


def test_check_heartbeat_fails_when_never_set():
    ok, message = health_check.check_heartbeat()
    assert ok is False
    assert "No heartbeat recorded" in message


def test_check_heartbeat_ok_when_fresh():
    database.set_setting("last_heartbeat", datetime.datetime.now(ZoneInfo("Asia/Dubai")).isoformat())
    ok, message = health_check.check_heartbeat()
    assert ok is True
    assert "fresh" in message


def test_check_heartbeat_fails_when_stale():
    stale = datetime.datetime.now(ZoneInfo("Asia/Dubai")) - datetime.timedelta(minutes=10)
    database.set_setting("last_heartbeat", stale.isoformat())
    ok, message = health_check.check_heartbeat()
    assert ok is False
    assert "stale" in message


def test_check_heartbeat_fails_gracefully_on_unparseable_value():
    """Found via manual live testing before writing this test: a
    corrupted/malformed heartbeat value must produce a clean failure
    report, not an unhandled exception that crashes the whole script."""
    database.set_setting("last_heartbeat", "not-a-real-timestamp")
    ok, message = health_check.check_heartbeat()
    assert ok is False
    assert "unparseable" in message


def test_main_returns_0_when_all_checks_pass():
    database.set_setting("last_heartbeat", datetime.datetime.now(ZoneInfo("Asia/Dubai")).isoformat())
    assert health_check.main() == 0


def test_main_returns_1_when_heartbeat_missing():
    # No heartbeat ever set in this test's fresh temp DB (per conftest.py's
    # per-test temp_db fixture) -- every other check passes, only this
    # one should fail, and that must be enough to fail the whole script.
    assert health_check.main() == 1
