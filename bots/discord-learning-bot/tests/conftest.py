"""Shared fixtures for pytest."""
import os
import sys

import pytest

# Ensure the bot package is importable from tests.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set required env vars before any src module is imported (config.py reads
# these at import time via os.getenv), mirroring discord-challenge-bot's
# conftest.py convention.
os.environ.setdefault("DISCORD_TOKEN", "test-token")
os.environ.setdefault("GUILD_ID", "1234567890")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("GROQ_API_KEY", "")
os.environ.setdefault("TIMEZONE", "UTC")


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Use a temporary SQLite database for each test, so tests never touch
    a real empire_english.db and never leak state between tests."""
    db_file = tmp_path / "test_empire_english.db"
    monkeypatch.setattr("src.config.DB_PATH", db_file)
    from src import database
    database.init_db()
    yield db_file


@pytest.fixture(autouse=True)
def clear_module_level_state():
    """features.py and verification.py both use plain module-level dicts
    for in-memory session state (exam DM stages, quiz cooldowns, voice
    sessions) rather than the database. Reset them before each test so
    no state leaks between tests regardless of run order."""
    from src import features, verification
    features._pending_exams.clear()
    verification._last_done_time.clear()
    verification._voice_sessions.clear()
    verification._pending_quizzes.clear()
    verification._pending_listening.clear()
    yield


@pytest.fixture(scope="session", autouse=True)
def load_curriculum():
    """Load the real curriculum data once for the whole test session.

    Deliberately uses the actual data/ and content/ JSON files (not mocks)
    so these tests catch real content regressions (e.g. a week silently
    losing its vocabulary, or a level's word counts drifting), the same
    way the challenge-bot's test_challenges_json_valid() exercises its
    real data/challenges.json rather than a fixture double.
    """
    from src import curriculum
    curriculum.load_all()
    yield curriculum
