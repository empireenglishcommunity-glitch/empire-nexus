"""Ijtihad — season re-anchoring, and the mixed-rate window it fixes.

THE PROBLEM
Season 1 launched on 2026-08-29 while the OLD award table was still active, and
the new table (Phase 7) was enabled a day later. That left Season 1 holding ~2
days of points earned at roughly double the current rate — about a 220-point
(~8% of a season) head start for whoever happened to work those two days. Small,
but real, and invisible to the students it affected.

WHY RE-ANCHORING RATHER THAN ADJUSTING POINTS
The mixed-rate days simply fall outside the season window and become legacy points
— still counted for life, still shown in Sijil — exactly as every pre-Ijtihad
point already does. Nothing is rewritten, and it is explainable in one sentence:
"your earlier work still counts in your record; the season race now starts fresh
for everyone." A downward points adjustment would be neither.
"""
import datetime

import pytest

from src import database


@pytest.fixture(autouse=True)
def clean():
    conn = database._connect()
    for sql in ("DELETE FROM seasons", "DELETE FROM points_log",
                "DELETE FROM student_targets", "DELETE FROM streak_freezes",
                "DELETE FROM settings WHERE key LIKE 'ijtihad_%'"):
        conn.execute(sql)
    conn.commit()
    conn.close()
    yield


def _earn(mid, points, day):
    conn = database._connect()
    conn.execute(
        "INSERT INTO points_log (discord_id,points,reason,logged_at) VALUES (?,?,?,?)",
        (mid, points, "task:x", f"{day.isoformat()} 12:00:00"))
    conn.commit()
    conn.close()


# ============================================================
#  The fix itself
# ============================================================

def test_reanchor_moves_mixed_rate_days_out_of_the_season():
    """THE FIX. Legacy-rate points earned before the new table become legacy —
    out of the season board, still in the lifetime total."""
    database.register_member("early", "EarlyBird")
    today = database._today_local()
    yesterday = today - datetime.timedelta(days=1)

    database.set_ijtihad_config("ijtihad_season1_start", yesterday.isoformat())
    season = database.ijtihad_ensure_seasons(today)
    _earn("early", 205, yesterday)        # old-rate day, inside Season 1
    _earn("early", 95, today)             # new-rate day
    assert database.ijtihad_season_points("early", season) == 300

    ok, detail = database.ijtihad_reanchor_seasons(today.isoformat())
    assert ok is True
    new_season = detail["season"]
    assert new_season["started_on"] == today.isoformat()
    # Only the new-rate day counts toward the season now.
    assert database.ijtihad_season_points("early", new_season) == 95


def test_reanchor_does_not_touch_lifetime_points_or_the_ledger():
    """Non-destructive: season rows are only date WINDOWS."""
    database.register_member("keep", "Keeper")
    database.add_points("keep", 205, "task:x")
    today = database._today_local()
    database.set_ijtihad_config("ijtihad_season1_start",
                                (today - datetime.timedelta(days=1)).isoformat())
    database.ijtihad_ensure_seasons(today)

    before_total = database.get_member("keep")["total_points"]
    conn = database._connect()
    before_rows = conn.execute(
        "SELECT COUNT(*) FROM points_log WHERE discord_id='keep'").fetchone()[0]
    conn.close()

    database.ijtihad_reanchor_seasons(today.isoformat())

    assert database.get_member("keep")["total_points"] == before_total
    conn = database._connect()
    after_rows = conn.execute(
        "SELECT COUNT(*) FROM points_log WHERE discord_id='keep'").fetchone()[0]
    conn.close()
    assert after_rows == before_rows


def test_earlier_points_remain_in_sijil_as_legacy():
    """Nothing is taken away — the work still counts for life."""
    database.register_member("vet", "Veteran")
    database.add_points("vet", 205, "task:x")
    today = database._today_local()
    database.set_ijtihad_config("ijtihad_season1_start",
                                (today - datetime.timedelta(days=1)).isoformat())
    database.ijtihad_ensure_seasons(today)
    database.ijtihad_reanchor_seasons(today.isoformat())
    assert database.sijil_record("vet")["legacy_xp"] == 205


def test_reanchor_produces_exactly_one_season():
    today = database._today_local()
    database.set_ijtihad_config("ijtihad_season1_start",
                                (today - datetime.timedelta(days=1)).isoformat())
    database.ijtihad_ensure_seasons(today)
    database.ijtihad_reanchor_seasons(today.isoformat())
    seasons = database.ijtihad_all_seasons()
    assert len(seasons) == 1
    assert seasons[0]["label"] == "Season 1"


def test_reanchor_keeps_the_season_length():
    today = database._today_local()
    database.set_ijtihad_config("ijtihad_season1_start", today.isoformat())
    database.ijtihad_ensure_seasons(today)
    ok, detail = database.ijtihad_reanchor_seasons(today.isoformat())
    s = detail["season"]
    span = (datetime.date.fromisoformat(s["ends_on"])
            - datetime.date.fromisoformat(s["started_on"])).days
    assert span == 27      # 28 days inclusive


def test_reanchor_persists_the_new_anchor():
    today = database._today_local()
    database.ijtihad_reanchor_seasons(today.isoformat())
    assert database.get_setting("ijtihad_season1_start") == today.isoformat()


# ============================================================
#  Guards
# ============================================================

def test_reanchor_rejects_a_bad_date():
    ok, reason = database.ijtihad_reanchor_seasons("not-a-date")
    assert ok is False
    assert reason == "bad_date"


def test_reanchor_refuses_once_more_than_one_season_exists():
    """Re-anchoring later would retroactively move a window students had already
    competed in."""
    today = database._today_local()
    database.set_ijtihad_config("ijtihad_season1_start", "2026-01-03")
    database.ijtihad_ensure_seasons(today)     # backfills several seasons
    assert len(database.ijtihad_all_seasons()) > 1
    ok, reason = database.ijtihad_reanchor_seasons(today.isoformat())
    assert ok is False
    assert reason == "multiple_seasons"


def test_reanchor_refuses_when_the_only_season_has_finished():
    conn = database._connect()
    conn.execute(
        "INSERT INTO seasons (label, started_on, ends_on) VALUES (?,?,?)",
        ("Season 1", "2026-01-03", "2026-01-30"))
    conn.commit()
    conn.close()
    ok, reason = database.ijtihad_reanchor_seasons(
        database._today_local().isoformat())
    assert ok is False
    assert reason == "season_completed"


def test_reanchor_to_a_future_date_leaves_no_active_season():
    ok, detail = database.ijtihad_reanchor_seasons("2099-01-02")
    assert ok is True
    assert detail["season"] is None
    assert database.ijtihad_current_season() is None
