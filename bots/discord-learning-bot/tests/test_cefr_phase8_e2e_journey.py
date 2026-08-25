"""Phase 8 (Phase-10 verification) — END-TO-END ghost journeys through the LIVE
CEFR exit-exam chain, driving the real production functions:

  start_advancement_attempt  →  (Part A)  →  finish_advancement_exit
      →  deliver_exit_exam_outcome / boundary review  →  promotion  →  certificate

Only the network is stubbed (rate_part_b) and the calendar "due" gate is forced
(a real student at end-of-level would be due). Everything else is the real code
students hit. Three journeys: clear pass, boundary→review→owner-pass, clear fail.
"""
import pytest

from src import advancement_outcomes, assessment, database


@pytest.fixture
def stub_part_b(monkeypatch):
    holder = {"total": 92, "conf": 0.9}

    async def _fake(transcript, level, prompt=None):
        return {"total": holder["total"], "fluency": 22, "accuracy": 22,
                "vocab_range": 22, "pronunciation": holder["total"] - 66,
                "evidenced_descriptors": ["A1.P.1"], "confidence": holder["conf"],
                "rater": "ai", "feedback": "ok", "feedback_ar": "تمام"}

    monkeypatch.setattr(assessment, "rate_part_b", _fake)
    return holder


@pytest.fixture(autouse=True)
def force_due(monkeypatch):
    # A real student at the end of a level is "due"; force it so start works.
    monkeypatch.setattr(database, "advancement_exam_due", lambda did: True)


def _begin_exam(discord_id, part_a_pct):
    """Register a ghost on A1, enable the exam, start it, and set a Part A score
    (as finish_advancement_part_a would) — returns the attempt_id."""
    database.register_member(discord_id, f"Ghost {discord_id}")
    database.set_level(discord_id, "A1")
    database.set_feature_flag("assessment_advancement_exam", True)
    start = assessment.start_advancement_attempt(discord_id, "A1")
    assert start["ok"], f"start failed: {start}"
    assert start["items"], "Part A should have items"
    attempt_id = start["attempt_id"]
    conn = database._connect()
    conn.execute(
        "UPDATE advancement_exams SET part_a_score=?, skill_mins=? WHERE attempt_id=?",
        (part_a_pct,
         '{"vocab":90,"listening":90,"speaking":90,"writing":90,"pronunciation":90}',
         attempt_id))
    conn.commit()
    conn.close()
    return attempt_id


@pytest.mark.asyncio
async def test_journey_clear_pass_promotes_and_certifies(stub_part_b):
    stub_part_b["total"] = 92        # clear pass + distinction (≥90)
    aid = _begin_exam("gpass", part_a_pct=95)

    result = await assessment.finish_advancement_exit("gpass", aid, "long sample " * 20)
    assert result["ok"] and result["decision"] == "pass"
    assert result["distinction"] is True

    await advancement_outcomes.deliver_exit_exam_outcome("gpass", "A1", {
        "decision": "pass", "distinction": True,
        "part_a_pct": result["part_a_pct"], "part_b_total": result["part_b_total"],
        "confidence": result["confidence"], "reasons": result["reasons"]})

    # Promoted A1 → A2
    assert (database.get_member("gpass") or {}).get("level") == "A2"
    # Exam-based certificate, certified at the level they PASSED (A1)
    cert = database.itqan_certificate_data("gpass", "A2")
    assert cert["basis"] == "exam" and cert["level"] == "A1"
    assert cert["distinction"] is True
    assert "demonstrated proficiency at CEFR Level A1" in cert["statement_en"]
    assert cert["can_do"]


@pytest.mark.asyncio
async def test_journey_boundary_goes_to_review_then_owner_passes(stub_part_b):
    stub_part_b["total"] = 62        # within ±7 of the A1 Part B cut (60) → review
    aid = _begin_exam("grev", part_a_pct=66)  # also near the Part A cut (65)

    result = await assessment.finish_advancement_exit("grev", aid, "sample " * 20)
    assert result["decision"] == "review"
    assert result["review_id"] is not None
    # Not promoted while under review
    assert (database.get_member("grev") or {}).get("level") == "A1"

    # Owner resolves the queued review as a pass → promotion
    pending = database.exit_exam_pending_reviews()
    assert any(r["id"] == result["review_id"] for r in pending)
    row = database.exit_exam_resolve_review(result["review_id"], "passed", "owner#1")
    await advancement_outcomes.promote_from_review(row)
    assert (database.get_member("grev") or {}).get("level") == "A2"


@pytest.mark.asyncio
async def test_journey_clear_fail_stays_put_no_exam_certificate(stub_part_b):
    stub_part_b["total"] = 40
    aid = _begin_exam("gfail", part_a_pct=40)

    result = await assessment.finish_advancement_exit("gfail", aid, "sample " * 20)
    assert result["decision"] == "fail" and result["passed"] is False

    await advancement_outcomes.deliver_exit_exam_outcome("gfail", "A1", {
        "decision": "fail", "distinction": False,
        "part_a_pct": result["part_a_pct"], "part_b_total": result["part_b_total"],
        "confidence": result["confidence"], "reasons": result["reasons"]})

    assert (database.get_member("gfail") or {}).get("level") == "A1"   # not promoted
    cert = database.itqan_certificate_data("gfail", "A1")
    assert cert["basis"] == "mastery" and cert["eligible"] is False    # no exam credential
