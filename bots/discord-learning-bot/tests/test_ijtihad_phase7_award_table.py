"""Ijtihad Phase 7 — the award table. The change earlier phases deferred.

It REPLACES POINTS_PER_TASK (15), POINTS_ALL_TASKS (100) and the
STREAK_BONUS_POINTS ladder. Introducing any one of those alongside the legacy
values would have produced two overlapping awards for the same action — the exact
double-award class of bug Phase 0.2 removed. So the most important test in this
file is the one asserting the two tables can never both fire.

Two incentive defects it fixes that no amount of tuning could:
  1. Attempting harder work was IRRATIONAL — "Challenging" made tasks longer and
     faster for exactly the same 15 points as "Easy", so a points-maximiser should
     have deliberately scored badly.
  2. Quality was INVISIBLE — a 95%-accurate recording and a mumbled one paid the
     same. Quality now multiplies, but only UPWARDS: the floor is 1.0, so a
     student who tries and does badly still gets the full base award.

See .kiro/specs/ijtihad-effort-economy/ design §2.2 / §2.5.
"""
import datetime

import pytest

from src import config, database, flag_registry, ijtihad, tasks


TABLE_FLAG = "ijtihad_award_table"


@pytest.fixture(autouse=True)
def clean():
    conn = database._connect()
    for sql in ("DELETE FROM seasons", "DELETE FROM student_targets",
                "DELETE FROM streak_freezes", "DELETE FROM points_log",
                "DELETE FROM streaks", "DELETE FROM daily_submissions",
                "DELETE FROM pronunciation_scores",
                "DELETE FROM settings WHERE key LIKE 'ijtihad_%'"):
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.commit()
    conn.close()
    yield


def _student(mid="s1", name="Student"):
    database.register_member(mid, name)
    database.sync_flag_registry()
    return mid


def _season():
    database.set_ijtihad_config("ijtihad_season1_start", "2026-01-03")
    return database.ijtihad_ensure_seasons()


def _enable_table():
    database.sync_flag_registry()
    database.set_feature_flag(TABLE_FLAG, True)


def _points(mid):
    return database.get_member(mid)["total_points"]


def _did_tasks(mid, day, n):
    conn = database._connect()
    conn.execute(
        "INSERT OR REPLACE INTO streaks (discord_id,date,tasks_completed,all_seven) "
        "VALUES (?,?,?,?)", (mid, day.isoformat(), n, 1 if n >= 7 else 0))
    conn.commit()
    conn.close()


# ============================================================
#  Flag + config
# ============================================================

def test_flag_registered_and_off_by_default():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == TABLE_FLAG), None)
    assert entry is not None
    assert entry[3] is False


def test_award_table_defaults():
    cfg = database.get_ijtihad_config()
    assert cfg["ijtihad_base_ip"] == 10
    assert cfg["ijtihad_full_day_ip"] == 25
    assert cfg["ijtihad_streak_28"] == 600


def test_streak_ladder_is_bounded_unlike_the_legacy_one():
    """The legacy top rung (100 days / 5000 pts) was worth 333 tasks and was
    unreachable without months of tenure — the clearest way the old economy paid
    for seniority rather than work."""
    assert database.IJTIHAD_STREAK_THRESHOLDS == (7, 14, 21, 28)
    cfg = database.get_ijtihad_config()
    biggest = cfg["ijtihad_streak_28"]
    legacy_biggest = max(config.STREAK_BONUS_POINTS.values())
    assert biggest < legacy_biggest


# ============================================================
#  THE CRITICAL TEST — the two tables must never both fire
# ============================================================

@pytest.mark.asyncio
async def test_legacy_table_used_when_flag_off():
    mid = _student("leg1")
    _season()
    out = await tasks.process_submission(mid, "Legacy", "accent")
    assert out["points"] == config.POINTS_PER_TASK
    assert _points(mid) == config.POINTS_PER_TASK
    assert "ijtihad" not in out


@pytest.mark.asyncio
async def test_new_table_used_when_flag_on_and_legacy_does_not_also_fire():
    """THE LOAD-BEARING ASSERTION. One submission, one award path."""
    mid = _student("new1")
    _season()
    _enable_table()
    out = await tasks.process_submission(mid, "New", "accent")
    assert out["ijtihad"]["task_points"] == 10          # base, no multipliers
    assert out["points"] == 10
    # The legacy 15 must NOT appear anywhere in the ledger.
    conn = database._connect()
    rows = [dict(r) for r in conn.execute(
        "SELECT points, reason FROM points_log WHERE discord_id=?", (mid,)).fetchall()]
    conn.close()
    assert all(r["points"] != config.POINTS_PER_TASK for r in rows), rows
    assert _points(mid) == 10


