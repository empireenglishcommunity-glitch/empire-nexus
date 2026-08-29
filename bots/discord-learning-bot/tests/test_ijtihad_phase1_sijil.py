"""Ijtihad Phase 1 — Sijil, the permanent Record of Honour.

Built BEFORE any seasonal reset exists, deliberately: veterans must see their
history preserved before they ever see a season start at zero. See
.kiro/specs/ijtihad-effort-economy/ design §3.

The load-bearing properties under test:
  * it is READ ONLY -- it must never mutate anything
  * a brand-new student gets an encouraging empty state, never a wall of zeros
  * it counts only EARNED things; attendance/tenure is explicitly not achievement
  * the Hall of Honour ranks by achievement, so a newcomer who masters weeks
    outranks a long-tenured student who has mastered none
"""
import pytest

from src import config, database, flag_registry, sijil


# ============================================================
#  Fixtures / helpers
# ============================================================

def _member(mid: str, name: str = "Student", level: str = "A1", points: int = 0):
    database.register_member(mid, name)
    if level != "A1":
        database.set_level(mid, level)
    if points:
        database.add_points(mid, points, "test_seed")
    return mid


def _master_week(mid: str, level: str, week: int, distinction: bool = False):
    conn = database._connect()
    conn.execute(
        """INSERT OR REPLACE INTO week_mastery
           (discord_id, level, week, mastered, distinction, mastered_at)
           VALUES (?,?,?,1,?,datetime('now'))""",
        (mid, level, week, 1 if distinction else 0),
    )
    conn.commit()
    conn.close()


def _pass_advancement(mid: str, level: str, attempt: int = 1):
    conn = database._connect()
    conn.execute(
        """INSERT OR REPLACE INTO advancement_exams
           (discord_id, level, attempt_num, passed, promoted, overall_score)
           VALUES (?,?,?,1,1,88.0)""",
        (mid, level, attempt),
    )
    conn.commit()
    conn.close()


def _pass_monthly(mid: str, level: str, n: int = 1):
    conn = database._connect()
    conn.execute(
        """INSERT OR REPLACE INTO monthly_reviews
           (discord_id, review_number, level, passed, retention_score)
           VALUES (?,?,?,1,80.0)""",
        (mid, n, level),
    )
    conn.commit()
    conn.close()


# ============================================================
#  Flag registration (project convention: same commit as the feature)
# ============================================================

def test_flag_registered_and_off_by_default():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == "ijtihad_sijil"), None)
    assert entry is not None, "ijtihad_sijil must be registered in flag_registry"
    assert entry[3] is False, "must default OFF — never accidentally active"


def test_module_flag_constant_matches_registry():
    assert sijil.FLAG == "ijtihad_sijil"


# ============================================================
#  The empty state — a requirement, not a nicety
# ============================================================

def test_brand_new_member_returns_zeros_not_none():
    _member("new1", "Newbie")
    rec = sijil.build_record("new1")
    assert rec["exists"] is True
    assert rec["weeks_mastered"] == 0
    assert rec["distinctions"] == 0
    assert rec["levels_earned"] == []
    assert rec["lifetime_tasks"] == 0
    assert rec["longest_streak"] == 0


def test_unknown_member_does_not_raise():
    """An id with no member row must still render, never explode."""
    rec = sijil.build_record("does_not_exist")
    assert rec["exists"] is False
    assert rec["weeks_mastered"] == 0


def test_new_member_gets_encouraging_empty_state_not_a_wall_of_zeros():
    _member("new2", "Newbie")
    out = sijil.format_record(sijil.build_record("new2"), "Newbie")
    assert "Record of Honour" in out
    # It must explain the philosophy, not just print zeros.
    assert "Work does" in out or "Time spent here earns nothing" in out
    # And it must NOT list achievement rows the student hasn't earned.
    assert "Weeks mastered" not in out
    assert "Distinctions" not in out


def test_empty_state_mentions_progress_when_tasks_exist():
    """Someone who has done real work but earned no badge yet should be
    acknowledged, not told their record is simply empty."""
    _member("new3", "Worker")
    database.log_submission("new3", "2026-08-01", "accent")
    database.log_submission("new3", "2026-08-01", "vocab")
    out = sijil.format_record(sijil.build_record("new3"), "Worker")
    assert "2 tasks" in out


# ============================================================
#  Achievement counting
# ============================================================

