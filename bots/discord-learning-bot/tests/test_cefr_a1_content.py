"""Mi'yar Phase 1 — A1 content validation tests.

Validates that the authored A1 curriculum is complete, well-formed, loads
through the curriculum engine, and stays within A1 scope. Catches content
regressions (a week silently losing vocabulary, a bad JSON field, a grammar
point drifting above A1, etc.).
"""
import json
from pathlib import Path

import pytest

from src import config, curriculum

DATA_DIR = config.BASE_DIR / "data"
CEFR_DIR = config.BASE_DIR / "content" / "cefr"

A1_WEEKS = list(range(1, 11))  # A1 = 10 weeks


# ============================================================
#  FILE PRESENCE + JSON VALIDITY
# ============================================================

def test_all_10_a1_week_files_exist():
    for w in A1_WEEKS:
        assert (DATA_DIR / f"a1_week{w}.json").exists(), f"missing a1_week{w}.json"


@pytest.mark.parametrize("w", A1_WEEKS)
def test_a1_week_file_valid_json_and_shape(w):
    data = json.loads((DATA_DIR / f"a1_week{w}.json").read_text(encoding="utf-8"))
    # Required fields (engine-compatible + CEFR)
    for field in ("level", "cefr", "week", "theme", "phoneme_focus",
                  "grammar_pattern", "grammar_point", "vocabulary",
                  "speaking_missions", "writing_prompts", "can_do", "listening"):
        assert field in data, f"week {w} missing '{field}'"
    assert data["level"] == "A1"
    assert data["cefr"] == "A1"
    assert data["week"] == w


@pytest.mark.parametrize("w", A1_WEEKS)
def test_a1_vocabulary_well_formed(w):
    data = json.loads((DATA_DIR / f"a1_week{w}.json").read_text(encoding="utf-8"))
    vocab = data["vocabulary"]
    assert len(vocab) >= 25, f"week {w} has too few words ({len(vocab)})"
    for v in vocab:
        for k in ("word", "pronunciation", "arabic", "pos", "example"):
            assert k in v and v[k], f"week {w} vocab item missing '{k}': {v}"


@pytest.mark.parametrize("w", A1_WEEKS)
def test_a1_speaking_missions_seven_days(w):
    data = json.loads((DATA_DIR / f"a1_week{w}.json").read_text(encoding="utf-8"))
    sm = data["speaking_missions"]
    for day in ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday"):
        assert day in sm, f"week {w} missing speaking mission for {day}"
        assert "prompt" in sm[day] and "target_seconds" in sm[day]


@pytest.mark.parametrize("w", A1_WEEKS)
def test_a1_writing_prompts_present(w):
    data = json.loads((DATA_DIR / f"a1_week{w}.json").read_text(encoding="utf-8"))
    assert len(data["writing_prompts"]) >= 5


@pytest.mark.parametrize("w", A1_WEEKS)
def test_a1_can_do_codes_reference_library(w):
    """Every can_do code a week claims must exist in the A1 can-do library."""
    data = json.loads((DATA_DIR / f"a1_week{w}.json").read_text(encoding="utf-8"))
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["A1"]
    all_codes = set()
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in lib[mode]:
            all_codes.add(d["code"])
    for code in data["can_do"]:
        assert code in all_codes, f"week {w} references unknown can-do code {code}"


# ============================================================
#  CAN-DO LIBRARY + GRAMMAR SYLLABUS
# ============================================================

def test_a1_can_do_library_complete():
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["A1"]
    assert "overview_en" in lib and "overview_ar" in lib
    for mode in ("reception", "production", "interaction", "mediation"):
        assert lib[mode], f"A1 can-do mode '{mode}' is empty"
        for d in lib[mode]:
            assert d["code"].startswith("A1.")
            assert d["en"] and d["ar"]


def test_a1_grammar_syllabus_ten_weeks():
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["A1"]
    assert len(syl) == 10
    weeks = sorted(p["week"] for p in syl)
    assert weeks == A1_WEEKS
    for p in syl:
        assert p["cefr"] == "A1"
        assert p["title"] and p["en"] and p["ar"]
        assert isinstance(p["examples"], list) and p["examples"]


def test_a1_no_above_level_grammar():
    """A1 grammar must not include A2+ structures (guard against drift)."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["A1"]
    titles = " ".join(p["title"].lower() for p in syl)
    # These belong to A2+ — they must NOT appear in the A1 syllabus titles.
    for banned in ("present perfect", "past simple of regular", "comparative",
                   "superlative", "present continuous", "conditional",
                   "passive", "reported speech"):
        assert banned not in titles, f"A1 syllabus contains above-level grammar: {banned}"


# ============================================================
#  ENGINE LOADING
# ============================================================

def test_curriculum_loads_a1_weeks():
    curriculum.load_all()
    a1_keys = [k for k in curriculum._weekly_data if k.startswith("A1_")]
    assert len(a1_keys) == 10, f"expected 10 A1 weeks loaded, got {len(a1_keys)}"


def test_curriculum_a1_vocabulary_accessible():
    curriculum.load_all()
    # The engine reads vocabulary via get_vocabulary_for_week(week, level)
    words = curriculum.get_vocabulary_for_week(1, "A1")
    assert words and len(words) >= 25
    assert any(v.get("word") == "hello" for v in words)


def test_a1_max_week_is_ten():
    assert curriculum.max_week_for_level("A1") == 10


def test_a1_total_vocab_reasonable():
    """A1 total active vocabulary should be a sound beginner core (~250-450)."""
    total = 0
    for w in A1_WEEKS:
        data = json.loads((DATA_DIR / f"a1_week{w}.json").read_text(encoding="utf-8"))
        total += len(data["vocabulary"])
    assert 250 <= total <= 500, f"A1 total vocab {total} outside expected A1 band"
