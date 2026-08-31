"""The inactivity nudge must never tell a working student she is not working.

WHAT HAPPENED (2026-08-31)
--------------------------
Mai had a 43-day streak and 100% weekly completion. At 06:00 the bot DMed her
a report saying "أداء ممتاز! استمر كده" (excellent work, keep going). Nine
hours later, the same bot DMed her:

    "We noticed you haven't been active. Even one task today keeps your streak
     alive."

Her streak was alive. She had not missed a day in six weeks. As the owner put
it, this reflects unprofessionalism — and it was not a one-off: it fired for
every student who studies later in the day, every single day.

THE CAUSE was a string comparison between two different timestamp formats.
`last_active_at` is written both as SQL datetime('now') -> "2026-08-30 23:59:00"
(UTC, SPACE) and, from the practice site, as Python .isoformat() ->
"2026-08-30T23:59:00" (LOCAL, "T"). The cutoff was .isoformat(), so "T". At
index 10, " " (32) sorts before "T" (84), so any activity on the cutoff's own
calendar date compared as older than the cutoff. "Active 17 hours ago" read as
"inactive for over a day".

These tests pin the behaviour, not the implementation: they assert about who
gets nudged, so they keep holding if the query is rewritten again.
"""
import datetime

from src import config, database, tasks as task_engine


def _mai(last_active_sql_offset: str = "-17 hours", streak: int = 43):
    """Mai as she actually was: long live streak, worked yesterday evening,
    last_active_at written the way add_submission() writes it — UTC, space
    separator, via SQLite itself."""
    database.register_member("mai", "Mai Mohamed")
    conn = database._connect()
    conn.execute(
        "UPDATE members SET last_active_at=datetime('now', ?), current_streak=? "
        "WHERE discord_id='mai'",
        (last_active_sql_offset, streak),
    )
    conn.commit()
    conn.close()


def test_student_active_yesterday_evening_is_not_inactive():
    """The exact regression. 17 hours ago is not "a day inactive"."""
    _mai()
    flagged = [m["discord_id"] for m in database.inactive_members(1)]
    assert "mai" not in flagged, (
        "a student who worked 17 hours ago was reported inactive — the "
        "space-vs-T string comparison is back"
    )


def test_the_space_vs_T_format_mismatch_specifically():
    """Both writers' formats must behave identically.

    The practice site wrote "T" and local time; add_submission writes a space
    and UTC. Whichever wrote the row, a recent timestamp must read as recent.
    """
    for label, value in (
        ("space separator (add_submission)",
         datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        ("T separator (practice site)",
         datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")),
    ):
        database.register_member("u_fmt", "Fmt")
        database.update_member("u_fmt", last_active_at=value)
        flagged = [m["discord_id"] for m in database.inactive_members(1)]
        assert "u_fmt" not in flagged, f"active-now student flagged: {label}"
        conn = database._connect()
        conn.execute("DELETE FROM members WHERE discord_id='u_fmt'")
        conn.commit()
        conn.close()


def test_a_genuinely_absent_student_is_still_found():
    """The fix must not silence the nudge altogether — it still has a job."""
    _mai(last_active_sql_offset="-9 days", streak=0)
    flagged = [m["discord_id"] for m in database.inactive_members(3)]
    assert "mai" in flagged, "a student absent 9 days must still be flagged"


def test_suspended_members_are_not_nudged_about_being_inactive():
    """They are inactive by design. DMing them about it is noise."""
    database.register_member("susp", "Suspended Student")
    conn = database._connect()
    conn.execute(
        "UPDATE members SET last_active_at=datetime('now','-30 days'), "
        "suspended_at=datetime('now') WHERE discord_id='susp'")
    conn.commit()
    conn.close()
    flagged = [m["discord_id"] for m in database.inactive_members(1)]
    assert "susp" not in flagged


def test_one_intervention_per_member_not_five():
    """check_inactive_members() promised this in a comment and did not do it.

    A student absent 9 days used to appear in dm_reminder AND buddy_outreach
    AND moderator_checkin AND reengagement_conversation AND membership_pause —
    five interventions at once, the mildest of them absurd by then.
    """
    _mai(last_active_sql_offset="-9 days", streak=0)
    buckets = task_engine.check_inactive_members()
    appearances = [action for action, members in buckets.items()
                   if any(m["discord_id"] == "mai" for m in members)]
    assert len(appearances) == 1, (
        f"expected exactly one intervention, got {len(appearances)}: {appearances}")
    # 9 days is past the largest threshold, so it must be the most serious one.
    worst = config.INTERVENTION_THRESHOLDS[max(config.INTERVENTION_THRESHOLDS)]
    assert appearances[0] == worst, f"expected {worst}, got {appearances[0]}"


def test_days_since_active_is_utc_correct_and_never_raises():
    """It compared a UTC column against naive local time, and .days truncation
    turned that offset into a whole extra day. It also raised on NULL."""
    database.register_member("u_ds", "DS")
    conn = database._connect()
    conn.execute("UPDATE members SET last_active_at=datetime('now','-2 hours') "
                 "WHERE discord_id='u_ds'")
    conn.commit()
    conn.close()
    m = database.get_member("u_ds")
    assert database.days_since_active(m) == 0, (
        "2 hours ago must be 0 days, whatever the host timezone")

    # NULL / junk must degrade, not take an owner report down with it.
    assert database.days_since_active({"last_active_at": None}) == 0
    assert database.days_since_active({"last_active_at": ""}) == 0
    assert database.days_since_active({"last_active_at": "not a date"}) == 0
    assert database.days_since_active({}) == 0


def test_timestamp_writers_agree_on_format():
    """utc_now_str() exists so no caller reaches for .isoformat() again."""
    assert database.utc_now_str() == database.utc_now_str()[:19]
    assert " " in database.utc_now_str() and "T" not in database.utc_now_str()
    conn = database._connect()
    sqlite_fmt = conn.execute("SELECT datetime('now')").fetchone()[0]
    conn.close()
    assert len(database.utc_now_str()) == len(sqlite_fmt), (
        "utc_now_str() must match SQLite datetime('now') exactly in shape")
