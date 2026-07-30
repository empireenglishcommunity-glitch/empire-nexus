"""Nutq — engine selector + usage guard + cost policy (Phase A2).

Verifies score_recording_bytes chooses Azure (primary) vs the local engine
(fallback) per the cost policy + usage guard, records usage/counters, and that
the fallback feedback is coarse (no specific sound named).
"""
import json
import pytest

from src import pronunciation_scorer as ps
from src import database, config


@pytest.fixture
def member():
    database.register_member("900200888", "Nutq Engine Test")
    return "900200888"


@pytest.fixture
def azure_on(monkeypatch):
    monkeypatch.setattr(config, "NUTQ_AZURE_ENABLED", True)
    monkeypatch.setattr(config, "AZURE_SPEECH_KEY", "test-key")
    monkeypatch.setattr(config, "AZURE_SPEECH_REGION", "eastus")


def _azure_payload(**over):
    d = {"score": 88.0, "accuracy": 88.0, "missed_words": ["through"],
         "worst_phoneme": "th", "display_text": "i walk through the park",
         "duration_s": 12.0}
    d.update(over)
    return d


def _fake_azure(payload):
    async def _f(audio_bytes, filename, reference_text):
        return payload
    return _f


def _fake_local(result):
    async def _f(audio_bytes, expected_text, level, filename):
        return result
    return _f


LOCAL_RESULT = {"score": 70.0, "raw_score": 68.0, "missed_words": ["park"],
                "heard_phonemes": "aɪ w ɔ k", "feedback_en": "x", "feedback_ar": "y"}


# ── Azure chosen when eligible ────────────────────────────────────────────
@pytest.mark.asyncio
async def test_azure_used_when_eligible(member, azure_on, monkeypatch):
    from src import pronunciation_azure
    monkeypatch.setattr(pronunciation_azure, "score", _fake_azure(_azure_payload()))
    res = await ps.score_recording_bytes(b"A", "r.webm", "I walk through the park",
                                          member, "shadow", "L0")
    assert res.success and res.score == 88.0
    assert res.transcript == "i walk through the park"      # Azure readable "we heard"
    assert "through" in res.missed_words
    assert "th" in res.feedback_en.lower() or "teeth" in res.feedback_en.lower()
    # usage + daily counter recorded
    month = database._today_local().strftime("%Y-%m")
    today = database._today_local().isoformat()
    assert database.azure_usage_seconds(month) == 12.0
    assert database.azure_calls_today(member, today) == 1


# ── Fallback to local ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_local_when_task_not_shadow(member, azure_on, monkeypatch):
    from src import pronunciation_azure
    called = {"azure": False}
    async def spy(*a, **k):
        called["azure"] = True
        return _azure_payload()
    monkeypatch.setattr(pronunciation_azure, "score", spy)
    monkeypatch.setattr(ps, "_call_nutq_scorer", _fake_local(LOCAL_RESULT))
    res = await ps.score_recording_bytes(b"A", "r.webm", "hi", member, "accent", "L0")
    assert called["azure"] is False          # accent → Azure never called
    assert res.success and res.score == 70.0
    assert res.transcript == ""              # local → no readable transcript


@pytest.mark.asyncio
async def test_local_when_usage_guard_tripped(member, azure_on, monkeypatch):
    month = database._today_local().strftime("%Y-%m")
    database.add_azure_usage(month, config.NUTQ_AZURE_FREE_SECONDS)  # over 90%
    from src import pronunciation_azure
    called = {"azure": False}
    async def spy(*a, **k):
        called["azure"] = True
        return _azure_payload()
    monkeypatch.setattr(pronunciation_azure, "score", spy)
    monkeypatch.setattr(ps, "_call_nutq_scorer", _fake_local(LOCAL_RESULT))
    res = await ps.score_recording_bytes(b"A", "r.webm", "hi", member, "shadow", "L0")
    assert called["azure"] is False          # guard → skip Azure
    assert res.score == 70.0


@pytest.mark.asyncio
async def test_local_when_daily_cap_reached(member, azure_on, monkeypatch):
    today = database._today_local().isoformat()
    for _ in range(config.NUTQ_AZURE_MAX_CALLS_PER_DAY):
        database.incr_azure_calls_today(member, today)
    from src import pronunciation_azure
    monkeypatch.setattr(pronunciation_azure, "score", _fake_azure(_azure_payload()))
    monkeypatch.setattr(ps, "_call_nutq_scorer", _fake_local(LOCAL_RESULT))
    res = await ps.score_recording_bytes(b"A", "r.webm", "hi", member, "shadow", "L0")
    assert res.score == 70.0                 # cap reached → local


@pytest.mark.asyncio
async def test_local_when_azure_returns_none(member, azure_on, monkeypatch):
    from src import pronunciation_azure
    monkeypatch.setattr(pronunciation_azure, "score", _fake_azure(None))
    monkeypatch.setattr(ps, "_call_nutq_scorer", _fake_local(LOCAL_RESULT))
    res = await ps.score_recording_bytes(b"A", "r.webm", "hi", member, "shadow", "L0")
    assert res.success and res.score == 70.0


@pytest.mark.asyncio
async def test_scored_false_when_both_fail(member, azure_on, monkeypatch):
    from src import pronunciation_azure
    monkeypatch.setattr(pronunciation_azure, "score", _fake_azure(None))
    monkeypatch.setattr(ps, "_call_nutq_scorer", _fake_local(None))
    res = await ps.score_recording_bytes(b"A", "r.webm", "hi", member, "shadow", "L0")
    assert res.success is False


@pytest.mark.asyncio
async def test_azure_disabled_without_key(member, monkeypatch):
    # No key → Azure ineligible even for shadow → local.
    monkeypatch.setattr(config, "AZURE_SPEECH_KEY", "")
    monkeypatch.setattr(ps, "_call_nutq_scorer", _fake_local(LOCAL_RESULT))
    res = await ps.score_recording_bytes(b"A", "r.webm", "hi", member, "shadow", "L0")
    assert res.score == 70.0


# ── feedback + guard math ─────────────────────────────────────────────────
def test_local_feedback_is_coarse_no_sound():
    for sc in (95, 70, 30):
        en, ar = ps._local_feedback(sc)
        assert en and ar and en != ar
        # coarse: never quotes a specific sound/word (that detail is unreliable locally)
        assert "'" not in en and "'" not in ar

def test_azure_eligible_respects_flag_and_task(member, azure_on):
    assert ps._azure_eligible(member, "shadow") is True
    assert ps._azure_eligible(member, "accent") is False
