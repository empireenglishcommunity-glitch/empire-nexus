"""Phase 11D — EXTENDED LISTENING (the `broadcast` exercise).

After reading and mediation landed, five CEFR descriptors were still taught by
no week, and they were the only ones authored TEXT could never reach:

    A2.R.2  main point of short, clear messages and ANNOUNCEMENTS
    B1.R.1  main points of clear standard SPEECH on familiar matters
    B1.R.2  main points of many RADIO or TV programmes on current affairs
    B2.R.1  extended SPEECH and LECTURES, complex lines of argument
    B2.R.2  most TV NEWS and current-affairs programmes, and FILMS

The existing `listening` exercise is five typed words a week. Its unit is
smaller than the unit these descriptors are about, so it can never evidence
them however many weeks a student does. `broadcast` is about a minute of
connected speech with gist-first comprehension.

These tests pin the two things that make the claim honest rather than
decorative:

  1. LENGTH  — a script too short for its level cannot close an "extended
     speech" descriptor (MIN_BROADCAST_WORDS_BY_LEVEL, enforced in code).
  2. CHANNEL — a broadcast script's descriptors are provable ONLY by the
     broadcast exercise, and a reading passage can never claim them.
"""

import json
import pathlib

import pytest

from src import assessment, coverage_ledger, curriculum, database

CONTENT = pathlib.Path(__file__).resolve().parent.parent / "content"

# Kokoro voices the render pipeline actually offers (scripts/generate_audio.py
# in empire-dojo). A typo here means a silent fallback to the default voice, so
# a two-person scene would quietly become one person talking to themselves.
KOKORO_VOICES = {
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael",
    "bf_emma", "bf_isabella", "bm_george", "bm_lewis",
}


def _authored_levels():
    return curriculum.broadcast_levels()


def _all_scripts():
    for level in _authored_levels():
        for week, bc in sorted((curriculum._broadcast_data.get(level) or {}).items()):
            yield level, week, bc


# ============================================================
#  WIRING — tracked, but never able to un-green a day
# ============================================================

def test_broadcast_is_tracked_but_never_gates_a_day():
    """One script is authored per WEEK and the rollout is level by level, so
    requiring it daily would retroactively break every existing green day and
    every streak -- the same reason grammar/reading/mediation/review are
    weekly."""
    assert "broadcast" in database.WEEKLY_EXERCISES
    assert "broadcast" in database.TRACKED_EXERCISES
    assert "broadcast" not in database.PRACTICE_EXERCISES
    assert "broadcast" not in database.CALENDAR_EXERCISES


def test_broadcast_is_a_separate_exercise_from_listening():
    """They are both spoken reception, but they are not interchangeable: the
    dictation proves word-level decoding, the broadcast proves gist of
    connected speech. Collapsing them would let five typed words claim "can
    follow a complex line of argument"."""
    assert "broadcast" != "listening"
    assert set(curriculum.SPOKEN_RECEPTION) == {"listening", "broadcast"}
    assert curriculum.EVIDENCE_MODES_BY_EXERCISE["broadcast"] == ("reception",)


# ============================================================
#  THE LENGTH BAR — what makes "extended" true
# ============================================================

def test_every_level_has_a_minimum_word_bar():
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        assert curriculum.MIN_BROADCAST_WORDS_BY_LEVEL[level] > 0
    # The bar must RISE with level: B2.R.1 is about extended speech and
    # complex argument, A2.R.2 about short clear messages.
    bars = [curriculum.MIN_BROADCAST_WORDS_BY_LEVEL[l]
            for l in ("A1", "A2", "B1", "B2", "C1", "C2")]
    assert bars == sorted(bars), bars
    assert bars[0] < bars[-1]


@pytest.mark.parametrize("level", ["A1", "A2", "B1", "B2", "C1", "C2"])
def test_authored_scripts_clear_their_level_bar(load_curriculum, level):
    if level not in curriculum.broadcast_levels():
        pytest.skip(f"{level} extended listening not authored yet")
    bar = curriculum.MIN_BROADCAST_WORDS_BY_LEVEL[level]
    for week, bc in sorted((curriculum._broadcast_data.get(level) or {}).items()):
        wc = curriculum.broadcast_word_count(bc)
        assert wc >= bar, f"{level} w{week}: {wc} words, bar is {bar}"


