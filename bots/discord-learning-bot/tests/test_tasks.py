"""Tests for src/tasks.py — task generation, formatting, and scoring logic.

Focuses on the pure/sync helpers (formatting, scoring, chunking) that don't
require a live Discord connection. generate_daily_tasks() and
process_submission() are async and hit ai_engine (network) — covered via
a smoke-level async test with GROQ/GEMINI keys empty (falls back gracefully).
"""
import datetime

import pytest

from src import config, database, tasks


# ============================================================
#  BILINGUAL HELPER
# ============================================================

def test_bl_combines_english_and_arabic():
    assert tasks.bl("Hello", "أهلا") == "Hello / أهلا"


# ============================================================
#  TIME UTILITIES
# ============================================================

def test_today_str_is_iso_format():
    s = tasks.today_str()
    # Should parse cleanly as an ISO date.
    datetime.date.fromisoformat(s)


def test_current_day_name_is_valid_weekday():
    valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
    assert tasks.current_day_name() in valid_days


def test_current_week_for_member_delegates_to_database():
    database.register_member("u1", "Alice")
    assert tasks.current_week_for_member("u1") == database.member_week_number("u1")


# ============================================================
#  DISCORD MESSAGE CHUNKING (real bug fix regression)
# ============================================================

def _sample_task_data(level="L0", total_minutes=55):
    return {
        "date": "2026-07-12",
        "day_name": "Saturday",
        "level": level,
        "week": 1,
        "tasks": [
            {"id": "accent", "title": "Accent Drill", "content": "x" * 300, "duration_min": 10},
            {"id": "vocab", "title": "Vocabulary", "content": "y" * 300, "duration_min": 10},
            {"id": "shadow", "title": "Shadowing", "content": "z" * 300, "duration_min": 10},
            {"id": "speaking", "title": "Speaking", "content": "a" * 300, "duration_min": 10},
            {"id": "listening", "title": "Listening", "content": "b" * 300, "duration_min": 8},
            {"id": "writing", "title": "Writing", "content": "c" * 300, "duration_min": 7},
            {"id": "community", "title": "Community", "content": "d" * 300, "duration_min": 5},
        ],
        "total_minutes": total_minutes,
    }


def test_format_daily_post_chunks_all_under_discord_limit():
    """Regression test for a real, previously-shipped bug: channel.send()
    raises discord.HTTPException above 2000 chars, and bot.py only logged
    that exception rather than surfacing it — meaning daily tasks were
    silently failing to post for most level/week combinations. Every
    chunk this function returns must stay under the limit."""
    chunks = tasks.format_daily_post_chunks(_sample_task_data())
    assert len(chunks) >= 1
    for chunk in chunks:
        assert len(chunk) <= tasks.DISCORD_MESSAGE_LIMIT


def test_format_daily_post_chunks_never_splits_a_task_mid_content():
    """Each task block ('1\ufe0f\u20e3 Accent Drill...') must appear intact and
    exactly once across the joined chunks — never truncated or duplicated."""
    task_data = _sample_task_data()
    chunks = tasks.format_daily_post_chunks(task_data)
    joined = "\n\n".join(chunks)
    for task in task_data["tasks"]:
        assert joined.count(task["title"]) == 1


def test_format_daily_post_chunks_platform_link_and_discord_content():
    """Darb Phase 0: the daily message has exactly ONE practice-platform
    link; the 4 platform tasks (accent/vocab/shadowing/listening) are
    listed by title only (their content lives on the platform); the 3
    Discord tasks (speaking/writing/community) keep their full content."""
    task_data = _sample_task_data()
    joined = "\n\n".join(tasks.format_daily_post_chunks(task_data))
    # Exactly one practice-platform link in the whole message.
    assert joined.count("practice.empireenglish.online") == 1
    # Discord tasks keep their prompts/content.
    for tid in ("speaking", "writing", "community"):
        content = next(t["content"] for t in task_data["tasks"] if t["id"] == tid)
        assert content in joined
    # Platform tasks' content is NOT dumped into the Discord message
    # (it lives on the platform; only the title/link appear here).
    for tid in ("accent", "vocab", "shadow", "listening"):
        content = next(t["content"] for t in task_data["tasks"] if t["id"] == tid)
        assert content not in joined


def test_format_daily_post_returns_single_joined_string():
    """format_daily_post() is retained for non-Discord callers (logging,
    tests) — confirm it's just the chunks joined together."""
    task_data = _sample_task_data()
    joined_via_helper = tasks.format_daily_post(task_data)
    joined_manually = "\n\n".join(tasks.format_daily_post_chunks(task_data))
    assert joined_via_helper == joined_manually


