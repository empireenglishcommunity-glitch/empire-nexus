"""Ijtihad Phase 5 — boards. Replacing the single god-board.

The old system had one public ranking (lifetime points) plus a nightly streak
ranking, and both were won by the same people for the same reason: they had been
present longest. One board means one winner and sixteen losers, decided mostly by
join date.

These tests pin the two rules that make several boards safe at community scale:
  * NEVER publish a bottom half — every board is capped and lists only students
    who actually earned something;
  * a cohort too small to rank degrades (journey -> level -> community) instead of
    rendering a one-person "ranking".

See .kiro/specs/ijtihad-effort-economy/ design §4.
"""
import datetime

import pytest

from src import database, flag_registry, ijtihad_boards


FLAG = "ijtihad_boards"


@pytest.fixture(autouse=True)
def clean_ijtihad():
    conn = database._connect()
    for sql in ("DELETE FROM seasons", "DELETE FROM student_targets",
                "DELETE FROM streak_freezes", "DELETE FROM points_log",
                "DELETE FROM streaks",
                "DELETE FROM settings WHERE key LIKE 'ijtihad_%'"):
        conn.execute(sql)
    conn.commit()
    conn.close()
    yield


def _season():
    database.set_ijtihad_config("ijtihad_season1_start", "2026-01-03")
    return database.ijtihad_ensure_seasons()


def _student(mid, name, level="A1"):
    database.register_member(mid, name)
    if level != "A1":
        database.set_level(mid, level)
    return mid


def _earn(mid, points, day=None):
    day = day or database._today_local()
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


# ============================================================
#  Flag
# ============================================================

def test_flag_registered_and_off_by_default():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == FLAG), None)
    assert entry is not None
    assert entry[3] is False


def test_module_flag_matches_registry():
    assert ijtihad_boards.FLAG == FLAG


# ============================================================
#  Season title
# ============================================================

def test_season_title_is_numbered_with_a_month_range():
    s = {"label": "Season 1", "started_on": "2026-08-29", "ends_on": "2026-09-25"}
    title = ijtihad_boards.season_title(s)
    assert "Season 1" in title
    assert "Aug" in title and "Sep" in title


def test_season_title_single_month():
    s = {"label": "Season 2", "started_on": "2026-09-01", "ends_on": "2026-09-25"}
    assert "Sep" in ijtihad_boards.season_title(s)


def test_season_title_handles_no_season():
    assert "No season" in ijtihad_boards.season_title(None)


# ============================================================
#  Never publish a bottom half
# ============================================================

def test_season_board_lists_only_students_who_earned_something():
    s = _season()
    _student("a", "Active")
    _student("b", "Silent")
    _earn("a", 100)
    rows = database.ijtihad_season_leaderboard(s, limit=5)
    assert [r["discord_name"] for r in rows] == ["Active"]


def test_season_board_is_capped_even_with_many_students():
    """With ~17 students a top-10 board names most of the community. Capped at 5."""
    s = _season()
    for i in range(12):
        _student(f"s{i}", f"S{i}")
        _earn(f"s{i}", 10 * (i + 1))
    assert len(database.ijtihad_season_leaderboard(s, limit=5)) == 5


def test_caller_sees_their_own_standing_without_it_being_published():
    """The caller's rank appears in the reply THEY asked for — not as a public
    ranked list naming everyone."""
    s = _season()
    for i in range(6):
        _student(f"t{i}", f"T{i}")
        _earn(f"t{i}", 100 * (6 - i))
    _student("me", "Me")
    _earn("me", 5)
    rows = database.ijtihad_season_leaderboard(s, limit=5)
    out = ijtihad_boards.format_season_board(
        s, rows, me_id="me",
        my_rank=database.ijtihad_season_rank("me", s),
        my_points=database.ijtihad_season_points("me", s))
    assert "Me" not in [r["discord_name"] for r in rows]
    assert "You" in out and "#7" in out


