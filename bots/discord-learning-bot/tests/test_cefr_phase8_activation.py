"""Phase 8 GO-LIVE — activation of the CEFR exit exam in the live finish path.

finish_advancement_exit() replaces the legacy weighted verdict with criterion
cut scores + AI descriptor-rater + boundary human review, while preserving the
advancement_exams bookkeeping. No network: rate_part_b is stubbed.
"""
import pytest

from src import assessment, database


def _seed_attempt(discord_id, level, attempt_id, part_a_score, passed=0,
                  skill_mins='{"vocab": 80, "listening": 80}'):
    database.register_member(discord_id, f"Student {discord_id}")
    database.set_level(discord_id, level)
    conn = database._connect()
    conn.execute(
        "INSERT INTO advancement_exams "
        "(discord_id, level, attempt_num, attempt_id, part_a_score, skill_mins, passed) "
        "VALUES (?,?,?,?,?,?,?)",
        (discord_id, level, 1, attempt_id, part_a_score, skill_mins, passed))
    conn.commit()
    conn.close()


@pytest.fixture
def stub_part_b(monkeypatch):
    holder = {}

    async def _fake(transcript, level, prompt=None):
        return holder["score"]

    monkeypatch.setattr(assessment, "rate_part_b", _fake)

    def _set(total, confidence, rater="ai"):
        holder["score"] = {
            "total": total, "fluency": 20, "accuracy": 20, "vocab_range": 20,
            "pronunciation": max(total - 60, 0),
            "evidenced_descriptors": ["A1.P.1"], "confidence": confidence,
            "rater": rater, "feedback": "ok", "feedback_ar": "تمام",
        }
    return _set


def _row(attempt_id):
    conn = database._connect()
    r = conn.execute("SELECT * FROM advancement_exams WHERE attempt_id=?",
                     (attempt_id,)).fetchone()
    conn.close()
    return dict(r) if r else None


@pytest.mark.asyncio
async def test_exit_finish_clear_pass_marks_passed(stub_part_b):
    _seed_attempt("ep", "A1", 5001, part_a_score=92)
    stub_part_b(92, 0.9)   # A1 cut 65/60 → clear pass, B≥90 → distinction
    out = await assessment.finish_advancement_exit("ep", 5001, "word " * 20)
    assert out["ok"] and out["decision"] == "pass"
    assert out["distinction"] is True
    assert out["overall_pct"] == 92.0
    assert _row(5001)["passed"] == 1


@pytest.mark.asyncio
async def test_exit_finish_clear_fail_marks_not_passed(stub_part_b):
    _seed_attempt("ef", "A1", 5002, part_a_score=40)
    stub_part_b(40, 0.9)
    out = await assessment.finish_advancement_exit("ef", 5002, "word " * 20)
    assert out["ok"] and out["decision"] == "fail"
    assert out["passed"] is False
    assert _row(5002)["passed"] == 0


@pytest.mark.asyncio
async def test_exit_finish_boundary_enqueues_review_and_stays_unpassed(stub_part_b):
    _seed_attempt("er", "A1", 5003, part_a_score=66)  # within ±7 of cut 65
    stub_part_b(85, 0.9)
    out = await assessment.finish_advancement_exit("er", 5003, "word " * 20)
    assert out["decision"] == "review"
    assert out["review_id"] is not None
    assert _row(5003)["passed"] == 0                  # not promoted pending review
    pending = database.exit_exam_pending_reviews()
    assert any(r["id"] == out["review_id"] for r in pending)


@pytest.mark.asyncio
async def test_exit_finish_unknown_attempt(stub_part_b):
    stub_part_b(90, 0.9)
    out = await assessment.finish_advancement_exit("nobody", 999999, "word " * 20)
    assert out == {"ok": False, "error": "not_found"}


@pytest.mark.asyncio
async def test_exit_finish_already_passed_is_guarded(stub_part_b):
    _seed_attempt("edone", "A1", 5004, part_a_score=90, passed=1)
    stub_part_b(90, 0.9)
    out = await assessment.finish_advancement_exit("edone", 5004, "word " * 20)
    assert out == {"ok": False, "error": "already_passed"}



def test_certificate_data_includes_can_do_checklist():
    """Phase 8: the certificate endpoint carries the level's CEFR can-do
    descriptors + the aligned-not-certified marker for the honest footer."""
    database.register_member("certu", "Cert User")
    database.set_level("certu", "A1")
    data = database.itqan_certificate_data("certu", "A1")
    assert data["cefr_aligned"] is True
    assert isinstance(data["can_do"], list) and data["can_do"]
    first = data["can_do"][0]
    assert {"code", "en", "mode"}.issubset(first.keys())
    assert first["code"].startswith("A1.")
