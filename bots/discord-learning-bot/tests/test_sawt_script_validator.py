"""Tests for the script validator (spec Phase 4.5 / 4.7 / 4.8).

Exit criterion for Phase 4: the validator PROVABLY rejects weak or non-compliant
episodes. So each test here builds a script that is good except for ONE defect and
asserts that defect is caught, plus a fully-good episode that passes clean.
"""
import pytest

from src import sawt_script_validator as V
from src import sawt_arc as arc


LEVEL = "A2"


def _arc():
    return {
        "arc_id": 1, "genre": "mystery", "setting": "an old library",
        "premise": "something is out of place", "mood": "mystery",
        "curiosity": "unanswered-question", "leads": ["Maya", "Leo"],
        "episode_in_arc": 2, "planned_episodes": 6,
        "established_facts": ["the library closes at nine"], "previous_genre": None,
    }


def _good_script(words=430):
    filler = " ".join(["The old room was quiet and cold and strange tonight."] * 45)
    return f"""Narrator: Welcome to Empire English Chronicles. Last time, Maya found a brass key.
Narrator: {filler}
Maya: Leo, do you hear that sound? Something is moving behind the shelves.
Leo: I hear it too. We only have a few minutes before the doors lock for the night.
[SFX:creak]
Narrator: A door opened slowly in the dark. Who was there?
Maya: Please, say something. Is anyone there?
[PAUSE 2s]
Narrator: The lights went out. Vote below. Tomorrow, the story continues the way you choose.
"""


def _good_episode(**over):
    ep = {
        "title": "The Key in the Dark",
        "script": _good_script(),
        "recap": "Maya and Leo hear a sound in the library.",
        "facts": ["a door opened by itself"],
        "mood": "mystery",
        "vote_a": "Follow the sound into the dark stacks",
        "vote_b": "Run back to the front door and call for help",
        "motif_used": True,
    }
    ep.update(over)
    return ep


def test_a_good_episode_passes_clean():
    problems = V.validate_episode(_good_episode(), level=LEVEL,
                                  episode_number=2, arc=_arc())
    assert problems == [], f"expected clean pass, got: {problems}"


def test_rejects_illegal_cast():
    ep = _good_episode(script=_good_script() + "\nZorg: I am not in the cast.\n")
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc())
    assert any("not in the cast" in p for p in problems)


def test_rejects_illegal_sfx():
    ep = _good_episode(script=_good_script().replace("[SFX:creak]", "[SFX:heartbeat]"))
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc())
    assert any("don't exist" in p for p in problems)


def test_rejects_parenthetical_stage_directions():
    ep = _good_episode(
        script=_good_script().replace("Maya: Please, say something. Is anyone there?",
                                      "Maya: (whispering) Please, say something."))
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc())
    assert any("parenthetical" in p for p in problems)


def test_rejects_identical_vote_options():
    ep = _good_episode(vote_a="Open the door", vote_b="Open the door")
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc())
    assert any("identical" in p for p in problems)


def test_rejects_missing_vote_prompt_at_close():
    script = _good_script().replace(
        "Vote below. Tomorrow, the story continues the way you choose.",
        "And so the night ended quietly and safely.")
    ep = _good_episode(script=script)
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc())
    assert any("VOTE" in p for p in problems)


def test_rejects_too_short_for_level():
    short = """Narrator: Welcome to Empire English Chronicles. Last time, a key appeared.
Maya: What is that?
Leo: I do not know. We should hurry before it is too late.
Narrator: A shadow moved. What next? Vote below to choose tomorrow's path.
"""
    ep = _good_episode(script=short)
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc())
    assert any("Too short" in p for p in problems)


def test_rejects_missing_recap_when_not_episode_one():
    # remove recap text AND any opening recap cue
    script = _good_script().replace(
        "Welcome to Empire English Chronicles. Last time, Maya found a brass key.",
        "Welcome to Empire English Chronicles.")
    ep = _good_episode(script=script, recap="")
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc())
    assert any("recap" in p.lower() for p in problems)


def test_episode_one_does_not_require_a_recap():
    script = _good_script().replace(
        "Welcome to Empire English Chronicles. Last time, Maya found a brass key.",
        "Welcome to Empire English Chronicles.")
    ep = _good_episode(script=script, recap="")
    problems = V.validate_episode(ep, level=LEVEL, episode_number=1, arc=_arc())
    assert not any("recap" in p.lower() for p in problems)


def test_rejects_missing_curiosity_device():
    # a script with no '?', no time pressure, no reveal, no branch words
    flat = " ".join(["The room was calm and everything stayed exactly the same."] * 60)
    script = (f"Narrator: Welcome to Empire English Chronicles. Last time we met Maya.\n"
              f"Narrator: {flat}\n"
              f"Maya: Everything is fine and nothing is wrong at all.\n"
              f"Leo: Yes. It is a normal calm day with nothing to wonder about.\n"
              f"Narrator: The end. Vote to continue tomorrow.\n")
    ep = _good_episode(script=script)
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc())
    assert any("curiosity" in p.lower() for p in problems)


def test_student_named_character_is_protected():
    script = _good_script() + "\nAhmed: I am so stupid and worthless.\n"
    ep = _good_episode(script=script)
    problems = V.validate_episode(ep, level=LEVEL, episode_number=2, arc=_arc(),
                                  student_names=["Ahmed"])
    assert any("antagonist" in p or "demeaning" in p for p in problems)


def test_validator_never_raises_on_garbage():
    for junk in (None, {}, {"script": 123}, {"script": None, "vote_a": 5}):
        out = V.validate_episode(junk, level=LEVEL, episode_number=1, arc={})
        assert isinstance(out, list)     # returns a list, never raises


def test_validator_soft_passes_when_it_crashes(monkeypatch):
    # Force an internal crash and assert it soft-passes (empty list), never blocks.
    monkeypatch.setattr(V, "_spoken_segments",
                        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = V.validate_episode(_good_episode(), level=LEVEL, episode_number=2,
                             arc=_arc())
    assert out == []
