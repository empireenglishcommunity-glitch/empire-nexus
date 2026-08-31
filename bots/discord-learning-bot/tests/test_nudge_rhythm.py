"""The nudge adapts to each student's own schedule — no shared clock.

Owner directive (2026-08-31): "I don't want the nudges tied to a specific
timezone. Students complete their tasks at different times based on their own
schedules. The system needs to be smart enough to adapt and only send a
reminder if a task genuinely hasn't been completed, rather than relying on a
rigid clock."

The old nudge fired at 16:00 Asia/Dubai for the whole roster, so a student who
studies in the evening was told she had not been active before her session had
even come round. There is no hour that is "late" for everyone, so the hour is
now learned per student from their own submission times in UTC — which encodes
their local schedule without anyone having to know or state a timezone.

These tests simulate specific moments, so they assert on the DECISION rather
than on whatever the clock happens to say when CI runs.
"""
import datetime

from src import database, tasks as task_engine

UTC = datetime.timezone.utc


def _seed(discord_id: str, days: int, hour_utc: float, *, name="S"):
    """Give a student a habit: active for `days` consecutive days, always
    starting around hour_utc UTC. Written through submitted_at, the same
    column SQLite stamps on a real submission.

    Returns (now, last_submission) — tests must build their probe moments from
    `last_submission`, because the silence that nudge_decision() measures is
    counted from there, not from `now`.
    """
    database.register_member(discord_id, name)
    conn = database._connect()
    now = datetime.datetime.now(UTC)
    last = None
    for i in range(days, 0, -1):
        day = now - datetime.timedelta(days=i)
        ts = day.replace(hour=int(hour_utc) % 24,
                         minute=int((hour_utc % 1) * 60),
                         second=0, microsecond=0)
        conn.execute(
            "INSERT OR IGNORE INTO daily_submissions "
            "(discord_id, date, task_id, submitted_at) VALUES (?,?,?,?)",
            (discord_id, ts.date().isoformat(), f"t{i}",
             ts.strftime("%Y-%m-%d %H:%M:%S")),
        )
        last = ts
    conn.commit()
    conn.close()
    return now, last


# ---------------------------------------------------------------- rhythm maths

def test_circular_mean_handles_midnight_wrap():
    """A plain average fails worst for the students most at risk of a wrong
    nudge: someone studying around midnight UTC produces 23.5 and 0.5, whose
    arithmetic mean is 12:00 — twelve hours out, the middle of their day."""
    got = task_engine._circular_mean_hour([23.5, 0.5, 23.0, 1.0])
    assert got > 23.0 or got < 1.0, f"expected ~midnight, got {got:.2f}"
    naive = sum([23.5, 0.5, 23.0, 1.0]) / 4
    assert abs(naive - 12.0) < 0.5, "sanity: the naive mean really is ~12:00"


def test_circular_mean_matches_plain_mean_away_from_the_wrap():
    got = task_engine._circular_mean_hour([20.0, 21.0, 22.0])
    assert abs(got - 21.0) < 0.05


def test_rhythm_is_learned_from_the_students_own_history():
    _seed("evening", days=14, hour_utc=21.0)
    r = task_engine.activity_rhythm("evening")
    assert r["known"] is True
    assert r["observations"] == 14
    assert abs(r["usual_hour_utc"] - 21.0) < 0.5


# ------------------------------------------------------- the directive itself

def test_evening_student_is_not_nudged_during_our_afternoon():
    """Mai's case, generalised. She studies at 21:00 UTC. At 13:00 UTC — when
    the old 16:00 Dubai job ran — she has done nothing wrong yet."""
    _now, last = _seed("evening", days=14, hour_utc=21.0)
    # 16 hours after her last session — i.e. the following early afternoon UTC,
    # exactly when the old 16:00 Dubai job ran. Her next slot is still hours off.
    at_old_nudge_time = last + datetime.timedelta(hours=16)
    send, reason = task_engine.nudge_decision("evening", now_utc=at_old_nudge_time)
    assert send is False, f"nudged an on-schedule evening student: {reason}"


def test_the_same_student_IS_nudged_once_her_own_slot_has_passed():
    """Adaptive, not silent: after her own window plus grace, she is late."""
    _now, last = _seed("evening", days=14, hour_utc=21.0)
    # Her slot came round again 24h later; give it the grace period plus an hour.
    late = last + datetime.timedelta(hours=24 + task_engine.NUDGE_GRACE_HOURS + 1)
    send, reason = task_engine.nudge_decision("evening", now_utc=late)
    assert send is True, f"failed to nudge a genuinely late student: {reason}"


