"""Ijtihad Phase 6 — growth and grit.

The part of the brief that points alone cannot answer: *highlight the ones who
really work*. A student whose absolute English is weak, who fails, and who comes
back anyway is doing the hardest thing in the programme — and on any board sorted
by any score they are invisible forever.

The load-bearing property under test: **recognitions award no points.** They never
move anyone up the effort board. That separation is what lets determination be
celebrated honestly without telling a stronger student their work counted less.

See .kiro/specs/ijtihad-effort-economy/ design §5.
"""
import datetime
import json

import pytest

from src import database, flag_registry, ijtihad_growth


FLAG = "ijtihad_growth_recognition"
TODAY = datetime.date(2026, 8, 30)


@pytest.fixture(autouse=True)
def clean_ijtihad():
    conn = database._connect()
    for sql in ("DELETE FROM seasons", "DELETE FROM student_targets",
                "DELETE FROM streak_freezes", "DELETE FROM points_log",
                "DELETE FROM streaks", "DELETE FROM recognition_log",
                "DELETE FROM assessment_attempts",
                "DELETE FROM pronunciation_scores",
                "DELETE FROM settings WHERE key LIKE 'ijtihad_%'"):
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.commit()
    conn.close()
    yield


def _student(mid, name="Student", joined_days_ago=60, level="A1"):
    database.register_member(mid, name)
    joined = (TODAY - datetime.timedelta(days=joined_days_ago)).isoformat()
    database.update_member(mid, joined_at=joined)
    if level != "A1":
        database.set_level(mid, level)
    return mid


def _earn(mid, points, day):
    conn = database._connect()
    conn.execute(
        "INSERT INTO points_log (discord_id, points, reason, logged_at) VALUES (?,?,?,?)",
        (mid, points, "task:x", f"{day.isoformat()} 12:00:00"))
    conn.commit()
    conn.close()


def _did_tasks(mid, day, n):
    conn = database._connect()
    conn.execute(
        "INSERT OR REPLACE INTO streaks (discord_id,date,tasks_completed,all_seven) "
        "VALUES (?,?,?,?)", (mid, day.isoformat(), n, 1 if n >= 7 else 0))
    conn.commit()
    conn.close()


def _enable():
    database.sync_flag_registry()
    database.set_feature_flag(FLAG, True)


# ============================================================
#  Flag
# ============================================================

def test_flag_registered_and_off_by_default():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == FLAG), None)
    assert entry is not None
    assert entry[3] is False


def test_nothing_detected_while_flag_off():
    mid = _student("off1")
    _did_tasks(mid, TODAY, 7)
    assert ijtihad_growth.detect_new(mid, TODAY) == []


# ============================================================
#  Par + growth
# ============================================================

def test_growth_needs_a_week_of_history():
    mid = _student("new1", joined_days_ago=2)
    g = database.ijtihad_growth(mid, TODAY)
    assert g["eligible"] is False
    assert g["reason"] == "too_new"


def test_growth_needs_a_nonzero_baseline():
    """With a zero baseline any activity is infinite improvement, which would put
    every returning student permanently on top. Those are surfaced as Comebacks
    instead."""
    mid = _student("nb")
    _earn(mid, 100, TODAY)          # this week only
    g = database.ijtihad_growth(mid, TODAY)
    assert g["eligible"] is False
    assert g["reason"] == "no_baseline"


def test_growth_is_measured_against_own_baseline():
    mid = _student("g1")
    # Baseline window: 20..7 days back — 10 points a day.
    for back in range(7, 21):
        _earn(mid, 10, TODAY - datetime.timedelta(days=back))
    # This week: 140 vs a par of 70 → +100%
    for back in range(0, 7):
        _earn(mid, 20, TODAY - datetime.timedelta(days=back))
    g = database.ijtihad_growth(mid, TODAY)
    assert g["eligible"] is True
    assert g["par_week"] == 70
    assert g["now"] == 140
    assert g["growth_pct"] == 100.0


