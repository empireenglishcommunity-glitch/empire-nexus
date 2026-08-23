"""Assessment Progression ("Taqdeem") Phase 0 — foundation tests.

Covers:
- 2 Taqdeem flags registered with correct defaults
- PROGRESSION_CONFIG_DEFAULTS + get/set_progression_config
- monthly_reviews + advancement_exams tables created
- type column migration on assessment_attempts
- monthly_review_due trigger logic
- advancement_exam_due trigger logic
- monthly_reviews_passed / monthly_reviews_taken helpers
"""
import pytest

from src import database, flag_registry


# ============================================================
#  FLAGS
# ============================================================

TAQDEEM_FLAGS = [
    "assessment_monthly_review",
    "assessment_advancement_exam",
]


def test_taqdeem_flags_registered():
    """Both Taqdeem flags exist in the registry."""
    names = {f[0] for f in flag_registry.REGISTRY}
    for flag in TAQDEEM_FLAGS:
        assert flag in names, f"Flag '{flag}' not in REGISTRY"


def test_taqdeem_flags_default_off():
    """Both Taqdeem flags default to OFF."""
    for name, _desc, _init, default in flag_registry.REGISTRY:
        if name in TAQDEEM_FLAGS:
            assert default is False, f"Flag '{name}' should default OFF"


def test_taqdeem_initiative_registered():
    """The 'taqdeem' initiative is in INITIATIVES."""
    assert "taqdeem" in flag_registry.INITIATIVES
    emoji, label, desc = flag_registry.INITIATIVES["taqdeem"]
    assert "TAQDEEM" in label


# ============================================================
#  CONFIG
# ============================================================

def test_progression_config_defaults():
    """get_progression_config returns sane defaults."""
    cfg = database.get_progression_config()
    assert cfg["progression_monthly_pass_pct"] == 65
    assert cfg["progression_monthly_retake_cooldown_hours"] == 72
    assert cfg["progression_monthly_weeks_per_review"] == 4
    assert cfg["progression_advancement_pass_pct"] == 75
    assert cfg["progression_advancement_skill_min_pct"] == 60
    assert cfg["progression_advancement_part_b_min_pct"] == 50
    assert cfg["progression_advancement_part_a_weight"] == 0.6
    assert cfg["progression_advancement_part_b_weight"] == 0.4
    assert cfg["progression_advancement_retake_cooldown_days"] == 7
    assert cfg["progression_advancement_time_limit_part_a_min"] == 20
    assert cfg["progression_advancement_time_limit_part_b_min"] == 10


def test_progression_config_override():
    """Owner can override a config value."""
    assert database.set_progression_config("progression_monthly_pass_pct", 70)
    cfg = database.get_progression_config()
    assert cfg["progression_monthly_pass_pct"] == 70


def test_progression_config_rejects_unknown():
    """Unknown keys are rejected."""
    assert database.set_progression_config("bad_key", 99) is False


# ============================================================
#  TABLES
# ============================================================

def test_monthly_reviews_table_exists():
    """monthly_reviews table is created by init_db."""
    conn = database._connect()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "monthly_reviews" in tables


def test_advancement_exams_table_exists():
    """advancement_exams table is created by init_db."""
    conn = database._connect()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    conn.close()
    assert "advancement_exams" in tables


def test_assessment_attempts_has_type_column():
    """assessment_attempts has the 'type' column after migration."""
    conn = database._connect()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(assessment_attempts)")}
    conn.close()
    assert "type" in cols


# ============================================================
#  TRIGGER HELPERS
# ============================================================

def _seed_mastery(uid, level, weeks):
    """Helper: seed week_mastery rows for testing."""
    conn = database._connect()
    for w in weeks:
        conn.execute(
            "INSERT OR REPLACE INTO week_mastery (discord_id, level, week, mastered) "
            "VALUES (?, ?, ?, 1)", (uid, level, w))
    conn.commit()
    conn.close()


def _seed_monthly_passed(uid, level, review_number):
    """Helper: seed a passed monthly review."""
    conn = database._connect()
    conn.execute(
        "INSERT OR REPLACE INTO monthly_reviews (discord_id, level, review_number, passed) "
        "VALUES (?, ?, ?, 1)", (uid, level, review_number))
    conn.commit()
    conn.close()


