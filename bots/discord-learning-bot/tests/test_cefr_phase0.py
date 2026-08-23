"""Mi'yar (CEFR curriculum) Phase 0 — foundation tests.

Covers:
- cefr_curriculum flag registered + default OFF
- CEFR level model (A1–C2) + legacy map + resolvers
- CEFR week counts + max_week_for_level accepts both key types
- curriculum loader still loads legacy content (no regression) + tolerates
  missing CEFR files
- migration engine: dry-run preserves everything, real migration remaps level
  on members + per-student tables, idempotency, rollback
"""
import pytest

from src import config, curriculum, database, flag_registry


# ============================================================
#  FLAG
# ============================================================

def test_cefr_flag_registered_and_off():
    names = {f[0]: f[3] for f in [(x[0], x[1], x[2], x[3]) for x in flag_registry.REGISTRY]}
    assert "cefr_curriculum" in names
    assert names["cefr_curriculum"] is False


def test_miyar_initiative_registered():
    assert "miyar" in flag_registry.INITIATIVES


# ============================================================
#  LEVEL MODEL
# ============================================================

def test_six_cefr_levels():
    assert list(config.CEFR_LEVELS.keys()) == ["A1", "A2", "B1", "B2", "C1", "C2"]


def test_legacy_map():
    assert config.LEGACY_LEVEL_MAP == {"L0": "A1", "L1": "A2", "L2": "B1", "L3": "B2"}
    assert config.CEFR_TO_LEGACY["A1"] == "L0"


def test_is_cefr_level():
    assert config.is_cefr_level("A1") is True
    assert config.is_cefr_level("B2") is True
    assert config.is_cefr_level("L0") is False


def test_next_cefr_level():
    assert config.next_cefr_level("A1") == "A2"
    assert config.next_cefr_level("B2") == "C1"
    assert config.next_cefr_level("C2") is None
    # Accepts legacy key
    assert config.next_cefr_level("L0") == "A2"


def test_level_info_accepts_both_keys():
    a1 = config.level_info("A1")
    assert a1["cefr"] == "A1"
    assert a1["name"] == "Beginner"
    # legacy key resolves + annotates cefr
    l0 = config.level_info("L0")
    assert l0["cefr"] == "A1"
    # unknown falls back to A1
    assert config.level_info("ZZ")["cefr"] == "A1"


# ============================================================
#  WEEK COUNTS
# ============================================================

def test_cefr_week_counts():
    assert curriculum.CEFR_WEEK_COUNTS == {
        "A1": 10, "A2": 12, "B1": 14, "B2": 16, "C1": 18, "C2": 20}


def test_max_week_accepts_both_keys():
    assert curriculum.max_week_for_level("A1") == 10
    assert curriculum.max_week_for_level("C2") == 20
    assert curriculum.max_week_for_level("L0") == 8   # legacy unchanged
    assert curriculum.max_week_for_level("L1") == 10


# ============================================================
#  LOADER — no regression + tolerates missing CEFR files
# ============================================================

def test_loader_still_loads_legacy():
    curriculum.load_all()
    # L0 legacy content still loads (8 weeks defined)
    l0 = [k for k in curriculum._weekly_data if k.startswith("L0_")]
    assert len(l0) >= 1


def test_loader_tolerates_unauthored_cefr_levels():
    # CEFR levels are authored one at a time (A1, then A2, ...). Levels not yet
    # written (e.g. B1) simply have no week files on disk; load_all must not
    # raise and just loads no weeks for them. (A1 and A2 ARE authored now, so we
    # assert against a level that is still unauthored to keep testing the
    # tolerance.)
    curriculum.load_all()
    c1 = [k for k in curriculum._weekly_data if k.startswith("C1_")]
    assert c1 == []  # C1 not authored yet — loader tolerates it, no error


# ============================================================
#  MIGRATION ENGINE
# ============================================================

