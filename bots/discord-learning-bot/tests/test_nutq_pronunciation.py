"""Nutq 2 (pronunciation-engine-v2 spec) — bot integration tests.

Covers the bot side of the self-hosted scorer wiring: score_recording_bytes now
calls the nutq-scorer service (mocked here), maps its result to ScoringResult
(same shape the dojo consumes), stores it, and degrades gracefully when the
scorer is unavailable. Also covers the expected-text lookup that mirrors the
page's displayed sentence (normal / review / assessment days).

The phoneme scoring MATH itself is unit-tested in services/nutq-scorer/tests.
"""
import pytest

from src import pronunciation_scorer as ps
from src import database, api_server, curriculum


@pytest.fixture
def member():
    database.register_member("900100777", "Nutq Test Student")
    return "900100777"


def _scorer_result(**over):
    """A representative nutq-scorer JSON success payload."""
    base = {
        "ok": True,
        "score": 82.0,
        "raw_score": 79.5,
        "missed_words": ["through"],
        "per_word": [{"word": "through", "accuracy": 0.3}],
        "feedback_en": "Great job! Practice 'through'.",
        "feedback_ar": "أحسنت! اتمرّن على 'through'.",
        "heard_phonemes": "aɪ w ɔ k θ r u ð a p a r k",
        "expected": "I walk through the park",
    }
    base.update(over)
    return base


# ── expected-text lookup — mirrors the page's displayed sentence ─────────

def test_expected_text_normal_day_uses_record_this(monkeypatch):
    captured = {}

    def fake_daily(week, day_name, day_index, level):
        captured["args"] = (week, day_name, day_index, level)
        return {"accent_drill": {"record_this": "I walk through the park"}}

    monkeypatch.setattr(curriculum, "get_daily_content", fake_daily)
    text = api_server._pronunciation_expected_text(2, 3, "L0")
    assert text == "I walk through the park"
    # day 3 → day_index 2 → curriculum day "Monday" (Sat=0 convention)
    assert captured["args"] == (2, "Monday", 2, "L0")


def test_expected_text_normal_day_falls_back_to_sentence_practice(monkeypatch):
    monkeypatch.setattr(curriculum, "get_daily_content",
                        lambda *a, **k: {"accent_drill": {"sentence_practice": ["Say this one."]}})
    assert api_server._pronunciation_expected_text(1, 1, "L0") == "Say this one."


def test_expected_text_assessment_day_uses_passage(monkeypatch):
    # Day-7 assessment: page shows test_yourself.passage → score that, not record_this.
    monkeypatch.setattr(curriculum, "get_daily_content", lambda *a, **k: {
        "accent_drill": {"type": "assessment",
                         "test_yourself": {"passage": "Please read this passage aloud."}}})
    assert api_server._pronunciation_expected_text(1, 7, "L0") == "Please read this passage aloud."


def test_expected_text_review_day_uses_record_this_then_challenge(monkeypatch):
    monkeypatch.setattr(curriculum, "get_daily_content", lambda *a, **k: {
        "accent_drill": {"type": "review", "challenge_sentences": ["Ship and sheep."]}})
    assert api_server._pronunciation_expected_text(1, 6, "L0") == "Ship and sheep."


def test_expected_text_empty_when_no_drill(monkeypatch):
    monkeypatch.setattr(curriculum, "get_daily_content", lambda *a, **k: {"accent_drill": None})
    assert api_server._pronunciation_expected_text(1, 1, "L0") == ""


def test_expected_text_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("curriculum blew up")
    monkeypatch.setattr(curriculum, "get_daily_content", boom)
    assert api_server._pronunciation_expected_text(1, 1, "L0") == ""


# ── bytes scoring pipeline (async) — now calls the self-hosted scorer ────

@pytest.mark.asyncio
async def test_score_bytes_happy_path(member, monkeypatch):
    async def fake_call(audio_bytes, expected_text, level, filename):
        assert audio_bytes == b"AUDIOBYTES"
        assert expected_text == "I walk through the park"
        return _scorer_result()

    monkeypatch.setattr(ps, "_call_nutq_scorer", fake_call)

    res = await ps.score_recording_bytes(
        b"AUDIOBYTES", "r.webm", "I walk through the park", member, "accent", "L0")

    assert res.success is True
    assert res.is_beginner_grace is False
    assert res.score == 82.0
    assert res.raw_score == 79.5
    assert res.missed_words == ["through"]
    assert res.feedback_en and res.feedback_ar
    assert res.transcript == ""  # phoneme engine → no readable "we heard" line
    assert res.expected_text == "I walk through the park"

    # Persisted: score + task_id, and recognized phonemes go in the transcript col.
    conn = database._connect()
    row = conn.execute(
        "SELECT score, transcript, task_id FROM pronunciation_scores WHERE discord_id=?",
        (member,)).fetchone()
    conn.close()
    assert row is not None and row["task_id"] == "accent"
    assert row["transcript"] == "aɪ w ɔ k θ r u ð a p a r k"  # heard phonemes stored


@pytest.mark.asyncio
async def test_score_bytes_scorer_unavailable_is_graceful(member, monkeypatch):
    # Scorer down / timeout → _call_nutq_scorer returns None. Must degrade to
    # success=False (endpoint → scored:false) and persist NOTHING.
    async def fake_call(*a, **k):
        return None
    monkeypatch.setattr(ps, "_call_nutq_scorer", fake_call)

    res = await ps.score_recording_bytes(
        b"AUDIO", "r.webm", "hello world", member, "accent", "L0")

    assert res.success is False
    assert res.error == "scorer unavailable"
    assert res.transcript == "" and res.score == 0

    conn = database._connect()
    n = conn.execute(
        "SELECT COUNT(*) FROM pronunciation_scores WHERE discord_id=?", (member,)).fetchone()[0]
    conn.close()
    assert n == 0


@pytest.mark.asyncio
async def test_score_bytes_store_false_does_not_persist(member, monkeypatch):
    # The "try again" re-check passes store=False → score must NOT be persisted.
    async def fake_call(*a, **k):
        return _scorer_result()
    monkeypatch.setattr(ps, "_call_nutq_scorer", fake_call)

    res = await ps.score_recording_bytes(
        b"A", "r.webm", "hello world", member, "accent", "L0", store=False)
    assert res.success is True

    conn = database._connect()
    n = conn.execute(
        "SELECT COUNT(*) FROM pronunciation_scores WHERE discord_id=?", (member,)).fetchone()[0]
    conn.close()
    assert n == 0


@pytest.mark.asyncio
async def test_url_path_still_delegates_to_bytes(member, monkeypatch):
    # The legacy URL entry should download then reuse the same bytes pipeline.
    async def fake_download(url):
        return b"DOWNLOADED"

    async def fake_call(audio_bytes, expected_text, level, filename):
        assert audio_bytes == b"DOWNLOADED"  # bytes flowed through
        return _scorer_result(score=90.0, missed_words=[])

    monkeypatch.setattr(ps, "download_audio", fake_download)
    monkeypatch.setattr(ps, "_call_nutq_scorer", fake_call)

    res = await ps.score_recording(
        "https://cdn/x.webm", "hello world", member, "accent", "L0")
    assert res.success is True
    assert res.score == 90.0