def test_board_tells_a_student_with_no_points_the_truth_kindly():
    s = _season()
    _student("np", "NoPoints")
    out = ijtihad_boards.format_season_board(s, [], me_id="np")
    assert "not earned points yet" in out


def test_empty_season_board_reads_as_opportunity_not_failure():
    s = _season()
    out = ijtihad_boards.format_season_board(s, [], me_id="")
    assert "wide open" in out


def test_season_board_without_a_season_says_so():
    out = ijtihad_boards.format_season_board(None, [], me_id="x")
    assert "not started" in out


# ============================================================
#  Journey-stage cohorts + degradation
# ============================================================

def test_journey_cohort_used_when_big_enough():
    """Students at a similar stage are compared with each other."""
    for i in range(4):
        mid = _student(f"j{i}", f"J{i}")
        database.update_member(mid, joined_at=datetime.datetime.now().isoformat())
    out = database.ijtihad_journey_peers("j0")
    assert out["scope"] == "journey"
    assert len(out["peers"]) >= database.IJTIHAD_MIN_COHORT


def test_degrades_to_community_when_alone():
    """A one-person 'ranking' is worse than no ranking, so scope widens."""
    _student("solo", "Solo")
    out = database.ijtihad_journey_peers("solo")
    assert out["scope"] == "community"
    assert out["peers"] == ["solo"]


def test_unknown_member_degrades_safely():
    out = database.ijtihad_journey_peers("ghost")
    assert out["scope"] == "community"
    assert out["peers"] == []


def test_scoped_board_restricts_to_the_cohort():
    s = _season()
    _student("in1", "In1")
    _student("in2", "In2")
    _student("out1", "Out1")
    _earn("in1", 50)
    _earn("in2", 30)
    _earn("out1", 9999)
    rows = database.ijtihad_season_board_scoped(s, ["in1", "in2"], limit=5)
    names = [r["discord_name"] for r in rows]
    assert names == ["In1", "In2"]
    assert "Out1" not in names


def test_scoped_board_handles_empty_cohort():
    s = _season()
    assert database.ijtihad_season_board_scoped(s, [], limit=5) == []
    assert database.ijtihad_season_board_scoped(None, ["a"], limit=5) == []


def test_peers_render_marks_you():
    s = _season()
    rows = [{"discord_id": "me", "discord_name": "Me", "season_points": 10},
            {"discord_id": "other", "discord_name": "Other", "season_points": 5}]
    out = ijtihad_boards.format_peers_board("journey", 3, s, rows, me_id="me")
    assert "you" in out
    assert "week 3" in out


def test_peers_render_states_the_scope():
    """A student should know WHO they're being compared with."""
    s = _season()
    out = ijtihad_boards.format_peers_board("level", 5, s, [], me_id="me")
    assert "your level" in out
    assert "No effort recorded" in out


# ============================================================
#  Consistency board
# ============================================================

def test_consistency_board_ranks_full_day_streaks():
    s = _season()
    a = _student("c1", "Steady")
    b = _student("c2", "Patchy")
    database.ijtihad_set_target(a, 3, s)
    database.ijtihad_set_target(b, 3, s)
    today = database._today_local()
    for back in range(4):
        _did_tasks(a, today - datetime.timedelta(days=back), 3)
    _did_tasks(b, today, 3)
    rows = database.ijtihad_consistency_board(limit=5)
    assert rows[0]["discord_name"] == "Steady"
    assert rows[0]["streak"] == 4


def test_a_low_target_student_can_top_the_consistency_board():
    """Reliability, not volume. Someone doing their honest 3/3 every day beats
    someone doing 7/7 sporadically."""
    s = _season()
    slow = _student("slow", "Slow")
    fast = _student("fast", "Fast")
    database.ijtihad_set_target(slow, 3, s)
    database.ijtihad_set_target(fast, 7, s)
    today = database._today_local()
    for back in range(5):
        _did_tasks(slow, today - datetime.timedelta(days=back), 3)
    _did_tasks(fast, today, 7)
    rows = database.ijtihad_consistency_board(limit=5)
    assert rows[0]["discord_name"] == "Slow"


