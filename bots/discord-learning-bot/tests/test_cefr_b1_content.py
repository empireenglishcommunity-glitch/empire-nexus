"""Mi'yar Phase 4 — B1 content validation tests.

Validates that the authored B1 curriculum is complete, well-formed, loads
through the curriculum engine, and stays within B1 scope. Mirrors the A1/A2
content tests.
"""
import json

import pytest

from src import config, curriculum

DATA_DIR = config.BASE_DIR / "data"
CEFR_DIR = config.BASE_DIR / "content" / "cefr"

B1_WEEKS = list(range(1, 15))  # B1 = 14 weeks


# ============================================================
#  FILE PRESENCE + JSON VALIDITY
# ============================================================

def test_all_14_b1_week_files_exist():
    for w in B1_WEEKS:
        assert (DATA_DIR / f"b1_week{w}.json").exists(), f"missing b1_week{w}.json"


@pytest.mark.parametrize("w", B1_WEEKS)
def test_b1_week_file_valid_json_and_shape(w):
    data = json.loads((DATA_DIR / f"b1_week{w}.json").read_text(encoding="utf-8"))
    for field in ("level", "cefr", "week", "theme", "phoneme_focus",
                  "grammar_pattern", "grammar_point", "vocabulary",
                  "speaking_missions", "writing_prompts", "can_do", "listening"):
        assert field in data, f"week {w} missing '{field}'"
    assert data["level"] == "B1"
    assert data["cefr"] == "B1"
    assert data["week"] == w


@pytest.mark.parametrize("w", B1_WEEKS)
def test_b1_vocabulary_well_formed(w):
    data = json.loads((DATA_DIR / f"b1_week{w}.json").read_text(encoding="utf-8"))
    vocab = data["vocabulary"]
    assert len(vocab) >= 25, f"week {w} has too few words ({len(vocab)})"
    for v in vocab:
        for k in ("word", "pronunciation", "arabic", "pos", "example"):
            assert k in v and v[k], f"week {w} vocab item missing '{k}': {v}"


@pytest.mark.parametrize("w", B1_WEEKS)
def test_b1_speaking_missions_seven_days(w):
    data = json.loads((DATA_DIR / f"b1_week{w}.json").read_text(encoding="utf-8"))
    sm = data["speaking_missions"]
    for day in ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday"):
        assert day in sm, f"week {w} missing speaking mission for {day}"
        assert "prompt" in sm[day] and "target_seconds" in sm[day]


@pytest.mark.parametrize("w", B1_WEEKS)
def test_b1_writing_prompts_present(w):
    data = json.loads((DATA_DIR / f"b1_week{w}.json").read_text(encoding="utf-8"))
    assert len(data["writing_prompts"]) >= 5


@pytest.mark.parametrize("w", B1_WEEKS)
def test_b1_can_do_codes_reference_library(w):
    data = json.loads((DATA_DIR / f"b1_week{w}.json").read_text(encoding="utf-8"))
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["B1"]
    all_codes = set()
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in lib[mode]:
            all_codes.add(d["code"])
    for code in data["can_do"]:
        assert code in all_codes, f"week {w} references unknown can-do code {code}"


# ============================================================
#  CAN-DO LIBRARY + GRAMMAR SYLLABUS
# ============================================================

def test_b1_can_do_library_complete():
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["B1"]
    assert "overview_en" in lib and "overview_ar" in lib
    for mode in ("reception", "production", "interaction", "mediation"):
        assert lib[mode], f"B1 can-do mode '{mode}' is empty"
        for d in lib[mode]:
            assert d["code"].startswith("B1.")
            assert d["en"] and d["ar"]


def test_b1_grammar_syllabus_fourteen_weeks():
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["B1"]
    assert len(syl) == 14
    weeks = sorted(p["week"] for p in syl)
    assert weeks == B1_WEEKS
    for p in syl:
        assert p["cefr"] == "B1"
        assert p["title"] and p["en"] and p["ar"]
        assert isinstance(p["examples"], list) and p["examples"]


def test_b1_no_above_level_grammar():
    """B1 grammar must not include B2+ structures (guard against drift).
    Note: present perfect continuous, second conditional, reported statements
    and the (present/past) passive ARE B1, so only the higher variants/tenses
    are banned."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["B1"]
    titles = " ".join(p["title"].lower() for p in syl)
    for banned in ("past perfect", "future perfect", "future continuous",
                   "third conditional", "mixed conditional", "causative",
                   "inversion", "cleft", "reported questions"):
        assert banned not in titles, f"B1 syllabus contains above-level grammar: {banned}"


def test_b1_builds_on_a2():
    """B1 should extend into conditionals + relative clauses + reported speech —
    the hallmark independent-user structures beyond A2."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["B1"]
    titles = " ".join(p["title"].lower() for p in syl)
    assert "second conditional" in titles
    assert "relative clause" in titles
    assert "reported speech" in titles


# ============================================================
#  ENGINE LOADING
# ============================================================

def test_curriculum_loads_b1_weeks():
    curriculum.load_all()
    b1_keys = [k for k in curriculum._weekly_data if k.startswith("B1_")]
    assert len(b1_keys) == 14, f"expected 14 B1 weeks loaded, got {len(b1_keys)}"


def test_curriculum_b1_vocabulary_accessible():
    curriculum.load_all()
    words = curriculum.get_vocabulary_for_week(1, "B1")
    assert words and len(words) >= 25
    assert any(v.get("word") == "recently" for v in words)


def test_b1_max_week_is_fourteen():
    assert curriculum.max_week_for_level("B1") == 14


def test_b1_total_vocab_reasonable():
    """B1 total active vocabulary should be a sound intermediate core (~400-650)."""
    total = 0
    for w in B1_WEEKS:
        data = json.loads((DATA_DIR / f"b1_week{w}.json").read_text(encoding="utf-8"))
        total += len(data["vocabulary"])
    assert 400 <= total <= 650, f"B1 total vocab {total} outside expected B1 band"
