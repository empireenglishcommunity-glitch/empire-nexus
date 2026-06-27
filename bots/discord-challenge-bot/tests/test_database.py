"""Tests for src/database.py — SQLite operations."""
from src import database


def test_register_new_user():
    database.register("u1", "Alice", "Speak English fluently")
    p = database.get_participant("u1")
    assert p is not None
    assert p["username"] == "Alice"
    assert p["goal"] == "Speak English fluently"


def test_register_updates_username():
    database.register("u1", "Alice", "goal1")
    database.register("u1", "Alice2", "")
    p = database.get_participant("u1")
    assert p["username"] == "Alice2"
    # Goal should NOT be overwritten with empty string
    assert p["goal"] == "goal1"


def test_register_updates_goal_when_provided():
    database.register("u1", "Alice", "goal1")
    database.register("u1", "Alice", "goal2")
    p = database.get_participant("u1")
    assert p["goal"] == "goal2"


def test_log_done_new():
    database.register("u1", "Alice")
    result = database.log_done("u1", "Alice", 1, 8)
    assert result is True


def test_log_done_duplicate():
    database.register("u1", "Alice")
    database.log_done("u1", "Alice", 1, 8)
    result = database.log_done("u1", "Alice", 1, 9)
    assert result is False  # already logged


def test_completed_count():
    database.register("u1", "Alice")
    assert database.completed_count("u1") == 0
    database.log_done("u1", "Alice", 1, 5)
    database.log_done("u1", "Alice", 2, 7)
    database.log_done("u1", "Alice", 3, 9)
    assert database.completed_count("u1") == 3


def test_current_streak_empty():
    database.register("u1", "Alice")
    assert database.current_streak("u1") == 0


def test_current_streak_consecutive():
    database.register("u1", "Alice")
    for day in range(1, 6):
        database.log_done("u1", "Alice", day, 7)
    assert database.current_streak("u1") == 5


def test_current_streak_with_gap():
    database.register("u1", "Alice")
    database.log_done("u1", "Alice", 1, 7)
    database.log_done("u1", "Alice", 2, 7)
    # Gap at day 3
    database.log_done("u1", "Alice", 4, 7)
    database.log_done("u1", "Alice", 5, 7)
    database.log_done("u1", "Alice", 6, 7)
    # Streak ending at latest = 4,5,6 = 3
    assert database.current_streak("u1") == 3


def test_current_streak_single_day():
    database.register("u1", "Alice")
    database.log_done("u1", "Alice", 10, 5)
    assert database.current_streak("u1") == 1


def test_leaderboard_ordering():
    database.register("u1", "Alice")
    database.register("u2", "Bob")
    database.register("u3", "Charlie")
    database.log_done("u1", "Alice", 1, 5)
    database.log_done("u2", "Bob", 1, 5)
    database.log_done("u2", "Bob", 2, 5)
    database.log_done("u3", "Charlie", 1, 5)
    database.log_done("u3", "Charlie", 2, 5)
    database.log_done("u3", "Charlie", 3, 5)

    lb = database.leaderboard(10)
    assert lb[0] == ("Charlie", 3)
    assert lb[1] == ("Bob", 2)
    assert lb[2] == ("Alice", 1)


def test_leaderboard_limit():
    for i in range(15):
        uid = f"u{i}"
        database.register(uid, f"User{i}")
        database.log_done(uid, f"User{i}", 1, 5)
    lb = database.leaderboard(5)
    assert len(lb) == 5


def test_all_participants():
    database.register("u1", "Alice")
    database.register("u2", "Bob")
    all_p = database.all_participants()
    ids = [p[0] for p in all_p]
    assert "u1" in ids
    assert "u2" in ids


def test_get_participant_not_found():
    assert database.get_participant("nonexistent") is None
