"""Tests for src/config.py — configuration loading and static learning-system
parameters (LEVELS, DAILY_TASKS, streak bonuses, etc.)."""
import os

from src import config


def test_paths_are_absolute():
    assert config.BASE_DIR.is_absolute()
    assert config.DATA_DIR.is_absolute()
    assert config.DB_PATH.is_absolute()


def test_all_four_levels_defined():
    assert set(config.LEVELS.keys()) == {"L0", "L1", "L2", "L3"}


def test_levels_have_required_fields():
    required = {
        "name", "name_ar", "emoji", "color", "duration_weeks",
        "daily_minutes_core", "daily_minutes_intensive",
        "vocab_target", "speaking_target_seconds", "advancement_score",
    }
    for level, info in config.LEVELS.items():
        missing = required - info.keys()
        assert not missing, f"{level} is missing fields: {missing}"


def test_l3_has_no_advancement_score():
    """L3 is mastery-tier, not advancement-gated — advancement_score and
    duration_weeks must both be None (ongoing, no next level to test into)."""
    assert config.LEVELS["L3"]["advancement_score"] is None
    assert config.LEVELS["L3"]["duration_weeks"] is None


def test_l0_to_l2_have_advancement_score():
    for level in ("L0", "L1", "L2"):
        assert config.LEVELS[level]["advancement_score"] is not None


def test_vocab_targets_increase_with_level():
    """Vocab target should strictly increase L0 < L1 < L2 < L3 — a level
    that isn't harder than the one before it would be a real design bug."""
    targets = [config.LEVELS[l]["vocab_target"] for l in ("L0", "L1", "L2", "L3")]
    assert targets == sorted(targets)
    assert len(set(targets)) == len(targets)  # strictly increasing, no ties


def test_speaking_targets_increase_with_level():
    targets = [config.LEVELS[l]["speaking_target_seconds"] for l in ("L0", "L1", "L2", "L3")]
    assert targets == sorted(targets)


def test_daily_tasks_has_seven_tasks_in_fixed_order():
    """The bot's whole daily loop assumes exactly 7 tasks, same order,
    every level (tasks.py builds them in this literal order)."""
    assert len(config.DAILY_TASKS) == 7
    ids = [t["id"] for t in config.DAILY_TASKS]
    assert ids == ["accent", "vocab", "shadow", "speaking", "listening", "writing", "community"]


def test_daily_tasks_have_required_fields():
    for task in config.DAILY_TASKS:
        assert task["id"]
        assert task["name"]
        assert task["name_ar"]
        assert task["emoji"]


def test_assessment_dimensions_weights_sum_to_one():
    """calculate_overall_score() in tasks.py assumes these weights sum to
    1.0 — if they drift, every weekly assessment's overall_score silently
    becomes wrong (too high or too low) without any error being raised."""
    total = sum(d["weight"] for d in config.ASSESSMENT_DIMENSIONS)
    assert abs(total - 1.0) < 1e-9


def test_streak_bonus_points_ascending():
    """Longer streaks must award more points than shorter ones."""
    days = sorted(config.STREAK_BONUS_POINTS.keys())
    points = [config.STREAK_BONUS_POINTS[d] for d in days]
    assert points == sorted(points)
    assert len(set(points)) == len(points)


def test_intervention_thresholds_ascending_days():
    days = sorted(config.INTERVENTION_THRESHOLDS.keys())
    assert days == [1, 2, 3, 5, 7]


def test_practice_platform_url_has_no_trailing_slash():
    """curriculum.py's URL builders assume no trailing slash and append
    their own '/' — a trailing slash here would produce double slashes
    in every generated practice-platform link."""
    assert not config.PRACTICE_PLATFORM_URL.endswith("/")


def test_bot_prefix_default():
    # BOT_PREFIX is read at import time; just confirm it resolves to a
    # non-empty string regardless of env (defaults to "!").
    assert config.BOT_PREFIX