def test_counts_weeks_mastered_and_distinctions():
    _member("v1", "Veteran")
    _master_week("v1", "A1", 1)
    _master_week("v1", "A1", 2, distinction=True)
    _master_week("v1", "A1", 3, distinction=True)
    rec = sijil.build_record("v1")
    assert rec["weeks_mastered"] == 3
    assert rec["distinctions"] == 2


def test_counts_across_multiple_levels():
    """Sijil is lifetime and cross-level — promotion must not hide history."""
    _member("v2", "Veteran")
    _master_week("v2", "A1", 1)
    _master_week("v2", "A2", 1)
    _master_week("v2", "A2", 2)
    rec = sijil.build_record("v2")
    assert rec["weeks_mastered"] == 3


def test_counts_levels_earned_by_exam():
    _member("v3", "Veteran")
    _pass_advancement("v3", "A1")
    _pass_advancement("v3", "A2")
    rec = sijil.build_record("v3")
    assert [lv["level"] for lv in rec["levels_earned"]] == ["A1", "A2"]


def test_multiple_attempts_at_one_level_count_once():
    _member("v4", "Veteran")
    _pass_advancement("v4", "A1", attempt=1)
    _pass_advancement("v4", "A1", attempt=2)
    rec = sijil.build_record("v4")
    assert len(rec["levels_earned"]) == 1


def test_counts_monthly_reviews_passed():
    _member("v5", "Veteran")
    _pass_monthly("v5", "A1", 1)
    _pass_monthly("v5", "A1", 2)
    rec = sijil.build_record("v5")
    assert rec["monthly_reviews_passed"] == 2


def test_failed_monthly_review_is_not_counted():
    _member("v6", "Veteran")
    conn = database._connect()
    conn.execute(
        """INSERT INTO monthly_reviews (discord_id, review_number, level, passed)
           VALUES (?,?,?,0)""", ("v6", 1, "A1"))
    conn.commit()
    conn.close()
    assert sijil.build_record("v6")["monthly_reviews_passed"] == 0


def test_counts_perfect_days_and_active_days():
    _member("v7", "Veteran")
    database.update_streak("v7", "2026-08-01", 7)   # perfect
    database.update_streak("v7", "2026-08-02", 3)   # active, not perfect
    rec = sijil.build_record("v7")
    assert rec["perfect_days"] == 1
    assert rec["active_days"] == 2


def test_legacy_xp_is_preserved_verbatim():
    """The pre-Ijtihad lifetime total is kept exactly — nothing is erased."""
    _member("v8", "Veteran", points=4321)
    assert sijil.build_record("v8")["legacy_xp"] == 4321


def test_longest_streak_is_carried_over():
    """Sijil surfaces members.longest_streak, the never-decaying personal best.

    NOTE: streaks are computed by walking backwards from TODAY, so the seeded
    days must END today for a streak to exist at all — seeding arbitrary past
    dates correctly yields 0. That is the real mechanism, so the test uses it
    rather than writing longest_streak directly.
    """
    import datetime
    _member("v9", "Veteran")
    today = database._today_local()
    for back in range(4, -1, -1):          # 5 consecutive days ending today
        day = (today - datetime.timedelta(days=back)).isoformat()
        database.update_streak("v9", day, 5)
    rec = sijil.build_record("v9")
    assert rec["longest_streak"] >= 5


# ============================================================
#  has_any_achievement — attendance is NOT achievement
# ============================================================

def test_attendance_alone_is_not_an_achievement():
    """The whole thesis: showing up and accumulating points must not by itself
    populate the Record of Honour."""
    _member("att", "Attender", points=9999)
    database.log_submission("att", "2026-08-01", "accent")
    rec = sijil.build_record("att")
    assert rec["legacy_xp"] == 9999
    assert rec["lifetime_tasks"] == 1
    assert sijil.has_any_achievement(rec) is False


def test_one_mastered_week_is_an_achievement():
    _member("ach", "Achiever")
    _master_week("ach", "A1", 1)
    assert sijil.has_any_achievement(sijil.build_record("ach")) is True


def test_perfect_day_counts_as_achievement():
    _member("pd", "Perfect")
    database.update_streak("pd", "2026-08-01", 7)
    assert sijil.has_any_achievement(sijil.build_record("pd")) is True


# ============================================================
#  Rendering the earned record
# ============================================================

