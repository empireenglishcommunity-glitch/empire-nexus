"""Tests for Aql (#15) Phase A8.1/A8.2/A8.3/A8.6 — golden/red-team
sets and the evaluation harness.

Covers:
- A8.1/A8.2/A8.3: the 3 JSON data files are well-formed, have the
  right counts, and every question/prompt has the fields the harness
  actually needs.
- A8.6: the evaluation harness's scoring/loading functions work
  correctly in isolation (these tests do NOT require a real API key --
  they test the harness's OWN logic with a mocked pipeline, not real
  model quality, which is exactly the split A8.7's sign-off document
  itself draws).
"""
import importlib
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

EVAL_DIR = Path(__file__).resolve().parent.parent / "data" / "nour_eval"
SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / "scripts")


def _load_harness():
    sys.path.insert(0, SCRIPTS_DIR)
    try:
        mod = importlib.import_module("run_golden_set_eval")
        importlib.reload(mod)
        return mod
    finally:
        sys.path.remove(SCRIPTS_DIR)


# ============================================================
#  A8.1/A8.2/A8.3 — data file structure
# ============================================================

def test_student_golden_set_has_exactly_100_questions():
    data = json.loads((EVAL_DIR / "golden_set_student.json").read_text(encoding="utf-8"))
    assert len(data["questions"]) == 100


def test_owner_golden_set_has_exactly_30_questions():
    data = json.loads((EVAL_DIR / "golden_set_owner.json").read_text(encoding="utf-8"))
    assert len(data["questions"]) == 30


def test_red_team_set_has_exactly_50_prompts():
    data = json.loads((EVAL_DIR / "red_team_set.json").read_text(encoding="utf-8"))
    assert len(data["prompts"]) == 50


def test_every_student_question_has_required_fields():
    data = json.loads((EVAL_DIR / "golden_set_student.json").read_text(encoding="utf-8"))
    for q in data["questions"]:
        assert q["id"]
        assert q["domain"]
        assert q["question"]
        assert isinstance(q["expected_keywords"], list) and len(q["expected_keywords"]) > 0


def test_every_owner_question_has_required_fields():
    data = json.loads((EVAL_DIR / "golden_set_owner.json").read_text(encoding="utf-8"))
    for q in data["questions"]:
        assert q["id"]
        assert q["domain"]
        assert q["question"]
        assert isinstance(q["expected_keywords"], list) and len(q["expected_keywords"]) > 0


def test_every_red_team_prompt_has_required_fields():
    data = json.loads((EVAL_DIR / "red_team_set.json").read_text(encoding="utf-8"))
    for p in data["prompts"]:
        assert p["id"]
        assert p["category"]
        assert p["prompt"]


def test_red_team_set_covers_all_five_categories_evenly():
    data = json.loads((EVAL_DIR / "red_team_set.json").read_text(encoding="utf-8"))
    categories = [p["category"] for p in data["prompts"]]
    expected = {"direct", "role_play", "instruction_override", "obfuscated_translated", "social_engineering"}
    assert set(categories) == expected
    for cat in expected:
        assert categories.count(cat) == 10


def test_student_question_ids_are_unique():
    data = json.loads((EVAL_DIR / "golden_set_student.json").read_text(encoding="utf-8"))
    ids = [q["id"] for q in data["questions"]]
    assert len(ids) == len(set(ids))


def test_owner_question_ids_are_unique():
    data = json.loads((EVAL_DIR / "golden_set_owner.json").read_text(encoding="utf-8"))
    ids = [q["id"] for q in data["questions"]]
    assert len(ids) == len(set(ids))


def test_red_team_prompt_ids_are_unique():
    data = json.loads((EVAL_DIR / "red_team_set.json").read_text(encoding="utf-8"))
    ids = [p["id"] for p in data["prompts"]]
    assert len(ids) == len(set(ids))


def test_student_golden_set_domains_are_all_real_student_domains():
    """Every domain tag used in the golden set must be a domain that
    actually exists in permissions.py's student-accessible list --
    otherwise the golden set would be testing retrieval against a
    domain that could never be reached anyway."""
    from src.nour import permissions
    from src.nour.roles import Role

    student_domains = set(permissions.get_knowledge_domains(Role.STUDENT))
    data = json.loads((EVAL_DIR / "golden_set_student.json").read_text(encoding="utf-8"))
    used_domains = {q["domain"] for q in data["questions"]}
    unknown = used_domains - student_domains
    assert not unknown, f"golden set references domains not in Role.STUDENT's list: {unknown}"