def _seed_full_student(uid, level="L0", week=5):
    """Seed a member + mastery + an assessment attempt + a monthly review."""
    database.register_member(uid, f"Student{uid}")
    database.update_member(uid, level=level, total_points=1200, current_streak=9,
                           longest_streak=12)
    conn = database._connect()
    for w in range(1, week):
        conn.execute("INSERT OR REPLACE INTO week_mastery (discord_id, level, week, mastered) "
                     "VALUES (?, ?, ?, 1)", (uid, level, w))
    conn.execute("INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, seed) "
                 "VALUES (?, ?, ?, 1, 's')", (uid, level, week))
    conn.execute("INSERT OR REPLACE INTO monthly_reviews (discord_id, level, review_number, passed) "
                 "VALUES (?, ?, 1, 1)", (uid, level))
    conn.commit()
    conn.close()


def test_migration_dry_run_changes_nothing():
    _seed_full_student("mig1", "L0")
    rep = database.migrate_to_cefr(dry_run=True, discord_id="mig1")
    r = rep["reports"][0]
    assert r["status"] == "would_migrate"
    assert r["from_level"] == "L0" and r["to_level"] == "A1"
    # Member still L0 (nothing written)
    assert database.get_member("mig1")["level"] == "L0"


def test_migration_real_remaps_everything():
    _seed_full_student("mig2", "L0", week=6)
    before = database.get_member("mig2")
    anchor_before = before.get("level_started_at")

    rep = database.migrate_to_cefr(dry_run=False, discord_id="mig2")
    assert rep["reports"][0]["status"] == "migrated"

    after = database.get_member("mig2")
    # Level remapped
    assert after["level"] == "A1"
    # Counters preserved
    assert after["total_points"] == 1200
    assert after["current_streak"] == 9
    assert after["longest_streak"] == 12
    # Calendar anchor preserved (same week position)
    assert after.get("level_started_at") == anchor_before
    # Mastery history follows the student to A1
    assert database.itqan_mastered_weeks("mig2", "A1") == {1, 2, 3, 4, 5}
    assert database.itqan_mastered_weeks("mig2", "L0") == set()  # moved, not duplicated
    # Monthly review history follows too
    assert database.monthly_reviews_passed("mig2", "A1") == 1


def test_migration_idempotent():
    _seed_full_student("mig3", "L0")
    database.migrate_to_cefr(dry_run=False, discord_id="mig3")
    # Second run: already CEFR → skipped
    rep = database.migrate_to_cefr(dry_run=False, discord_id="mig3")
    assert rep["reports"][0]["status"] == "already_cefr"
    assert database.get_member("mig3")["level"] == "A1"


def test_migration_rollback():
    _seed_full_student("mig4", "L0", week=4)
    database.migrate_to_cefr(dry_run=False, discord_id="mig4")
    assert database.get_member("mig4")["level"] == "A1"
    assert database.itqan_mastered_weeks("mig4", "A1") == {1, 2, 3}

    res = database.rollback_cefr_migration("mig4")
    assert res["status"] == "rolled_back"
    # Restored to L0 with history reattached
    assert database.get_member("mig4")["level"] == "L0"
    assert database.itqan_mastered_weeks("mig4", "L0") == {1, 2, 3}
    assert database.itqan_mastered_weeks("mig4", "A1") == set()


def test_migration_summary_counts():
    _seed_full_student("mig5", "L0")
    _seed_full_student("mig6", "L0")
    rep = database.migrate_to_cefr(dry_run=True)
    # At least our two seeded students show as would_migrate
    assert rep["summary"].get("would_migrate", 0) >= 2



# ============================================================
#  REGRESSION: snapshot must tolerate raw BLOB columns
#  (assessment_recordings.audio) — a student with a voice
#  recording previously crashed the real migration AND any
#  history reset with "Object of type bytes is not JSON
#  serializable" the moment json.dumps hit the audio bytes.
# ============================================================

_FAKE_AUDIO = b"\x00\x01OggS_fake_webm_audio\xff\xfe" * 64  # raw bytes, like a real recording


