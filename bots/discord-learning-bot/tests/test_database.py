"""Tests for src/database.py — SQLite persistence layer."""
import datetime

from src import database


# ============================================================
#  MEMBERS
# ============================================================

def test_register_member_new_returns_true():
    assert database.register_member("u1", "Alice") is True


def test_register_member_existing_returns_false():
    database.register_member("u1", "Alice")
    assert database.register_member("u1", "Alice") is False


def test_register_member_defaults():
    database.register_member("u1", "Alice")
    m = database.get_member("u1")
    assert m["level"] == "L0"
    assert m["track"] == "Core"
    assert m["status"] == "active"
    assert m["total_points"] == 0
    assert m["current_streak"] == 0


def test_register_member_updates_name_on_re_register():
    database.register_member("u1", "Alice")
    database.register_member("u1", "Alice2")
    m = database.get_member("u1")
    assert m["discord_name"] == "Alice2"


def test_get_member_not_found_returns_none():
    assert database.get_member("nonexistent") is None


def test_update_member_arbitrary_fields():
    database.register_member("u1", "Alice")
    database.update_member("u1", total_points=50, current_streak=3)
    m = database.get_member("u1")
    assert m["total_points"] == 50
    assert m["current_streak"] == 3


def test_update_member_no_fields_is_noop():
    database.register_member("u1", "Alice")
    database.update_member("u1")  # should not raise
    assert database.get_member("u1") is not None


def test_set_level():
    database.register_member("u1", "Alice")
    database.set_level("u1", "L1")
    assert database.get_member("u1")["level"] == "L1"


# ============================================================
#  NOTIFICATION LOG / THROTTLING (Masar M4, R5)
# ============================================================

def test_was_notification_sent_within_false_when_never_sent():
    database.register_member("u1", "Alice")
    assert database.was_notification_sent_within("u1", "difficulty_change", days=7) is False


def test_was_notification_sent_within_true_for_recent_send():
    database.register_member("u1", "Alice")
    today = datetime.date.today().isoformat()
    database.log_notification("u1", "difficulty_change", today)
    assert database.was_notification_sent_within("u1", "difficulty_change", days=7) is True


def test_was_notification_sent_within_false_once_outside_window():
    database.register_member("u1", "Alice")
    old_date = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    database.log_notification("u1", "difficulty_change", old_date)
    assert database.was_notification_sent_within("u1", "difficulty_change", days=7) is False


def test_was_notification_sent_within_boundary_is_inclusive():
    database.register_member("u1", "Alice")
    exactly_7_days_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    database.log_notification("u1", "difficulty_change", exactly_7_days_ago)
    assert database.was_notification_sent_within("u1", "difficulty_change", days=7) is True


def test_was_notification_sent_within_only_matches_same_type():
    database.register_member("u1", "Alice")
    today = datetime.date.today().isoformat()
    database.log_notification("u1", "streak_alert", today)
    assert database.was_notification_sent_within("u1", "difficulty_change", days=7) is False


def test_all_active_members_excludes_inactive():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.update_member("u2", status="inactive")
    active = database.all_active_members()
    ids = [m["discord_id"] for m in active]
    assert "u1" in ids
    assert "u2" not in ids


def test_all_active_members_ordered_by_points_desc():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.update_member("u1", total_points=10)
    database.update_member("u2", total_points=50)
    active = database.all_active_members()
    assert active[0]["discord_id"] == "u2"


def test_members_at_level():
    database.register_member("u1", "Alice", level="L1")
    database.register_member("u2", "Bob", level="L0")
    l1_members = database.members_at_level("L1")
    assert len(l1_members) == 1
    assert l1_members[0]["discord_id"] == "u1"


# ============================================================
#  DAILY SUBMISSIONS
# ============================================================

def test_log_submission_new_returns_true():
    database.register_member("u1", "Alice")
    assert database.log_submission("u1", "2026-07-12", "vocab") is True


def test_log_submission_duplicate_returns_false():
    database.register_member("u1", "Alice")
    database.log_submission("u1", "2026-07-12", "vocab")
    assert database.log_submission("u1", "2026-07-12", "vocab") is False


def test_log_submission_different_task_same_day_both_succeed():
    database.register_member("u1", "Alice")
    assert database.log_submission("u1", "2026-07-12", "vocab") is True
    assert database.log_submission("u1", "2026-07-12", "writing") is True


