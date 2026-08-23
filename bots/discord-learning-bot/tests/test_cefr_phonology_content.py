"""Mi'yar — CEFR accent (phonology) + grammar pattern content tests.

Background: when the CEFR levels were first authored, only the weekly vocab
files existed. `content/a1..c2/{accent,grammar}/` did not, so:
  * the practice site's Accent Drill page rendered EMPTY for every CEFR day
    (generate.py's normalize_drill() fell back to a placeholder), and
  * every shadowing passage — and therefore every generated audio clip —
    became the same placeholder sentence "I am practicing English.", and
  * the weekly grammar card was silently skipped for CEFR levels.

These tests lock the authored content in place and guard the invariants that
were violated, so the regression cannot return silently.
"""
import json

import pytest

from src import config, curriculum, features

CONTENT = config.BASE_DIR / "content"

# Levels whose accent/grammar content has been authored so far. Add a level
# here as its phonology content ships (that makes the coverage explicit).
AUTHORED = ["A1", "A2"]

_PLACEHOLDER = "I am practicing English."


def _accent_files(level):
    return sorted((CONTENT / level.lower() / "accent").glob("week*.json"))


def _grammar_files(level):
    return sorted((CONTENT / level.lower() / "grammar").glob("week*.json"))


# ============================================================
#  PRESENCE + COVERAGE
# ============================================================

@pytest.mark.parametrize("level", AUTHORED)
def test_accent_content_exists_for_every_week(level):
    expected = curriculum.CEFR_WEEK_COUNTS[level]
    files = _accent_files(level)
    assert len(files) == expected, (
        f"{level}: expected {expected} accent week files, found {len(files)}"
    )
    weeks = sorted(json.loads(f.read_text(encoding="utf-8"))["week"] for f in files)
    assert weeks == list(range(1, expected + 1))


@pytest.mark.parametrize("level", AUTHORED)
def test_grammar_content_exists_for_every_week(level):
    expected = curriculum.CEFR_WEEK_COUNTS[level]
    files = _grammar_files(level)
    assert len(files) == expected, (
        f"{level}: expected {expected} grammar week files, found {len(files)}"
    )
    weeks = sorted(json.loads(f.read_text(encoding="utf-8"))["week"] for f in files)
    assert weeks == list(range(1, expected + 1))


@pytest.mark.parametrize("level", AUTHORED)
def test_engine_loads_accent_and_grammar(level):
    curriculum.load_all()
    assert curriculum.has_accent_content(level), f"{level} accent not loaded"
    assert curriculum.has_grammar_content(level), f"{level} grammar not loaded"
    expected = curriculum.CEFR_WEEK_COUNTS[level]
    assert len(curriculum._accent_data[level]) == expected
    assert len(curriculum._grammar_data[level]) == expected


# ============================================================
#  ACCENT FILE SHAPE (must match what generate.py consumes)
# ============================================================

@pytest.mark.parametrize("level", AUTHORED)
def test_accent_files_well_formed(level):
    for path in _accent_files(level):
        d = json.loads(path.read_text(encoding="utf-8"))
        w = d["week"]
        for key in ("level", "cefr", "week", "focus", "focus_ar",
                    "arabic_challenge", "daily_drills", "supplementary_notes"):
            assert key in d, f"{level} w{w} missing '{key}'"
        assert d["level"] == level
        drills = d["daily_drills"]
        assert len(drills) == 7, f"{level} w{w} has {len(drills)} drills, need 7"
        assert [x["day"] for x in drills] == list(range(1, 8))


@pytest.mark.parametrize("level", AUTHORED)
def test_every_day_supplies_a_shadowing_passage(level):
    """The single most important invariant: every day must yield real
    primary_text for the shadowing page + audio, never the placeholder."""
    for path in _accent_files(level):
        d = json.loads(path.read_text(encoding="utf-8"))
        w = d["week"]
        for drill in d["daily_drills"]:
            day = drill["day"]
            if drill.get("type") == "assessment":
                text = (drill.get("test_yourself") or {}).get("passage", "")
            else:
                text = drill.get("record_this", "")
            assert text, f"{level} w{w} d{day}: no shadowing passage"
            assert text != _PLACEHOLDER, (
                f"{level} w{w} d{day}: still the placeholder passage"
            )
            assert len(text) >= 30, (
                f"{level} w{w} d{day}: passage too short to shadow ({text!r})"
            )


@pytest.mark.parametrize("level", AUTHORED)
def test_practice_days_have_drill_material(level):
    """Days 1-5 must give the Accent Drill page real pairs + words."""
    for path in _accent_files(level):
        d = json.loads(path.read_text(encoding="utf-8"))
        w = d["week"]
        for drill in d["daily_drills"]:
            if drill.get("type") in ("review", "assessment"):
                continue
            day = drill["day"]
            assert drill.get("target_sounds"), f"{level} w{w} d{day} no target_sounds"
            pairs = drill.get("minimal_pairs") or []
            assert len(pairs) >= 4, f"{level} w{w} d{day} needs >=4 minimal pairs"
            for p in pairs:
                assert isinstance(p.get("pair"), list) and len(p["pair"]) == 2, (
                    f"{level} w{w} d{day} malformed pair: {p}"
                )
                assert p.get("meaning"), f"{level} w{w} d{day} pair missing meaning"
            assert drill.get("word_practice"), f"{level} w{w} d{day} no word_practice"
            assert drill.get("sentence_practice"), f"{level} w{w} d{day} no sentences"


