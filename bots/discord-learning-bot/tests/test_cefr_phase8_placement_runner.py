"""Phase 8 — CEFR placement RUNNER (interactive session on top of placement.py).

Full 4-skill flow: vocab/grammar (adaptive MC) → listening (dictation, browser
TTS) → writing (AI-rated) → speaking (AI-rated) → conservative overall level.
The AI rater is stubbed (no network); answers are read from the server-side
session (never exposed to the client).
"""
import pytest

from src import assessment, database, placement, placement_runner


@pytest.fixture
def stub_rater(monkeypatch):
    holder = {"total": 80}

    async def _fake(text, level, prompt=None):
        return {"total": holder["total"], "fluency": 20, "accuracy": 20,
                "vocab_range": 20, "pronunciation": 20, "evidenced_descriptors": [],
                "confidence": 0.9, "rater": "ai", "feedback": "", "feedback_ar": ""}

    monkeypatch.setattr(assessment, "rate_part_b", _fake)
    return holder


def _answer_current(discord_id, correct=True):
    """Answer the current block — works for vocab (has options) and listening
    (dictation, no options)."""
    st = database.placement_session_get(discord_id)
    block = st["current_block"]
    out = {}
    for it in block:
        ans = it["answer"]
        if not correct:
            if it.get("options"):
                ans = next((o for o in it["options"] if o != it["answer"]), it["answer"])
            else:
                ans = it["answer"] + "zzz"
        out[it["q_id"]] = ans
    return out


async def _run_objective_to_writing(discord_id):
    """Answer vocab blocks + the listening block until the writing task appears."""
    out = {"phase": "vocab"}
    guard = 0
    while out.get("phase") in ("vocab", "listening") and guard < 12:
        out = await placement_runner.submit_answers(discord_id, _answer_current(discord_id))
        guard += 1
    return out


def test_start_returns_block_without_answers():
    database.register_member("plc1", "Placement One")
    out = placement_runner.start_session("plc1", seed="fixed")
    assert out["ok"] and out["phase"] == "vocab"
    assert out["block"]
    for it in out["block"]:
        assert "answer" not in it
        assert len(it["options"]) == 4


@pytest.mark.asyncio
async def test_objective_phase_flows_vocab_then_listening_then_writing(stub_rater):
    database.register_member("plc2", "Placement Two")
    placement_runner.start_session("plc2", seed="fixed")
    # Vocab blocks first…
    out = await placement_runner.submit_answers("plc2", _answer_current("plc2"))
    seen_listening = out["phase"] == "listening"
    guard = 0
    while out.get("phase") in ("vocab", "listening") and guard < 12:
        if out["phase"] == "listening":
            seen_listening = True
            # listening items carry say_en (for TTS) but no options/answer
            for it in out["block"]:
                assert "say_en" in it and "answer" not in it and "options" not in it
        out = await placement_runner.submit_answers("plc2", _answer_current("plc2"))
        guard += 1
    assert seen_listening, "listening phase should occur between vocab and writing"
    assert out["phase"] == "writing"


@pytest.mark.asyncio
async def test_full_4skill_run_produces_profile_and_finalises(stub_rater):
    database.register_member("plc3", "Placement Three")
    placement_runner.start_session("plc3", seed="fixed")
    w = await _run_objective_to_writing("plc3")
    assert w["phase"] == "writing"
    sp = await placement_runner.submit_writing("plc3", "This is my writing sample. " * 5)
    assert sp["phase"] == "speaking" and "prompt" in sp
    final = await placement_runner.submit_speaking("plc3", "I would like to talk about my day and my goals in English.")
    assert final["ok"] and final["phase"] == "done"
    for skill in ("vocab_grammar", "listening", "writing", "speaking"):
        assert skill in final["skill_bands"], f"missing {skill}"
        assert skill in final["measured_skills"]
    assert final["overall_level"] in ("A1", "A2", "B1", "B2", "C1", "C2")
    assert final["slotted"] is False
    assert database.latest_placement_result("plc3")["overall_level"] == final["overall_level"]


@pytest.mark.asyncio
async def test_empty_speaking_transcript_finalises_on_other_skills(stub_rater):
    database.register_member("plc4", "Placement Four")
    placement_runner.start_session("plc4", seed="fixed")
    await _run_objective_to_writing("plc4")
    await placement_runner.submit_writing("plc4", "sample " * 8)
    final = await placement_runner.submit_speaking("plc4", "")   # STT failed / no audio
    assert final["ok"] and final["phase"] == "done"
    assert "speaking" not in final["skill_bands"]        # skipped, not fabricated
    assert "vocab_grammar" in final["skill_bands"] and "writing" in final["skill_bands"]


@pytest.mark.asyncio
async def test_weak_writing_never_scores_above_vocab_band(stub_rater):
    stub_rater["total"] = 30
    database.register_member("plc5", "Placement Five")
    placement_runner.start_session("plc5", seed="fixed")
    w = await _run_objective_to_writing("plc5")
    vocab_band = w["band"]
    sp = await placement_runner.submit_writing("plc5", "short")
    st = database.placement_session_get("plc5")
    assert placement.band_index(st["skill_bands"]["writing"]) <= placement.band_index(vocab_band)


@pytest.mark.asyncio
async def test_slot_is_opt_in_and_sets_level(stub_rater):
    database.register_member("plc6", "Placement Six")
    placement_runner.start_session("plc6", seed="fixed")
    await _run_objective_to_writing("plc6")
    await placement_runner.submit_writing("plc6", "sample " * 8)
    final = await placement_runner.submit_speaking("plc6", "a spoken answer about my week")
    slot = placement_runner.slot_student("plc6")
    assert slot["ok"] and slot["slotted"] is True
    assert (database.get_member("plc6") or {}).get("level") == final["overall_level"]
    assert database.placement_session_get("plc6") is None


@pytest.mark.asyncio
async def test_answer_without_session_errors():
    out = await placement_runner.submit_answers("ghost", {})
    assert out == {"ok": False, "error": "no_session"}