def test_consistency_board_excludes_zero_streaks():
    _season()
    _student("z", "Zero")
    assert database.ijtihad_consistency_board(limit=5) == []


def test_consistency_board_does_not_spend_freezes():
    """Merely LOOKING at a leaderboard must not consume a student's allowance."""
    s = _season()
    mid = _student("f1", "Freezer")
    database.ijtihad_set_target(mid, 3, s)
    today = database._today_local()
    _did_tasks(mid, today, 3)
    _did_tasks(mid, today - datetime.timedelta(days=2), 3)   # gap yesterday
    database.ijtihad_consistency_board(limit=5)
    assert database.ijtihad_freezes_used(mid, s) == 0


def test_consistency_render_shows_each_students_own_target():
    out = ijtihad_boards.format_consistency_board(
        [{"discord_name": "A", "level": "A1", "streak": 6, "target": 3}])
    assert "6" in out
    assert "3" in out


def test_empty_consistency_board_is_encouraging():
    out = ijtihad_boards.format_consistency_board([])
    assert "One complete day starts one" in out


# ============================================================
#  The reformed nightly roll
# ============================================================

def test_full_days_on_lists_everyone_who_hit_their_own_target():
    s = _season()
    a = _student("r1", "Three")
    b = _student("r2", "Seven")
    c = _student("r3", "Partial")
    database.ijtihad_set_target(a, 3, s)
    database.ijtihad_set_target(b, 7, s)
    database.ijtihad_set_target(c, 7, s)
    today = database._today_local()
    _did_tasks(a, today, 3)      # met target 3
    _did_tasks(b, today, 7)      # met target 7
    _did_tasks(c, today, 3)      # did NOT meet target 7
    names = [r["discord_name"] for r in database.ijtihad_full_days_on(today.isoformat())]
    assert "Three" in names
    assert "Seven" in names
    assert "Partial" not in names


def test_roll_is_a_roll_not_a_ranking():
    """No positions, so nobody can be in a losing one. The old post ranked up to
    15 students by a >=1-task streak."""
    rows = [{"discord_name": "A", "tasks": 7, "target": 7},
            {"discord_name": "B", "tasks": 3, "target": 3}]
    out = ijtihad_boards.format_full_day_roll("2026-08-30", rows, [])
    assert "🥇" not in out and "🥈" not in out
    assert "A" in out and "B" in out
    assert "2 students hit their target" in out


def test_roll_singular_wording():
    rows = [{"discord_name": "A", "tasks": 5, "target": 5}]
    out = ijtihad_boards.format_full_day_roll("2026-08-30", rows, [])
    assert "1 student hit their target" in out


def test_empty_roll_is_gentle_and_forward_looking():
    out = ijtihad_boards.format_full_day_roll("2026-08-30", [], [])
    assert "tomorrow is open" in out.lower()


def test_roll_appends_a_small_top_three_of_runs():
    rows = [{"discord_name": "A", "tasks": 3, "target": 3}]
    streaks = [{"discord_name": "X", "streak": 9},
               {"discord_name": "Y", "streak": 4},
               {"discord_name": "Z", "streak": 2},
               {"discord_name": "W", "streak": 1}]
    out = ijtihad_boards.format_full_day_roll("2026-08-30", rows, streaks)
    assert "X 9d" in out
    assert "W" not in out.split("Longest runs")[1]


def test_names_are_stripped_of_discriminators():
    out = ijtihad_boards.format_full_day_roll(
        "2026-08-30", [{"discord_name": "Mai#1234", "tasks": 3, "target": 3}], [])
    assert "Mai" in out
    assert "#1234" not in out