def test_morning_student_and_evening_student_get_different_hours():
    """The point of the change: one clock cannot serve both."""
    _now, m_last = _seed("morning", days=14, hour_utc=6.0)
    _seed("night", days=14, hour_utc=22.0)
    # One instant, both students: 08:00 UTC the day after the morning student
    # last worked. She is 26h silent and 8h past her 06:00 slot; the 22:00
    # student is only 10h silent and nowhere near hers.
    probe = (m_last + datetime.timedelta(days=1)).replace(hour=14)
    morning_send, _ = task_engine.nudge_decision("morning", now_utc=probe)
    night_send, _ = task_engine.nudge_decision("night", now_utc=probe)
    assert morning_send is True, "06:00 student is 8h past her slot at 14:00"
    assert night_send is False, "22:00 student is not late at 14:00"


def test_never_nudged_inside_24h_of_working():
    """'Genuinely hasn't been completed' — a student who worked 3h ago has."""
    now, _last = _seed("recent", days=10, hour_utc=12.0)
    conn = database._connect()
    ts = now - datetime.timedelta(hours=3)
    conn.execute(
        "INSERT OR IGNORE INTO daily_submissions "
        "(discord_id, date, task_id, submitted_at) VALUES (?,?,?,?)",
        ("recent", ts.date().isoformat(), "fresh",
         ts.strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    send, reason = task_engine.nudge_decision("recent", now_utc=now)
    assert send is False and "not behind" in reason


def test_unknown_rhythm_waits_for_an_unambiguous_gap():
    """With too little history no hour is assumed, so nothing is called 'late'
    until the gap is longer than any schedule difference could explain."""
    _now, last = _seed("newbie", days=2, hour_utc=9.0)
    r = task_engine.activity_rhythm("newbie")
    assert r["known"] is False

    at_30h = last + datetime.timedelta(hours=30)
    send, reason = task_engine.nudge_decision("newbie", now_utc=at_30h)
    assert send is False, f"guessed at a new student's schedule: {reason}"

    at_45h = last + datetime.timedelta(hours=45)
    send, _ = task_engine.nudge_decision("newbie", now_utc=at_45h)
    assert send is True, "a 45h gap is genuinely missed work"


def test_a_student_who_never_submitted_is_not_nudged():
    """Nothing to remind them about yet — that is onboarding's job."""
    database.register_member("fresh", "Fresh")
    send, reason = task_engine.nudge_decision("fresh")
    assert send is False and "never submitted" in reason


def test_decision_is_timezone_independent():
    """The same student, the same instant, must get the same answer however
    the host is configured — that is the whole point of the directive."""
    import os
    from src import config
    _now, last = _seed("tz", days=14, hour_utc=21.0)
    probe = last + datetime.timedelta(hours=16)
    answers = set()
    original = config.TIMEZONE
    try:
        for tz in ("Asia/Dubai", "Africa/Cairo", "UTC", "America/New_York",
                   "Pacific/Auckland"):
            config.TIMEZONE = tz
            os.environ["TZ"] = tz
            answers.add(task_engine.nudge_decision("tz", now_utc=probe)[0])
    finally:
        config.TIMEZONE = original
        os.environ.pop("TZ", None)
    assert answers == {False}, f"answer changed with the host timezone: {answers}"


def test_reason_is_always_explainable():
    """Every decision carries a reason, so a student asking 'why did I get
    this?' can be answered from the log instead of guessed at."""
    _now, last = _seed("why", days=14, hour_utc=8.0)
    for probe in (last, last + datetime.timedelta(hours=12),
                  last + datetime.timedelta(hours=40)):
        send, reason = task_engine.nudge_decision("why", now_utc=probe)
        assert isinstance(reason, str) and len(reason) > 10
        assert isinstance(send, bool)



def test_reminder_stays_near_the_students_own_waking_hours():
    """The window replaces Dubai quiet-hours, which applied one region's night
    to everyone. A restart 20h into someone's gap must not fire instantly at
    whatever hour that happens to be for them."""
    _now, last = _seed("owl", days=14, hour_utc=21.0)
    slot_again = last + datetime.timedelta(days=1)      # her 21:00 slot, next day

    # Inside the window: reminded.
    inside = slot_again + datetime.timedelta(
        hours=task_engine.NUDGE_GRACE_HOURS + 1)
    assert task_engine.nudge_decision("owl", now_utc=inside)[0] is True

    # Well past it — the middle of her night. Must wait for the next slot.
    outside = slot_again + datetime.timedelta(
        hours=task_engine.NUDGE_GRACE_HOURS + task_engine.NUDGE_WINDOW_HOURS + 2)
    send, reason = task_engine.nudge_decision("owl", now_utc=outside)
    assert send is False, f"messaged outside her waking window: {reason}"
    assert "delivery window" in reason


def test_a_long_absence_is_still_caught_at_the_next_slot():
    """Bounding delivery must not let a genuinely absent student slip through:
    the window comes round again every day."""
    _now, last = _seed("gone", days=14, hour_utc=10.0)
    # Four days later, at her usual slot plus the grace period.
    probe = last + datetime.timedelta(
        days=4, hours=task_engine.NUDGE_GRACE_HOURS)
    send, reason = task_engine.nudge_decision("gone", now_utc=probe)
    assert send is True, f"missed a 4-day absence: {reason}"



# ============================================================
#  STREAK-AT-RISK — same defect, higher stakes
# ============================================================
#
# This alert says "your streak will break tonight!". It fired at 21:00 for the
# whole roster, judging "did you work today" by the Asia/Dubai date — so a
# student who habitually studies later than that was alarmed EVERY NIGHT about
# a streak she never lost. More alarming than the nudge that started all this.


def test_late_studier_is_not_alarmed_every_night():
    """The regression. She works in the last hours of the day, every day, and
    is not at risk — so she must not be told she is."""
    _now, last = _seed("cutter", days=14, hour_utc=21.0)
    # 22:00 UTC: 2h of the day left, and her 21:00 slot is where she always is.
    # She worked at 21:00 yesterday and will again tonight.
    now = last + datetime.timedelta(days=1, hours=0)   # her slot, next day
    send, reason = task_engine.streak_alert_decision(
        "cutter", now_utc=now, hours_left=2.0)
    assert send is False, f"alarmed a student who is on her own pattern: {reason}"
    assert "on pattern" in reason


def test_student_who_actually_deviated_is_warned():
    """Not silent: someone who normally works in the morning and still has not
    by late evening is genuinely about to lose the streak."""
    _now, last = _seed("morningperson", days=14, hour_utc=7.0)
    now = last + datetime.timedelta(days=1, hours=14)   # ~21:00 UTC, 14h past slot
    send, reason = task_engine.streak_alert_decision(
        "morningperson", now_utc=now, hours_left=2.0)
    assert send is True, f"failed to warn a genuinely at-risk student: {reason}"


def test_no_alarm_early_in_the_day():
    """With most of the day left, nothing is at risk yet."""
    _now, last = _seed("anyone", days=14, hour_utc=8.0)
    send, reason = task_engine.streak_alert_decision(
        "anyone", now_utc=last + datetime.timedelta(days=1, hours=6),
        hours_left=11.0)
    assert send is False and "too early" in reason


def test_new_student_is_warned_rather_than_losing_a_streak_silently():
    """With too little history we cannot know their habits. Near the boundary,
    warning is the kinder error."""
    database.register_member("brandnew", "New")
    send, reason = task_engine.streak_alert_decision(
        "brandnew", hours_left=1.0)
    assert send is True
    assert "active days on record" in reason


def test_hours_to_boundary_is_a_positive_duration():
    left = task_engine.hours_to_streak_boundary()
    assert 0.0 < left <= 24.0



def test_a_stale_streak_counter_must_not_block_re_engagement():
    """current_streak is only recalculated when a student SUBMITS, so it goes
    stale the moment they stop.

    Verified against production: ten students carried a non-zero streak while
    absent 7 to 33 days — Abeer at 798h with streak 2, ياسمين at 643h with
    streak 12. An earlier version of this fix skipped anyone with
    current_streak > 0 on the reasoning that the message must never contradict a
    live streak, which would have silently disabled the re-engagement nudge for
    exactly the students it exists for.
    """
    _now, last = _seed("churned", days=8, hour_utc=9.0)
    conn = database._connect()
    conn.execute("UPDATE members SET current_streak=12 WHERE discord_id='churned'")
    conn.commit()
    conn.close()

    assert database.get_member("churned")["current_streak"] == 12, "stale counter set"

    # Three weeks later, at her usual slot plus grace.
    probe = last + datetime.timedelta(days=21,
                                      hours=task_engine.NUDGE_GRACE_HOURS)
    send, reason = task_engine.nudge_decision("churned", now_utc=probe)
    assert send is True, (
        f"a student absent three weeks was not nudged because a stale streak "
        f"counter said 12: {reason}")