def test_a_short_script_cannot_close_a_descriptor(load_curriculum):
    """The bar is enforced in code, not left to the author's judgement."""
    stub = {
        "can_do": ["B2.R.1"],
        "segments": [{"text": "Good morning. That is all.", "voice": "af_heart"}],
        "gist_question": {"q": "What?", "options": ["a", "b", "c"], "answer": 0},
        "questions": [{"q": "q1", "options": ["a", "b"], "answer": 0},
                      {"q": "q2", "options": ["a", "b"], "answer": 0}],
    }
    assert curriculum.broadcast_is_deliverable(stub), "renderable"
    assert not curriculum.broadcast_meets_descriptor_bar(stub, "B2"), (
        "a 5-word clip must not be allowed to claim 'extended speech'")


def test_a_script_without_enough_questions_cannot_close_a_descriptor():
    """One 3-option gist question alone is a 33% coin flip, which is not
    evidence that anything was understood."""
    long_text = " ".join(["word"] * 400)
    stub = {
        "segments": [{"text": long_text, "voice": "af_heart"}],
        "gist_question": {"q": "What?", "options": ["a", "b", "c"], "answer": 0},
        "questions": [{"q": "only one", "options": ["a", "b"], "answer": 0}],
    }
    assert not curriculum.broadcast_meets_descriptor_bar(stub, "A2")
    stub["questions"].append({"q": "two", "options": ["a", "b"], "answer": 1})
    assert curriculum.broadcast_meets_descriptor_bar(stub, "A2")


def test_a_silent_or_gistless_script_is_not_deliverable():
    assert not curriculum.broadcast_is_deliverable(None)
    assert not curriculum.broadcast_is_deliverable({"segments": [], "gist_question": {}})
    # audio but no main-point question -> the one thing the descriptors are
    # about is missing, so it must not count as taught
    assert not curriculum.broadcast_is_deliverable(
        {"segments": [{"text": "hello there"}], "gist_question": {}})
    # a gist question but silent segments -> plays nothing
    assert not curriculum.broadcast_is_deliverable(
        {"segments": [{"text": "   "}],
         "gist_question": {"q": "x", "options": ["a", "b"]}})


# ============================================================
#  CHANNEL ATTRIBUTION — the honesty of the evidence
# ============================================================

def test_broadcast_descriptors_are_provable_only_by_broadcast(load_curriculum):
    for level, week, bc in _all_scripts():
        if not curriculum.broadcast_meets_descriptor_bar(bc, level):
            continue
        emap = curriculum.descriptor_evidence_map(week, level)
        for code in bc.get("can_do") or []:
            if code not in curriculum.can_do_descriptor_map(level):
                continue
            assert emap.get(code) == ("broadcast",), (
                f"{level} w{week} {code} evidenced by {emap.get(code)} -- a "
                f"broadcast descriptor must not be claimable by another exercise")


def test_a_reading_passage_can_never_claim_a_spoken_descriptor(load_curriculum):
    """The whole point of the channel split. If reading could evidence
    A2.R.2 there would have been no gap to close in the first place."""
    for level in curriculum.reading_levels():
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            passage = curriculum.get_reading_for_week(week, level)
            for code in (passage or {}).get("can_do") or []:
                d = curriculum.can_do_descriptor_map(level).get(code) or {}
                en = (d.get("en") or "").lower()
                assert not any(k in en for k in ("announcement", "lecture", "radio", "film")), (
                    f"{level} w{week}: reading passage claims spoken descriptor {code}")


def test_broadcast_completion_evidences_the_descriptor(load_curriculum, tmp_path):
    """End to end: a student who completes the broadcast exercise must show up
    as having EVIDENCE for the descriptor the script targets."""
    levels = curriculum.broadcast_levels()
    if not levels:
        pytest.skip("no extended listening authored yet")
    level = levels[0]
    week, bc = next(iter(sorted((curriculum._broadcast_data[level]).items())))
    codes = [c for c in (bc.get("can_do") or [])
             if c in curriculum.can_do_descriptor_map(level)]
    assert codes, f"{level} w{week} targets no known descriptor"

    database.register_member("bcast1", "Broadcast Student")
    conn = database._connect()
    conn.execute("UPDATE members SET level=?, joined_at=?, level_started_at=? "
                 "WHERE discord_id=?", (level, "2026-01-01", "2026-01-01", "bcast1"))
    conn.commit()
    conn.close()

    before = {d["code"]: d["evidenced"]
              for d in assessment.descriptor_portfolio("bcast1", level)["descriptors"]}
    assert before.get(codes[0]) is False, "should start unevidenced"

    database.record_practice_mastery("bcast1", level, week, 1, "broadcast")

    after = {d["code"]: d for d in
             assessment.descriptor_portfolio("bcast1", level)["descriptors"]}
    assert after[codes[0]]["evidenced"] is True
    assert after[codes[0]]["evidence"][0]["exercise"] == "broadcast"