def test_format_daily_post_chunks_short_content_fits_one_chunk():
    """A realistically short day (not the padded worst-case above) should
    fit in a single chunk, including the footer."""
    task_data = {
        "date": "2026-07-12", "day_name": "Saturday", "level": "L0", "week": 1,
        "tasks": [{"id": "vocab", "title": "Vocab", "content": "short", "duration_min": 10}],
        "total_minutes": 10,
    }
    chunks = tasks.format_daily_post_chunks(task_data)
    assert len(chunks) == 1


# ============================================================
#  STREAK UPDATE FORMATTING
# ============================================================

def test_format_streak_update_shows_progress_bar():
    database.register_member("u1", "Alice")
    today = datetime.date.today().isoformat()
    database.log_submission("u1", today, "vocab")
    database.log_submission("u1", today, "writing")
    database.update_streak("u1", today, 2)
    msg = tasks.format_streak_update("u1", "Alice")
    assert "2/7" in msg
    assert "Alice" in msg


def test_format_streak_update_shows_bonus_at_milestone():
    database.register_member("u1", "Alice")
    today = datetime.date.today()
    for i in range(7):
        d = (today - datetime.timedelta(days=6 - i)).isoformat()
        database.update_streak("u1", d, 7)
    msg = tasks.format_streak_update("u1", "Alice")
    assert "STREAK BONUS" in msg
    assert str(config.STREAK_BONUS_POINTS[7]) in msg


def test_format_streak_update_no_bonus_line_off_milestone():
    database.register_member("u1", "Alice")
    today = datetime.date.today().isoformat()
    database.update_streak("u1", today, 3)
    msg = tasks.format_streak_update("u1", "Alice")
    assert "STREAK BONUS" not in msg


# ============================================================
#  COMPLETION RATE / SCORING
# ============================================================

def test_calculate_completion_rate_zero_when_no_submissions():
    database.register_member("u1", "Alice")
    assert tasks.calculate_completion_rate("u1", days=7) == 0


def test_calculate_completion_rate_full_week():
    database.register_member("u1", "Alice")
    today = datetime.date.today()
    for i in range(7):
        d = (today - datetime.timedelta(days=i)).isoformat()
        for task_id in ("accent", "vocab", "shadow", "speaking", "listening", "writing", "community"):
            database.log_submission("u1", d, task_id)
    assert tasks.calculate_completion_rate("u1", days=7) == 100.0


def test_calculate_completion_rate_partial():
    database.register_member("u1", "Alice")
    today_str = datetime.date.today().isoformat()
    # 1 of 7 tasks on 1 of 7 days = 1/49 ≈ 2.0%
    database.log_submission("u1", today_str, "vocab")
    rate = tasks.calculate_completion_rate("u1", days=7)
    assert 0 < rate < 100


def test_calculate_overall_score_weighted():
    scores = {
        "speaking": 100, "listening": 100, "vocabulary": 100,
        "accent": 100, "writing": 100, "completion": 100,
    }
    assert tasks.calculate_overall_score(scores) == 100.0


def test_calculate_overall_score_missing_dimension_treated_as_zero():
    scores = {"speaking": 100}  # everything else missing
    score = tasks.calculate_overall_score(scores)
    speaking_weight = next(d["weight"] for d in config.ASSESSMENT_DIMENSIONS if d["id"] == "speaking")
    assert score == round(100 * speaking_weight, 1)


def test_calculate_overall_score_none_values_treated_as_zero():
    scores = {"speaking": None, "listening": 80}
    score = tasks.calculate_overall_score(scores)
    assert score > 0  # should not raise on None, and listening still contributes


@pytest.mark.parametrize("score,expected", [
    (95, "Excellent"),
    (90, "Excellent"),
    (85, "Strong"),
    (80, "Strong"),
    (75, "Satisfactory"),
    (70, "Satisfactory"),
    (65, "At Risk"),
    (60, "At Risk"),
    (50, "Critical"),
    (0, "Critical"),
])
def test_score_to_rating_boundaries(score, expected):
    assert tasks.score_to_rating(score) == expected


# ============================================================
#  INACTIVE MEMBER DETECTION
# ============================================================

def test_check_inactive_members_empty_when_all_active():
    database.register_member("u1", "Alice")
    result = tasks.check_inactive_members()
    assert result == {}


def test_check_inactive_members_flags_by_threshold():
    database.register_member("u1", "Alice")
    old_time = (datetime.datetime.now() - datetime.timedelta(days=5)).isoformat()
    database.update_member("u1", last_active_at=old_time)
    result = tasks.check_inactive_members()
    # 5 days inactive should trigger every threshold <= 5 (1, 2, 3, 5)
    assert "reengagement_conversation" in result