def test_get_submissions_for_date():
    database.register_member("u1", "Alice")
    database.log_submission("u1", "2026-07-12", "vocab", content="hello")
    subs = database.get_submissions_for_date("u1", "2026-07-12")
    assert len(subs) == 1
    assert subs[0]["task_id"] == "vocab"
    assert subs[0]["content"] == "hello"


def test_count_submissions_for_date():
    database.register_member("u1", "Alice")
    assert database.count_submissions_for_date("u1", "2026-07-12") == 0
    database.log_submission("u1", "2026-07-12", "vocab")
    database.log_submission("u1", "2026-07-12", "writing")
    assert database.count_submissions_for_date("u1", "2026-07-12") == 2


def test_tasks_completed_today():
    database.register_member("u1", "Alice")
    today = datetime.date.today().isoformat()
    database.log_submission("u1", today, "vocab")
    database.log_submission("u1", today, "writing")
    completed = database.tasks_completed_today("u1")
    assert set(completed) == {"vocab", "writing"}


# ============================================================
#  STREAKS
# ============================================================

def test_update_streak_sets_current_streak():
    """Found via load/scale testing (unrelated change, discovered while
    running the full suite): this test hardcoded a literal past date
    ("2026-07-12") instead of computing it relative to today, like every
    other streak test in this file already does. _recompute_streak()
    compares the stored date against datetime.date.today(), so this was
    a ticking time bomb -- it passed for as long as "today" happened to
    still be 2026-07-12, then started failing the moment the real clock
    moved to 2026-07-13, with zero code change. Confirmed by reproducing
    the failure with this session's other changes fully stashed out."""
    database.register_member("u1", "Alice")
    today = datetime.date.today().isoformat()
    database.update_streak("u1", today, 5)
    current, longest = database.get_streak("u1")
    assert current == 1
    assert longest == 1


def test_streak_consecutive_days():
    database.register_member("u1", "Alice")
    today = datetime.date.today()
    for i in range(5):
        d = (today - datetime.timedelta(days=4 - i)).isoformat()
        database.update_streak("u1", d, 7)
    current, longest = database.get_streak("u1")
    assert current == 5
    assert longest == 5


def test_streak_broken_by_gap():
    database.register_member("u1", "Alice")
    today = datetime.date.today()
    # Day -3 and -2 have activity, day -1 (yesterday) is skipped, today has activity.
    database.update_streak("u1", (today - datetime.timedelta(days=3)).isoformat(), 5)
    database.update_streak("u1", (today - datetime.timedelta(days=2)).isoformat(), 5)
    database.update_streak("u1", today.isoformat(), 5)
    current, _ = database.get_streak("u1")
    assert current == 1  # only today counts; yesterday's gap breaks the chain


def test_streak_longest_persists_after_current_streak_drops():
    """longest_streak must never decrease even after current_streak drops
    to 0 — this is what makes !streak's 'Best: N' display meaningful
    (recognizing a member's best-ever run, not just their latest one)."""
    database.register_member("u1", "Alice")
    today = datetime.date.today()
    for i in range(5):
        d = (today - datetime.timedelta(days=4 - i)).isoformat()
        database.update_streak("u1", d, 7)
    current, longest = database.get_streak("u1")
    assert current == 5
    assert longest == 5
    # A day with 0 tasks completed breaks the current streak...
    database.update_streak("u1", today.isoformat(), 0)
    current, longest = database.get_streak("u1")
    assert current == 0
    # ...but the best-ever streak of 5 must still be remembered.
    assert longest == 5


def test_get_streak_unknown_member_returns_zeros():
    assert database.get_streak("nonexistent") == (0, 0)


# ============================================================
#  POINTS & LEADERBOARDS
# ============================================================

def test_add_points_increments_total():
    database.register_member("u1", "Alice")
    database.add_points("u1", 15, "task:vocab")
    database.add_points("u1", 15, "task:writing")
    assert database.get_member("u1")["total_points"] == 30


def test_leaderboard_ordering():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.add_points("u1", 10, "x")
    database.add_points("u2", 50, "x")
    lb = database.leaderboard(10)
    assert lb[0]["discord_id"] == "u2"
    assert lb[1]["discord_id"] == "u1"


def test_leaderboard_respects_limit():
    for i in range(15):
        database.register_member(f"u{i}", f"User{i}")
        database.add_points(f"u{i}", 1, "x")
    assert len(database.leaderboard(5)) == 5