@pytest.mark.asyncio
async def test_legacy_all_7_bonus_never_fires_under_the_new_table():
    """POINTS_ALL_TASKS (100) is replaced by the target-based full-day bonus."""
    mid = _student("new2")
    s = _season()
    database.ijtihad_set_target(mid, 7, s)
    _enable_table()
    for i in range(1, 8):
        out = await tasks.process_submission(mid, "New", f"task{i}")
    conn = database._connect()
    reasons = [r["reason"] for r in conn.execute(
        "SELECT reason FROM points_log WHERE discord_id=?", (mid,)).fetchall()]
    conn.close()
    assert "all_7_tasks" not in reasons
    assert any(r.startswith("ijtihad:fullday:") for r in reasons)


# ============================================================
#  Difficulty multiplier — attempting harder work now pays
# ============================================================

def test_difficulty_multiplier_is_1_when_adaptive_is_off():
    """Everyone sits at the default tier 2 while adaptive is disabled; paying the
    whole community 1.25x for a tier nothing assigns would be silent inflation,
    not a reward for choosing harder work."""
    mid = _student("d0")
    database.sync_flag_registry()
    database.set_feature_flag("tatawwur_adaptive", False)
    database.update_member(mid, difficulty_level=3)
    assert ijtihad.difficulty_multiplier(mid) == 1.0


def test_challenging_pays_more_than_easy_when_adaptive_is_on():
    """THE INCENTIVE FIX. Before this, Challenging content was longer and faster
    for identical pay, so a points-maximiser should have scored badly."""
    easy = _student("d1", "Easy")
    hard = _student("d2", "Hard")
    database.sync_flag_registry()
    database.set_feature_flag("tatawwur_adaptive", True)
    database.update_member(easy, difficulty_level=1)
    database.update_member(hard, difficulty_level=3)
    assert ijtihad.difficulty_multiplier(easy) == 1.0
    assert ijtihad.difficulty_multiplier(hard) == 1.5
    assert (ijtihad.compute_task_award(hard, "accent")["points"]
            > ijtihad.compute_task_award(easy, "accent")["points"])


# ============================================================
#  Quality multiplier — bonus only, never a penalty
# ============================================================

def test_quality_multiplier_is_1_without_a_score():
    """No score is the NORMAL case (pronunciation scoring is a separate, disabled
    engine). It must mean 'no signal', never 'scored zero'."""
    mid = _student("q0")
    assert ijtihad.quality_multiplier(mid, "accent") == 1.0


@pytest.mark.parametrize("score,expected", [
    (95.0, 1.3), (90.0, 1.3), (85.0, 1.2), (80.0, 1.2),
    (75.0, 1.1), (70.0, 1.1), (69.9, 1.0), (10.0, 1.0), (0.0, 1.0),
])
def test_quality_bands(score, expected):
    mid = _student(f"q{int(score*10)}")
    day = database._today_local().isoformat()
    conn = database._connect()
    conn.execute(
        "INSERT INTO pronunciation_scores (discord_id,date,task_id,score,"
        "expected_text,transcript) VALUES (?,?,?,?,?,?)",
        (mid, day, "accent", score, "x", "x"))
    conn.commit()
    conn.close()
    assert ijtihad.quality_multiplier(mid, "accent", day) == expected


def test_a_bad_score_is_never_punished():
    """The floor is 1.0 on purpose: punishing low scores would hit exactly the
    struggling-but-persistent students this rework exists to keep."""
    mid = _student("qbad")
    day = database._today_local().isoformat()
    conn = database._connect()
    conn.execute(
        "INSERT INTO pronunciation_scores (discord_id,date,task_id,score,"
        "expected_text,transcript) VALUES (?,?,?,?,?,?)",
        (mid, day, "accent", 5.0, "x", "x"))
    conn.commit()
    conn.close()
    award = ijtihad.compute_task_award(mid, "accent", day)
    assert award["quality_mult"] == 1.0
    assert award["points"] == 10, "a bad score still earns the full base award"


def test_multipliers_compound():
    mid = _student("qc")
    database.sync_flag_registry()
    database.set_feature_flag("tatawwur_adaptive", True)
    database.update_member(mid, difficulty_level=3)
    day = database._today_local().isoformat()
    conn = database._connect()
    conn.execute(
        "INSERT INTO pronunciation_scores (discord_id,date,task_id,score,"
        "expected_text,transcript) VALUES (?,?,?,?,?,?)",
        (mid, day, "accent", 95.0, "x", "x"))
    conn.commit()
    conn.close()
    award = ijtihad.compute_task_award(mid, "accent", day)
    assert award["points"] == round(10 * 1.5 * 1.3)   # 19-20


