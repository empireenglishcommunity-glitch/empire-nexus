"""Shared fixtures for pytest."""
import os
import sys
import tempfile

import pytest

# Ensure the bot package is importable from tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Override DB path to a temp file before any import touches it.
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("CHALLENGE_CHANNEL_ID", "1234567890")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("DAILY_POST_HOUR", "9")
os.environ.setdefault("TIMEZONE", "UTC")
os.environ.setdefault("START_DATE", "2026-06-01")


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Use a temporary SQLite database for each test."""
    db_file = str(tmp_path / "test_challenge.db")
    monkeypatch.setattr("src.config.DB_PATH", db_file)
    from src import database
    database.init_db()
    yield db_file
