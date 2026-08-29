"""Ijtihad Phase 2 — effort seasons.

This is the phase that actually kills the unfairness the owner reported. Rank was
`ORDER BY total_points DESC` over a column that only ever increases, so rank
approximated tenure x minimum activity. Scoping effort to a 4-week window fixes
that on its own, WITHOUT changing a single award value -- which is why Phase 2
deliberately ships no new points maths.

Season effort is DERIVED from points_log date windows, so there is no migration
and no second ledger to disagree with the first.
See .kiro/specs/ijtihad-effort-economy/ design §2.1.
"""
import datetime

import pytest

from src import database, flag_registry


# ============================================================
#  Helpers
# ============================================================

def _member(mid: str, name: str = "Student"):
    database.register_member(mid, name)
    return mid


def _award_on(mid: str, day: datetime.date, points: int, reason: str = "task:seed"):
    """Insert a points_log row on a specific date (add_points always stamps
    'now', so seeding history needs a direct insert)."""
    conn = database._connect()
    conn.execute(
        "INSERT INTO points_log (discord_id, points, reason, logged_at) "
        "VALUES (?,?,?,?)",
        (mid, points, reason, f"{day.isoformat()} 12:00:00"),
    )
    conn.commit()
    conn.close()


def _clear_seasons():
    conn = database._connect()
    conn.execute("DELETE FROM seasons")
    conn.execute("DELETE FROM settings WHERE key LIKE 'ijtihad_%'")
    conn.commit()
    conn.close()


@pytest.fixture(autouse=True)
def clean_seasons():
    _clear_seasons()
    yield
    _clear_seasons()


# ============================================================
#  Flag + config
# ============================================================

def test_flag_registered_and_off_by_default():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == "ijtihad_seasons"), None)
    assert entry is not None, "ijtihad_seasons must be registered"
    assert entry[3] is False, "must default OFF"


def test_config_defaults():
    cfg = database.get_ijtihad_config()
    assert cfg["ijtihad_season_weeks"] == 4
    assert cfg["ijtihad_season1_start"] == ""


def test_config_override_and_bad_value_falls_back():
    database.set_ijtihad_config("ijtihad_season_weeks", 2)
    assert database.get_ijtihad_config()["ijtihad_season_weeks"] == 2
    database.set_setting("ijtihad_season_weeks", "not-a-number")
    assert database.get_ijtihad_config()["ijtihad_season_weeks"] == 4


def test_unknown_config_key_is_rejected():
    assert database.set_ijtihad_config("ijtihad_nonsense", 1) is False


# ============================================================
#  Season creation
# ============================================================

def test_first_season_starts_on_a_saturday():
    """Season boundaries land on the curriculum's week boundary (Sat=0), not
    mid-week."""
    s = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))  # a Saturday
    assert s is not None
    start = datetime.date.fromisoformat(s["started_on"])
    assert start.weekday() == 5, "season must start on a Saturday"
    assert s["label"] == "Season 1"


def test_anchor_is_most_recent_saturday_for_a_midweek_start():
    s = database.ijtihad_ensure_seasons(datetime.date(2026, 9, 2))  # Wednesday
    assert s["started_on"] == "2026-08-29"  # the Saturday before


def test_season_is_four_weeks_inclusive():
    s = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    start = datetime.date.fromisoformat(s["started_on"])
    end = datetime.date.fromisoformat(s["ends_on"])
    assert (end - start).days == 27  # 28 days inclusive


def test_anchor_is_persisted_so_boundaries_never_shift():
    database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    assert database.get_setting("ijtihad_season1_start") == "2026-08-29"
    # A later call from a different day must NOT re-anchor season 1.
    database.ijtihad_ensure_seasons(datetime.date(2026, 9, 15))
    assert database.ijtihad_all_seasons()[0]["started_on"] == "2026-08-29"


def test_ensure_is_idempotent():
    for _ in range(4):
        database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    assert len(database.ijtihad_all_seasons()) == 1


def test_season_rolls_over_and_is_contiguous():
    database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    s2 = database.ijtihad_ensure_seasons(datetime.date(2026, 9, 27))  # into season 2
    seasons = database.ijtihad_all_seasons()
    assert len(seasons) == 2
    assert s2["label"] == "Season 2"
    # No gap, no overlap.
    end1 = datetime.date.fromisoformat(seasons[0]["ends_on"])
    start2 = datetime.date.fromisoformat(seasons[1]["started_on"])
    assert start2 == end1 + datetime.timedelta(days=1)


def test_long_offline_gap_produces_contiguous_history_not_one_giant_window():
    """If the bot is down for months, seasons must backfill correctly."""
    database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    current = database.ijtihad_ensure_seasons(datetime.date(2026, 12, 5))
    seasons = database.ijtihad_all_seasons()
    assert len(seasons) >= 4
    for a, b in zip(seasons, seasons[1:]):
        assert (datetime.date.fromisoformat(b["started_on"])
                - datetime.date.fromisoformat(a["ends_on"])) == datetime.timedelta(days=1)
    assert (datetime.date.fromisoformat(current["started_on"])
            <= datetime.date(2026, 12, 5)
            <= datetime.date.fromisoformat(current["ends_on"]))


def test_future_anchor_means_no_current_season():
    """The owner can schedule Season 1 to begin later; until then there is no
    current season and nothing breaks."""
    database.set_ijtihad_config("ijtihad_season1_start", "2027-01-02")
    assert database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29)) is None