def test_owner_golden_set_domains_are_all_real_owner_domains():
    from src.nour import permissions
    from src.nour.roles import Role

    owner_domains = set(permissions.get_knowledge_domains(Role.OWNER))
    data = json.loads((EVAL_DIR / "golden_set_owner.json").read_text(encoding="utf-8"))
    used_domains = {q["domain"] for q in data["questions"]}
    unknown = used_domains - owner_domains
    assert not unknown, f"owner golden set references domains not in Role.OWNER's list: {unknown}"


# ============================================================
#  A8.6 — evaluation harness logic (mocked pipeline, no real API key)
# ============================================================

def test_harness_summarize_computes_correct_pass_rate():
    harness = _load_harness()
    results = [{"id": "x1", "passed": True}, {"id": "x2", "passed": True}, {"id": "x3", "passed": False}]
    summary = harness._summarize("test_set", results, pass_bar=0.9)
    assert summary["total"] == 3
    assert summary["passed"] == 2
    assert summary["failed"] == 1
    assert abs(summary["pass_rate"] - (2 / 3)) < 1e-9
    assert summary["meets_bar"] is False
    assert len(summary["failures"]) == 1


def test_harness_summarize_meets_bar_when_rate_equals_bar_exactly():
    harness = _load_harness()
    results = [{"id": f"x{i}", "passed": True} for i in range(9)] + [{"id": "x9", "passed": False}]
    summary = harness._summarize("test_set", results, pass_bar=0.9)
    assert summary["pass_rate"] == 0.9
    assert summary["meets_bar"] is True


@pytest.mark.asyncio
async def test_run_student_golden_set_scores_via_keyword_match(monkeypatch):
    """Mocks the pipeline call itself (NOT the scoring logic) to
    confirm the harness's keyword-match scoring correctly passes a
    response containing an expected keyword and fails one that
    doesn't -- this tests the HARNESS, independent of real model
    quality."""
    harness = _load_harness()
    from src import database
    database.register_member("owner_for_test", "Owner")

    async def fake_handle_message(discord_id, text):
        # Deliberately return a response containing the keyword for
        # ONLY the first question ID pattern, to create a mixed
        # pass/fail result deterministically.
        if "مهمة يومية" in text:
            return "لديك سبع مهام يومية"
        return "رد عام لا يحتوي أي كلمة مفتاحية متوقعة إطلاقًا"

    with patch.object(harness.orchestrator, "handle_message", new=fake_handle_message):
        summary = await harness.run_student_golden_set()

    assert summary["total"] == 100
    # At least the "كم مهمة يومية عندي؟" question (S001) must pass,
    # since its keyword ("سبع"/"7"/"٧") is present in the fake response.
    s001 = next(r for r in summary["results"] if r["id"] == "S001")
    assert s001["passed"] is True


@pytest.mark.asyncio
async def test_run_red_team_set_structural_checks_use_real_permissions(monkeypatch):
    """Confirms the red-team runner's structural checks are wired to
    the REAL permissions.py boundary (not a mocked/fake one) -- runs
    against real retrieve()/dispatcher functions with the LLM call
    itself mocked out, and confirms 0 leaks are reported when the
    real boundary holds."""
    harness = _load_harness()
    from src import database, config
    monkeypatch.setattr(config, "OWNER_DISCORD_ID", "owner_for_redteam_test")
    database.register_member("owner_for_redteam_test", "Owner")

    async def fake_handle_message(discord_id, text):
        return "رد عادي بدون أي تسريب"

    async def fake_embed(text, task_type="RETRIEVAL_QUERY"):
        return None  # forces keyword-fallback retrieval path, no network needed

    with patch.object(harness.orchestrator, "handle_message", new=fake_handle_message), \
         patch("src.nour.knowledge.retriever.embed_text", new=fake_embed):
        summary = await harness.run_red_team_set()

    assert summary["total"] == 50
    assert all(not r["leaked_domain"] for r in summary["results"])
    assert all(not r["leaked_tool_schema"] for r in summary["results"])
    assert all(not r["executed_owner_tool"] for r in summary["results"])
