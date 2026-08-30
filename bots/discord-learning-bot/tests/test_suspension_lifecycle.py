"""Suspension lifecycle — monthly membership withdrawal, restore, retention.

The owner's condition on 2026-08-30 was explicit: suspension must preserve
EVERYTHING, and !restore must resume from the exact point the student stopped.
So the most important tests here are the ones asserting that suspension deletes
nothing at all, and that a 40-day streak survives a multi-week gap.

The second most important is that the purge cannot run without an archive.
Payments happen on WhatsApp, entirely outside this system — there is no payment
table — so the purge is driven only by a flag the owner maintains by hand. An
un-archived purge would be an unrecoverable way to lose a paying student's
history.
"""
import datetime
import json
import os

import pytest

from src import database, suspension


def _mk(discord_id="100", name="Test Student", level="A1"):
    database.register_member(discord_id, name, level=level)
    return discord_id


def _seed_history(discord_id, days=5, tasks_per_day=7):
    """Give a student real, recomputed history — submissions + streak rows."""
    today = database._today_local()
    for i in range(days):
        d = (today - datetime.timedelta(days=days - 1 - i)).isoformat()
        for t in range(tasks_per_day):
            database.log_submission(discord_id, d, f"task{t}")
        database.update_streak(discord_id, d, tasks_per_day)
    database.add_points(discord_id, 500, "test:seed")


# ============================================================
#  SUSPENSION PRESERVES EVERYTHING
# ============================================================

def test_suspend_deletes_nothing():
    """The owner's hard condition. Every counter and row survives."""
    did = _mk()
    _seed_history(did, days=5)

    before_rows = database.member_snapshot(did)["total_rows"]
    before = database.get_member(did)
    before_points = before["total_points"]
    before_streak = before["current_streak"]

    assert database.suspend_member(did) is True

    after = database.get_member(did)
    assert after["total_points"] == before_points
    assert after["current_streak"] == before_streak
    assert after["longest_streak"] == before["longest_streak"]
    assert database.member_snapshot(did)["total_rows"] == before_rows
    assert len(database.get_submissions_since(did, days=30)) > 0


def test_suspend_sets_the_clock_and_status():
    did = _mk()
    database.suspend_member(did)
    m = database.get_member(did)
    assert m["suspended_at"]           # the retention clock
    assert m["status"] == "suspended"  # drops out of all_active_members
    assert database.is_suspended(did) is True
    assert did not in [x["discord_id"] for x in database.all_active_members()]


def test_resuspending_does_not_move_the_clock():
    """Otherwise a stray second !suspend silently extends retention."""
    did = _mk()
    database.suspend_member(did, when="2026-07-01 00:00:00")
    first = database.get_member(did)["suspended_at"]
    assert database.suspend_member(did) is False   # no-op
    assert database.get_member(did)["suspended_at"] == first


def test_suspended_members_reports_days_and_countdown():
    did = _mk()
    twenty_ago = (datetime.datetime.now(datetime.timezone.utc)
                  - datetime.timedelta(days=20)).strftime("%Y-%m-%d %H:%M:%S")
    database.suspend_member(did, when=twenty_ago)
    row = database.suspended_members()[0]
    assert row["days_suspended"] == pytest.approx(20, abs=1)
    assert row["days_until_purge"] == pytest.approx(
        database.RETENTION_DAYS - 20, abs=1)


# ============================================================
#  RESTORE RESUMES, NEVER RESTARTS
# ============================================================

def test_restore_clears_flag_and_returns_the_gap_start():
    did = _mk()
    database.suspend_member(did, when="2026-07-01 00:00:00")
    was = database.restore_member(did)
    assert was == "2026-07-01 00:00:00"
    m = database.get_member(did)
    assert m["suspended_at"] is None
    assert m["status"] == "active"


def test_restore_of_an_active_member_is_a_noop():
    did = _mk()
    assert database.restore_member(did) is None


def test_restore_preserves_points_and_streak_counters():
    did = _mk()
    _seed_history(did, days=5)
    before = database.get_member(did)
    database.suspend_member(did)
    database.restore_member(did)
    after = database.get_member(did)
    assert after["total_points"] == before["total_points"]
    assert after["current_streak"] == before["current_streak"]


# ============================================================
#  THE STREAK BRIDGE — the part that protects a 40-day streak
# ============================================================

def test_gap_days_excludes_today():
    """Today is a day the student CAN work again, so bridging it would hand
    them a free day they didn't earn."""
    today = database._today_local()
    start = today - datetime.timedelta(days=3)
    gap = suspension._gap_days(start.isoformat())
    assert today.isoformat() not in gap
    assert (today - datetime.timedelta(days=1)).isoformat() in gap
    assert start.isoformat() in gap
    assert len(gap) == 3


def test_gap_days_empty_when_suspended_today():
    gap = suspension._gap_days(database._today_local().isoformat())
    assert gap == []