def test_invalid_anchor_setting_falls_back_gracefully():
    database.set_setting("ijtihad_season1_start", "not-a-date")
    s = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    assert s is not None


def test_season_for_date_is_a_pure_read():
    database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    assert database.ijtihad_season_for_date("2026-08-30")["label"] == "Season 1"
    # A date before any season exists must not create one.
    before = len(database.ijtihad_all_seasons())
    assert database.ijtihad_season_for_date("2020-01-01") is None
    assert len(database.ijtihad_all_seasons()) == before


# ============================================================
#  Season points — the tenure integral is broken here
# ============================================================

def test_points_outside_the_window_do_not_count():
    """THE FIX. Legacy points earned before seasons existed are invisible to the
    season board -- they live in Sijil instead. This is what stops rank from
    being a lifetime integral."""
    _member("legacy", "OldTimer")
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    _award_on("legacy", datetime.date(2026, 1, 15), 50_000)   # ancient
    assert database.ijtihad_season_points("legacy", season) == 0


def test_points_inside_the_window_count():
    _member("worker", "Worker")
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    _award_on("worker", datetime.date(2026, 8, 30), 105)
    _award_on("worker", datetime.date(2026, 8, 31), 205)
    assert database.ijtihad_season_points("worker", season) == 310


def test_window_boundaries_are_inclusive():
    _member("edge", "Edge")
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    _award_on("edge", datetime.date.fromisoformat(season["started_on"]), 10)
    _award_on("edge", datetime.date.fromisoformat(season["ends_on"]), 10)
    day_after = datetime.date.fromisoformat(season["ends_on"]) + datetime.timedelta(days=1)
    _award_on("edge", day_after, 999)
    assert database.ijtihad_season_points("edge", season) == 20


def test_a_newcomer_can_outrank_a_veteran_in_the_same_season():
    """The whole point of the rework, as an executable assertion.

    The veteran has 50,000 lifetime points from months of coasting; the newcomer
    joined this season and worked hard. On the SEASON board the newcomer wins.
    """
    _member("vet", "Veteran")
    _member("new", "Newcomer")
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))

    _award_on("vet", datetime.date(2026, 2, 1), 50_000)          # legacy hoard
    _award_on("vet", datetime.date(2026, 8, 30), 30)             # coasting now
    for d in range(1, 8):                                        # a hard week
        _award_on("new", datetime.date(2026, 8, 29) + datetime.timedelta(days=d), 205)

    board = database.ijtihad_season_leaderboard(season, limit=5)
    assert board[0]["discord_name"] == "Newcomer"
    assert database.ijtihad_season_rank("new", season) == 1
    assert database.ijtihad_season_rank("vet", season) == 2


def test_zero_activity_season_yields_an_empty_board():
    _member("idle", "Idle")
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    assert database.ijtihad_season_leaderboard(season, limit=5) == []


def test_board_excludes_students_with_no_season_activity():
    """Never publish a bottom half (spec R7/N3): only students who actually
    earned something this season appear at all."""
    _member("active1", "Active")
    _member("silent1", "Silent")
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    _award_on("active1", datetime.date(2026, 8, 30), 100)
    names = [r["discord_name"] for r in database.ijtihad_season_leaderboard(season, 5)]
    assert names == ["Active"]


def test_board_respects_limit():
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    for i in range(8):
        mid = f"b{i}"
        _member(mid, f"B{i}")
        _award_on(mid, datetime.date(2026, 8, 30), 10 * (i + 1))
    assert len(database.ijtihad_season_leaderboard(season, limit=3)) == 3


def test_rank_is_zero_when_nothing_earned():
    _member("norank", "NoRank")
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    assert database.ijtihad_season_rank("norank", season) == 0


def test_points_and_board_tolerate_a_missing_season():
    _member("x", "X")
    assert database.ijtihad_season_points("x", None) == 0
    assert database.ijtihad_season_leaderboard(None, 5) == []
    assert database.ijtihad_season_rank("x", None) == 0


def test_inactive_members_are_excluded_from_the_board():
    _member("gone", "Gone")
    season = database.ijtihad_ensure_seasons(datetime.date(2026, 8, 29))
    _award_on("gone", datetime.date(2026, 8, 30), 500)
    database.update_member("gone", status="inactive")
    assert database.ijtihad_season_leaderboard(season, 5) == []


# ============================================================
#  Non-destructiveness
# ============================================================

def test_seasons_do_not_touch_total_points_or_points_log():
    """Phase 2 changes how effort is READ, never what was written. Lifetime
    totals must be untouched so Sijil's Legacy XP stays honest."""
    _member("safe", "Safe")
    database.add_points("safe", 250, "task:x")
    before_total = database.get_member("safe")["total_points"]
    conn = database._connect()
    before_rows = conn.execute(
        "SELECT COUNT(*) FROM points_log WHERE discord_id='safe'").fetchone()[0]
    conn.close()

    season = database.ijtihad_ensure_seasons()
    database.ijtihad_season_points("safe", season)
    database.ijtihad_season_leaderboard(season, 5)
    database.ijtihad_season_rank("safe", season)

    assert database.get_member("safe")["total_points"] == before_total
    conn = database._connect()
    after_rows = conn.execute(
        "SELECT COUNT(*) FROM points_log WHERE discord_id='safe'").fetchone()[0]
    conn.close()
    assert after_rows == before_rows
