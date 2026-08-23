"""Mi'yar Phase 3 — A2 content validation tests.

Validates that the authored A2 curriculum is complete, well-formed, loads
through the curriculum engine, and stays within A2 scope. Catches content
regressions (a week silently losing vocabulary, a bad JSON field, a grammar
point drifting above A2, etc.). Mirrors tests/test_cefr_a1_content.py.
"""
import json
from pathlib import Path

import pytest

from src import config, curriculum

DATA_DIR = config.BASE_DIR / "data"
CEFR_DIR = config.BASE_DIR / "content" / "cefr"

A2_WEEKS = list(range(1, 13))  # A2 = 12 weeks


# ============================================================
#  FILE PRESENCE + JSON VALIDITY
# ============================================================

def test_all_12_a2_week_files_exist():
    for w in A2_WEEKS:
        assert (DATA_DIR / f"a2_week{w}.json").exists(), f"missing a2_week{w}.json"


@pytest.mark.parametrize("w", A2_WEEKS)
def test_a2_week_file_valid_json_and_shape(w):
    data = json.loads((DATA_DIR / f"a2_week{w}.json").read_text(encoding="utf-8"))
    for field in ("level", "cefr", "week", "theme", "phoneme_focus",
                  "grammar_pattern", "grammar_point", "vocabulary",
                  "speaking_missions", "writing_prompts", "can_do", "listening"):
        assert field in data, f"week {w} missing '{field}'"
    assert data["level"] == "A2"
    assert data["cefr"] == "A2"
    assert data["week"] == w


@pytest.mark.parametrize("w", A2_WEEKS)
def test_a2_vocabulary_well_formed(w):
    data = json.loads((DATA_DIR / f"a2_week{w}.json").read_text(encoding="utf-8"))
    vocab = data["vocabulary"]
    assert len(vocab) >= 25, f"week {w} has too few words ({len(vocab)})"
    for v in vocab:
        for k in ("word", "pronunciation", "arabic", "pos", "example"):
            assert k in v and v[k], f"week {w} vocab item missing '{k}': {v}"


@pytest.mark.parametrize("w", A2_WEEKS)
def test_a2_speaking_missions_seven_days(w):
    data = json.loads((DATA_DIR / f"a2_week{w}.json").read_text(encoding="utf-8"))
    sm = data["speaking_missions"]
    for day in ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday"):
        assert day in sm, f"week {w} missing speaking mission for {day}"
        assert "prompt" in sm[day] and "target_seconds" in sm[day]


@pytest.mark.parametrize("w", A2_WEEKS)
def test_a2_writing_prompts_present(w):
    data = json.loads((DATA_DIR / f"a2_week{w}.json").read_text(encoding="utf-8"))
    assert len(data["writing_prompts"]) >= 5


@pytest.mark.parametrize("w", A2_WEEKS)
def test_a2_can_do_codes_reference_library(w):
    """Every can_do code a week claims must exist in the A2 can-do library."""
    data = json.loads((DATA_DIR / f"a2_week{w}.json").read_text(encoding="utf-8"))
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["A2"]
    all_codes = set()
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in lib[mode]:
            all_codes.add(d["code"])
    for code in data["can_do"]:
        assert code in all_codes, f"week {w} references unknown can-do code {code}"


# ============================================================
#  CAN-DO LIBRARY + GRAMMAR SYLLABUS
# ============================================================

def test_a2_can_do_library_complete():
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["A2"]
    assert "overview_en" in lib and "overview_ar" in lib
    for mode in ("reception", "production", "interaction", "mediation"):
        assert lib[mode], f"A2 can-do mode '{mode}' is empty"
        for d in lib[mode]:
            assert d["code"].startswith("A2.")
            assert d["en"] and d["ar"]


def test_a2_grammar_syllabus_twelve_weeks():
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["A2"]
    assert len(syl) == 12
    weeks = sorted(p["week"] for p in syl)
    assert weeks == A2_WEEKS
    for p in syl:
        assert p["cefr"] == "A2"
        assert p["title"] and p["en"] and p["ar"]
        assert isinstance(p["examples"], list) and p["examples"]


def test_a2_no_above_level_grammar():
    """A2 grammar must not include B1+ structures (guard against drift).
    Note: 'present perfect' (for experience) IS A2, so only the B1+
    continuations/variants are banned."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["A2"]
    titles = " ".join(p["title"].lower() for p in syl)
    for banned in ("present perfect continuous", "past continuous",
                   "past perfect", "conditional", "passive",
                   "reported speech", "relative clause", "used to"):
        assert banned not in titles, f"A2 syllabus contains above-level grammar: {banned}"


def test_a2_builds_on_a1_past_tense():
    """A2 should introduce the past simple (the natural step up from A1's
    was/were), proving continuity with the A1 syllabus."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["A2"]
    titles = " ".join(p["title"].lower() for p in syl)
    assert "past simple" in titles


# ============================================================
#  ENGINE LOADING
# ============================================================

def test_curriculum_loads_a2_weeks():
    curriculum.load_all()
    a2_keys = [k for k in curriculum._weekly_data if k.startswith("A2_")]
    assert len(a2_keys) == 12, f"expected 12 A2 weeks loaded, got {len(a2_keys)}"


def test_curriculum_a2_vocabulary_accessible():
    curriculum.load_all()
    words = curriculum.get_vocabulary_for_week(1, "A2")
    assert words and len(words) >= 25
    assert any(v.get("word") == "yesterday" for v in words)


def test_a2_max_week_is_twelve():
    assert curriculum.max_week_for_level("A2") == 12


def test_a2_total_vocab_reasonable():
    """A2 total active vocabulary should be a sound elementary core (~300-550)."""
    total = 0
    for w in A2_WEEKS:
        data = json.loads((DATA_DIR / f"a2_week{w}.json").read_text(encoding="utf-8"))
        total += len(data["vocabulary"])
    assert 300 <= total <= 550, f"A2 total vocab {total} outside expected A2 band"