def test_listening_dictation_cannot_evidence_a_broadcast_descriptor(load_curriculum):
    """A student who only ever did the five-word dictation must NOT come out
    with the extended-listening descriptor evidenced."""
    levels = curriculum.broadcast_levels()
    if not levels:
        pytest.skip("no extended listening authored yet")
    level = levels[0]
    week, bc = next(iter(sorted((curriculum._broadcast_data[level]).items())))
    codes = [c for c in (bc.get("can_do") or [])
             if c in curriculum.can_do_descriptor_map(level)]

    database.register_member("bcast2", "Dictation Only")
    conn = database._connect()
    conn.execute("UPDATE members SET level=?, joined_at=?, level_started_at=? "
                 "WHERE discord_id=?", (level, "2026-01-01", "2026-01-01", "bcast2"))
    conn.commit()
    conn.close()
    for day in range(1, 8):
        database.record_practice_mastery("bcast2", level, week, day, "listening")

    pf = {d["code"]: d for d in
          assessment.descriptor_portfolio("bcast2", level)["descriptors"]}
    # Only codes the broadcast script OWNS (i.e. not also targeted by the week
    # file, where listening is a legitimate route) are checked.
    emap = curriculum.descriptor_evidence_map(week, level)
    for code in codes:
        if emap.get(code) == ("broadcast",):
            assert pf[code]["evidenced"] is False, (
                f"{code} was evidenced by dictation alone")


# ============================================================
#  CONTENT INTEGRITY — every authored file must be usable
# ============================================================

def test_every_authored_script_is_deliverable(load_curriculum):
    for level, week, bc in _all_scripts():
        assert curriculum.broadcast_is_deliverable(bc), f"{level} w{week}"
        assert curriculum.broadcast_meets_descriptor_bar(bc, level), f"{level} w{week}"


def test_every_script_week_is_in_range(load_curriculum):
    for level in _authored_levels():
        max_wk = curriculum.max_week_for_level(level)
        for week in (curriculum._broadcast_data.get(level) or {}):
            assert 1 <= week <= max_wk, f"{level} w{week} outside 1..{max_wk}"


def test_every_can_do_code_exists_in_the_level_library(load_curriculum):
    for level, week, bc in _all_scripts():
        library = curriculum.can_do_descriptor_map(level)
        assert bc.get("can_do"), f"{level} w{week} targets no descriptor"
        for code in bc["can_do"]:
            assert code in library, f"{level} w{week}: unknown descriptor {code}"
            assert code.startswith(level), f"{level} w{week}: foreign code {code}"


def test_no_script_claims_a_written_reception_descriptor(load_curriculum):
    """A2.R.3 is about adverts, menus, timetables and letters -- WRITTEN
    everyday material. A spoken clip cannot evidence it, so no script may
    name it."""
    for level, week, bc in _all_scripts():
        library = curriculum.can_do_descriptor_map(level)
        for code in bc.get("can_do") or []:
            en = (library.get(code) or {}).get("en", "").lower()
            for word in ("menu", "timetable", "advertisement"):
                assert word not in en, (
                    f"{level} w{week}: {code} is about written material ({word})")


def test_every_question_has_a_valid_answer_index(load_curriculum):
    for level, week, bc in _all_scripts():
        qs = [bc["gist_question"]] + list(bc.get("questions") or [])
        for q in qs:
            opts = q.get("options") or []
            assert len(opts) >= 3, f"{level} w{week}: {q.get('q')} has {len(opts)} options"
            assert len(set(opts)) == len(opts), f"{level} w{week}: duplicate options"
            assert isinstance(q.get("answer"), int), f"{level} w{week}: {q.get('q')}"
            assert 0 <= q["answer"] < len(opts), f"{level} w{week}: {q.get('q')}"


def test_answers_are_not_all_the_same_index(load_curriculum):
    """If every correct answer were option A a student could score full marks
    without listening, which would make the evidence worthless."""
    for level in _authored_levels():
        answers = []
        for week, bc in sorted((curriculum._broadcast_data.get(level) or {}).items()):
            answers.append(bc["gist_question"]["answer"])
            answers.extend(q["answer"] for q in bc.get("questions") or [])
        assert len(set(answers)) > 1, f"{level}: every answer is index {answers[0]}"