def test_full_record_renders_all_earned_sections():
    _member("full", "Champion", points=1500)
    _master_week("full", "A1", 1)
    _master_week("full", "A1", 2, distinction=True)
    _pass_advancement("full", "A1")
    _pass_monthly("full", "A1")
    database.update_streak("full", "2026-08-01", 7)
    out = sijil.format_record(sijil.build_record("full"), "Champion")
    assert "Weeks mastered" in out
    assert "Distinctions" in out
    assert "Levels passed by exam" in out
    assert "Monthly reviews passed" in out
    assert "Perfect days" in out
    assert "Legacy XP" in out
    assert "Never resets" in out


def test_record_omits_sections_with_nothing_earned():
    """No zero-rows: a student with only mastered weeks shouldn't see
    'Distinctions: 0' staring back at them."""
    _member("part", "Partial")
    _master_week("part", "A1", 1)
    out = sijil.format_record(sijil.build_record("part"), "Partial")
    assert "Weeks mastered" in out
    assert "Distinctions" not in out
    assert "Levels passed by exam" not in out


# ============================================================
#  Hall of Honour — achievement, not tenure
# ============================================================

def test_hall_ranks_achievement_over_tenure_and_points():
    """A newcomer who masters 3 weeks must outrank a long-tenured student with a
    huge lifetime total and no mastery. This is the core inversion."""
    _member("old", "OldTimer", points=50_000)   # lots of points, no mastery
    _member("newbie", "Newcomer", points=100)
    _master_week("newbie", "A1", 1)
    _master_week("newbie", "A1", 2)
    _master_week("newbie", "A1", 3)

    hall = database.sijil_hall_of_honour(limit=5)
    names = [h["discord_name"] for h in hall]
    assert "Newcomer" in names
    assert "OldTimer" not in names, "points/tenure must not enter the Hall"
    assert hall[0]["discord_name"] == "Newcomer"


def test_hall_excludes_students_with_no_achievements():
    _member("nobody", "Nobody", points=8000)
    assert database.sijil_hall_of_honour(limit=5) == []


def test_hall_respects_limit():
    for i in range(7):
        mid = f"h{i}"
        _member(mid, f"H{i}")
        _master_week(mid, "A1", i + 1)
    assert len(database.sijil_hall_of_honour(limit=3)) == 3


def test_hall_distinctions_break_ties():
    _member("t1", "TieA")
    _member("t2", "TieB")
    _master_week("t1", "A1", 1)
    _master_week("t2", "A1", 1, distinction=True)
    hall = database.sijil_hall_of_honour(limit=5)
    assert hall[0]["discord_name"] == "TieB"


def test_empty_hall_renders_gracefully():
    out = sijil.format_hall_of_honour([])
    assert "Hall of Honour" in out
    assert "No achievements recorded yet" in out


def test_hall_render_strips_discriminator():
    out = sijil.format_hall_of_honour(
        [{"discord_name": "Mai#1234", "level": "A1", "weeks_mastered": 2,
          "distinctions": 1, "levels_earned": 0}])
    assert "Mai" in out
    assert "#1234" not in out


def test_hall_render_states_the_ranking_basis():
    """The board must say out loud that it is not a tenure ranking."""
    out = sijil.format_hall_of_honour(
        [{"discord_name": "A", "level": "A1", "weeks_mastered": 1,
          "distinctions": 0, "levels_earned": 0}])
    assert "not by how long" in out


# ============================================================
#  Read-only guarantee
# ============================================================

def test_build_record_mutates_nothing():
    _member("ro", "ReadOnly", points=777)
    _master_week("ro", "A1", 1)

    def snapshot():
        conn = database._connect()
        try:
            return {
                "points": conn.execute(
                    "SELECT total_points FROM members WHERE discord_id='ro'"
                ).fetchone()[0],
                "points_log": conn.execute(
                    "SELECT COUNT(*) FROM points_log WHERE discord_id='ro'"
                ).fetchone()[0],
                "mastery": conn.execute(
                    "SELECT COUNT(*) FROM week_mastery WHERE discord_id='ro'"
                ).fetchone()[0],
                "subs": conn.execute(
                    "SELECT COUNT(*) FROM daily_submissions WHERE discord_id='ro'"
                ).fetchone()[0],
            }
        finally:
            conn.close()

    before = snapshot()
    sijil.build_record("ro")
    database.sijil_hall_of_honour(limit=5)
    assert snapshot() == before, "Sijil must never write to the database"