@pytest.mark.parametrize("level", AUTHORED)
def test_week_has_review_and_assessment_days(level):
    for path in _accent_files(level):
        d = json.loads(path.read_text(encoding="utf-8"))
        w = d["week"]
        types = {x["day"]: x.get("type") for x in d["daily_drills"]}
        assert types[6] == "review", f"{level} w{w} day6 should be a review day"
        assert types[7] == "assessment", f"{level} w{w} day7 should be assessment"
        day7 = next(x for x in d["daily_drills"] if x["day"] == 7)
        assert day7["test_yourself"].get("passage")
        assert day7.get("scoring_guide"), f"{level} w{w} day7 needs a scoring_guide"


@pytest.mark.parametrize("level", AUTHORED)
def test_accent_focus_matches_week_file_phoneme_focus_theme(level):
    """The accent file's focus must be non-trivial and the loader must expose
    it (this is what the bot's !week and the page header show)."""
    curriculum.load_all()
    for w in range(1, curriculum.CEFR_WEEK_COUNTS[level] + 1):
        focus = curriculum.get_accent_focus(w, level)
        assert focus and len(focus) > 15, f"{level} w{w} focus too thin: {focus!r}"
        assert curriculum.get_accent_focus_ar(w, level), f"{level} w{w} no Arabic focus"


# ============================================================
#  GRAMMAR FILE SHAPE (must match features.format_grammar_card)
# ============================================================

@pytest.mark.parametrize("level", AUTHORED)
def test_grammar_files_well_formed(level):
    for path in _grammar_files(level):
        d = json.loads(path.read_text(encoding="utf-8"))
        w = d["week"]
        for key in ("id", "level", "cefr", "week", "pattern_name",
                    "pattern_name_ar", "formula", "formula_visual",
                    "when_to_use", "when_to_use_ar",
                    "why_arabic_speakers_struggle", "examples",
                    "common_errors", "quick_rule", "quick_rule_ar"):
            assert key in d, f"{level} grammar w{w} missing '{key}'"
        assert d["level"] == level
        assert len(d["examples"]) >= 3
        for ex in d["examples"]:
            for k in ("en", "ar", "structure"):
                assert ex.get(k), f"{level} w{w} example missing {k}: {ex}"
        assert len(d["common_errors"]) >= 2
        for err in d["common_errors"]:
            for k in ("wrong", "correct", "explanation"):
                assert err.get(k), f"{level} w{w} error missing {k}: {err}"


@pytest.mark.parametrize("level", AUTHORED)
def test_grammar_card_renders_without_raw_dicts(level):
    """format_grammar_card used to interpolate example dicts directly,
    printing a Python repr to students. Guard against that returning."""
    curriculum.load_all()
    for w in range(1, curriculum.CEFR_WEEK_COUNTS[level] + 1):
        card = features.format_grammar_card(w, level)
        assert card, f"{level} w{w} produced no grammar card"
        assert "{'en'" not in card and '{"en"' not in card, (
            f"{level} w{w} grammar card contains a raw dict repr"
        )
        # The card must show the English example text itself, not the
        # internal 'structure' scaffolding field.
        assert "'structure'" not in card and '"structure"' not in card


@pytest.mark.parametrize("level", AUTHORED)
def test_grammar_titles_align_with_cefr_syllabus(level):
    """Per-week grammar pattern files should track the level's authored
    grammar syllabus so the two never drift apart."""
    syllabus = json.loads(
        (CONTENT / "cefr" / "grammar_syllabus.json").read_text(encoding="utf-8")
    )[level]
    by_week = {p["week"]: p["title"] for p in syllabus}
    for path in _grammar_files(level):
        d = json.loads(path.read_text(encoding="utf-8"))
        w = d["week"]
        syl_title = by_week[w]
        # Compare on a loose key-token basis: the pattern file title is a
        # teaching label, not required to be byte-identical, but it must not
        # describe a different grammar point.
        first_token = syl_title.split("(")[0].split("+")[0].strip().lower()
        assert first_token[:6] in d["pattern_name"].lower() or \
            d["pattern_name"].lower()[:6] in syl_title.lower(), (
                f"{level} w{w}: pattern '{d['pattern_name']}' looks unrelated to "
                f"syllabus '{syl_title}'"
            )


# ============================================================
#  INTEGRATION: the daily bundle the bot actually sends
# ============================================================

@pytest.mark.parametrize("level", AUTHORED)
def test_daily_content_bundle_has_accent_and_grammar(level):
    curriculum.load_all()
    bundle = curriculum.get_daily_content(1, "Saturday", 0, level)
    drill = bundle.get("accent_drill")
    assert drill, f"{level} daily bundle has no accent_drill"
    assert drill.get("record_this") != _PLACEHOLDER
    assert bundle.get("accent_focus")
    assert bundle.get("grammar_pattern"), f"{level} daily bundle has no grammar_pattern"


def test_legacy_levels_still_load():
    """Authoring CEFR content must not disturb the legacy L0-L3 content."""
    curriculum.load_all()
    for legacy, weeks in (("L0", 8), ("L1", 10), ("L2", 12), ("L3", 8)):
        assert len(curriculum._accent_data.get(legacy, {})) == weeks
