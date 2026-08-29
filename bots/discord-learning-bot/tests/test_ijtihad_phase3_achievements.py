"""Ijtihad Phase 3 — achievement payouts. The central inversion.

Before this phase the four highest-signal achievements in the programme were
worth exactly ZERO points: weekly mastery, distinction, monthly review pass, and
level promotion. Attendance paid 105-205/day. The economy could not express
"this student improved" -- only "this student showed up".

These tests pin the inversion, the dedup (an achievement is a permanent fact, not
a repeatable action), and the graceful-off behaviour.
See .kiro/specs/ijtihad-effort-economy/ design §2.4.
"""
import datetime

import pytest

from src import database, flag_registry, ijtihad


FLAG = "ijtihad_achievement_awards"


@pytest.fixture(autouse=True)
def clean_ijtihad():
    conn = database._connect()
    conn.execute("DELETE FROM seasons")
    conn.execute("DELETE FROM settings WHERE key LIKE 'ijtihad_%'")
    conn.commit()
    conn.close()
    yield


def _student(mid: str = "s1", name: str = "Student", enabled: bool = True):
    database.register_member(mid, name)
    database.sync_flag_registry()
    if enabled:
        database.set_feature_flag(FLAG, True)
    return mid


def _points(mid: str) -> int:
    return database.get_member(mid)["total_points"]


# ============================================================
#  Flag + config
# ============================================================

def test_flag_registered_and_off_by_default():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == FLAG), None)
    assert entry is not None, f"{FLAG} must be registered"
    assert entry[3] is False, "must default OFF"


def test_module_flag_constant_matches_registry():
    assert ijtihad.FLAG == FLAG


def test_award_amounts_are_owner_tunable_with_documented_defaults():
    cfg = database.get_ijtihad_config()
    assert cfg["ijtihad_ip_mastery"] == 150
    assert cfg["ijtihad_ip_distinction"] == 250
    assert cfg["ijtihad_ip_monthly"] == 300
    assert cfg["ijtihad_ip_promotion"] == 500


def test_promotion_is_the_largest_award_in_the_economy():
    """The inversion, as an assertion: a single promotion must outweigh a full
    perfect day of attendance (7 tasks + the all-7 bonus = 205)."""
    from src import config
    cfg = database.get_ijtihad_config()
    perfect_day = config.POINTS_PER_TASK * 7 + config.POINTS_ALL_TASKS
    assert cfg["ijtihad_ip_promotion"] > perfect_day


# ============================================================
#  Nothing is awarded while the flag is off
# ============================================================

def test_no_award_when_flag_off():
    mid = _student("off1", enabled=False)
    before = _points(mid)
    assert ijtihad.award_week_mastery(mid, "A1", 1) == 0
    assert ijtihad.award_monthly_review(mid, "A1", 1) == 0
    assert ijtihad.award_promotion(mid, "A1") == 0
    assert _points(mid) == before


# ============================================================
#  Weekly mastery + distinction
# ============================================================

def test_mastery_pays_and_is_visible_in_points():
    mid = _student("m1")
    before = _points(mid)
    assert ijtihad.award_week_mastery(mid, "A1", 1) == 150
    assert _points(mid) == before + 150


def test_distinction_pays_more_than_plain_mastery():
    m1 = _student("d1")
    m2 = _student("d2")
    plain = ijtihad.award_week_mastery(m1, "A1", 1, distinction=False)
    dist = ijtihad.award_week_mastery(m2, "A1", 1, distinction=True)
    assert dist > plain
    assert dist == 250


def test_a_week_pays_only_once():
    mid = _student("m2")
    assert ijtihad.award_week_mastery(mid, "A1", 1) == 150
    assert ijtihad.award_week_mastery(mid, "A1", 1) == 0
    assert ijtihad.award_week_mastery(mid, "A1", 1) == 0
    assert _points(mid) == 150


def test_different_weeks_each_pay():
    mid = _student("m3")
    ijtihad.award_week_mastery(mid, "A1", 1)
    ijtihad.award_week_mastery(mid, "A1", 2)
    assert _points(mid) == 300


def test_same_week_number_at_a_different_level_pays_separately():
    """Week 1 of A2 is not week 1 of A1 — the dedup key includes the level."""
    mid = _student("m4")
    ijtihad.award_week_mastery(mid, "A1", 1)
    ijtihad.award_week_mastery(mid, "A2", 1)
    assert _points(mid) == 300