def test_leaderboard_excludes_inactive():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.add_points("u2", 100, "x")
    database.update_member("u2", status="inactive")
    lb = database.leaderboard(10)
    ids = [m["discord_id"] for m in lb]
    assert "u2" not in ids


def test_streak_leaderboard_ordering():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.update_member("u1", current_streak=3)
    database.update_member("u2", current_streak=10)
    lb = database.streak_leaderboard(10)
    assert lb[0]["discord_id"] == "u2"


# ============================================================
#  ASSESSMENTS
# ============================================================

def test_save_and_get_assessment():
    database.register_member("u1", "Alice")
    scores = {"speaking": 80, "listening": 75, "vocabulary": 90,
              "accent": 70, "writing": 85, "completion": 100}
    database.save_assessment("u1", 1, scores, overall=82.5, rating="Strong")
    assessments = database.get_assessments("u1")
    assert len(assessments) == 1
    assert assessments[0]["overall_score"] == 82.5
    assert assessments[0]["rating"] == "Strong"


def test_save_assessment_upserts_same_week():
    database.register_member("u1", "Alice")
    database.save_assessment("u1", 1, {}, overall=50, rating="Critical")
    database.save_assessment("u1", 1, {}, overall=90, rating="Excellent")
    assessments = database.get_assessments("u1")
    assert len(assessments) == 1
    assert assessments[0]["overall_score"] == 90


def test_get_latest_assessment():
    database.register_member("u1", "Alice")
    database.save_assessment("u1", 1, {}, overall=60, rating="At Risk")
    database.save_assessment("u1", 2, {}, overall=80, rating="Strong")
    latest = database.get_latest_assessment("u1")
    assert latest["week_number"] == 2
    assert latest["overall_score"] == 80


def test_get_latest_assessment_none_when_no_assessments():
    database.register_member("u1", "Alice")
    assert database.get_latest_assessment("u1") is None


def test_get_assessment_for_week_returns_matching_week_only():
    database.register_member("u1", "Alice")
    database.save_assessment("u1", 1, {}, overall=60, rating="At Risk")
    database.save_assessment("u1", 2, {}, overall=80, rating="Strong")
    assert database.get_assessment_for_week("u1", 1)["overall_score"] == 60
    assert database.get_assessment_for_week("u1", 2)["overall_score"] == 80
    assert database.get_assessment_for_week("u1", 3) is None


def test_save_assessment_clamps_huge_week_number_instead_of_crashing():
    """Found via adversarial-input stress testing: sqlite3 raises a bare
    OverflowError (not a catchable sqlite3.Error) for ints outside
    signed-64-bit range, same class of bug as add_points()."""
    database.register_member("u1", "Alice")
    database.save_assessment("u1", 2**63, {}, overall=50, rating="Critical")
    database.save_assessment("u1", -(2**63) - 100, {}, overall=50, rating="Critical")
    # Both clamp to valid (if extreme) values rather than raising.
    assert len(database.get_assessments("u1")) == 2


# ============================================================
#  SUBMISSIONS SINCE (get_submissions_since)
# ============================================================

def test_get_submissions_since_includes_today():
    database.register_member("u1", "Alice")
    database.log_submission("u1", datetime.date.today().isoformat(), "speaking")
    subs = database.get_submissions_since("u1", days=7)
    assert len(subs) == 1
    assert subs[0]["task_id"] == "speaking"


def test_get_submissions_since_excludes_outside_window():
    database.register_member("u1", "Alice")
    old_date = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    database.log_submission("u1", old_date, "speaking")
    subs = database.get_submissions_since("u1", days=7)
    assert subs == []


def test_get_submissions_since_empty_for_new_member():
    database.register_member("u1", "Alice")
    assert database.get_submissions_since("u1", days=7) == []


def test_declining_assessment_members():
    database.register_member("u1", "Alice")
    database.save_assessment("u1", 1, {}, overall=90, rating="Excellent")
    database.save_assessment("u1", 2, {}, overall=70, rating="Satisfactory")
    declining = database.declining_assessment_members()
    ids = [m["discord_id"] for m in declining]
    assert "u1" in ids


