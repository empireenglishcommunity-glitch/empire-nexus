"""Phase 5 — student personalisation tests (spec R8).

Proves the safety-critical guarantees, each as a focused test:
  * gender-matched casting with ZERO inference (unknown gender => never cast);
  * fair rotation by least-recently-featured, advanced ONLY on an emitted episode;
  * opt-out is honoured;
  * empty roster degrades to a name-free episode (never blocks);
  * the validator rejects an undignified / full-name use of a student name;
  * cameo lines get a gender-matched GUEST voice, distinct from the fixed cast.
"""
import importlib
import os
import tempfile

import pytest


@pytest.fixture()
def db(monkeypatch):
    """A fresh, isolated SQLite DB for each test, wired through config.DB_PATH."""
    os.environ.setdefault("DISCORD_TOKEN", "x")
    os.environ.setdefault("GUILD_ID", "1")
    os.environ.setdefault("TIMEZONE", "UTC")
    import pathlib
    from src import config, database
    d = tempfile.mkdtemp()
    path = pathlib.Path(d) / "t.db"
    # database._connect() reads config.DB_PATH at call time, so patching config is
    # sufficient to isolate every accessor onto this temp DB.
    monkeypatch.setattr(config, "DB_PATH", path)
    database.init_db()
    return database


def _member(db, did, name, level="A2", gender=None):
    db.register_member(did, name, level=level)
    if gender is not None:
        db.update_member(did, gender=gender)


def _confirm_all(db):
    for r in db.get_story_roster():
        db.upsert_story_roster(r["discord_id"], r["story_name"], r["gender"],
                               confirmed=True)


def test_zero_gender_inference(db):
    """A member with unknown/empty gender is NEVER seeded or cast (R8.2/R8.3)."""
    from src import sawt_roster as R
    _member(db, "1", "Amina H", gender="female")
    _member(db, "2", "Sam Doe")                      # no gender
    _member(db, "3", "Karim B", gender="male")
    R.seed_from_members()
    names = {r["story_name"] for r in db.get_story_roster()}
    assert "Sam" not in names, "unknown-gender member must never be seeded"
    assert {"Amina", "Karim"} <= names
    # And even a hand-inserted bad row (empty gender) is refused by the writer.
    assert db.upsert_story_roster("2", "Sam", "", confirmed=True) is False


def test_first_name_only(db):
    """Only the first name is stored, never the full display name (R8.8)."""
    from src import sawt_roster as R
    _member(db, "1", "Amina Hassan Ali", gender="female")
    R.seed_from_members()
    assert db.get_story_roster()[0]["story_name"] == "Amina"


def test_unconfirmed_not_cast(db):
    """Seeded-but-unconfirmed rows are not eligible until the owner confirms."""
    from src import sawt_roster as R
    _member(db, "1", "Amina H", gender="female")
    R.seed_from_members()
    assert R.select_cameos() == []                   # unconfirmed
    _confirm_all(db)
    assert [c["story_name"] for c in R.select_cameos()] == ["Amina"]


def test_gender_matched_selection(db):
    """Selection can be constrained to a single known gender."""
    from src import sawt_roster as R
    _member(db, "1", "Amina H", gender="female")
    _member(db, "2", "Karim B", gender="male")
    R.seed_from_members()
    _confirm_all(db)
    assert [c["story_name"] for c in R.select_cameos(5, gender="female")] == ["Amina"]
    assert [c["story_name"] for c in R.select_cameos(5, gender="male")] == ["Karim"]


def test_fair_rotation_least_recently_featured(db):
    """After featuring some, the next selection leads with the never/least-recently
    featured students (R8.5)."""
    from src import sawt_roster as R
    _member(db, "1", "Amina H", gender="female")
    _member(db, "2", "Karim B", gender="male")
    _member(db, "3", "Leila C", gender="female")
    R.seed_from_members()
    _confirm_all(db)
    first_two = R.select_cameos(2)
    assert len(first_two) == 2
    R.record_featured(first_two)
    # The one NOT yet featured must now sort first.
    nxt = [c["story_name"] for c in R.select_cameos(3)]
    remaining = {"Amina", "Karim", "Leila"} - {c["story_name"] for c in first_two}
    assert nxt[0] in remaining


def test_opt_out_is_honoured(db):
    """An opted-out student is never selected (R8.6)."""
    from src import sawt_roster as R
    _member(db, "1", "Amina H", gender="female")
    R.seed_from_members()
    _confirm_all(db)
    db.set_story_opt_out("1", True)
    assert R.select_cameos() == []
    db.set_story_opt_out("1", False)
    assert [c["story_name"] for c in R.select_cameos()] == ["Amina"]


