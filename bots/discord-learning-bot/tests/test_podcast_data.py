"""Tests for Podcast Studio (Sawt) Phase 1 — data model + level profiles.

Covers the config level profiles and the database CRUD helpers for episodes and
listens: create/get/list/publish, audio updates, and deduplicated listen credit.
"""
import pytest

from src import config, database


# ============================================================
#  Level profiles (config)
# ============================================================

def test_every_cefr_level_has_a_profile():
    for lvl in config.CEFR_ORDER:
        p = config.PODCAST_LEVEL_PROFILES[lvl]
        assert "arabic_ratio" in p and "pace" in p and "vocab" in p
        assert p["duration_min"] < p["duration_max"]


def test_arabic_ratio_decreases_with_level():
    # A1 has the most Arabic; C2 has none.
    ratios = [config.PODCAST_LEVEL_PROFILES[l]["arabic_ratio"] for l in config.CEFR_ORDER]
    assert ratios == sorted(ratios, reverse=True)
    assert config.PODCAST_LEVEL_PROFILES["A1"]["arabic_ratio"] == 0.40
    assert config.PODCAST_LEVEL_PROFILES["C2"]["arabic_ratio"] == 0.0


def test_podcast_level_profile_helper_and_legacy():
    assert config.podcast_level_profile("A1")["pace"] == "very_slow"
    # Legacy L0 maps to A1.
    assert config.podcast_level_profile("L0")["pace"] == "very_slow"
    # Unknown falls back to A1 (never crashes).
    assert config.podcast_level_profile("ZZ")["pace"] == "very_slow"


# ============================================================
#  Episode CRUD (database)
# ============================================================

def test_create_and_get_episode():
    eid = database.create_episode("A1", "My First Episode", "solo_ai",
                                  description="intro")
    ep = database.get_episode(eid)
    assert ep["title"] == "My First Episode"
    assert ep["level"] == "A1"
    assert ep["format"] == "solo_ai"
    assert ep["description"] == "intro"
    assert ep["published"] == 0
    # arabic_ratio auto-filled from the A1 profile.
    assert ep["arabic_ratio"] == 0.40


def test_create_episode_normalizes_legacy_level():
    eid = database.create_episode("L0", "Legacy", "ai_only")
    assert database.get_episode(eid)["level"] == "A1"


def test_create_episode_rejects_invalid_format():
    with pytest.raises(ValueError):
        database.create_episode("A1", "Bad", "not_a_format")


def test_get_missing_episode_returns_none():
    assert database.get_episode(9999) is None


def test_list_episodes_by_level_and_published():
    a1 = database.create_episode("A1", "A1 ep", "solo_ai")
    b2 = database.create_episode("B2", "B2 ep", "ai_only")
    assert len(database.list_episodes("A1")) == 1
    assert len(database.list_episodes("B2")) == 1
    assert len(database.list_episodes()) == 2
    assert database.list_episodes(published_only=True) == []
    database.publish_episode(a1)
    pub = database.list_episodes(published_only=True)
    assert len(pub) == 1 and pub[0]["episode_id"] == a1


def test_publish_episode_sets_flag_and_timestamp():
    eid = database.create_episode("A1", "ep", "solo_ai")
    assert database.publish_episode(eid) is True
    ep = database.get_episode(eid)
    assert ep["published"] == 1
    assert ep["published_at"]
    # Publishing again is a no-op (already published).
    assert database.publish_episode(eid) is False


def test_update_episode_audio_and_message_id():
    eid = database.create_episode("A1", "ep", "solo_ai")
    database.update_episode_audio(eid, "https://cdn/audio.mp3", duration_seconds=240)
    database.set_episode_audio_message_id(eid, "555")
    ep = database.get_episode(eid)
    assert ep["audio_url"] == "https://cdn/audio.mp3"
    assert ep["duration_seconds"] == 240
    assert ep["audio_message_id"] == "555"


# ============================================================
#  Listen credit (database) — deduplicated
# ============================================================

def test_record_listen_dedups_and_counts():
    database.register_member("stu1", "Student One", level="A1")
    database.register_member("stu2", "Student Two", level="A1")
    eid = database.create_episode("A1", "ep", "solo_ai")

    assert database.record_listen("stu1", eid) is True     # first time
    assert database.has_listened("stu1", eid) is True
    assert database.record_listen("stu1", eid) is False    # duplicate ignored
    assert database.record_listen("stu2", eid) is True
    assert database.episode_listen_count(eid) == 2


def test_has_listened_false_when_never_listened():
    database.register_member("stu3", "Student Three", level="A1")
    eid = database.create_episode("A1", "ep", "solo_ai")
    assert database.has_listened("stu3", eid) is False
    assert database.episode_listen_count(eid) == 0