# ============================================================
#  ASYNC SMOKE TEST (process_submission)
# ============================================================

@pytest.mark.asyncio
async def test_process_submission_new_awards_points():
    database.register_member("u1", "Alice")
    result = await tasks.process_submission("u1", "Alice", "vocab", content="test answer")
    assert result["new"] is True
    assert result["points"] >= config.POINTS_PER_TASK
    assert database.get_member("u1")["total_points"] >= config.POINTS_PER_TASK


@pytest.mark.asyncio
async def test_process_submission_duplicate_awards_no_points():
    database.register_member("u1", "Alice")
    await tasks.process_submission("u1", "Alice", "vocab")
    result = await tasks.process_submission("u1", "Alice", "vocab")
    assert result["new"] is False
    assert result["points"] == 0


@pytest.mark.asyncio
async def test_process_submission_all_seven_awards_bonus():
    database.register_member("u1", "Alice")
    task_ids = ["accent", "vocab", "shadow", "speaking", "listening", "writing", "community"]
    total_awarded = 0
    for task_id in task_ids:
        result = await tasks.process_submission("u1", "Alice", task_id)
        total_awarded += result["points"]
    # 7 tasks * POINTS_PER_TASK + POINTS_ALL_TASKS bonus on the 7th
    expected_min = 7 * config.POINTS_PER_TASK + config.POINTS_ALL_TASKS
    assert total_awarded >= expected_min


# ============================================================
#  WEEKLY ASSESSMENT SCORING (build_weekly_assessment)
# ============================================================
# Backs the !assess command (bot.py::cmd_assess), which never existed
# until it was added alongside these tests -- found via adversarial-input
# stress testing on database.save_assessment(), which had zero production
# callers despite weekly_assessment()'s DM and !help both telling members
# to run `!assess`.

def test_build_weekly_assessment_zero_when_nothing_submitted():
    database.register_member("u1", "Alice")
    result = tasks.build_weekly_assessment("u1")
    assert result["overall"] == 0.0
    assert result["rating"] == "Critical"
    assert result["submitted_tasks"] == []
    for dim_id in ("speaking", "listening", "vocabulary", "accent", "writing", "completion"):
        assert result["scores"][dim_id] == 0.0


def test_build_weekly_assessment_verified_tasks_score_full_marks():
    database.register_member("u1", "Alice")
    today = tasks.today_str()
    for task_id in ("speaking", "listening", "vocab", "accent"):
        database.log_submission("u1", today, task_id)

    result = tasks.build_weekly_assessment("u1")
    assert result["scores"]["speaking"] == 100.0
    assert result["scores"]["listening"] == 100.0
    assert result["scores"]["vocabulary"] == 100.0
    assert result["scores"]["accent"] == 100.0
    assert set(result["submitted_tasks"]) == {"speaking", "listening", "vocab", "accent"}


def test_build_weekly_assessment_uses_latest_writing_score():
    database.register_member("u1", "Alice")
    today = tasks.today_str()
    database.log_submission("u1", today, "writing", content="draft 1", score=40.0)

    result = tasks.build_weekly_assessment("u1")
    assert result["scores"]["writing"] == 40.0
    assert "writing" in result["submitted_tasks"]


def test_build_weekly_assessment_writing_without_score_counts_as_zero():
    """A writing submission logged without an AI score (e.g. evaluate_writing()
    failed/returned None) should not crash and should not silently count as
    a passing score -- but the submission itself DID happen (the row
    exists), so it still shows up in submitted_tasks; only the score is 0."""
    database.register_member("u1", "Alice")
    today = tasks.today_str()
    database.log_submission("u1", today, "writing", content="draft", score=None)

    result = tasks.build_weekly_assessment("u1")
    assert result["scores"]["writing"] == 0.0
    assert "writing" in result["submitted_tasks"]


def test_build_weekly_assessment_unregistered_member_does_not_crash():
    """No member row at all (never joined) -- should degrade to an
    all-zero assessment rather than raising, matching the codebase's
    established defensive-degradation pattern elsewhere."""
    result = tasks.build_weekly_assessment("never_joined")
    assert result["overall"] == 0.0
    assert result["submitted_tasks"] == []


def test_build_weekly_assessment_ignores_submissions_outside_window():
    database.register_member("u1", "Alice")
    old_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    database.log_submission("u1", old_date, "speaking")

    result = tasks.build_weekly_assessment("u1", days=7)
    assert result["scores"]["speaking"] == 0.0
    assert "speaking" not in result["submitted_tasks"]
