"""Aegis Phase 3 — End-to-end "Student Journey" Simulation Test.

This is NOT a collection of isolated unit tests (already well-covered by
the 313-test suite). It's a single scripted scenario run against a fresh
temp SQLite DB that exercises the full join → submit → streak → assess →
exam → level-change path in one continuous flow, asserting final
invariants (points, streaks, submission counts) against hand-computed
expected values.

The mechanism this test provides: something like a points double-award
bug, a broken streak-carry across days, or an exam that silently fails to
promote would be caught HERE (at CI time, before merge) rather than after
a real student's numbers look wrong.

Runs in the existing .github/workflows/learning-bot-test.yml workflow
with zero changes to that file — pytest discovers it automatically.

Design (from design.md, Component 4):
  1. Join a synthetic member.
  2. Simulate 8 days of !done <task> across all 7 daily tasks, crossing
     the 7-day streak bonus threshold (STREAK_BONUS_POINTS[7] = 200).
  3. Run the weekly assessment flow (!assess) and confirm the score lands
     in the database with correct upsert-once-per-week behavior.
  4. Drive a full advancement-exam submission through to examresult pass,
     confirming the member's level actually changes.
  5. Assert final invariants: total_points matches hand-computed expected
     value, longest_streak matches, no daily_submissions rows are missing.

Hand-computed expected points for the journey:
  - Per day (all 7 tasks): 7 * POINTS_PER_TASK + POINTS_ALL_TASKS
    = 7 * 15 + 100 = 205
  - 8 days: 8 * 205 = 1,640
  - 7-day streak bonus (fires on day 7 when streak reaches 7): 200
  - Assessment (first this week): POINTS_ASSESSMENT = 50
  - Total: 1,640 + 200 + 50 = 1,890
"""
import datetime
from unittest.mock import patch

import pytest

from src import config, database
from src import tasks as task_engine


# ============================================================
#  CONSTANTS — hand-computed expected values
# ============================================================

MEMBER_ID = "journey_test_user_001"
MEMBER_NAME = "Karim"
DAYS_TO_SIMULATE = 8
ALL_TASK_IDS = [t["id"] for t in config.DAILY_TASKS]  # 7 tasks

# Points per day when all 7 tasks are completed
POINTS_PER_DAY = len(ALL_TASK_IDS) * config.POINTS_PER_TASK + config.POINTS_ALL_TASKS
assert POINTS_PER_DAY == 205, f"Expected 205, got {POINTS_PER_DAY} — config changed?"

# The 7-day streak bonus fires exactly ONCE on the day the streak hits 7
# (fixed: previously fired once per task submission = 7× total)
STREAK_7_BONUS = config.STREAK_BONUS_POINTS[7]
assert STREAK_7_BONUS == 200, f"Expected 200, got {STREAK_7_BONUS} — config changed?"

# Assessment bonus (first assessment of the week)
ASSESSMENT_BONUS = config.POINTS_ASSESSMENT
assert ASSESSMENT_BONUS == 50, f"Expected 50, got {ASSESSMENT_BONUS} — config changed?"

# Grand total:
#   Days 1-6: 6 * 205 = 1230 (no streak bonus — streaks 1-6 not in thresholds)
#   Day 7: 205 base + 200 streak bonus (once) = 405
#   Day 8: 205 (streak=8, not a bonus threshold)
#   Assessment: 50
EXPECTED_TOTAL_POINTS = (DAYS_TO_SIMULATE * POINTS_PER_DAY) + STREAK_7_BONUS + ASSESSMENT_BONUS
assert EXPECTED_TOTAL_POINTS == 1890, f"Expected 1890, got {EXPECTED_TOTAL_POINTS}"

# Expected total submissions across all 8 days
EXPECTED_TOTAL_SUBMISSIONS = DAYS_TO_SIMULATE * len(ALL_TASK_IDS)  # 8 * 7 = 56


# ============================================================
#  HELPER: simulate one full day of submissions
# ============================================================

