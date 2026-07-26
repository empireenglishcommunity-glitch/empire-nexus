"""Itqan (weekly assessment) — Phase 0: foundations.

Flag OFF by default, the three tables exist, and owner-tunable config reads
back with safe fallbacks. No behavior change to anything else.
"""
from src import database, flag_registry


def _tables():
    conn = database._connect()
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()
    return {r["name"] for r in rows}


def test_new_tables_exist():
    t = _tables()
    assert "assessment_attempts" in t
    assert "assessment_items" in t
    assert "week_mastery" in t


def test_flag_registered_and_off_by_default():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == "itqan_weekly_assessment"), None)
    assert entry is not None, "itqan_weekly_assessment must be registered"
    assert entry[3] is False, "must default OFF"
    assert database.is_feature_enabled("itqan_weekly_assessment") is False


def test_config_defaults():
    cfg = database.get_itqan_config()
    assert cfg["itqan_mastery_pass_pct"] == 70
    assert cfg["itqan_consistency_pass_pct"] == 70
    assert cfg["itqan_distinction_pct"] == 90
    assert cfg["itqan_retake_cooldown_min"] == 720
    assert cfg["itqan_spiral_recent_weight"] == 0.65
    assert cfg["itqan_time_limit_min"] == 15
    # types preserved
    assert isinstance(cfg["itqan_spiral_recent_weight"], float)
    assert isinstance(cfg["itqan_mastery_pass_pct"], int)


def test_config_override_and_typing():
    assert database.set_itqan_config("itqan_mastery_pass_pct", 75) is True
    assert database.set_itqan_config("itqan_spiral_recent_weight", 0.7) is True
    cfg = database.get_itqan_config()
    assert cfg["itqan_mastery_pass_pct"] == 75
    assert cfg["itqan_spiral_recent_weight"] == 0.7


def test_config_unknown_key_rejected():
    assert database.set_itqan_config("itqan_bogus", 1) is False


def test_config_bad_value_falls_back_to_default():
    database.set_setting("itqan_time_limit_min", "not-a-number")
    cfg = database.get_itqan_config()
    assert cfg["itqan_time_limit_min"] == 15  # fell back, no crash


def test_attempt_and_mastery_rows_insertable():
    database.register_member("900", "Tester")
    conn = database._connect()
    conn.execute(
        "INSERT INTO assessment_attempts (discord_id, level, week) VALUES (?,?,?)",
        ("900", "L0", 1),
    )
    aid = conn.execute("SELECT id FROM assessment_attempts WHERE discord_id='900'").fetchone()["id"]
    conn.execute(
        "INSERT INTO assessment_items (attempt_id, discord_id, item_no, skill, source_week) "
        "VALUES (?,?,?,?,?)",
        (aid, "900", 1, "vocab", 1),
    )
    conn.execute(
        "INSERT INTO week_mastery (discord_id, level, week, mastered) VALUES (?,?,?,1)",
        ("900", "L0", 1),
    )
    conn.commit()
    got = conn.execute("SELECT mastered FROM week_mastery WHERE discord_id='900' AND week=1").fetchone()
    conn.close()
    assert got["mastered"] == 1
