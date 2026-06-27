"""Tests for src/challenges.py — challenge loading and day calculation."""
from datetime import date

from src import challenges, config


def test_load_challenges_returns_30():
    data = challenges.load_challenges()
    assert len(data["challenges"]) == 30


def test_all_days_present():
    data = challenges.load_challenges()
    days = {c["day"] for c in data["challenges"]}
    assert days == set(range(1, 31))


def test_all_challenges_have_required_keys():
    data = challenges.load_challenges()
    required = {"day", "week", "domain", "level", "task", "tip"}
    for c in data["challenges"]:
        assert required.issubset(set(c.keys())), f"Day {c.get('day')} missing keys"


def test_get_challenge_valid():
    c = challenges.get_challenge(1)
    assert c is not None
    assert c["day"] == 1
    assert c["task"]


def test_get_challenge_invalid_day():
    assert challenges.get_challenge(0) is None
    assert challenges.get_challenge(31) is None
    assert challenges.get_challenge(-5) is None


def test_current_day_no_start_date(monkeypatch):
    monkeypatch.setattr(config, "START_DATE", "")
    assert challenges.current_day() == 1


def test_current_day_day_one(monkeypatch):
    monkeypatch.setattr(config, "START_DATE", "2026-06-01")
    assert challenges.current_day(date(2026, 6, 1)) == 1


def test_current_day_day_fifteen(monkeypatch):
    monkeypatch.setattr(config, "START_DATE", "2026-06-01")
    assert challenges.current_day(date(2026, 6, 15)) == 15


def test_current_day_day_thirty(monkeypatch):
    monkeypatch.setattr(config, "START_DATE", "2026-06-01")
    assert challenges.current_day(date(2026, 6, 30)) == 30


def test_current_day_after_challenge(monkeypatch):
    monkeypatch.setattr(config, "START_DATE", "2026-06-01")
    assert challenges.current_day(date(2026, 7, 2)) == 0


def test_current_day_before_start(monkeypatch):
    monkeypatch.setattr(config, "START_DATE", "2026-06-15")
    assert challenges.current_day(date(2026, 6, 10)) == 0


def test_stars():
    assert "⭐" in challenges.stars(1)
    assert challenges.stars(4).count("⭐") == 4


def test_format_challenge():
    c = challenges.get_challenge(10)
    text = challenges.format_challenge(c)
    assert "10" in text
    assert c["task"] in text
    assert c["tip"] in text
    assert "!done" in text