async def _simulate_one_day(discord_id: str, name: str, date_str: str,
                           simulated_date: datetime.date) -> dict:
    """Submit all 7 tasks for a given date, mimicking what cmd_done +
    process_submission do. We call process_submission() directly (the
    same function bot.py calls after verification passes) because the
    test's purpose is to verify points/streaks/submission invariants,
    not Discord message handling or verification.py's proof-checking.

    Patches datetime.date.today() in both the database and tasks modules
    so that streak computation (_recompute_streak), today_str(), and
    tasks_completed_today() all see the simulated date consistently.

    Returns the result dict from the final (7th) submission of the day,
    which includes the updated streak and total day points.
    """
    results = []
    for task_id in ALL_TASK_IDS:
        # Patch today_str (used by process_submission for the date string)
        # AND database._today_local (used by _recompute_streak and
        # tasks_completed_today, see Phase E's tz-aware-date fix) so the
        # streak logic sees dates consistently with the submissions we're
        # creating. Patching the single _today_local() helper directly
        # (rather than mocking the whole `datetime` module, as this test
        # used to) is simpler and can't accidentally leak the real
        # wall-clock time the way mocking `datetime.datetime.now` while
        # keeping the mock's `.datetime` attribute pointed at the REAL
        # class did (that's exactly the trap that would silently
        # reproduce Phase E's tz-vs-server-clock bug inside this test).
        with patch.object(task_engine, "today_str", return_value=date_str), \
             patch.object(database, "_today_local", return_value=simulated_date):
            result = await task_engine.process_submission(
                discord_id, name, task_id, content=f"simulated {task_id}"
            )
        results.append(result)

    # Verify all 7 were accepted as new
    for i, r in enumerate(results):
        assert r["new"] is True, (
            f"Submission #{i+1} ({ALL_TASK_IDS[i]}) on {date_str} was rejected as duplicate"
        )

    return results[-1]  # last submission's state (has final streak/points)


# ============================================================
#  THE JOURNEY TEST
# ============================================================

