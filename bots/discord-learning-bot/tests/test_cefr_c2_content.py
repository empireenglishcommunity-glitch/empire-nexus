"""Mi'yar Phase 7 — C2 content validation tests.

Validates that the authored C2 curriculum is complete, well-formed, loads
through the curriculum engine, and reaches C2/mastery scope. C2 is the top of
the CEFR ladder, so there is no "above-level" ceiling to guard against; instead
we assert it genuinely builds beyond C1. Mirrors the A1–C1 content tests.
"""
import json

import pytest

from src import config, curriculum

DATA_DIR = config.BASE_DIR / "data"
CEFR_DIR = config.BASE_DIR / "content" / "cefr"

C2_WEEKS = list(range(1, 21))  # C2 = 20 weeks


# ============================================================
#  FILE PRESENCE + JSON VALIDITY
# ============================================================

def test_all_20_c2_week_files_exist():
    for w in C2_WEEKS:
        assert (DATA_DIR / f"c2_week{w}.json").exists(), f"missing c2_week{w}.json"


@pytest.mark.parametrize("w", C2_WEEKS)
def test_c2_week_file_valid_json_and_shape(w):
    data = json.loads((DATA_DIR / f"c2_week{w}.json").read_text(encoding="utf-8"))
    for field in ("level", "cefr", "week", "theme", "phoneme_focus",
                  "grammar_pattern", "grammar_point", "vocabulary",
                  "speaking_missions", "writing_prompts", "can_do", "listening"):
        assert field in data, f"week {w} missing '{field}'"
    assert data["level"] == "C2"
    assert data["cefr"] == "C2"
    assert data["week"] == w


@pytest.mark.parametrize("w", C2_WEEKS)
def test_c2_vocabulary_well_formed(w):
    data = json.loads((DATA_DIR / f"c2_week{w}.json").read_text(encoding="utf-8"))
    vocab = data["vocabulary"]
    assert len(vocab) >= 25, f"week {w} has too few words ({len(vocab)})"
    for v in vocab:
        for k in ("word", "pronunciation", "arabic", "pos", "example"):
            assert k in v and v[k], f"week {w} vocab item missing '{k}': {v}"


@pytest.mark.parametrize("w", C2_WEEKS)
def test_c2_speaking_missions_seven_days(w):
    data = json.loads((DATA_DIR / f"c2_week{w}.json").read_text(encoding="utf-8"))
    sm = data["speaking_missions"]
    for day in ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday"):
        assert day in sm, f"week {w} missing speaking mission for {day}"
        assert "prompt" in sm[day] and "target_seconds" in sm[day]


@pytest.mark.parametrize("w", C2_WEEKS)
def test_c2_writing_prompts_present(w):
    data = json.loads((DATA_DIR / f"c2_week{w}.json").read_text(encoding="utf-8"))
    assert len(data["writing_prompts"]) >= 5


@pytest.mark.parametrize("w", C2_WEEKS)
def test_c2_can_do_codes_reference_library(w):
    data = json.loads((DATA_DIR / f"c2_week{w}.json").read_text(encoding="utf-8"))
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["C2"]
    all_codes = set()
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in lib[mode]:
            all_codes.add(d["code"])
    for code in data["can_do"]:
        assert code in all_codes, f"week {w} references unknown can-do code {code}"


def test_c2_all_can_do_codes_are_covered():
    """Across the 20 weeks, every C2 descriptor should be practised at least once."""
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["C2"]
    all_codes = set()
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in lib[mode]:
            all_codes.add(d["code"])
    used = set()
    for w in C2_WEEKS:
        data = json.loads((DATA_DIR / f"c2_week{w}.json").read_text(encoding="utf-8"))
        used.update(data["can_do"])
    assert used == all_codes, f"uncovered C2 can-do codes: {sorted(all_codes - used)}"


@pytest.mark.parametrize("w", C2_WEEKS)
def test_c2_grammar_point_matches_syllabus(w):
    data = json.loads((DATA_DIR / f"c2_week{w}.json").read_text(encoding="utf-8"))
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["C2"]
    by_week = {p["week"]: p for p in syl}
    assert data["grammar_point"]["title"] == by_week[w]["title"], \
        f"week {w} grammar_point title does not match syllabus"


# ============================================================
#  CAN-DO LIBRARY + GRAMMAR SYLLABUS
# ============================================================

def test_c2_can_do_library_complete():
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["C2"]
    assert "overview_en" in lib and "overview_ar" in lib
    for mode in ("reception", "production", "interaction", "mediation"):
        assert lib[mode], f"C2 can-do mode '{mode}' is empty"
        for d in lib[mode]:
            assert d["code"].startswith("C2.")
            assert d["en"] and d["ar"]


def test_c2_grammar_syllabus_twenty_weeks():
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["C2"]
    assert len(syl) == 20
    weeks = sorted(p["week"] for p in syl)
    assert weeks == C2_WEEKS
    for p in syl:
        assert p["cefr"] == "C2"
        assert p["title"] and p["en"] and p["ar"]
        assert isinstance(p["examples"], list) and p["examples"]


def test_c2_builds_on_c1():
    """C2 should extend into the hallmark mastery-level structures beyond C1."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["C2"]
    titles = " ".join(p["title"].lower() for p in syl)
    assert "subjunctive" in titles
    assert "cleft mastery" in titles
    assert "grammatical metaphor" in titles
    assert "irony" in titles
    assert "rhetoric" in titles


def test_c2_is_top_of_ladder():
    """C2 is the highest CEFR level: nothing is authored above it."""
    assert config.next_cefr_level("C2") is None
    curriculum.load_all()
    # No level key beyond C2 should ever load (there is no C3/D1).
    stray = [k for k in curriculum._weekly_data
             if k[:2] in ("C3", "D1", "D2")]
    assert stray == []


# ============================================================
#  ENGINE LOADING
# ============================================================

def test_curriculum_loads_c2_weeks():
    curriculum.load_all()
    c2_keys = [k for k in curriculum._weekly_data if k.startswith("C2_")]
    assert len(c2_keys) == 20, f"expected 20 C2 weeks loaded, got {len(c2_keys)}"


def test_curriculum_c2_vocabulary_accessible():
    curriculum.load_all()
    words = curriculum.get_vocabulary_for_week(1, "C2")
    assert words and len(words) >= 25
    assert any(v.get("word") == "be that as it may" for v in words)


def test_c2_max_week_is_twenty():
    assert curriculum.max_week_for_level("C2") == 20


def test_c2_total_vocab_reasonable():
    """C2 total active vocabulary should be a sound mastery core (~500-950)."""
    total = 0
    for w in C2_WEEKS:
        data = json.loads((DATA_DIR / f"c2_week{w}.json").read_text(encoding="utf-8"))
        total += len(data["vocabulary"])
    assert 500 <= total <= 950, f"C2 total vocab {total} outside expected C2 band"


def test_full_cefr_ladder_complete():
    """With C2 authored, the entire A1->C2 ladder loads with expected week counts."""
    curriculum.load_all()
    for level, count in curriculum.CEFR_WEEK_COUNTS.items():
        keys = [k for k in curriculum._weekly_data if k.startswith(f"{level}_")]
        assert len(keys) == count, \
            f"{level}: expected {count} weeks, got {len(keys)}"