def test_add_maintenance_days_is_additive_and_deduped():
    assert database.add_maintenance_days(["2026-09-02", "2026-09-03"]) == 2
    assert database.add_maintenance_days(["2026-09-03"]) == 0  # already there
    assert database.add_maintenance_days(["2026-09-04"]) == 1
    stored = json.loads(database.get_setting("maintenance_days", "[]"))
    assert stored == ["2026-09-02", "2026-09-03", "2026-09-04"]


def test_bridged_suspension_gap_preserves_a_long_streak():
    """The whole point. Build a streak, suspend, bridge the gap, come back
    weeks later — the streak must CONTINUE, not reset to 1."""
    did = _mk()
    today = database._today_local()

    # 10 consecutive active days ending 15 days ago.
    first = today - datetime.timedelta(days=24)
    for i in range(10):
        d = (first + datetime.timedelta(days=i)).isoformat()
        database.log_submission(did, d, "vocab")
        database.update_streak(did, d, 7)

    # The stored counter is 0, not 10: `current_streak` means "consecutive days
    # ENDING TODAY", and this run ended a fortnight ago. That is also precisely
    # why the bridge matters — the 10 days are still in the `streaks` table and
    # can be reconnected, but only if the gap between them and today is forgiven.
    assert database.get_member(did)["current_streak"] == 0

    # Suspended the day after that last active day.
    gap_start = first + datetime.timedelta(days=10)
    database.suspend_member(did, when=gap_start.isoformat() + " 00:00:00")

    # Restored today: bridge exactly the no-access window.
    was = database.restore_member(did)
    bridged = database.add_maintenance_days(suspension._gap_days(was))
    assert bridged == 14

    # First submission back. Without the bridge this would recompute to 1.
    database.log_submission(did, today.isoformat(), "vocab")
    database.update_streak(did, today.isoformat(), 7)
    assert database.get_member(did)["current_streak"] == 11


def test_unbridged_gap_would_reset_the_streak():
    """Control for the test above — proves the bridge is what does the work,
    not some incidental behaviour of the recompute."""
    did = _mk()
    today = database._today_local()
    first = today - datetime.timedelta(days=24)
    for i in range(10):
        d = (first + datetime.timedelta(days=i)).isoformat()
        database.log_submission(did, d, "vocab")
        database.update_streak(did, d, 7)

    database.log_submission(did, today.isoformat(), "vocab")
    database.update_streak(did, today.isoformat(), 7)
    assert database.get_member(did)["current_streak"] == 1


# ============================================================
#  60-DAY RETENTION
# ============================================================

