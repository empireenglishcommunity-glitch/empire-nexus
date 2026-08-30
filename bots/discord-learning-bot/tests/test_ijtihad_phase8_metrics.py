"""Ijtihad Phase 8 — measurement. Did the rework actually work?

The spec committed to measuring this rather than assuming it (design §9), and
committed to a GUARD metric: if veterans disengaged, the honour track failed to do
its job, and that matters more than any improvement elsewhere. So the guard is
reported alongside the good news rather than buried.

Every number comes from data already collected, so it can be run at any time and
compared against its own history.
"""
import datetime

import pytest

from src import database


TODAY = datetime.date(2026, 8, 30)


@pytest.fixture(autouse=True)
def clean():
    conn = database._connect()
    for sql in ("DELETE FROM seasons", "DELETE FROM student_targets",
                "DELETE FROM streak_freezes", "DELETE FROM points_log",
                "DELETE FROM streaks", "DELETE FROM recognition_log",
                "DELETE FROM settings WHERE key LIKE 'ijtihad_%'"):
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.commit()
    conn.close()
    yield


def _student(mid, name="S", joined_days_ago=90):
    database.register_member(mid, name)
    database.update_member(
        mid, joined_at=(TODAY - datetime.timedelta(days=joined_days_ago)).isoformat())
    return mid


def _did_tasks(mid, day, n):
    conn = database._connect()
    conn.execute(
        "INSERT OR REPLACE INTO streaks (discord_id,date,tasks_completed,all_seven) "
        "VALUES (?,?,?,?)", (mid, day.isoformat(), n, 1 if n >= 7 else 0))
    conn.commit()
    conn.close()


def _season():
    database.set_ijtihad_config("ijtihad_season1_start", "2026-01-03")
    return database.ijtihad_ensure_seasons(TODAY)


def test_metrics_run_on_an_empty_community():
    """Must never divide by zero or crash before anyone has done anything."""
    m = database.ijtihad_metrics(TODAY)
    assert m["active_members"] == 0
    assert m["active_rate_7d"] == 0.0
    assert m["veteran_active_rate_7d"] == 0.0
    assert m["newcomer_in_a_top3"] is False


def test_full_day_rate_counts_against_each_students_own_target():
    s = _season()
    a = _student("m1", "Three")
    b = _student("m2", "Seven")
    database.ijtihad_set_target(a, 3, s)
    database.ijtihad_set_target(b, 7, s)
    for back in range(3):
        _did_tasks(a, TODAY - datetime.timedelta(days=back), 3)   # 3 full days
        _did_tasks(b, TODAY - datetime.timedelta(days=back), 3)   # 0 full days
    m = database.ijtihad_metrics(TODAY)
    assert m["full_days_7d"] == 3


def test_active_rate_is_a_percentage_of_active_members():
    _season()
    _student("a1")
    _student("a2")
    _did_tasks("a1", TODAY, 1)
    m = database.ijtihad_metrics(TODAY)
    assert m["active_rate_7d"] == 50.0


def test_recognition_circulation_counts_distinct_students():
    """The point of the rotating spotlight is that recognition SPREADS. Counting
    distinct students is what detects ossification; counting total recognitions
    would look healthy even if one person won everything."""
    _season()
    _student("r1")
    _student("r2")
    database.ijtihad_record_recognition("r1", "comeback", "k1")
    database.ijtihad_record_recognition("r1", "uphill", "k2")
    database.ijtihad_record_recognition("r2", "comeback", "k3")
    m = database.ijtihad_metrics(TODAY)
    assert m["recognitions_30d"] == 3
    assert m["distinct_recognised_30d"] == 2


def test_newcomer_visibility_detects_a_new_student_in_a_top3():
    """The headline promise of the whole rework: a student who joined days ago can
    be visible. This metric is how we check it actually happened."""
    s = _season()
    vet = _student("vet", "Veteran", joined_days_ago=200)
    new = _student("new", "Newcomer", joined_days_ago=3)
    database.ijtihad_set_target(new, 3, s)
    # Newcomer works hard this season; veteran does nothing.
    conn = database._connect()
    for back in range(5):
        d = (TODAY - datetime.timedelta(days=back)).isoformat()
        conn.execute(
            "INSERT INTO points_log (discord_id,points,reason,logged_at) VALUES (?,?,?,?)",
            (new, 100, "task:x", f"{d} 12:00:00"))
    conn.commit()
    conn.close()
    m = database.ijtihad_metrics(TODAY)
    assert m["newcomers_14d"] == 1
    assert m["newcomer_in_a_top3"] is True


def test_guard_metric_reports_veteran_engagement():
    """If this drops, the honour track failed and that outweighs any other gain."""
    _season()
    v1 = _student("v1", "V1", joined_days_ago=200)
    v2 = _student("v2", "V2", joined_days_ago=300)
    _student("n1", "N1", joined_days_ago=5)
    _did_tasks(v1, TODAY, 3)          # one veteran active
    m = database.ijtihad_metrics(TODAY)
    assert m["veterans"] == 2
    assert m["veterans_active_7d"] == 1
    assert m["veteran_active_rate_7d"] == 50.0


def test_guard_metric_ignores_activity_outside_the_window():
    _season()
    v = _student("v3", "V3", joined_days_ago=200)
    _did_tasks(v, TODAY - datetime.timedelta(days=30), 7)
    m = database.ijtihad_metrics(TODAY)
    assert m["veterans_active_7d"] == 0


def test_metrics_tolerate_a_missing_join_date():
    _season()
    mid = _student("bad1")
    database.update_member(mid, joined_at="")
    m = database.ijtihad_metrics(TODAY)
    assert m["active_members"] == 1     # counted, just not classified


def test_metrics_include_the_season_window():
    s = _season()
    m = database.ijtihad_metrics(TODAY)
    assert m["season"]["label"] == s["label"]


# ============================================================
#  The guard must be able to tell "nobody disengaged" from "I can see nothing"
# ============================================================

def test_veteran_threshold_is_tunable():
    """Hardcoded at 60 days it reported ZERO veterans on a ~33-day-old community,
    so the guard read 0.0% no matter what happened."""
    assert database.get_ijtihad_config()["ijtihad_veteran_days"] == 30
    database.set_ijtihad_config("ijtihad_veteran_days", 10)
    assert database.get_ijtihad_config()["ijtihad_veteran_days"] == 10


def test_guard_reports_when_it_cannot_see_anything():
    """A guard that cannot fire is worse than no guard, because it looks like
    reassurance. It must say so explicitly."""
    _season()
    _student("young", "Young", joined_days_ago=3)
    m = database.ijtihad_metrics(TODAY)
    assert m["veterans"] == 0
    assert m["guard_meaningful"] is False


def test_guard_becomes_meaningful_once_someone_is_old_enough():
    _season()
    _student("older", "Older", joined_days_ago=45)
    m = database.ijtihad_metrics(TODAY)
    assert m["veterans"] == 1
    assert m["guard_meaningful"] is True


def test_lowering_the_threshold_makes_the_guard_see_a_young_community():
    _season()
    _student("y1", "Y1", joined_days_ago=20)
    assert database.ijtihad_metrics(TODAY)["guard_meaningful"] is False
    database.set_ijtihad_config("ijtihad_veteran_days", 14)
    m = database.ijtihad_metrics(TODAY)
    assert m["veterans"] == 1
    assert m["guard_meaningful"] is True
    assert m["veteran_days"] == 14