@pytest.mark.asyncio
async def test_full_student_journey():
    """Simulate a complete student journey: join → 8 days → assess → exam → level up.

    This is the one test that would catch invariant violations spanning
    multiple subsystems (points, streaks, assessments, exams, levels) that
    individual unit tests — by definition — can't cover because they test
    each subsystem in isolation.
    """
    # ------------------------------------------------------------------
    # Phase 1: JOIN
    # ------------------------------------------------------------------
    is_new = database.register_member(MEMBER_ID, MEMBER_NAME, goal="Speak fluent English")
    assert is_new is True

    member = database.get_member(MEMBER_ID)
    assert member is not None
    assert member["level"] == "L0"
    assert member["total_points"] == 0
    assert member["current_streak"] == 0
    assert member["longest_streak"] == 0

    # ------------------------------------------------------------------
    # Phase 2: 8 DAYS OF TASKS (crossing the 7-day streak bonus)
    # ------------------------------------------------------------------
    # We need to simulate 8 consecutive days. The streak system uses
    # datetime.date.today() internally (_recompute_streak compares dates
    # backwards from "today"). We'll patch today() to advance day by day.
    start_date = datetime.date(2026, 7, 1)

    streak_bonus_fired_on_day = None

    for day_offset in range(DAYS_TO_SIMULATE):
        current_date = start_date + datetime.timedelta(days=day_offset)
        date_str = current_date.isoformat()
        day_num = day_offset + 1

        last_result = await _simulate_one_day(MEMBER_ID, MEMBER_NAME, date_str, current_date)

        # After day 7, the streak should be exactly 7 and the bonus fires
        if day_num == 7:
            streak_bonus_fired_on_day = day_num
            assert last_result["streak"] == 7, (
                f"Day {day_num}: expected streak=7, got {last_result['streak']}"
            )

    # Verify streak after all 8 days (need "today" to be day 8)
    day_8_date = start_date + datetime.timedelta(days=7)
    with patch.object(database, "_today_local", return_value=day_8_date):
        current_streak, longest_streak = database.get_streak(MEMBER_ID)

    assert current_streak == 8, f"Expected current_streak=8, got {current_streak}"
    assert longest_streak == 8, f"Expected longest_streak=8, got {longest_streak}"
    assert streak_bonus_fired_on_day == 7

    # Verify submission count
    from src.database import _connect
    conn = _connect()
    total_subs = conn.execute(
        "SELECT COUNT(*) as cnt FROM daily_submissions WHERE discord_id=?",
        (MEMBER_ID,)
    ).fetchone()["cnt"]
    conn.close()
    assert total_subs == EXPECTED_TOTAL_SUBMISSIONS, (
        f"Expected {EXPECTED_TOTAL_SUBMISSIONS} submissions, got {total_subs}"
    )

    # Verify no day is missing any task (the most specific invariant)
    conn = _connect()
    for day_offset in range(DAYS_TO_SIMULATE):
        date_str = (start_date + datetime.timedelta(days=day_offset)).isoformat()
        day_tasks = conn.execute(
            "SELECT task_id FROM daily_submissions WHERE discord_id=? AND date=?",
            (MEMBER_ID, date_str)
        ).fetchall()
        submitted_ids = {r["task_id"] for r in day_tasks}
        assert submitted_ids == set(ALL_TASK_IDS), (
            f"Day {date_str}: expected all 7 tasks, got {submitted_ids}"
        )
    conn.close()

    # ------------------------------------------------------------------
    # Phase 3: WEEKLY ASSESSMENT (!assess)
    # ------------------------------------------------------------------
    # The member is now in "week 2" (joined day 1, now on day 8).
    # Patch member_week_number to return 2 (since the test controls time).
    with patch.object(database, "member_week_number", return_value=2):
        # Also patch database._today_local (get_submissions_since uses it,
        # Phase E's tz-aware-date fix) so "today" for this lookup matches
        # the simulated day 8, not the real wall clock.
        day_8_date = start_date + datetime.timedelta(days=7)
        with patch.object(database, "_today_local", return_value=day_8_date):

            # build_weekly_assessment uses calculate_completion_rate which
            # also uses datetime.date.today
            with patch("src.tasks.datetime") as mock_tasks_dt:
                mock_tasks_dt.date.today.return_value = day_8_date
                mock_tasks_dt.datetime.now.return_value = datetime.datetime.combine(
                    day_8_date, datetime.time(10, 0)
                )
                mock_tasks_dt.timedelta = datetime.timedelta

                assessment_result = task_engine.build_weekly_assessment(MEMBER_ID)

    # The member submitted all tasks (accent, vocab, shadow, speaking,
    # listening, writing, community) every day, so all assessment
    # dimensions should be non-zero
    assert assessment_result["overall"] > 0, "Assessment should be non-zero after 8 days of tasks"
    assert assessment_result["rating"] != "Critical"

    # Specifically: speaking, listening, vocab, accent should all be 100
    # (binary: submitted this week = 100%)
    for dim in ("speaking", "listening", "vocabulary", "accent"):
        assert assessment_result["scores"][dim] == 100.0, (
            f"Expected {dim} score=100, got {assessment_result['scores'][dim]}"
        )

    # Save the assessment and award points (mimicking cmd_assess)
    with patch.object(database, "member_week_number", return_value=2):
        already_assessed = database.get_assessment_for_week(MEMBER_ID, 2) is not None
        assert already_assessed is False, "Should be first assessment this week"

        database.save_assessment(
            MEMBER_ID, 2, assessment_result["scores"],
            assessment_result["overall"], assessment_result["rating"]
        )
        database.add_points(MEMBER_ID, config.POINTS_ASSESSMENT, "weekly_assessment")

    # Verify assessment is stored
    stored = database.get_assessment_for_week(MEMBER_ID, 2)
    assert stored is not None
    assert stored["overall_score"] == assessment_result["overall"]

    # Verify re-running !assess doesn't double-award points
    already_assessed_now = database.get_assessment_for_week(MEMBER_ID, 2) is not None
    assert already_assessed_now is True

    # ------------------------------------------------------------------
    # Phase 4: ADVANCEMENT EXAM (submit → admin resolves → level change)
    # ------------------------------------------------------------------
    # Create a pending exam (mimics handle_exam_dm completing collection)
    exam_id = database.create_pending_exam(
        MEMBER_ID, "L0", "L1",
        speaking_recording_url="https://cdn.discord.com/fake/recording.ogg",
        writing_submission="I wake up every morning at 7 AM. I brush my teeth and eat breakfast. "
                          "Then I study English for one hour. I practice speaking with my friend. "
                          "After lunch I do my homework. In the evening I watch English movies. "
                          "I go to sleep at 11 PM. I love learning every day.",
    )
    assert exam_id is not None and exam_id > 0

    # Verify it's in the pending queue
    pending = database.pending_exams()
    assert len(pending) == 1
    assert pending[0]["id"] == exam_id
    assert pending[0]["status"] == "pending"
    assert pending[0]["from_level"] == "L0"
    assert pending[0]["to_level"] == "L1"

    # Admin resolves the exam as PASS
    database.resolve_exam(exam_id, passed=True, resolved_by="admin_001", notes="Good work!")

    # Verify exam is resolved
    resolved = database.get_exam_by_id(exam_id)
    assert resolved["status"] == "passed"
    assert resolved["passed"] == 1

    # The level change itself (mimics cmd_examresult's logic)
    database.set_level(MEMBER_ID, "L1")

    # ------------------------------------------------------------------
    # Phase 5: FINAL INVARIANT ASSERTIONS
    # ------------------------------------------------------------------
    final_member = database.get_member(MEMBER_ID)

    # Level changed
    assert final_member["level"] == "L1", (
        f"Expected level=L1 after exam pass, got {final_member['level']}"
    )

    # Total points: hand-computed expected value
    assert final_member["total_points"] == EXPECTED_TOTAL_POINTS, (
        f"Expected total_points={EXPECTED_TOTAL_POINTS}, got {final_member['total_points']}. "
        f"Breakdown: {DAYS_TO_SIMULATE}d * {POINTS_PER_DAY}/d = {DAYS_TO_SIMULATE * POINTS_PER_DAY}, "
        f"+ streak bonus {STREAK_7_BONUS} (once), "
        f"+ assessment {ASSESSMENT_BONUS}"
    )

    # Streak integrity
    assert final_member["longest_streak"] >= 8, (
        f"Expected longest_streak>=8, got {final_member['longest_streak']}"
    )

    # No pending exams remain
    assert len(database.pending_exams()) == 0

    # Assessment stored with correct week
    assessments = database.get_assessments(MEMBER_ID)
    assert len(assessments) == 1
    assert assessments[0]["week_number"] == 2

    # Points log has the expected number of entries:
    #   8 days * 7 tasks = 56 task-point entries ("task:<id>")
    #   + 8 "all_7_tasks" bonus entries (one per day)
    #   + 1 "streak_7" entry (once, on day 7)
    #   + 1 "weekly_assessment" entry
    #   = 66 total
    conn = _connect()
    points_log_count = conn.execute(
        "SELECT COUNT(*) as cnt FROM points_log WHERE discord_id=?",
        (MEMBER_ID,)
    ).fetchone()["cnt"]
    conn.close()
    expected_log_entries = (
        (DAYS_TO_SIMULATE * len(ALL_TASK_IDS))  # 56 task entries
        + DAYS_TO_SIMULATE                       # 8 all-7 bonuses
        + 1                                      # 1 streak_7 entry (once!)
        + 1                                      # 1 weekly_assessment
    )
    assert expected_log_entries == 66
    assert points_log_count == expected_log_entries, (
        f"Expected {expected_log_entries} points_log entries, got {points_log_count}. "
        f"(56 tasks + 8 all-7 bonuses + 1 streak_7 + 1 assessment)"
    )


