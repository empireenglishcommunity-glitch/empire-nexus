"""Phase 8 (Mi'yar CEFR) — exit-exam retarget, AI rater, boundary decision,
review queue and placement storage.

Everything here is criterion-referenced and behind the OFF assessment flags;
these tests exercise the pure logic + DB layer with NO network (the AI rater is
stubbed), matching the design's test plan in
.kiro/specs/cefr-curriculum/design.md.
"""
import asyncio
import json

import pytest

from src import assessment, config, database

CONTENT = config.BASE_DIR / "content"
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]


# ── R7: Part B prompts retargeted to CEFR, legacy keys still resolve ──

def test_part_b_prompts_cover_every_cefr_level():
    assert sorted(assessment._PART_B_PROMPTS.keys()) == LEVELS
    for lv in LEVELS:
        p = assessment._PART_B_PROMPTS[lv]
        assert p["prompt_en"] and p["prompt_ar"]
        assert p["duration_sec"] > 0
        assert p.get("descriptors"), f"{lv} Part B has no descriptor tags"


def test_legacy_level_keys_still_resolve_to_cefr():
    # L0->A1, L1->A2, L2->B1, L3->B2 via config.cefr_key
    assert assessment.get_part_b_prompt("L0")["descriptors"][0].startswith("A1")
    assert assessment.get_part_b_prompt("L3")["descriptors"][0].startswith("B2")
    # unknown never raises -> A1 default
    assert assessment.get_part_b_prompt("nonsense")["descriptors"][0].startswith("A1")


def test_part_b_descriptor_codes_all_exist_in_can_do():
    cando = json.loads((CONTENT / "cefr" / "can_do.json").read_text(encoding="utf-8"))
    for lv in LEVELS:
        codes = set()
        for mode in ("reception", "production", "interaction", "mediation"):
            for d in cando[lv].get(mode, []):
                codes.add(d["code"])
        for c in assessment._PART_B_PROMPTS[lv]["descriptors"]:
            assert c in codes, f"{lv} Part B references missing descriptor {c}"


# ── Cut scores: expert-set, rise with level, single source of truth ──

def test_cut_scores_rise_with_level_and_resolve_legacy():
    a1, b2, c2 = (assessment.exit_exam_cut(x) for x in ("A1", "B2", "C2"))
    assert a1["part_b_min"] == 60 and b2["part_b_min"] == 65 and c2["part_b_min"] == 70
    # legacy key normalises (L2 -> B1)
    assert assessment.exit_exam_cut("L2")["part_b_min"] == 65


# ── Boundary decision: clear pass/fail auto-resolve; near-cut / low-conf review ──

@pytest.mark.parametrize("a,b,conf,expected", [
    (85, 80, 0.9, "pass"),    # clear
    (40, 30, 0.9, "fail"),    # clear
    (66, 80, 0.9, "review"),  # within +/-7 of Part A cut (65)
    (85, 63, 0.9, "review"),  # within +/-7 of Part B cut (65 for B1)
    (85, 80, 0.4, "review"),  # low AI confidence
])
def test_exit_exam_decision(a, b, conf, expected):
    d = assessment.exit_exam_decision("B1", a, {"total": b, "confidence": conf})
    assert d["decision"] == expected
    if expected == "review":
        assert d["reasons"], "a review decision must explain itself"


def test_distinction_only_on_clear_pass_with_high_part_b():
    d = assessment.exit_exam_decision("A1", 90, {"total": 92, "confidence": 0.95})
    assert d["decision"] == "pass" and d["distinction"] is True
    d2 = assessment.exit_exam_decision("A1", 90, {"total": 80, "confidence": 0.95})
    assert d2["distinction"] is False


# ── AI rater: success path + graceful fallback with NO network ──

def test_rate_part_b_uses_ai_when_available(monkeypatch):
    fake = json.dumps({
        "fluency": 20, "accuracy": 18, "vocab_range": 19, "pronunciation": 17,
        "evidenced_descriptors": ["B1.P.1"], "confidence": 0.82,
        "feedback": "Clear and well-organised.", "feedback_ar": "واضح ومنظّم.",
    })

    async def _fake_llm(prompt, temperature=0.2):
        return fake
    monkeypatch.setattr("src.ai_engine._call_llm", _fake_llm)

    res = asyncio.run(assessment.rate_part_b(
        "This is a genuine spoken response with enough words to be rated properly "
        "by the examiner about a time I learned something.", "B1"))
    assert res["rater"] == "ai"
    assert res["total"] == 74 and res["confidence"] == 0.82
    assert res["evidenced_descriptors"] == ["B1.P.1"]


def test_rate_part_b_falls_back_when_llm_unavailable(monkeypatch):
    async def _no_llm(prompt, temperature=0.2):
        return None
    monkeypatch.setattr("src.ai_engine._call_llm", _no_llm)

    res = asyncio.run(assessment.rate_part_b(
        "This is a reasonably long spoken response with several distinct words so "
        "the rule based scorer has something to work with here today.", "B1"))
    assert res["rater"] == "rule"          # fell back, did not crash
    assert "total" in res and res["confidence"] == 0.5
    assert "evidenced_descriptors" in res  # schema stays consistent across raters


def test_rate_part_b_fallback_when_llm_raises(monkeypatch):
    async def _boom(prompt, temperature=0.2):
        raise RuntimeError("network down")
    monkeypatch.setattr("src.ai_engine._call_llm", _boom)
    res = asyncio.run(assessment.rate_part_b("word " * 30, "A1"))
    assert res["rater"] == "rule"


# ── DB: review queue lifecycle ──

def test_review_queue_lifecycle():
    database.register_member("stu1", "Test Student")
    rid = database.exit_exam_enqueue_review(
        "stu1", "B1", attempt_num=1, part_a_pct=66.0, part_b_total=64,
        ai_confidence=0.6, rater="ai",
        reasons=["within ±7 of a cut"], evidenced=["B1.P.1", "B1.P.3"])
    assert rid > 0

    pending = database.exit_exam_pending_reviews()
    assert len(pending) == 1
    assert pending[0]["reasons"] == ["within ±7 of a cut"]
    assert pending[0]["evidenced"] == ["B1.P.1", "B1.P.3"]

    # filter by level
    assert database.exit_exam_pending_reviews("A1") == []
    assert len(database.exit_exam_pending_reviews("B1")) == 1

    updated = database.exit_exam_resolve_review(rid, "passed", "owner#1")
    assert updated["status"] == "passed" and updated["resolved_by"] == "owner#1"
    # no longer pending; resolving again is a no-op
    assert database.exit_exam_pending_reviews() == []
    assert database.exit_exam_resolve_review(rid, "failed", "owner#1") is None


def test_resolve_review_rejects_bad_status():
    database.register_member("stu2", "Test")
    rid = database.exit_exam_enqueue_review("stu2", "A1", 1, 60, 55, 0.5, "rule", [], [])
    with pytest.raises(ValueError):
        database.exit_exam_resolve_review(rid, "maybe", "owner")


# ── DB: placement result storage (per-skill profile) ──

def test_placement_result_roundtrip():
    database.register_member("stu3", "Test")
    bands = {"vocab_grammar": "B1", "listening": "A2", "writing": "B1", "speaking": "A2"}
    pid = database.save_placement_result("stu3", "A2", bands, recommended_week=1,
                                         source="self")
    assert pid > 0
    latest = database.latest_placement_result("stu3")
    assert latest["overall_level"] == "A2"
    assert latest["skill_bands"] == bands
    assert latest["recommended_week"] == 1
    assert database.latest_placement_result("nobody") is None
