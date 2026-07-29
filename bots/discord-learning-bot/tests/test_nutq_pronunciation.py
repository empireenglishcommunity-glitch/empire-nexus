"""Nutq (pronunciation-feedback spec) — Phase 1 backend tests.

Covers the bytes-based scoring path (score_recording_bytes) and the API's
expected-text lookup. Scoring MATH is already covered by
test_pronunciation_scorer.py; here we test the new plumbing: bytes → score,
beginner grace, graceful transcription failure, persistence, and the
(week, day) → target-sentence mapping.
"""
import pytest

from src import pronunciation_scorer as ps
from src import database, api_server, curriculum


@pytest.fixture
def member():
    database.register_member("900100777", "Nutq Test Student")
    return "900100777"


# ── expected-text lookup (sync) ─────────────────────────────────────────

def test_expected_text_maps_week_and_day(monkeypatch):
    captured = {}

    def fake_daily(week, day_name, day_index, level):
        captured["args"] = (week, day_name, day_index, level)
        return {"accent_drill": {"record_this": "I walk through the park"}}

    monkeypatch.setattr(curriculum, "get_daily_content", fake_daily)
    text = api_server._pronunciation_expected_text(2, 3, "L0")
    assert text == "I walk through the park"
    # day 3 → day_index 2 → curriculum day "Monday" (Sat=0 convention)
    assert captured["args"] == (2, "Monday", 2, "L0")


def test_expected_text_empty_when_no_drill(monkeypatch):
    monkeypatch.setattr(curriculum, "get_daily_content", lambda *a, **k: {"accent_drill": None})
    assert api_server._pronunciation_expected_text(1, 1, "L0") == ""


def test_expected_text_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("curriculum blew up")
    monkeypatch.setattr(curriculum, "get_daily_content", boom)
    # Must degrade to "" (→ scoring skipped), never propagate.
    assert api_server._pronunciation_expected_text(1, 1, "L0") == ""


# ── bytes scoring pipeline (async) ──────────────────────────────────────

@pytest.mark.asyncio
async def test_score_bytes_happy_path_non_beginner(member, monkeypatch):
    async def fake_transcribe(b, f):
        return "i walk through the park"

    async def fake_feedback(*a, **k):
        return ("Great job!", "أحسنت!")

    monkeypatch.setattr(ps, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(ps, "generate_feedback", fake_feedback)
    monkeypatch.setattr(database, "get_recent_scores", lambda did, days=30: [1, 2, 3])

    res = await ps.score_recording_bytes(
        b"AUDIOBYTES", "r.webm", "I walk through the park", member, "accent", "L0")

    assert res.success is True
    assert res.is_beginner_grace is False
    assert res.transcript == "i walk through the park"
    assert res.expected_text == "I walk through the park"
    assert res.feedback_en == "Great job!" and res.feedback_ar == "أحسنت!"
    assert res.score >= 40.0  # floor honored

    # Persisted to pronunciation_scores (real DB via temp_db fixture).
    conn = database._connect()
    row = conn.execute(
        "SELECT score, transcript, task_id FROM pronunciation_scores WHERE discord_id=?",
        (member,)).fetchone()
    conn.close()
    assert row is not None and row["task_id"] == "accent"


@pytest.mark.asyncio
async def test_score_bytes_beginner_grace(member, monkeypatch):
    async def fake_transcribe(b, f):
        return "hello"
    monkeypatch.setattr(ps, "transcribe_audio", fake_transcribe)
    # <3 prior scores → beginner grace (encouragement only, no number).
    monkeypatch.setattr(database, "get_recent_scores", lambda did, days=30: [])

    res = await ps.score_recording_bytes(
        b"AUDIO", "r.webm", "hello world", member, "shadow", "L0")

    assert res.success is True
    assert res.is_beginner_grace is True
    assert res.feedback_en and res.feedback_ar  # grace message present


@pytest.mark.asyncio
async def test_score_bytes_transcription_failure_is_graceful(member, monkeypatch):
    async def fake_transcribe(b, f):
        return None  # Whisper failed / empty
    monkeypatch.setattr(ps, "transcribe_audio", fake_transcribe)

    res = await ps.score_recording_bytes(
        b"AUDIO", "r.webm", "hello", member, "accent", "L0")

    assert res.success is False
    assert res.error == "Transcription failed"
    assert res.transcript == ""


@pytest.mark.asyncio
async def test_score_bytes_store_false_does_not_persist(member, monkeypatch):
    # Phase 3: the "try again" re-check passes store=False → the score must
    # NOT be persisted (no trend pollution, no beginner-grace count change).
    async def fake_transcribe(b, f):
        return "hello world"

    async def fake_feedback(*a, **k):
        return ("ok", "تمام")

    monkeypatch.setattr(ps, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(ps, "generate_feedback", fake_feedback)
    monkeypatch.setattr(database, "get_recent_scores", lambda did, days=30: [1, 2, 3])

    res = await ps.score_recording_bytes(
        b"A", "r.webm", "hello world", member, "accent", "L0", store=False)
    assert res.success is True

    conn = database._connect()
    n = conn.execute(
        "SELECT COUNT(*) FROM pronunciation_scores WHERE discord_id=?", (member,)).fetchone()[0]
    conn.close()
    assert n == 0  # store=False → nothing persisted


@pytest.mark.asyncio
async def test_url_path_still_delegates_to_bytes(member, monkeypatch):
    # The legacy URL entry should download then reuse the same pipeline.
    async def fake_download(url):
        return b"DOWNLOADED"

    async def fake_transcribe(b, f):
        assert b == b"DOWNLOADED"  # bytes flowed through
        return "hello world"

    async def fake_feedback(*a, **k):
        return ("ok", "تمام")

    monkeypatch.setattr(ps, "download_audio", fake_download)
    monkeypatch.setattr(ps, "transcribe_audio", fake_transcribe)
    monkeypatch.setattr(ps, "generate_feedback", fake_feedback)
    monkeypatch.setattr(database, "get_recent_scores", lambda did, days=30: [1, 2, 3])

    res = await ps.score_recording(
        "https://cdn/x.webm", "hello world", member, "accent", "L0")
    assert res.success is True
    assert res.transcript == "hello world"