def test_every_segment_has_text_and_a_real_voice(load_curriculum):
    for level, week, bc in _all_scripts():
        segs = bc.get("segments") or []
        assert segs, f"{level} w{week} has no segments"
        for i, s in enumerate(segs):
            assert (s.get("text") or "").strip(), f"{level} w{week} segment {i} is silent"
            assert s.get("voice") in KOKORO_VOICES, (
                f"{level} w{week} segment {i}: unknown voice {s.get('voice')!r}")
            assert s.get("speaker"), f"{level} w{week} segment {i} has no speaker label"


def test_declared_word_count_matches_the_segments(load_curriculum):
    for level, week, bc in _all_scripts():
        assert bc.get("word_count") == curriculum.broadcast_word_count(bc), (
            f"{level} w{week}: declared {bc.get('word_count')}, "
            f"actual {curriculum.broadcast_word_count(bc)}")


def test_every_script_sets_the_task_before_listening(load_curriculum):
    """The student must know what to listen FOR before the audio starts --
    that is the difference between a comprehension exercise and a quiz."""
    for level, week, bc in _all_scripts():
        bl = bc.get("before_listening") or {}
        assert bl.get("en"), f"{level} w{week} has no English pre-listening task"
        assert bl.get("ar"), f"{level} w{week} has no Arabic pre-listening task"


def test_gist_question_is_about_the_whole_clip(load_curriculum):
    """A gist question that quotes a single number is a detail question in
    disguise, and the descriptors are about the MAIN POINT."""
    for level, week, bc in _all_scripts():
        q = bc["gist_question"]["q"].lower()
        assert not q.startswith("what time"), f"{level} w{week}: {q}"
        assert "how many" not in q, f"{level} w{week}: {q}"


def test_content_files_are_valid_json_on_disk():
    """The loader swallows a bad file and logs -- which would silently drop a
    week -- so the files are parsed here directly."""
    for level_dir in sorted(CONTENT.glob("*/broadcast")):
        files = sorted(level_dir.glob("week*.json"))
        assert files, f"{level_dir} exists but has no week files"
        for path in files:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            assert data.get("segments"), path.name
            assert data.get("id"), path.name


def test_no_two_files_claim_the_same_week():
    for level_dir in sorted(CONTENT.glob("*/broadcast")):
        weeks = [curriculum._parse_week_number(p.name)
                 for p in sorted(level_dir.glob("week*.json"))]
        assert len(weeks) == len(set(weeks)), f"{level_dir}: duplicate weeks {weeks}"
        assert None not in weeks, f"{level_dir}: unparseable filename"


# ============================================================
#  LEDGER + CONTRACT
# ============================================================

def test_ledger_reports_broadcast_atoms_with_no_orphans(load_curriculum):
    rep = coverage_ledger.report()
    kinds = [k for k in rep["totals"] if k.startswith("broadcast_")]
    assert set(kinds) == {"broadcast_script", "broadcast_segments",
                          "broadcast_gist_question", "broadcast_questions",
                          "broadcast_glossary"}, kinds
    for k in kinds:
        t = rep["totals"][k]
        assert t["authored"] == t["delivered"], f"{k}: {t}"


def test_unauthored_levels_contribute_no_broadcast_atoms(load_curriculum):
    """A level awaiting content must keep the gate honestly green: nothing
    authored means nothing orphaned."""
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        if level in curriculum.broadcast_levels():
            continue
        rows = [r for r in coverage_ledger._atom_rows(level)
                if r["kind"].startswith("broadcast_")]
        assert rows, f"{level} should still report broadcast rows"
        assert all(r["authored"] == 0 for r in rows), level
        assert all(r["delivered"] == 0 for r in rows), level


def test_contract_does_not_require_broadcast_where_unauthored(load_curriculum):
    """Demanding an exercise whose content does not exist would make the
    level completion contract unsatisfiable."""
    unauthored = [l for l in ("A1", "A2", "B1", "B2", "C1", "C2")
                  if l not in curriculum.broadcast_levels()]
    if not unauthored:
        pytest.skip("every level authored")
    level = unauthored[0]
    database.register_member("bcast3", "Contract Student")
    c = assessment.level_completion_contract("bcast3", level)
    work = next(x for x in c["criteria"] if x["id"] == "work")
    assert "broadcast" not in (work.get("detail") or "").lower()


def test_a2_r_2_is_now_taught(load_curriculum):
    """The descriptor this level of the phase exists to close."""
    if "A2" not in curriculum.broadcast_levels():
        pytest.skip("A2 extended listening not authored yet")
    assert "A2.R.2" not in coverage_ledger.untaught_descriptors("A2")