def test_distinction_after_plain_mastery_tops_up_the_difference_only():
    """A student who masters a week (150), then later re-passes with distinction,
    converges on 250 for that week — never 400."""
    mid = _student("m5")
    assert ijtihad.award_week_mastery(mid, "A1", 3, distinction=False) == 150
    assert ijtihad.award_week_mastery(mid, "A1", 3, distinction=True) == 100
    assert _points(mid) == 250
    # And the top-up itself cannot be farmed.
    assert ijtihad.award_week_mastery(mid, "A1", 3, distinction=True) == 0
    assert _points(mid) == 250


def test_distinction_first_does_not_also_collect_the_base():
    mid = _student("m6")
    assert ijtihad.award_week_mastery(mid, "A1", 4, distinction=True) == 250
    assert ijtihad.award_week_mastery(mid, "A1", 4, distinction=False) == 0
    assert _points(mid) == 250


# ============================================================
#  Monthly review
# ============================================================

def test_monthly_review_pays_once_per_review():
    mid = _student("mo1")
    assert ijtihad.award_monthly_review(mid, "A1", 1) == 300
    assert ijtihad.award_monthly_review(mid, "A1", 1) == 0
    assert ijtihad.award_monthly_review(mid, "A1", 2) == 300
    assert _points(mid) == 600


# ============================================================
#  Promotion — the biggest award
# ============================================================

def test_promotion_pays_once_per_level_left_behind():
    mid = _student("p1")
    assert ijtihad.award_promotion(mid, "A1") == 500
    assert ijtihad.award_promotion(mid, "A1") == 0     # re-passing A1's exam
    assert ijtihad.award_promotion(mid, "A2") == 500   # next rung
    assert _points(mid) == 1000


# ============================================================
#  Interaction with seasons (Phase 2)
# ============================================================

def test_achievement_award_counts_toward_the_current_season():
    """No extra plumbing: season effort is derived from points_log date windows,
    so an achievement paid today lands in today's season automatically."""
    mid = _student("sea1")
    season = database.ijtihad_ensure_seasons()
    assert database.ijtihad_season_points(mid, season) == 0
    ijtihad.award_promotion(mid, "A1")
    assert database.ijtihad_season_points(mid, season) == 500


def test_achievement_can_carry_a_student_up_the_season_board():
    """The inversion in competitive terms: one promotion outweighs two full
    perfect days of attendance."""
    from src import config
    achiever = _student("ach", "Achiever")
    grinder = _student("grind", "Grinder")
    season = database.ijtihad_ensure_seasons()

    ijtihad.award_promotion(achiever, "A1")                       # 500
    perfect_day = config.POINTS_PER_TASK * 7 + config.POINTS_ALL_TASKS
    database.add_points(grinder, perfect_day, "task:day1")        # 205
    database.add_points(grinder, perfect_day, "task:day2")        # 205

    board = database.ijtihad_season_leaderboard(season, limit=5)
    assert board[0]["discord_name"] == "Achiever"


# ============================================================
#  Primitive behaviour
# ============================================================

def test_award_once_rejects_non_positive_amounts():
    mid = _student("z1")
    assert database.ijtihad_award_once(mid, "ijtihad:test:zero", 0) == 0
    assert database.ijtihad_award_once(mid, "ijtihad:test:neg", -50) == 0
    assert _points(mid) == 0


def test_already_awarded_reports_correctly():
    mid = _student("z2")
    assert database.ijtihad_already_awarded(mid, "ijtihad:test:x") is False
    database.ijtihad_award_once(mid, "ijtihad:test:x", 10)
    assert database.ijtihad_already_awarded(mid, "ijtihad:test:x") is True


def test_dedup_is_per_student():
    a = _student("pa", "A")
    b = _student("pb", "B")
    assert ijtihad.award_promotion(a, "A1") == 500
    assert ijtihad.award_promotion(b, "A1") == 500


# ============================================================
#  Student-visible line
# ============================================================

def test_award_line_is_rendered_when_points_were_paid():
    line = ijtihad.format_award_line(250)
    assert "250" in line
    assert "Ijtihad" in line
    assert "اجتهاد" in line


def test_award_line_is_empty_when_nothing_was_paid():
    """A student who earned no new points must not see a '+0 points' line."""
    assert ijtihad.format_award_line(0) == ""
    assert ijtihad.format_award_line(-5) == ""