def test_declining_assessment_members_excludes_improving():
    database.register_member("u1", "Alice")
    database.save_assessment("u1", 1, {}, overall=60, rating="At Risk")
    database.save_assessment("u1", 2, {}, overall=90, rating="Excellent")
    declining = database.declining_assessment_members()
    ids = [m["discord_id"] for m in declining]
    assert "u1" not in ids


# ============================================================
#  ADVANCEMENT EXAMS
# ============================================================

def test_create_pending_exam_and_retrieve():
    database.register_member("u1", "Alice")
    exam_id = database.create_pending_exam("u1", "L0", "L1", speaking_recording_url="http://x/y.mp3")
    exam = database.get_exam_by_id(exam_id)
    assert exam["status"] == "pending"
    assert exam["from_level"] == "L0"
    assert exam["to_level"] == "L1"
    assert exam["speaking_recording_url"] == "http://x/y.mp3"


def test_last_advancement_attempt_returns_most_recent():
    database.register_member("u1", "Alice")
    database.create_pending_exam("u1", "L0", "L1")
    second_id = database.create_pending_exam("u1", "L0", "L1")
    latest = database.last_advancement_attempt("u1")
    assert latest["id"] == second_id


def test_last_advancement_attempt_none_when_no_attempts():
    database.register_member("u1", "Alice")
    assert database.last_advancement_attempt("u1") is None


def test_pending_exams_only_returns_pending_status():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    id1 = database.create_pending_exam("u1", "L0", "L1")
    database.create_pending_exam("u2", "L0", "L1")
    database.resolve_exam(id1, passed=True, resolved_by="admin1")
    pending = database.pending_exams()
    ids = [e["discord_id"] for e in pending]
    assert "u1" not in ids
    assert "u2" in ids


def test_resolve_exam_passed():
    database.register_member("u1", "Alice")
    exam_id = database.create_pending_exam("u1", "L0", "L1")
    database.resolve_exam(exam_id, passed=True, resolved_by="admin1", notes="great job")
    exam = database.get_exam_by_id(exam_id)
    assert exam["status"] == "passed"
    assert exam["passed"] == 1
    assert exam["resolved_by"] == "admin1"
    assert exam["resolved_at"] is not None


def test_resolve_exam_does_not_change_member_level():
    """resolve_exam() intentionally does NOT call set_level() itself —
    the caller must do that explicitly. Guards against a regression where
    resolving an exam silently promotes someone without an explicit step."""
    database.register_member("u1", "Alice", level="L0")
    exam_id = database.create_pending_exam("u1", "L0", "L1")
    database.resolve_exam(exam_id, passed=True, resolved_by="admin1")
    assert database.get_member("u1")["level"] == "L0"


def test_get_exam_by_id_not_found_returns_none():
    assert database.get_exam_by_id(99999) is None


def test_get_exam_by_id_handles_out_of_range_int_without_crashing():
    """Found via boundary-condition stress testing: an admin typo like
    !examresult 9223372036854775808 pass (one extra digit) previously
    raised a bare OverflowError instead of the normal "not found" path."""
    assert database.get_exam_by_id(2**63) is None
    assert database.get_exam_by_id(-(2**63) - 1) is None


# ============================================================
#  SETTINGS
# ============================================================

def test_get_setting_default_when_missing():
    assert database.get_setting("nonexistent_key", "fallback") == "fallback"


def test_set_and_get_setting():
    database.set_setting("last_backup", "2026-07-12")
    assert database.get_setting("last_backup") == "2026-07-12"


def test_set_setting_upserts():
    database.set_setting("key1", "value1")
    database.set_setting("key1", "value2")
    assert database.get_setting("key1") == "value2"


# ============================================================
#  FEATURE FLAGS (Aegis Phase 1)
# ============================================================

def test_feature_flag_never_set_is_disabled():
    """A flag that has never been touched must fail closed, not open --
    a typo'd flag name should never accidentally enable a feature for
    everyone."""
    assert database.is_feature_enabled("never_set") is False
    assert database.is_feature_enabled("never_set", "u1") is False


def test_feature_flag_enabled_with_empty_allowlist_is_everyone():
    database.set_feature_flag("new_thing", enabled=True)
    assert database.is_feature_enabled("new_thing") is True
    assert database.is_feature_enabled("new_thing", "any_random_id") is True