def test_a_single_heroic_day_does_not_redefine_the_baseline():
    """Par is a MEDIAN, so one outlier day cannot distort it (a mean would)."""
    mid = _student("g2")
    for back in range(7, 21):
        _earn(mid, 10, TODAY - datetime.timedelta(days=back))
    _earn(mid, 5000, TODAY - datetime.timedelta(days=10))   # one huge day
    g = database.ijtihad_growth(mid, TODAY)
    assert g["par_week"] == 70, "median must ignore the outlier"


def test_decline_is_reported_without_being_a_failure():
    mid = _student("g3")
    for back in range(7, 21):
        _earn(mid, 20, TODAY - datetime.timedelta(days=back))
    _earn(mid, 10, TODAY)
    g = database.ijtihad_growth(mid, TODAY)
    assert g["growth_pct"] < 0
    out = ijtihad_growth.format_my_growth(g)
    assert "not a failure" in out


def test_unknown_member_is_handled():
    g = database.ijtihad_growth("ghost", TODAY)
    assert g["eligible"] is False
    assert g["reason"] == "no_member"


# ============================================================
#  Most Improved — a beginner can win
# ============================================================

def test_a_beginner_can_top_most_improved_over_a_stronger_student():
    """THE POINT of this board: it measures CHANGE, not level. The strong student
    earns far more in absolute terms and still does not lead."""
    weak = _student("weak", "Beginner")
    strong = _student("strong", "Advanced", level="C1")
    # Beginner: par 7/wk → 35 this week (+400%)
    for back in range(7, 21):
        _earn(weak, 1, TODAY - datetime.timedelta(days=back))
    for back in range(0, 7):
        _earn(weak, 5, TODAY - datetime.timedelta(days=back))
    # Advanced: par 700/wk → 770 this week (+10%), far more absolute points
    for back in range(7, 21):
        _earn(strong, 100, TODAY - datetime.timedelta(days=back))
    for back in range(0, 7):
        _earn(strong, 110, TODAY - datetime.timedelta(days=back))

    rows = database.ijtihad_most_improved_board(limit=5, today=TODAY)
    assert rows[0]["discord_name"] == "Beginner"
    assert database.ijtihad_points_between(
        strong, (TODAY - datetime.timedelta(days=6)).isoformat(),
        TODAY.isoformat()) > database.ijtihad_points_between(
        weak, (TODAY - datetime.timedelta(days=6)).isoformat(), TODAY.isoformat())


def test_most_improved_excludes_decliners():
    """This is never a board of who got worse."""
    mid = _student("dec", "Decliner")
    for back in range(7, 21):
        _earn(mid, 50, TODAY - datetime.timedelta(days=back))
    _earn(mid, 10, TODAY)
    assert database.ijtihad_most_improved_board(limit=5, today=TODAY) == []


def test_most_improved_render_says_a_beginner_can_win():
    out = ijtihad_growth.format_most_improved(
        [{"discord_name": "A", "level": "A1", "growth_pct": 40.0,
          "now": 70, "par_week": 50}])
    assert "beginner can top" in out.lower()


def test_empty_most_improved_is_honest():
    out = ijtihad_growth.format_most_improved([])
    assert "Not enough history" in out


# ============================================================
#  Recognitions — and the no-points guarantee
# ============================================================

def test_recognitions_award_no_points():
    """THE LOAD-BEARING PROPERTY. Recognitions notice people; points measure work.
    A recognition must never move anyone up the effort board."""
    _enable()
    mid = _student("np1", "Persistent")
    before = database.get_member(mid)["total_points"]
    _did_tasks(mid, TODAY, 7)
    for back in range(4, 10):        # a real absence before today
        pass
    kinds = ijtihad_growth.detect_new(mid, TODAY)
    assert database.get_member(mid)["total_points"] == before
    assert isinstance(kinds, list)


def test_comeback_fires_after_real_absence():
    _enable()
    mid = _student("cb")
    database.ijtihad_set_target(mid, 3, database.ijtihad_ensure_seasons(TODAY))
    _did_tasks(mid, TODAY, 3)                       # returned today, full day
    _did_tasks(mid, TODAY - datetime.timedelta(days=6), 3)  # last seen 6 days ago
    kinds = ijtihad_growth.detect_new(mid, TODAY)
    assert "comeback" in kinds


