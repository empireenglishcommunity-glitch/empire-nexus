"""Phase 6 — CEFR alignment tests (spec R7).

Proves that the episode follows the CURRICULUM, from live data:
  * target level is the mode of active members' levels (never hardcoded);
  * a representative curriculum week is chosen and its words are surfaced;
  * the words are woven into the generation prompt (not dumped as a list);
  * the duration gate window follows the level's CEFR profile;
  * the Arabic hook is reserved but disabled;
  * everything degrades gracefully when there's no DB/curriculum.
"""
import os
import pathlib
import tempfile

import pytest


@pytest.fixture()
def db(monkeypatch):
    os.environ.setdefault("DISCORD_TOKEN", "x")
    os.environ.setdefault("GUILD_ID", "1")
    os.environ.setdefault("TIMEZONE", "UTC")
    from src import config, database
    d = tempfile.mkdtemp()
    monkeypatch.setattr(config, "DB_PATH", pathlib.Path(d) / "t.db")
    database.init_db()
    return database


def test_target_level_follows_live_data(db):
    """Level is the MODE of active members' levels, not a constant (R7.2)."""
    from src import sawt_syllabus as S
    for i in range(6):
        db.register_member(str(i), f"S{i}", level="A1")
    for i in range(6, 8):
        db.register_member(str(i), f"S{i}", level="B1")
    assert S.resolve_target_level() == "A1"

    # Shift the body up to B1 and the target follows.
    for i in range(6):
        db.set_level(str(i), "B1")
    assert S.resolve_target_level() == "B1"


def test_target_level_tie_breaks_low(db):
    """A tie resolves to the LOWER band (serve the most learners gently)."""
    from src import sawt_syllabus as S
    db.register_member("1", "A", level="A2")
    db.register_member("2", "B", level="B1")
    assert S.resolve_target_level() == "A2"


def test_target_level_fallback_without_db(monkeypatch):
    """No readable membership => the story default level, never a crash (R7.2)."""
    from src import sawt_syllabus as S, sawt_story
    monkeypatch.setattr(S, "resolve_target_level", S.resolve_target_level)
    # Point at an empty temp DB.
    from src import config, database
    d = tempfile.mkdtemp()
    monkeypatch.setattr(config, "DB_PATH", pathlib.Path(d) / "empty.db")
    database.init_db()
    assert S.resolve_target_level() == sawt_story.STORY_LEVEL


def test_current_week_clamped_to_authored_weeks(db):
    """The chosen week never exceeds the level's authored week count (R7.3)."""
    from src import sawt_syllabus as S, curriculum, config
    db.register_member("1", "A", level="A1")
    wk = S.resolve_current_week("A1")
    maxw = curriculum.max_week_for_level(config.cefr_key("A1"))
    assert 1 <= wk <= max(1, maxw)


def test_vocabulary_words_are_real(db):
    """The current week's words come from the curriculum (R7.3)."""
    from src import sawt_syllabus as S
    words = S.vocabulary_for("A1", 1)
    # A1 week 1 authored content exists in the repo (data/a1_week1.json).
    assert isinstance(words, list)
    assert all(isinstance(w, str) and w for w in words)
    assert len(words) <= S.MAX_VOCAB_WORDS


def test_vocabulary_woven_into_prompt():
    """Given words, the prompt asks to weave them in — NOT as a list/quiz (R7.3)."""
    from src import sawt_story
    p = sawt_story.build_story_prompt(
        "", "", 1, level="A1",
        arc={"genre": "mystery", "setting": "a library", "premise": "x",
             "mood": "mystery", "curiosity": "unanswered-question",
             "leads": ["Maya", "Leo"], "established_facts": []},
        is_arc_opener=True, vocabulary=["hello", "goodbye", "please"])
    assert "CURRICULUM TIE-IN" in p
    assert "hello" in p and "goodbye" in p
    assert "NATURALLY" in p or "naturally" in p
    assert "never as a list" in p


def test_no_vocabulary_no_block():
    """No words => no curriculum block at all (graceful)."""
    from src import sawt_story
    p = sawt_story.build_story_prompt(
        "", "", 1, level="A1",
        arc={"genre": "mystery", "setting": "a library", "premise": "x",
             "mood": "mystery", "curiosity": "unanswered-question",
             "leads": ["Maya", "Leo"], "established_facts": []},
        is_arc_opener=True, vocabulary=[])
    assert "CURRICULUM TIE-IN" not in p


def test_duration_gate_follows_the_level_profile():
    """The gate's duration window is read from the level's CEFR profile (R7.1/6.4):
    A1's window differs from B1's, matching config.PODCAST_LEVEL_PROFILES."""
    from src import audio_standards as STD, config
    for lvl in ("A1", "A2", "B1", "B2"):
        prof = config.podcast_level_profile(lvl)
        assert STD.duration_window(lvl) == (float(prof["duration_min"]),
                                            float(prof["duration_max"]))
    # And the windows actually differ across levels (not a constant).
    assert STD.duration_window("A1") != STD.duration_window("B1")


def test_arabic_hook_reserved_but_disabled():
    """arabic_directive returns nothing while scaffolding is off (R7.4)."""
    from src import sawt_syllabus as S
    assert S.ARABIC_SCAFFOLDING_ENABLED is False
    assert S.arabic_directive("A1") == ""


def test_arabic_hook_activates_when_enabled(monkeypatch):
    """When the reserved switch is flipped, the directive uses the level's
    arabic_ratio — proving the hook is wired for later (R7.4)."""
    from src import sawt_syllabus as S
    monkeypatch.setattr(S, "ARABIC_SCAFFOLDING_ENABLED", True)
    d = S.arabic_directive("A1")            # A1 arabic_ratio = 0.40
    assert "ARABIC SUPPORT" in d and "%" in d


def test_plan_for_today_is_always_usable(db):
    """plan_for_today never raises and always returns a level."""
    from src import sawt_syllabus as S
    db.register_member("1", "A", level="A1")
    plan = S.plan_for_today()
    assert plan["level"] in ("A1", "A2", "B1", "B2", "C1", "C2")
    assert isinstance(plan["vocabulary"], list)
