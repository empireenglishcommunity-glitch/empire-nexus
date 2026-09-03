"""Tests for Sawt Phase 3 — owner voice-clone consent + reference clip storage.

Voice cloning is allowed only for the owner and only with explicit stored
consent + a saved reference clip. These lock in the consent gate and clip
validation.
"""
import pytest

from src import sawt_voice, database, flag_registry


def _enable(flag, on=True):
    database.set_feature_flag(flag, on, "", "test")


# ── flags registered ─────────────────────────────────────────────────────────
def test_phase3_flags_registered_default_off():
    reg = {e[0]: e for e in flag_registry.REGISTRY}
    for f in ("sawt_tts_pipeline", "sawt_voice_clone"):
        assert f in reg and reg[f][3] is False and reg[f][2] == "sawt"


# ── consent ──────────────────────────────────────────────────────────────────
def test_consent_grant_revoke():
    assert sawt_voice.has_consent() is False
    sawt_voice.grant_consent()
    assert sawt_voice.has_consent() is True
    sawt_voice.revoke_consent()
    assert sawt_voice.has_consent() is False


# ── reference clip ─────────────────────────────────────────────────────────────
def test_save_ref_clip_valid(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.SAWT_DIR", tmp_path / "sawt")
    path = sawt_voice.save_ref_clip(b"RIFFfakeaudio", "myvoice.wav")
    assert path.endswith("owner_voice_ref.wav")
    assert sawt_voice.ref_clip_path() == path      # persisted + on disk


def test_save_ref_clip_rejects_bad_extension(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.SAWT_DIR", tmp_path / "sawt")
    with pytest.raises(ValueError):
        sawt_voice.save_ref_clip(b"data", "notes.txt")


def test_ref_clip_path_empty_when_none():
    assert sawt_voice.ref_clip_path() == ""


# ── clone_ready gating (flag + consent + clip) ───────────────────────────────
def test_clone_ready_requires_flag_consent_and_clip(tmp_path, monkeypatch):
    monkeypatch.setattr("src.config.SAWT_DIR", tmp_path / "sawt")

    # flag off
    _enable("sawt_voice_clone", False)
    ready, reason = sawt_voice.clone_ready()
    assert ready is False and "flag" in reason

    # flag on, no consent
    _enable("sawt_voice_clone", True)
    ready, reason = sawt_voice.clone_ready()
    assert ready is False and "consent" in reason

    # consent, no clip
    sawt_voice.grant_consent()
    ready, reason = sawt_voice.clone_ready()
    assert ready is False and "clip" in reason

    # consent + clip → ready
    sawt_voice.save_ref_clip(b"RIFFfake", "v.wav")
    ready, reason = sawt_voice.clone_ready()
    assert ready is True and reason == ""