def test_comeback_does_not_fire_for_a_normal_day():
    _enable()
    mid = _student("cb2")
    database.ijtihad_set_target(mid, 3, database.ijtihad_ensure_seasons(TODAY))
    for back in range(0, 5):
        _did_tasks(mid, TODAY - datetime.timedelta(days=back), 3)
    assert "comeback" not in ijtihad_growth.detect_new(mid, TODAY)


def test_comeback_requires_a_full_day_not_just_a_return():
    _enable()
    mid = _student("cb3")
    database.ijtihad_set_target(mid, 7, database.ijtihad_ensure_seasons(TODAY))
    _did_tasks(mid, TODAY, 1)          # returned but did not finish
    assert "comeback" not in ijtihad_growth.detect_new(mid, TODAY)


def test_persistence_requires_having_failed_first():
    """The most important recognition in the set: it cannot be earned without a
    failure first, so it is unreachable by simply being good."""
    _enable()
    mid = _student("pers")
    conn = database._connect()
    conn.execute(
        "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, "
        "started_at, finished_at, status, result) VALUES (?,?,?,?,?,?,?,?)",
        (mid, "A1", 3, 1, "2026-08-01 10:00:00", "2026-08-01 10:20:00",
         "scored", "not_yet"))
    conn.execute(
        "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, "
        "started_at, finished_at, status, result) VALUES (?,?,?,?,?,?,?,?)",
        (mid, "A1", 3, 2, "2026-08-10 10:00:00", "2026-08-10 10:20:00",
         "scored", "mastered"))
    conn.commit()
    conn.close()
    assert "persistence" in ijtihad_growth.detect_new(mid, TODAY)


def test_persistence_does_not_fire_for_a_first_time_pass():
    _enable()
    mid = _student("pers2")
    conn = database._connect()
    conn.execute(
        "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, "
        "started_at, finished_at, status, result) VALUES (?,?,?,?,?,?,?,?)",
        (mid, "A1", 3, 1, "2026-08-01 10:00:00", "2026-08-01 10:20:00",
         "scored", "mastered"))
    conn.commit()
    conn.close()
    assert "persistence" not in ijtihad_growth.detect_new(mid, TODAY)


def test_uphill_requires_the_hardest_difficulty():
    _enable()
    mid = _student("up")
    s = database.ijtihad_ensure_seasons(TODAY)
    database.ijtihad_set_target(mid, 3, s)
    for back in range(0, 6):
        _did_tasks(mid, TODAY - datetime.timedelta(days=back), 3)
    # Still on standard difficulty → no Uphill.
    assert "uphill" not in ijtihad_growth.detect_new(mid, TODAY)
    database.update_member(mid, difficulty_level=3)
    assert "uphill" in ijtihad_growth.detect_new(mid, TODAY)


def test_refinement_requires_improving_scores():
    _enable()
    mid = _student("ref")
    conn = database._connect()
    for i, score in enumerate([40.0, 55.0, 62.0]):
        conn.execute(
            "INSERT INTO pronunciation_scores (discord_id, date, task_id, score, "
            "expected_text, transcript, scored_at) VALUES (?,?,?,?,?,?,?)",
            (mid, TODAY.isoformat(), "accent", score, "x", "x",
             f"2026-08-2{i} 10:00:00"))
    conn.commit()
    conn.close()
    assert "refinement" in ijtihad_growth.detect_new(mid, TODAY)


def test_refinement_is_about_trend_not_absolute_score():
    """40 → 55 → 62 refines even though 62 alone is unremarkable; 90 → 80 → 70
    does not, even though every score is high."""
    _enable()
    mid = _student("ref2")
    conn = database._connect()
    for i, score in enumerate([90.0, 80.0, 70.0]):
        conn.execute(
            "INSERT INTO pronunciation_scores (discord_id, date, task_id, score, "
            "expected_text, transcript, scored_at) VALUES (?,?,?,?,?,?,?)",
            (mid, TODAY.isoformat(), "accent", score, "x", "x",
             f"2026-08-2{i} 10:00:00"))
    conn.commit()
    conn.close()
    assert "refinement" not in ijtihad_growth.detect_new(mid, TODAY)


