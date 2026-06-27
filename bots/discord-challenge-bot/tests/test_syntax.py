"""Syntax and import smoke tests — verify all modules compile cleanly."""
import importlib
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_import_config():
    mod = importlib.import_module("src.config")
    assert hasattr(mod, "DISCORD_TOKEN")
    assert hasattr(mod, "RANKS")


def test_import_database():
    mod = importlib.import_module("src.database")
    assert hasattr(mod, "init_db")
    assert hasattr(mod, "register")
    assert hasattr(mod, "log_done")


def test_import_challenges():
    mod = importlib.import_module("src.challenges")
    assert hasattr(mod, "load_challenges")
    assert hasattr(mod, "get_challenge")
    assert hasattr(mod, "current_day")


def test_import_ai_coach():
    mod = importlib.import_module("src.ai_coach")
    assert hasattr(mod, "feedback")
    assert hasattr(mod, "daily_intro")
    assert hasattr(mod, "weekly_recap")


def test_import_certificate():
    mod = importlib.import_module("src.certificate")
    assert hasattr(mod, "make_certificate")


def test_challenges_json_valid():
    """Ensure the JSON data file parses without error."""
    import json
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "challenges.json"
    )
    with open(data_path, encoding="utf-8") as f:
        data = json.load(f)
    assert "challenges" in data
    assert len(data["challenges"]) == 30