def test_empty_roster_degrades(db):
    """No roster => no cameos, and nothing raises (R8.4)."""
    from src import sawt_roster as R
    assert R.select_cameos() == []
    assert R.cameo_names([]) == []
    R.record_featured([])                            # no-op, must not raise


def test_rotation_only_advances_on_emit(db):
    """record_featured is the ONLY thing that advances rotation; selecting a cameo
    must NOT (a failed render never consumes a turn, R9.3)."""
    from src import sawt_roster as R
    _member(db, "1", "Amina H", gender="female")
    R.seed_from_members()
    _confirm_all(db)
    _ = R.select_cameos()                            # selection alone
    assert db.get_story_roster()[0]["times_featured"] == 0
    assert db.get_story_roster()[0]["last_featured_at"] is None


def test_cameo_gets_gender_matched_guest_voice():
    """A registered cameo resolves to a GUEST voice matching its gender, and that
    voice is NOT one of the fixed cast's voices."""
    from src import sawt_cast as C
    try:
        C.register_cameos([{"story_name": "Amina", "gender": "female"},
                            {"story_name": "Karim", "gender": "male"}])
        a = C.character_for("Amina")
        k = C.character_for("Karim")
        assert a["gender"] == "female" and k["gender"] == "male"
        lead_voices = {C.CAST[key]["voice_id"] for key in C.CAST}
        assert a["voice_id"] not in lead_voices
        assert k["voice_id"] not in lead_voices
        assert a["voice_id"] != k["voice_id"]
        # An unknown, unregistered speaker still falls back to the narrator.
        assert C.character_for("Zzz")["key"] == C.DEFAULT_CHARACTER
    finally:
        C.clear_cameos()


def test_cameo_with_unknown_gender_is_not_voiced_as_guest():
    """Defence in depth: a cameo whose gender isn't male/female is ignored by the
    voice registry (never guessed) and falls back to the narrator."""
    from src import sawt_cast as C
    try:
        C.register_cameos([{"story_name": "Sam", "gender": ""}])
        assert C.character_for("Sam")["key"] == C.DEFAULT_CHARACTER
    finally:
        C.clear_cameos()


def _episode(script, **over):
    ep = {"title": "T", "script": script, "recap": "r", "facts": [],
          "mood": "mystery", "vote_a": "Go left down the hall",
          "vote_b": "Go right toward the light", "motif_used": False}
    ep.update(over)
    return ep


def test_validator_rejects_undignified_student_use():
    """A student-named guest cast as villain or given demeaning words is rejected
    (R8.7)."""
    from src import sawt_script_validator as V
    base = "Narrator: Welcome to Empire English Chronicles.\n"
    close = "\nNarrator: Vote below. Tomorrow, the story continues the way you choose."
    demeaning = _episode(base + "Maya: Amina, you are stupid and worthless.\n"
                         "Amina: ok." + close)
    probs = V.validate_episode(demeaning, level="A2", episode_number=1,
                               student_names=["Amina"])
    assert any("demean" in p.lower() or "kind" in p.lower() for p in probs)

    villain = _episode(base + "Narrator: Amina was the antagonist all along.\n"
                       "Amina: hello." + close)
    probs = V.validate_episode(villain, level="A2", episode_number=1,
                               student_names=["Amina"])
    # Either the antagonist rule or the demeaning rule may catch it — both mean
    # "this undignified use is rejected".
    assert any("antagonist" in p.lower() or "demean" in p.lower() or "kind" in p.lower()
               for p in probs)


def test_validator_rejects_full_name_use():
    """First-name-only privacy: a surname after the student's name is rejected
    (R8.8)."""
    from src import sawt_script_validator as V
    base = "Narrator: Welcome to Empire English Chronicles.\n"
    close = "\nNarrator: Vote below. Tomorrow, the story continues the way you choose."
    ep = _episode(base + "Narrator: Amina Hassan smiled kindly.\n"
                  "Amina: hello friends." + close)
    probs = V.validate_episode(ep, level="A2", episode_number=1,
                               student_names=["Amina"])
    assert any("first name" in p.lower() for p in probs)


def test_validator_accepts_a_kind_cameo():
    """A warm, first-name-only guest appearance raises NO dignity/privacy problem
    (the episode may still fail unrelated checks like length; we assert only that
    the Phase-5 rules are silent)."""
    from src import sawt_script_validator as V
    base = "Narrator: Welcome to Empire English Chronicles.\n"
    close = "\nNarrator: Vote below. Tomorrow, the story continues the way you choose."
    ep = _episode(base + "Amina: I found the key! Let me help.\n"
                  "Maya: Thank you, Amina — you are brave." + close)
    probs = V.validate_episode(ep, level="A2", episode_number=1,
                               student_names=["Amina"])
    assert not [p for p in probs if "guest" in p.lower() or "first name" in p.lower()
                or "demean" in p.lower() or "antagonist" in p.lower()]
