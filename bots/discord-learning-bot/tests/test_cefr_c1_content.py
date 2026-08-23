"""Mi'yar Phase 6 — C1 content validation tests.

Validates that the authored C1 curriculum is complete, well-formed, loads
through the curriculum engine, and stays within C1 scope. Mirrors the
A1/A2/B1/B2 content tests.
"""
import json

import pytest

from src import config, curriculum

DATA_DIR = config.BASE_DIR / "data"
CEFR_DIR = config.BASE_DIR / "content" / "cefr"

C1_WEEKS = list(range(1, 19))  # C1 = 18 weeks


# ============================================================
#  FILE PRESENCE + JSON VALIDITY
# ============================================================

def test_all_18_c1_week_files_exist():
    for w in C1_WEEKS:
        assert (DATA_DIR / f"c1_week{w}.json").exists(), f"missing c1_week{w}.json"


@pytest.mark.parametrize("w", C1_WEEKS)
def test_c1_week_file_valid_json_and_shape(w):
    data = json.loads((DATA_DIR / f"c1_week{w}.json").read_text(encoding="utf-8"))
    for field in ("level", "cefr", "week", "theme", "phoneme_focus",
                  "grammar_pattern", "grammar_point", "vocabulary",
                  "speaking_missions", "writing_prompts", "can_do", "listening"):
        assert field in data, f"week {w} missing '{field}'"
    assert data["level"] == "C1"
    assert data["cefr"] == "C1"
    assert data["week"] == w


@pytest.mark.parametrize("w", C1_WEEKS)
def test_c1_vocabulary_well_formed(w):
    data = json.loads((DATA_DIR / f"c1_week{w}.json").read_text(encoding="utf-8"))
    vocab = data["vocabulary"]
    assert len(vocab) >= 25, f"week {w} has too few words ({len(vocab)})"
    for v in vocab:
        for k in ("word", "pronunciation", "arabic", "pos", "example"):
            assert k in v and v[k], f"week {w} vocab item missing '{k}': {v}"


@pytest.mark.parametrize("w", C1_WEEKS)
def test_c1_speaking_missions_seven_days(w):
    data = json.loads((DATA_DIR / f"c1_week{w}.json").read_text(encoding="utf-8"))
    sm = data["speaking_missions"]
    for day in ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday"):
        assert day in sm, f"week {w} missing speaking mission for {day}"
        assert "prompt" in sm[day] and "target_seconds" in sm[day]


@pytest.mark.parametrize("w", C1_WEEKS)
def test_c1_writing_prompts_present(w):
    data = json.loads((DATA_DIR / f"c1_week{w}.json").read_text(encoding="utf-8"))
    assert len(data["writing_prompts"]) >= 5


@pytest.mark.parametrize("w", C1_WEEKS)
def test_c1_can_do_codes_reference_library(w):
    data = json.loads((DATA_DIR / f"c1_week{w}.json").read_text(encoding="utf-8"))
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["C1"]
    all_codes = set()
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in lib[mode]:
            all_codes.add(d["code"])
    for code in data["can_do"]:
        assert code in all_codes, f"week {w} references unknown can-do code {code}"


def test_c1_all_can_do_codes_are_covered():
    """Across the 18 weeks, every C1 descriptor should be practised at least once."""
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["C1"]
    all_codes = set()
    for mode in ("reception", "production", "interaction", "mediation"):
        for d in lib[mode]:
            all_codes.add(d["code"])
    used = set()
    for w in C1_WEEKS:
        data = json.loads((DATA_DIR / f"c1_week{w}.json").read_text(encoding="utf-8"))
        used.update(data["can_do"])
    assert used == all_codes, f"uncovered C1 can-do codes: {sorted(all_codes - used)}"


@pytest.mark.parametrize("w", C1_WEEKS)
def test_c1_grammar_point_matches_syllabus(w):
    data = json.loads((DATA_DIR / f"c1_week{w}.json").read_text(encoding="utf-8"))
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["C1"]
    by_week = {p["week"]: p for p in syl}
    assert data["grammar_point"]["title"] == by_week[w]["title"], \
        f"week {w} grammar_point title does not match syllabus"


# ============================================================
#  CAN-DO LIBRARY + GRAMMAR SYLLABUS
# ============================================================

def test_c1_can_do_library_complete():
    lib = json.loads((CEFR_DIR / "can_do.json").read_text(encoding="utf-8"))["C1"]
    assert "overview_en" in lib and "overview_ar" in lib
    for mode in ("reception", "production", "interaction", "mediation"):
        assert lib[mode], f"C1 can-do mode '{mode}' is empty"
        for d in lib[mode]:
            assert d["code"].startswith("C1.")
            assert d["en"] and d["ar"]


def test_c1_grammar_syllabus_eighteen_weeks():
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["C1"]
    assert len(syl) == 18
    weeks = sorted(p["week"] for p in syl)
    assert weeks == C1_WEEKS
    for p in syl:
        assert p["cefr"] == "C1"
        assert p["title"] and p["en"] and p["ar"]
        assert isinstance(p["examples"], list) and p["examples"]


def test_c1_no_above_level_grammar():
    """C1 grammar must not include clearly C2-only stylistic foci (guard against drift).
    Inversion, nominalisation, ellipsis and hedging are all C1, so only items that
    belong to C2 mastery-level stylistic manipulation are banned."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["C1"]
    titles = " ".join(p["title"].lower() for p in syl)
    for banned in ("subjunctive", "literary", "stylistic manipulation",
                   "marked syntax for effect"):
        assert banned not in titles, f"C1 syllabus contains above-level grammar: {banned}"


def test_c1_builds_on_b2():
    """C1 should extend into the hallmark advanced structures beyond B2."""
    syl = json.loads((CEFR_DIR / "grammar_syllabus.json").read_text(encoding="utf-8"))["C1"]
    titles = " ".join(p["title"].lower() for p in syl)
    assert "inversion" in titles
    assert "participle clauses" in titles
    assert "nominalisation" in titles
    assert "ellipsis" in titles


# ============================================================
#  ENGINE LOADING
# ============================================================

def test_curriculum_loads_c1_weeks():
    curriculum.load_all()
    c1_keys = [k for k in curriculum._weekly_data if k.startswith("C1_")]
    assert len(c1_keys) == 18, f"expected 18 C1 weeks loaded, got {len(c1_keys)}"


def test_curriculum_c1_vocabulary_accessible():
    curriculum.load_all()
    words = curriculum.get_vocabulary_for_week(1, "C1")
    assert words and len(words) >= 25
    assert any(v.get("word") == "seldom" for v in words)


def test_c1_max_week_is_eighteen():
    assert curriculum.max_week_for_level("C1") == 18


def test_c1_total_vocab_reasonable():
    """C1 total active vocabulary should be a sound advanced core (~450-850)."""
    total = 0
    for w in C1_WEEKS:
        data = json.loads((DATA_DIR / f"c1_week{w}.json").read_text(encoding="utf-8"))
        total += len(data["vocabulary"])
    assert 450 <= total <= 850, f"C1 total vocab {total} outside expected C1 band"
