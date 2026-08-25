"""Phase 8 — CEFR placement RUNNER (interactive session on top of placement.py).

Verifies the adaptive vocab session, the transition to the writing task, the
final per-skill profile + conservative overall, and opt-in slotting. The AI
writing rater is stubbed (no network); correct answers are read from the
server-side session (never exposed to the client).
"""
import pytest

from src import assessment, database, placement_runner


@pytest.fixture
def stub_writing(monkeypatch):
    holder = {"total": 80}

    async def _fake(text, level, prompt=None):
        return {"total": holder["total"], "fluency": 20, "accuracy": 20,
                "vocab_range": 20, "pronunciation": 20, "evidenced_descriptors": [],
                "confidence": 0.9, "rater": "ai", "feedback": "", "feedback_ar": ""}

    monkeypatch.setattr(assessment, "rate_part_b", _fake)
    return holder


def _answer_current(discord_id, correct=True):
    st = database.placement_session_get(discord_id)
    block = st["current_block"]
    out = {}
    for it in block:
        if correct:
            out[it["q_id"]] = it["answer"]
        else:
            out[it["q_id"]] = next((o for o in it["options"] if o != it["answer"]),
                                   it["answer"])
    return out


def test_start_returns_block_without_answers():
    database.register_member("plc1", "Placement One")
    out = placement_runner.start_session("plc1", seed="fixed")
    assert out["ok"] and out["phase"] == "vocab"
    assert out["block"], "expected objective items"
    for it in out["block"]:
        assert "answer" not in it              # answers never sent to the client
        assert len(it["options"]) == 4
        assert "prompt_ar" in it


@pytest.mark.asyncio
async def test_full_run_produces_per_skill_profile(stub_writing):
    database.register_member("plc2", "Placement Two")
    placement_runner.start_session("plc2", seed="fixed")

    # Answer objective blocks until the writing task appears.
    out = {"phase": "vocab"}
    guard = 0
    while out.get("phase") == "vocab" and guard < 10:
        out = await placement_runner.submit_answers("plc2", _answer_current("plc2"))
        guard += 1
    assert out["phase"] == "writing"
    assert "band" in out and "prompt" in out

    # Submit the writing sample → final profile.
    final = await placement_runner.submit_writing("plc2", "This is my writing sample. " * 5)
    assert final["ok"] and final["phase"] == "done"
    assert "vocab_grammar" in final["skill_bands"]
    assert "writing" in final["skill_bands"]
    assert final["overall_level"] in ("A1", "A2", "B1", "B2", "C1", "C2")
    assert "vocab_grammar" in final["measured_skills"]
    # Result was persisted, but the student is NOT auto-slotted.
    assert final["slotted"] is False
    assert database.latest_placement_result("plc2")["overall_level"] == final["overall_level"]


@pytest.mark.asyncio
async def test_weak_writing_drops_writing_band(stub_writing):
    stub_writing["total"] = 30                # below WRITING_PASS
    database.register_member("plc3", "Placement Three")
    placement_runner.start_session("plc3", seed="fixed")
    out = {"phase": "vocab"}
    guard = 0
    while out.get("phase") == "vocab" and guard < 10:
        out = await placement_runner.submit_answers("plc3", _answer_current("plc3"))
        guard += 1
    vocab_band = out["band"]
    final = await placement_runner.submit_writing("plc3", "short")
    # weak writing resolves at or below the vocab band, never above
    from src import placement
    assert placement.band_index(final["skill_bands"]["writing"]) <= placement.band_index(vocab_band)


@pytest.mark.asyncio
async def test_slot_is_opt_in_and_sets_level(stub_writing):
    database.register_member("plc4", "Placement Four")
    placement_runner.start_session("plc4", seed="fixed")
    out = {"phase": "vocab"}
    guard = 0
    while out.get("phase") == "vocab" and guard < 10:
        out = await placement_runner.submit_answers("plc4", _answer_current("plc4"))
        guard += 1
    final = await placement_runner.submit_writing("plc4", "sample " * 10)
    slot = placement_runner.slot_student("plc4")
    assert slot["ok"] and slot["slotted"] is True
    assert (database.get_member("plc4") or {}).get("level") == final["overall_level"]
    # session cleared after slotting
    assert database.placement_session_get("plc4") is None


@pytest.mark.asyncio
async def test_answer_without_session_errors():
    out = await placement_runner.submit_answers("ghost", {})
    assert out == {"ok": False, "error": "no_session"}