def _suspend_days_ago(did, days):
    when = (datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    database.suspend_member(did, when=when)


def test_nobody_is_due_before_the_window_closes():
    did = _mk()
    _suspend_days_ago(did, database.RETENTION_DAYS - 5)
    assert database.members_due_for_purge() == []


def test_due_for_purge_once_the_window_elapses():
    did = _mk()
    _suspend_days_ago(did, database.RETENTION_DAYS + 1)
    assert [m["discord_id"] for m in database.members_due_for_purge()] == [did]


def test_warning_fires_only_inside_the_final_week():
    early, late = _mk("201", "Early"), _mk("202", "Late")
    _suspend_days_ago(early, database.RETENTION_DAYS - 30)   # too soon
    _suspend_days_ago(late, database.RETENTION_DAYS - 3)     # inside 7 days
    warned = [m["discord_id"] for m in database.members_due_for_purge_warning()]
    assert warned == [late]


def test_active_members_are_never_due():
    _mk()
    assert database.members_due_for_purge() == []
    assert database.members_due_for_purge_warning() == []


# ============================================================
#  PURGE
# ============================================================

def test_snapshot_covers_every_table_not_just_the_reset_list():
    """A purge that reused RESET_WIPE_TABLES would leave rows behind in ~10
    tables while reporting the data as deleted."""
    did = _mk()
    _seed_history(did, days=3)
    database.ijtihad_record_recognition(did, "refinement", "2026-W35")

    snap = database.member_snapshot(did)
    assert "recognition_log" in snap["tables"], \
        "recognition_log is absent from RESET_WIPE_TABLES — dynamic discovery " \
        "is what stops it being missed"
    assert "daily_submissions" in snap["tables"]
    assert snap["total_rows"] > 0


def test_purge_removes_everything_including_the_member_row():
    did = _mk()
    _seed_history(did, days=3)
    assert database.get_member(did) is not None

    deleted = database.purge_member(did)

    assert deleted["members"] == 1
    assert deleted["_total"] > 1
    assert database.get_member(did) is None
    assert database.member_snapshot(did)["total_rows"] == 0


def test_purge_leaves_other_students_untouched():
    keep, go = _mk("301", "Keep"), _mk("302", "Go")
    _seed_history(keep, days=3)
    _seed_history(go, days=3)
    before = database.member_snapshot(keep)["total_rows"]

    database.purge_member(go)

    assert database.get_member(keep) is not None
    assert database.member_snapshot(keep)["total_rows"] == before


def test_purge_one_refuses_without_an_archive(monkeypatch):
    """Leaving the data in place is always the safer failure."""
    did = _mk()
    _seed_history(did, days=2)
    monkeypatch.setattr(suspension, "write_archive", lambda row: (None, 0))

    out = suspension.purge_one({"discord_id": did, "discord_name": "Test"})

    assert out["skipped"]
    assert out["deleted"] == {}
    assert database.get_member(did) is not None, \
        "data must survive a failed archive"


def test_purge_one_archives_then_deletes(tmp_path, monkeypatch):
    did = _mk()
    _seed_history(did, days=3)
    monkeypatch.setattr(suspension, "ARCHIVE_DIR", str(tmp_path / "purged"))

    out = suspension.purge_one({"discord_id": did, "discord_name": "Test Student",
                                "suspended_at": "2026-07-01 00:00:00"})

    assert out["archived"] and os.path.exists(out["archived"])
    assert out["rows_archived"] > 0
    assert database.get_member(did) is None

    with open(out["archived"], encoding="utf-8") as fh:
        saved = json.load(fh)
    assert saved["discord_id"] == did
    assert saved["suspended_at"] == "2026-07-01 00:00:00"
    assert saved["total_rows"] == out["rows_archived"]
    assert "daily_submissions" in saved["tables"]


def test_reset_consent_log_is_never_purged():
    """It is the append-only proof that a wipe was authorised."""
    conn = database._connect()
    assert "reset_consent_log" not in database._tables_with_discord_id(conn)
    conn.close()


# ============================================================
#  MESSAGE CONTENT
# ============================================================

def test_renewal_dm_states_the_exact_cutoff_and_retention():
    msg = suspension.renewal_dm("Mai Mohamed", "الأربعاء ٢ سبتمبر")
    assert "الأربعاء ٢ سبتمبر" in msg
    assert str(database.RETENTION_DAYS) in msg, \
        "promising preservation without stating the limit is a promise we break"
    assert "wa.me" in msg


def test_renewal_dm_uses_the_first_name_only():
    assert suspension.renewal_dm("Mai Mohamed", "X").startswith("مرحب Mai")


def test_renewal_dm_gender_variants_differ():
    f = suspension.renewal_dm("A", "X", gender="f")
    m = suspension.renewal_dm("A", "X", gender="m")
    neutral = suspension.renewal_dm("A", "X")
    assert "عايزة تكمّلي" in f
    assert "عايز تكمّل" in m
    # Unknown gender must not silently guess — it avoids the inflection instead.
    assert "عايزة" not in neutral and "عايز تكمّل" not in neutral


def test_stat_block_is_only_included_when_supplied():
    assert "📊" not in suspension.renewal_dm("A", "X")
    assert "📊" in suspension.renewal_dm("A", "X", stats="٤٢ يوم")


def test_telegram_variant_carries_no_markdown():
    """_send_telegram_groups posts without parse_mode, so ** would render
    literally."""
    assert "**" not in suspension.renewal_telegram("الأربعاء ٢ سبتمبر")


def test_discord_messages_fit_the_2000_char_limit():
    long_stats = "٤٢ يوم شغل — مفيش ولا يوم واحد فاتك، وسلسلة ٤٢ يوم\n   " \
                 "٥ امتحانات، نجحتي في الخمسة، ٤ منهم بامتياز"
    for msg in (suspension.renewal_dm("Test Student", "الأربعاء ٢ سبتمبر",
                                      gender="f", stats=long_stats),
                suspension.renewal_announcement("الأربعاء ٢ سبتمبر")):
        assert len(msg) < 2000, f"{len(msg)} chars exceeds Discord's limit"


# ============================================================
#  SELECTORS
# ============================================================

def test_all_selector_excludes_already_suspended():
    a, b = _mk("401", "Active"), _mk("402", "Suspended")
    database.suspend_member(b)
    rows, desc = suspension.resolve_selection("all")
    assert [r["discord_id"] for r in rows] == [a]
    assert "1" in desc


def test_suspended_selector_returns_only_suspended():
    _mk("501", "Active")
    b = _mk("502", "Suspended")
    database.suspend_member(b)
    rows, _ = suspension.resolve_selection("suspended")
    assert [r["discord_id"] for r in rows] == [b]


def test_unknown_selector_returns_nothing():
    _mk()
    assert suspension.resolve_selection("")[0] == []
    assert suspension.resolve_selection("everyone")[0] == []


def test_flag_is_registered_and_defaults_off():
    from src import flag_registry
    info = flag_registry.get_flag_info(suspension.FLAG)
    assert info is not None, "a new flag must be registered in the same PR"
    assert info["default_enabled"] is False