# ============================================================
#  Full-day bonus — the busy-adult fix, paid
# ============================================================

def test_full_day_bonus_pays_at_your_own_target():
    """POINTS_ALL_TASKS only ever paid at 7/7, so it was unreachable for a student
    whose honest capacity is 3 a day."""
    mid = _student("fd1")
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    _enable_table()
    day = database._today_local().isoformat()
    assert ijtihad.award_full_day(mid, day) == 25


def test_full_day_bonus_pays_once_per_day():
    mid = _student("fd2")
    _season()
    day = database._today_local().isoformat()
    assert ijtihad.award_full_day(mid, day) == 25
    assert ijtihad.award_full_day(mid, day) == 0


@pytest.mark.asyncio
async def test_seven_of_seven_still_out_earns_three_of_three():
    """Volume must still scale, or the target would change what counts as MORE
    rather than what counts as COMPLETE."""
    s = _season()
    small = _student("v3", "Three")
    big = _student("v7", "Seven")
    database.ijtihad_set_target(small, 3, s)
    database.ijtihad_set_target(big, 7, s)
    _enable_table()
    for i in range(3):
        await tasks.process_submission(small, "Three", f"t{i}")
    for i in range(7):
        await tasks.process_submission(big, "Seven", f"t{i}")
    assert _points(big) > _points(small)
    assert _points(small) == 3 * 10 + 25      # both got a full day
    assert _points(big) == 7 * 10 + 25


# ============================================================
#  Seasonal streak bonus
# ============================================================

def test_streak_bonus_pays_at_a_threshold_and_only_once_per_season():
    mid = _student("sb1")
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    _enable_table()
    today = database._today_local()
    for back in range(7):
        _did_tasks(mid, today - datetime.timedelta(days=back), 3)
    threshold, points = ijtihad.award_streak_bonus(mid)
    assert (threshold, points) == (7, 100)
    assert ijtihad.award_streak_bonus(mid) == (0, 0)


def test_streak_bonus_pays_the_highest_threshold_reached():
    mid = _student("sb2")
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    _enable_table()
    today = database._today_local()
    for back in range(14):
        _did_tasks(mid, today - datetime.timedelta(days=back), 3)
    threshold, points = ijtihad.award_streak_bonus(mid)
    assert (threshold, points) == (14, 200)


def test_streak_bonus_needs_a_season():
    mid = _student("sb3")
    database.set_ijtihad_config("ijtihad_season1_start", "2099-01-02")
    assert ijtihad.award_streak_bonus(mid) == (0, 0)


def test_legacy_streak_ladder_does_not_fire_under_the_new_table():
    mid = _student("sb4")
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    _enable_table()
    today = database._today_local()
    for back in range(7):
        _did_tasks(mid, today - datetime.timedelta(days=back), 3)
    ijtihad.award_streak_bonus(mid)
    conn = database._connect()
    reasons = [r["reason"] for r in conn.execute(
        "SELECT reason FROM points_log WHERE discord_id=?", (mid,)).fetchall()]
    conn.close()
    assert not any(r.startswith("streak_") for r in reasons), reasons
    assert any(r.startswith("ijtihad:streak:") for r in reasons)


# ============================================================
#  Achievement remains dominant under the new table
# ============================================================

def test_achievement_is_even_more_dominant_under_the_new_table():
    """Lower per-task values are deliberate: a promotion should feel like a
    milestone, not like two good days."""
    cfg = database.get_ijtihad_config()
    perfect_day_new = cfg["ijtihad_base_ip"] * 7 + cfg["ijtihad_full_day_ip"]
    perfect_day_legacy = config.POINTS_PER_TASK * 7 + config.POINTS_ALL_TASKS
    assert perfect_day_new < perfect_day_legacy
    promotion = cfg["ijtihad_ip_promotion"]
    assert promotion / perfect_day_new > promotion / perfect_day_legacy
    assert promotion > perfect_day_new * 4


# ============================================================
#  Season integration
# ============================================================

@pytest.mark.asyncio
async def test_new_table_awards_count_toward_the_season():
    mid = _student("si1")
    s = _season()
    database.ijtihad_set_target(mid, 3, s)
    _enable_table()
    for i in range(3):
        await tasks.process_submission(mid, "S", f"t{i}")
    assert database.ijtihad_season_points(mid, s) == 3 * 10 + 25