def test_monthly_review_due_after_4_weeklies():
    """Monthly review is due after 4 weekly passes."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_monthly_review", True, "", "test")
    database.register_member("m1", "Alice")
    _seed_mastery("m1", "L0", [1, 2, 3, 4])

    assert database.monthly_review_due("m1") is True


def test_monthly_review_not_due_with_3_weeklies():
    """Monthly review is NOT due with only 3 weekly passes."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_monthly_review", True, "", "test")
    database.register_member("m2", "Alice")
    _seed_mastery("m2", "L0", [1, 2, 3])

    assert database.monthly_review_due("m2") is False


def test_monthly_review_not_due_after_taken():
    """After taking the 1st monthly, need 8 weeklies for the 2nd."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_monthly_review", True, "", "test")
    database.register_member("m3", "Alice")
    _seed_mastery("m3", "L0", [1, 2, 3, 4, 5])
    _seed_monthly_passed("m3", "L0", 1)

    # Only 5 weeklies, need 8 for the 2nd monthly
    assert database.monthly_review_due("m3") is False


def test_monthly_review_due_for_second():
    """2nd monthly due after 8 weekly passes."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_monthly_review", True, "", "test")
    database.register_member("m4", "Alice")
    _seed_mastery("m4", "L0", [1, 2, 3, 4, 5, 6, 7, 8])
    _seed_monthly_passed("m4", "L0", 1)

    assert database.monthly_review_due("m4") is True


def test_monthly_review_flag_off():
    """With flag OFF, monthly review is never due."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_monthly_review", False, "", "test")
    database.register_member("m5", "Alice")
    _seed_mastery("m5", "L0", [1, 2, 3, 4, 5, 6, 7, 8])

    assert database.monthly_review_due("m5") is False


def test_advancement_exam_due_all_conditions():
    """Advancement is due when all weeklies + 1 monthly passed."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_advancement_exam", True, "", "test")
    database.register_member("a1", "Bob")
    _seed_mastery("a1", "L0", list(range(1, 9)))  # all 8 weeks
    _seed_monthly_passed("a1", "L0", 1)

    assert database.advancement_exam_due("a1") is True


def test_advancement_not_due_missing_weekly():
    """Not due if a weekly is missing."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_advancement_exam", True, "", "test")
    database.register_member("a2", "Bob")
    _seed_mastery("a2", "L0", [1, 2, 3, 4, 5, 6, 7])  # only 7 of 8
    _seed_monthly_passed("a2", "L0", 1)

    assert database.advancement_exam_due("a2") is False


def test_advancement_not_due_no_monthly():
    """Not due without a monthly review passed."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_advancement_exam", True, "", "test")
    database.register_member("a3", "Bob")
    _seed_mastery("a3", "L0", list(range(1, 9)))  # all 8
    # No monthly passed

    assert database.advancement_exam_due("a3") is False


def test_advancement_flag_off():
    """With flag OFF, advancement is never due."""
    database.sync_flag_registry()
    database.set_feature_flag("assessment_advancement_exam", False, "", "test")
    database.register_member("a4", "Bob")
    _seed_mastery("a4", "L0", list(range(1, 9)))
    _seed_monthly_passed("a4", "L0", 1)

    assert database.advancement_exam_due("a4") is False


# ============================================================
#  HELPER COUNTS
# ============================================================

def test_monthly_reviews_passed_count():
    database.register_member("c1", "Carol")
    _seed_monthly_passed("c1", "L0", 1)
    _seed_monthly_passed("c1", "L0", 2)
    assert database.monthly_reviews_passed("c1", "L0") == 2
    assert database.monthly_reviews_passed("c1", "L1") == 0


def test_advancement_attempts_count():
    database.register_member("c2", "Dave")
    conn = database._connect()
    conn.execute(
        "INSERT INTO advancement_exams (discord_id, level, attempt_num, passed) "
        "VALUES (?, ?, ?, ?)", ("c2", "L0", 1, 0))
    conn.execute(
        "INSERT INTO advancement_exams (discord_id, level, attempt_num, passed) "
        "VALUES (?, ?, ?, ?)", ("c2", "L0", 2, 1))
    conn.commit()
    conn.close()
    assert database.advancement_attempts_count("c2", "L0") == 2
    assert database.advancement_attempts_count("c2", "L1") == 0