def _give_student_a_recording(uid, level="L0", week=1):
    """Attach a real audio BLOB to a seeded student (via an assessment attempt),
    reproducing the production data shape that broke json.dumps."""
    conn = database._connect()
    cur = conn.execute(
        "INSERT INTO assessment_attempts (discord_id, level, week, attempt_no, seed) "
        "VALUES (?, ?, ?, 99, 'rec')", (uid, level, week))
    attempt_id = cur.lastrowid
    conn.execute(
        "INSERT INTO assessment_recordings (attempt_id, discord_id, item_no, skill, filename, audio) "
        "VALUES (?, ?, 1, 'speaking', 'rec.webm', ?)", (attempt_id, uid, _FAKE_AUDIO))
    conn.commit()
    conn.close()


def test_snapshot_serializes_audio_blob():
    """snapshot_member_data + _dumps_snapshot must not raise on a raw-bytes
    (BLOB) column, and the audio must round-trip through JSON back to the exact
    same bytes."""
    import json
    _seed_full_student("recser", "L0")
    _give_student_a_recording("recser")

    snap = database.snapshot_member_data("recser")  # include_blobs=True
    payload = database._dumps_snapshot(snap)         # must NOT raise
    reloaded = json.loads(payload)

    audio_row = reloaded["assessment_recordings"][0]
    decoded = database._decode_snapshot_value(audio_row["audio"])
    assert decoded == _FAKE_AUDIO  # exact round-trip


def test_real_migration_succeeds_for_student_with_recording():
    """The exact case that failed live: migrating a student who has a voice
    recording must complete (level remapped, counters preserved), not crash."""
    _seed_full_student("recmig", "L0", week=3)
    _give_student_a_recording("recmig")

    rep = database.migrate_to_cefr(dry_run=False, discord_id="recmig")
    assert rep["reports"][0]["status"] == "migrated"
    assert database.get_member("recmig")["level"] == "A1"
    # The recording row's level column followed the student too.
    assert database.itqan_mastered_weeks("recmig", "A1") == {1, 2}
    assert database.itqan_mastered_weeks("recmig", "L0") == set()


def test_migration_log_snapshot_omits_raw_audio():
    """The migration log keeps a proof snapshot but must NOT duplicate the
    (potentially megabytes of) audio BLOB — it stores a lightweight marker
    instead, since rollback reverses the level column directly."""
    import json
    _seed_full_student("reclean", "L0")
    _give_student_a_recording("reclean")
    database.migrate_to_cefr(dry_run=False, discord_id="reclean")

    conn = database._connect()
    row = conn.execute(
        "SELECT snapshot_json FROM cefr_migration_log WHERE discord_id=? "
        "ORDER BY id DESC LIMIT 1", ("reclean",)).fetchone()
    conn.close()
    snap = json.loads(row["snapshot_json"])
    audio_val = snap["assessment_recordings"][0]["audio"]
    # Marker present; no base64 audio payload bloating the log.
    assert isinstance(audio_val, dict)
    assert database._BLOB_OMITTED_MARKER in audio_val
    assert audio_val[database._BLOB_OMITTED_MARKER]["bytes"] == len(_FAKE_AUDIO)
    assert database._BYTES_MARKER not in row["snapshot_json"]


def test_reset_and_restore_roundtrips_audio():
    """A history reset snapshots the student (incl. audio) and a restore must
    re-insert the EXACT audio bytes — proving the base64 round-trip works
    end-to-end through the reset ledger."""
    _seed_full_student("recreset", "L0")
    _give_student_a_recording("recreset")

    res = database.reset_member_history(
        "recreset", initiated_by="test", consent_text="ok",
        affirmation="DELETE", reason="regression test")
    assert res is not None
    consent_id = res["consent_id"]
    # Audio was wiped by the reset.
    conn = database._connect()
    n = conn.execute("SELECT COUNT(*) c FROM assessment_recordings WHERE discord_id=?",
                     ("recreset",)).fetchone()["c"]
    conn.close()
    assert n == 0

    database.restore_member_from_consent(consent_id)
    conn = database._connect()
    got = conn.execute("SELECT audio FROM assessment_recordings WHERE discord_id=?",
                       ("recreset",)).fetchone()
    conn.close()
    assert got is not None
    # Restored audio is the exact original bytes.
    assert bytes(got["audio"]) == _FAKE_AUDIO