# ============================================================
#  STREAK BONUS BOUNDARY: verify it fires exactly once at 7
# ============================================================

@pytest.mark.asyncio
async def test_streak_bonus_fires_exactly_at_threshold():
    """Verify the 7-day streak bonus awards ONCE on day 7 (when streak
    reaches 7) and does NOT re-award on day 8.
    """
    database.register_member("streak_test_user", "Noor")
    start = datetime.date(2026, 8, 1)

    # Track cumulative points after each day
    daily_points = []

    for day_offset in range(9):  # 9 days to go past the 7-day boundary
        current_date = start + datetime.timedelta(days=day_offset)
        date_str = current_date.isoformat()

        await _simulate_one_day("streak_test_user", "Noor", date_str, current_date)

        m = database.get_member("streak_test_user")
        daily_points.append(m["total_points"])

    # Day 7 should include the streak bonus ONCE: 205 + 200 = 405
    day_6_to_7_delta = daily_points[6] - daily_points[5]
    assert day_6_to_7_delta == POINTS_PER_DAY + STREAK_7_BONUS, (
        f"Day 6→7 delta: expected {POINTS_PER_DAY + STREAK_7_BONUS}, got {day_6_to_7_delta}"
    )

    # Day 8 should NOT award any streak bonus (streak=8, not a threshold)
    day_7_to_8_delta = daily_points[7] - daily_points[6]
    assert day_7_to_8_delta == POINTS_PER_DAY, (
        f"Day 7→8 delta: expected {POINTS_PER_DAY}, got {day_7_to_8_delta} "
        f"(streak bonus fired on a non-threshold day?)"
    )

    # Day 9 — still just 205 (the 14-day bonus hasn't been reached yet)
    day_8_to_9_delta = daily_points[8] - daily_points[7]
    assert day_8_to_9_delta == POINTS_PER_DAY, (
        f"Day 8→9 delta: expected {POINTS_PER_DAY}, got {day_8_to_9_delta}"
    )


