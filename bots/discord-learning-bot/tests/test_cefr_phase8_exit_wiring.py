"""Phase 8b-wiring (Mi'yar CEFR) — exit-exam wiring:
  * Part A items tagged with real can-do descriptor codes.
  * exit_exam_finalize() routing: pass / fail / review / disabled, and the
    review queue getting populated on a boundary/low-confidence verdict.
  * The owner review-resolution path (promote_from_review) actually promoting.

No network: rate_part_b is stubbed so the AI rater is never called. All
exit-exam paths are gated by the OFF `assessment_advancement_exam` flag; tests
enable it explicitly.
"""
import json

import pytest

from src import advancement_outcomes, assessment, config, database


def _enable():
    database.set_feature_flag("assessment_advancement_exam", True,
                              allowed_ids="", updated_by="test")


# ── can-do tagging ──

def test_part_a_items_tagged_with_valid_can_do_codes():
    bp = assessment.generate_advancement_blueprint_a("u1", "A1", seed="fixed",
                                                     total_items=18)
    cando = json.load(open(config.BASE_DIR / "content" / "cefr" / "can_do.json",
                           encoding="utf-8"))["A1"]
    valid = {d["code"] for mode in ("reception", "production", "interaction", "mediation")
             for d in cando.get(mode, [])}
    tagged = [it for it in bp["items"] if "can_do" in it]
    # every objective/production item (all 5 mapped skills) should be tagged
    assert tagged, "no items were tagged with can-do codes"
    for it in tagged:
        assert it["can_do"]["code"] in valid
        assert it["can_do"]["mode"] in ("reception", "production")
        # skill→mode mapping is respected
        assert assessment._CAN_DO_SKILL_MODE[it["skill"]] == it["can_do"]["mode"]


def test_can_do_descriptors_returns_dict_and_never_raises():
    assert isinstance(assessment.can_do_descriptors("ZZ"), dict)   # never raises
    assert isinstance(assessment.can_do_descriptors("A1"), dict)


# ── exit_exam_finalize routing ──

@pytest.fixture
def stub_part_b(monkeypatch):
    """Force rate_part_b to return a chosen score dict (no LLM)."""
    holder = {}

    async def _fake(transcript, level, prompt=None):
        return holder["score"]

    monkeypatch.setattr(assessment, "rate_part_b", _fake)

    def _set(total, confidence, rater="ai"):
        holder["score"] = {
            "total": total, "fluency": 20, "accuracy": 20, "vocab_range": 20,
            "pronunciation": total - 60, "evidenced_descriptors": ["A1.P.1"],
            "confidence": confidence, "rater": rater,
            "feedback": "ok", "feedback_ar": "تمام",
        }
    return _set


@pytest.mark.asyncio
async def test_finalize_disabled_when_flag_off(stub_part_b):
    stub_part_b(90, 0.9)
    out = await assessment.exit_exam_finalize("uoff", "A1", 90, "word " * 20)
    assert out["decision"] == "disabled"


@pytest.mark.asyncio
async def test_finalize_clear_pass_with_distinction(stub_part_b):
    _enable()
    stub_part_b(92, 0.9)   # A1 cut 65/60 → big margins, conf high → pass; B≥90 → distinction
    out = await assessment.exit_exam_finalize("up", "A1", 90, "word " * 20)
    assert out["decision"] == "pass"
    assert out["distinction"] is True
    assert out["review_id"] is None


@pytest.mark.asyncio
async def test_finalize_clear_fail(stub_part_b):
    _enable()
    stub_part_b(40, 0.9)   # part_a 40 << 65 → clear fail
    out = await assessment.exit_exam_finalize("uf", "A1", 40, "word " * 20)
    assert out["decision"] == "fail"
    assert out["review_id"] is None


@pytest.mark.asyncio
async def test_finalize_near_boundary_enqueues_review(stub_part_b):
    _enable()
    database.register_member("ur", "Boundary Student")  # FK: reviews reference members
    stub_part_b(85, 0.9)   # part_a 66 is within ±7 of cut 65 → review
    out = await assessment.exit_exam_finalize("ur", "A1", 66, "word " * 20,
                                              attempt_num=1)
    assert out["decision"] == "review"
    assert out["review_id"] is not None
    pending = database.exit_exam_pending_reviews()
    assert any(r["id"] == out["review_id"] and r["discord_id"] == "ur" for r in pending)


@pytest.mark.asyncio
async def test_finalize_low_confidence_forces_review(stub_part_b):
    _enable()
    database.register_member("ulc", "LowConf Student")  # FK: reviews reference members
    stub_part_b(92, 0.40)  # scores clearly pass, but AI unsure → review
    out = await assessment.exit_exam_finalize("ulc", "A1", 90, "word " * 20)
    assert out["decision"] == "review"
    assert any("confidence" in r for r in out["reasons"])


# ── owner review resolution → promotion ──

@pytest.mark.asyncio
async def test_promote_from_review_advances_level():
    database.register_member("urev", "Rev Student")
    database.set_level("urev", "A1")
    rid = database.exit_exam_enqueue_review("urev", "A1", 1, 66.0, 61, 0.9,
                                            "ai", ["near cut"], ["A1.P.1"])
    row = database.exit_exam_resolve_review(rid, "passed", "owner#1")
    assert row and row["discord_id"] == "urev"
    await advancement_outcomes.promote_from_review(row)
    # promotion actually moved them to the next CEFR level
    assert (database.get_member("urev") or {}).get("level") == "A2"


@pytest.mark.asyncio
async def test_fail_from_review_does_not_promote():
    database.register_member("urev2", "Rev Student 2")
    database.set_level("urev2", "A1")
    rid = database.exit_exam_enqueue_review("urev2", "A1", 1, 63.0, 59, 0.9,
                                            "ai", ["near cut"], [])
    row = database.exit_exam_resolve_review(rid, "failed", "owner#1")
    await advancement_outcomes.fail_from_review(row)   # no bot → DM no-op, must not raise
    assert (database.get_member("urev2") or {}).get("level") == "A1"


def test_resolving_unknown_review_returns_none():
    assert database.exit_exam_resolve_review(999999, "passed", "owner#1") is None