def test_feature_flag_enabled_with_allowlist_restricts_to_it():
    database.set_feature_flag("new_thing", enabled=True, allowed_ids="u1,u2")
    assert database.is_feature_enabled("new_thing", "u1") is True
    assert database.is_feature_enabled("new_thing", "u2") is True
    assert database.is_feature_enabled("new_thing", "u3") is False
    # No discord_id given at all (e.g. a scheduled task with no single
    # member context) must not be treated as "in the allowlist".
    assert database.is_feature_enabled("new_thing") is False


def test_feature_flag_disabled_blocks_everyone_including_allowlist():
    database.set_feature_flag("new_thing", enabled=True, allowed_ids="u1")
    database.set_feature_flag("new_thing", enabled=False)
    assert database.is_feature_enabled("new_thing", "u1") is False
    assert database.is_feature_enabled("new_thing") is False


def test_feature_flag_disabling_clears_stale_allowlist():
    """Disabling a flag that had an active beta allowlist, then
    re-enabling it with no allowlist, must start from a clean 'everyone'
    state -- not silently resurrect the old beta list."""
    database.set_feature_flag("new_thing", enabled=True, allowed_ids="u1")
    database.set_feature_flag("new_thing", enabled=False)
    database.set_feature_flag("new_thing", enabled=True)
    assert database.is_feature_enabled("new_thing", "u1") is True
    assert database.is_feature_enabled("new_thing", "u99_never_in_any_allowlist") is True


def test_feature_flag_upserts_not_duplicates():
    database.set_feature_flag("thing", enabled=True)
    database.set_feature_flag("thing", enabled=False)
    flags = database.list_feature_flags()
    assert len([f for f in flags if f["name"] == "thing"]) == 1


def test_list_feature_flags_returns_all_ever_set():
    database.set_feature_flag("flag_a", enabled=True, updated_by="admin1")
    database.set_feature_flag("flag_b", enabled=False, updated_by="admin2")
    names = {f["name"] for f in database.list_feature_flags()}
    assert names == {"flag_a", "flag_b"}


def test_feature_flag_updated_by_is_recorded():
    database.set_feature_flag("thing", enabled=True, updated_by="123456")
    flags = {f["name"]: f for f in database.list_feature_flags()}
    assert flags["thing"]["updated_by"] == "123456"


# ============================================================
#  UTILITY / STATS
# ============================================================

def test_member_count():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    assert database.member_count() == 2


def test_member_count_excludes_inactive():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.update_member("u2", status="inactive")
    assert database.member_count() == 1


def test_total_submissions_today():
    database.register_member("u1", "Alice")
    today = datetime.date.today().isoformat()
    database.log_submission("u1", today, "vocab")
    database.log_submission("u1", today, "writing")
    assert database.total_submissions_today() == 2


def test_inactive_members_respects_days_threshold():
    database.register_member("u1", "Alice")
    old_time = (datetime.datetime.now() - datetime.timedelta(days=5)).isoformat()
    database.update_member("u1", last_active_at=old_time)
    assert len(database.inactive_members(days=3)) == 1
    assert len(database.inactive_members(days=10)) == 0


def test_count_buddy_load():
    database.register_member("u1", "Alice", telegram_id="")
    database.register_member("u2", "Bob")
    database.register_member("u3", "Carol")
    database.update_member("u2", buddy_id="u1")
    database.update_member("u3", buddy_id="u1")
    assert database.count_buddy_load("u1") == 2


def test_members_with_buddy():
    database.register_member("u1", "Alice")
    database.register_member("u2", "Bob")
    database.update_member("u2", buddy_id="u1")
    buddies = database.members_with_buddy("u1")
    assert len(buddies) == 1
    assert buddies[0]["discord_id"] == "u2"


def test_member_week_number_defaults_to_one_for_new_member():
    database.register_member("u1", "Alice")
    assert database.member_week_number("u1") == 1


def test_member_week_number_increases_with_join_date():
    database.register_member("u1", "Alice")
    joined = (datetime.datetime.now() - datetime.timedelta(days=15)).isoformat()
    database.update_member("u1", joined_at=joined)
    assert database.member_week_number("u1") == 3  # 15 // 7 + 1


def test_member_week_number_unknown_member_returns_one():
    assert database.member_week_number("nonexistent") == 1


def test_days_since_active():
    database.register_member("u1", "Alice")
    old_time = (datetime.datetime.now() - datetime.timedelta(days=4)).isoformat()
    database.update_member("u1", last_active_at=old_time)
    member = database.get_member("u1")
    assert database.days_since_active(member) == 4
