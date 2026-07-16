"""Tests for adaptive_engine.py (Dhaka').

Includes a regression test for D034: check_and_adjust() must pass
discord_id through to is_feature_enabled(), or an allowlist-scoped
rollout of tatawwur_adaptive silently disables the whole feature for
every member, even ones on the allowlist. Found live during Masar
M4.4's Ghost Bot verification (2026-07-16).
"""
import datetime

from src import adaptive_engine, database


def _seed_scores(discord_id: str, score: float, days: int = 7):
    today = datetime.date.today()
    for i in range(days):
        d = (today - datetime.timedelta(days=days - 1 - i)).isoformat()
        database.store_pronunciation_score(
            discord_id, d, f"task_{i}", score, "expected", "transcript",
        )


def test_check_and_adjust_returns_none_when_flag_globally_disabled():
    database.register_member("u1", "Alice")
    _seed_scores("u1", 90.0)
    assert adaptive_engine.check_and_adjust("u1") is None


def test_check_and_adjust_works_when_flag_globally_enabled():
    database.register_member("u1", "Alice")
    database.set_feature_flag("tatawwur_adaptive", True, allowed_ids="", updated_by="test")
    _seed_scores("u1", 90.0)
    adjustment = adaptive_engine.check_and_adjust("u1")
    assert adjustment is not None
    assert adjustment["direction"] == "up"


def test_check_and_adjust_works_for_a_member_on_an_allowlist_scoped_flag():
    """Regression test for D034: an allowlist-scoped flag (the exact
    'beta squad rollout' use case allowed_ids exists for) must still
    work for a member who IS on that allowlist, not silently no-op."""
    database.register_member("u1", "Alice")
    database.set_feature_flag("tatawwur_adaptive", True, allowed_ids="u1", updated_by="test")
    _seed_scores("u1", 90.0)
    adjustment = adaptive_engine.check_and_adjust("u1")
    assert adjustment is not None
    assert adjustment["direction"] == "up"


def test_check_and_adjust_still_rejects_members_not_on_the_allowlist():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.set_feature_flag("tatawwur_adaptive", True, allowed_ids="u1", updated_by="test")
    _seed_scores("u2", 90.0)
    assert adaptive_engine.check_and_adjust("u2") is None


def test_check_and_adjust_direction_down():
    database.register_member("u1", "Alice")
    database.set_feature_flag("tatawwur_adaptive", True, allowed_ids="u1", updated_by="test")
    database.update_member("u1", difficulty_level=2)
    _seed_scores("u1", 40.0)
    adjustment = adaptive_engine.check_and_adjust("u1")
    assert adjustment is not None
    assert adjustment["direction"] == "down"