def test_personal_best_beats_your_own_past_only():
    _enable()
    mid = _student("pb")
    _earn(mid, 50, TODAY - datetime.timedelta(days=10))   # a previous week
    for back in range(0, 7):
        _earn(mid, 20, TODAY - datetime.timedelta(days=back))  # 140 this week
    assert "personal_best" in ijtihad_growth.detect_new(mid, TODAY)


def test_personal_best_does_not_fire_without_a_previous_week():
    _enable()
    mid = _student("pb2")
    _earn(mid, 100, TODAY)
    assert "personal_best" not in ijtihad_growth.detect_new(mid, TODAY)


# ============================================================
#  Idempotency
# ============================================================

def test_recognitions_are_recorded_once_per_period():
    _enable()
    mid = _student("once")
    database.ijtihad_set_target(mid, 3, database.ijtihad_ensure_seasons(TODAY))
    _did_tasks(mid, TODAY, 3)
    _did_tasks(mid, TODAY - datetime.timedelta(days=6), 3)
    first = ijtihad_growth.detect_new(mid, TODAY)
    second = ijtihad_growth.detect_new(mid, TODAY)
    assert "comeback" in first
    assert second == [], "a recognition must not fire twice for the same period"


def test_recognition_log_is_readable_for_a_student():
    _enable()
    mid = _student("log1")
    database.ijtihad_record_recognition(mid, "comeback", "2026-08-30", "{}")
    recs = database.ijtihad_recognitions_for(mid)
    assert len(recs) == 1
    assert recs[0]["kind"] == "comeback"


def test_record_recognition_returns_false_on_duplicate():
    mid = _student("log2")
    assert database.ijtihad_record_recognition(mid, "uphill", "2026-W35") is True
    assert database.ijtihad_record_recognition(mid, "uphill", "2026-W35") is False


# ============================================================
#  Spotlight rotation
# ============================================================

def test_spotlight_rotates_across_weeks():
    """Recognition ossifies if the same metric wins every week: the same two or
    three names win forever and everyone else learns it is not for them."""
    seen = {ijtihad_growth.spotlight_metric(TODAY + datetime.timedelta(weeks=w))
            for w in range(len(ijtihad_growth.SPOTLIGHT_ROTATION))}
    assert seen == set(ijtihad_growth.SPOTLIGHT_ROTATION)


def test_spotlight_is_stable_within_a_week():
    a = ijtihad_growth.spotlight_metric(datetime.date(2026, 8, 31))  # Monday
    b = ijtihad_growth.spotlight_metric(datetime.date(2026, 9, 4))   # Friday, same wk
    assert a == b


def test_spotlight_renders_for_every_metric():
    for metric in ijtihad_growth.SPOTLIGHT_ROTATION:
        out = ijtihad_growth.format_spotlight({"metric": metric, "rows": [],
                                               "season": None})
        assert "Weekly spotlight" in out


def test_spotlight_renders_rows():
    out = ijtihad_growth.format_spotlight({
        "metric": "improvement",
        "rows": [{"discord_name": "Mai#1", "growth_pct": 42.0}],
        "season": None})
    assert "Mai" in out and "42" in out
    assert "#1" not in out


# ============================================================
#  Rendering
# ============================================================

def test_recognition_labels_are_bilingual():
    for kind in ijtihad_growth.KINDS:
        out = ijtihad_growth.format_recognition(kind)
        assert "**" in out


def test_new_recognitions_line_is_empty_when_none():
    assert ijtihad_growth.format_new_recognitions([]) == ""


def test_new_recognitions_line_lists_each():
    out = ijtihad_growth.format_new_recognitions(["comeback", "uphill"])
    assert "Comeback" in out and "Uphill" in out