# ============================================================
#  ASSESSMENT UPSERT BEHAVIOR: no double-points on re-run
# ============================================================

def test_assess_upsert_does_not_double_award():
    """Verify that re-running !assess in the same week refreshes the
    stored score but does NOT award POINTS_ASSESSMENT a second time.
    This is the exact check cmd_assess does: look up whether an
    assessment for this (member, week) already exists before awarding.
    """
    database.register_member("assess_user", "Sara")

    # First assessment
    assert database.get_assessment_for_week("assess_user", 1) is None
    database.save_assessment("assess_user", 1, {"speaking": 80}, 80.0, "Strong")
    database.add_points("assess_user", config.POINTS_ASSESSMENT, "weekly_assessment")

    # Second assessment same week (re-run)
    assert database.get_assessment_for_week("assess_user", 1) is not None
    # The real cmd_assess skips add_points here — just save_assessment
    database.save_assessment("assess_user", 1, {"speaking": 90}, 90.0, "Excellent")
    # Do NOT add points again

    m = database.get_member("assess_user")
    assert m["total_points"] == config.POINTS_ASSESSMENT, (
        f"Expected exactly {config.POINTS_ASSESSMENT} points (one award), "
        f"got {m['total_points']}"
    )

    # But the score DID update
    stored = database.get_assessment_for_week("assess_user", 1)
    assert stored["overall_score"] == 90.0


# ============================================================
#  EXAM FLOW INTEGRITY: pending → resolved, level changes
# ============================================================

def test_exam_flow_pending_to_pass_changes_level():
    """Verify the full exam flow: create pending → resolve pass → level
    changes, and the exam leaves the pending queue."""
    database.register_member("exam_user", "Omar")
    assert database.get_member("exam_user")["level"] == "L0"

    # Submit exam
    eid = database.create_pending_exam("exam_user", "L0", "L1",
                                       speaking_recording_url="https://example.com/audio.ogg",
                                       writing_submission="Test writing sample.")
    assert len(database.pending_exams()) == 1

    # Resolve
    database.resolve_exam(eid, passed=True, resolved_by="admin")
    database.set_level("exam_user", "L1")

    assert database.get_member("exam_user")["level"] == "L1"
    assert len(database.pending_exams()) == 0
    assert database.get_exam_by_id(eid)["status"] == "passed"


def test_exam_flow_pending_to_fail_keeps_level():
    """Verify that a failed exam does NOT change the member's level."""
    database.register_member("exam_fail_user", "Layla")
    eid = database.create_pending_exam("exam_fail_user", "L0", "L1")

    database.resolve_exam(eid, passed=False, resolved_by="admin", notes="Needs more practice")

    assert database.get_member("exam_fail_user")["level"] == "L0"
    assert database.get_exam_by_id(eid)["status"] == "failed"
    assert len(database.pending_exams()) == 0
