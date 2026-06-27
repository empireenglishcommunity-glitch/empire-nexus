"""Tests for src/ai_coach.py — AI coaching with fallback."""
from src import ai_coach


def test_feedback_returns_string():
    """Without a Groq key, should return a built-in fallback message."""
    result = ai_coach.feedback("TestUser", 1, 8, "Wake up early")
    assert isinstance(result, str)
    assert len(result) > 5


def test_feedback_low_feeling():
    """Low feeling (<=4) should trigger empathetic fallback."""
    result = ai_coach.feedback("TestUser", 3, 2, "No sugar")
    assert isinstance(result, str)
    assert len(result) > 5


def test_daily_intro_returns_string():
    result = ai_coach.daily_intro(1, "Wake up early")
    assert isinstance(result, str)
    assert len(result) > 5


def test_weekly_recap_returns_string():
    stats = {"active": 10, "done": 45, "champion": "Alice"}
    result = ai_coach.weekly_recap(1, stats)
    assert isinstance(result, str)
    assert "1" in result or "الأسبوع" in result
