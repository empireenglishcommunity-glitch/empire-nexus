"""Mi'yar Phase 5 — B2 content validation tests.

Validates that the authored B2 curriculum is complete, well-formed, loads
through the curriculum engine, and stays within B2 scope. Mirrors the
A1/A2/B1 content tests.
"""
import json

import pytest

from src import config, curriculum

DATA_DIR = config.BASE_DIR / "data"
CEFR_DIR = config.BASE_DIR / "content" / "cefr"

B2_WEEKS = list(range(1, 17))  # B2 = 16 weeks


# ============================================================
#  FILE PRESENCE + JSON VALIDITY
# ============================================================

def test_all_16_b2_week_files_exist():
    for w in B2_WEEKS:
        assert (DATA_DIR / f"b2_week{w}.json").exists(), f"missing b2_week{w}.json"


@pytest.mark.parametrize("w", B2_WEEKS)
def test_b2_week_file_valid_json_and_shape(w):
    data = json.loads((DATA_DIR / f"b2_week{w}.json").read_text(encoding="utf-8"))
    for field in ("level", "cefr", "week", "theme", "phoneme_focus",
                  "grammar_pattern", "grammar_point", "vocabulary",
                  "speaking_missions", "writing_prompts", "can_do", "listening"):
        assert field in data, f"week {w} missing '{field}'"
    assert data["level"] == "B2"
    assert data["cefr"] == "B2"
    assert data["week"] == w


@pytest.mark.parametrize("w", B2_WEEKS)
def test_b2_vocabulary_well_formed(w):
    data = json.loads((DATA_DIR / f"b2_week{w}.json").read_text(encoding="utf-8"))
    vocab = data["vocabulary"]
    assert len(vocab) >= 25, f"week {w} has too few words ({len(vocab)})"
    for v in vocab:
        for k in ("word", "pronunciation", "arabic", "pos", "example"):
            assert k in v and v[k], f"week {w} vocab item missing '{k}': {v}"


@pytest.mark.parametrize("w", B2_WEEKS)
def test_b2_speaking_missions_seven_days(w):
    data = json.loads((DATA_DIR / f"b2_week{w}.json").read_text(encoding="utf-8"))
    sm = data["speaking_missions"]
    for day in ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday"):
        assert day in sm, f"week {w} missing speaking mission for {day}"
        assert "prompt" in sm[day] and "target_seconds" in sm[day]


@pytest.mark.parametrize("w", B2_WEEKS)
def test_b2_writing_prompts_present(w):
    data = json.loads((DATA_DIR / f"b2_week{w}.json").read_text(encoding="utf-8"))
    assert len(data["writing_prompts"]) >= 5


@pytest.mark.parametrize("w", B2_WEEKS)
def test_b2_can_do_codes_reference_library(w):
    data = json.loads((DATA_DIR / f"b2_week{w}.json").read_text(encoding="utf-8"))
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["B2"]
    all_codes = set()
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in lib[mode]:
            all_codes.add(d["code"])
    for code in data["can_do"]:
        assert code in all_codes, f"week {w} references unknown can-do code {code}"


# ============================================================
#  CAN-DO LIBRARY + GRAMMAR SYLLABUS
# ============================================================

def test_b2_can_do_library_complete():
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["B2"]
    assert "overview_en" in lib and "overview_ar" in lib
    for mode in ("reception", "production", "interaction", "mediation"):
        assert lib[mode], f"B2 can-do mode '{mode}' is empty"
        for d in lib[mode]:
            assert d["code"].startswith("B2.")
            assert d["en"] and d["ar"]


def test_b2_grammar_syllabus_sixteen_weeks():
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["B2"]
    assert len(syl) == 16
    weeks = sorted(p["week"] for p in syl)
    assert weeks == B2_WEEKS
    for p in syl:
        assert p["cefr"] == "B2"
        assert p["title"] and p["en"] and p["ar"]
        assert isinstance(p["examples"], list) and p["examples"]


def test_b2_no_above_level_grammar():
    """B2 grammar must not include C1+ structures (guard against drift).
    Cleft sentences, third/mixed conditionals, past perfect and the passive are
    B2, so only clearly C1+ items are banned."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["B2"]
    titles = " ".join(p["title"].lower() for p in syl)
    for banned in ("inversion", "subjunctive", "ellipsis", "nominalisation",
                   "future in the past"):
        assert banned not in titles, f"B2 syllabus contains above-level grammar: {banned}"


def test_b2_builds_on_b1():
    """B2 should extend into the hallmark upper-intermediate structures beyond B1."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["B2"]
    titles = " ".join(p["title"].lower() for p in syl)
    assert "third conditional" in titles
    assert "past perfect" in titles
    assert "mixed conditional" in titles


# ============================================================
#  ENGINE LOADING
# ============================================================

def test_curriculum_loads_b2_weeks():
    curriculum.load_all()
    b2_keys = [k for k in curriculum._weekly_data if k.startswith("B2_")]
    assert len(b2_keys) == 16, f"expected 16 B2 weeks loaded, got {len(b2_keys)}"


def test_curriculum_b2_vocabulary_accessible():
    curriculum.load_all()
    words = curriculum.get_vocabulary_for_week(1, "B2")
    assert words and len(words) >= 25
    assert any(v.get("word") == "achievement" for v in words)


def test_b2_max_week_is_sixteen():
    assert curriculum.max_week_for_level("B2") == 16


def test_b2_total_vocab_reasonable():
    """B2 total active vocabulary should be a sound upper-intermediate core (~450-750)."""
    total = 0
    for w in B2_WEEKS:
        data = json.loads((DATA_DIR / f"b2_week{w}.json").read_text(encoding="utf-8"))
        total += len(data["vocabulary"])
    assert 450 <= total <= 750, f"B2 total vocab {total} outside expected B2 band"
