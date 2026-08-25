"""Tests for src/curriculum.py — curriculum data loading and access.

Uses the real data/ and content/ JSON files (via the session-scoped
load_curriculum fixture in conftest.py), not mocks, so these tests catch
real content regressions the same way the underlying data would actually
break the bot in production.
"""
from src import config, curriculum


# ============================================================
#  LOADING / COVERAGE
# ============================================================

def test_all_four_levels_loaded():
    stats = curriculum.stats()
    # Dynamic: legacy L0–L3 (38) + any authored CEFR levels (Mi'yar A1–C2).
    # expected_week_count() counts the week files present on disk, so this
    # stays correct as CEFR levels ship while still catching a file that
    # failed to parse (loaded < expected).
    assert stats["weeks_loaded"] == curriculum.expected_week_count()
    assert stats["weeks_loaded"] >= 90  # CEFR A1–C2 floor (90 weeks)


def test_level_week_counts_matches_loaded_weeks():
    for level, expected_weeks in curriculum.CEFR_WEEK_COUNTS.items():
        for week in range(1, expected_weeks + 1):
            vocab = curriculum.get_vocabulary_for_week(week, level)
            assert vocab, f"{level} week {week} has no vocabulary loaded"


def test_max_week_for_level():
    assert curriculum.max_week_for_level("A1") == 10
    assert curriculum.max_week_for_level("A2") == 12
    assert curriculum.max_week_for_level("B1") == 14
    assert curriculum.max_week_for_level("B2") == 16
    assert curriculum.max_week_for_level("C1") == 18
    assert curriculum.max_week_for_level("C2") == 20


def test_max_week_for_level_unknown_defaults_to_a1():
    assert curriculum.max_week_for_level("L99") == curriculum.CEFR_WEEK_COUNTS["A1"]


def test_accent_and_grammar_content_covers_all_levels():
    """All four legacy levels have accent/grammar content authored (since
    2026-07-11), and CEFR levels gain it as each level's phonology ships
    (A1 first). If a future change accidentally removes a level's content
    folder, this should fail loudly instead of curriculum.py's
    has_accent_content()/has_grammar_content() silently returning False for
    real students.

    Asserted as a SUBSET rather than an exact list so that authoring the next
    CEFR level's phonology does not require editing this test — while still
    failing loudly if any covered level disappears.
    """
    stats = curriculum.stats()
    required = {"A1", "A2", "B1", "B2", "C1", "C2"}
    assert required <= set(stats["accent_levels_covered"]), (
        f"missing accent content for: {required - set(stats['accent_levels_covered'])}"
    )
    assert required <= set(stats["grammar_levels_covered"]), (
        f"missing grammar content for: {required - set(stats['grammar_levels_covered'])}"
    )


def test_has_accent_content_and_has_grammar_content():
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        assert curriculum.has_accent_content(level)
        assert curriculum.has_grammar_content(level)


def test_has_accent_content_false_for_unknown_level():
    assert curriculum.has_accent_content("L99") is False


# ============================================================
#  VOCABULARY — WEEK-LEVEL
# ============================================================

def test_get_vocabulary_for_week_unknown_level_returns_empty():
    assert curriculum.get_vocabulary_for_week(1, "L99") == []


def test_get_vocabulary_for_week_unknown_week_returns_empty():
    assert curriculum.get_vocabulary_for_week(999, "A1") == []


def test_vocabulary_entries_have_required_fields():
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            for entry in curriculum.get_vocabulary_for_week(week, level):
                assert entry.get("word"), f"{level} week {week} has a vocab entry with no word"
                assert "arabic" in entry
                assert "pronunciation" in entry
                assert "pos" in entry


def test_no_cross_week_exact_vocabulary_duplication():
    """Regression test for a real bug: 7 of L1's 10 weeks were silently
    serving Week 1's 'Daily Routines' vocabulary verbatim, despite each
    having its own correct, distinct theme. Guards against this (or any
    similar copy-paste) recurring in any level, at the exact boundary
    where the bot's own curriculum.py loader would serve it to students."""
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        seen = {}
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            words = tuple(w["word"] for w in curriculum.get_vocabulary_for_week(week, level))
            for prev_week, prev_words in seen.items():
                assert words != prev_words, (
                    f"{level} week {week} vocabulary is byte-identical to "
                    f"week {prev_week} — likely a copy-paste bug, not real content"
                )
            seen[week] = words


def test_vocabulary_word_count_reasonable_per_level():
    """Sanity floor — a week with e.g. 0-5 words would indicate a loading
    failure or an empty/corrupted file, not real curriculum content."""
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            count = len(curriculum.get_vocabulary_for_week(week, level))
            assert count >= 30, f"{level} week {week} has suspiciously few words ({count})"


# ============================================================
#  VOCABULARY — DAY SPLIT (regression: bot vs. practice-site parity)
# ============================================================

def test_get_vocabulary_for_day_covers_whole_week_without_overlap():
    """The 7 daily slices for a week must be genuinely distinct day to
    day — this is the exact function whose splitting logic empire-dojo's
    generate.py must mirror byte-for-byte for the bot and practice
    website to ever agree on what a student sees on a given day.

    Compares each day's word LIST (not a flattened set of all words) to
    every other day's, since a handful of weeks legitimately contain the
    same word twice within their vocabulary on purpose — e.g. L2 week 1
    teaches "impact"/"protest"/"broadcast" as both noun and verb, with
    different stress/pronunciation and different Arabic meaning for each
    sense. That's real content, not a duplication bug, and can land on
    two different days without it being the regression this guards
    against (site falling back to day 1's exact word list on later days).
    """
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            day_lists = []
            for day_index in range(7):
                day_words = curriculum.get_vocabulary_for_day(week, day_index, level)
                assert day_words, f"{level} week {week} day {day_index} has no words"
                day_lists.append(tuple(w["word"] for w in day_words))
            for i in range(len(day_lists)):
                for j in range(i + 1, len(day_lists)):
                    assert day_lists[i] != day_lists[j], (
                        f"{level} week {week}: day {i} and day {j} have the "
                        f"exact same word list — days are not being split distinctly"
                    )


# ============================================================
#  READING (Phase 11B — the CEFR mode that had no task at all)
# ============================================================

def test_reading_is_authored_for_a1_and_absent_levels_return_none():
    """Reading rolls out level by level behind the owner approval gate, so an
    unauthored level must return None -- never another level's passage."""
    assert "A1" in curriculum.reading_levels()
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        assert curriculum.get_reading_for_week(week, "A1"), f"A1 w{week} missing"
    for level in curriculum.reading_levels():
        assert level in ("A1", "A2", "B1", "B2", "C1", "C2")
    unauthored = [l for l in ("A2", "B1", "B2", "C1", "C2")
                  if l not in curriculum.reading_levels()]
    for level in unauthored:
        assert curriculum.get_reading_for_week(1, level) is None, (
            f"{level} has no authored reading but returned a passage — it must "
            f"not borrow another level's text"
        )


def test_a1_reading_passages_are_wellformed_and_answerable():
    """Every authored passage must be usable as an exercise: real text, a
    bilingual title, glossary entries, and comprehension questions whose
    answer index actually points at an option."""
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        r = curriculum.get_reading_for_week(week, "A1")
        assert r["text"].strip(), f"w{week}: empty passage"
        assert r["title"] and r["title_ar"], f"w{week}: title not bilingual"
        assert r["gist_ar"], f"w{week}: no Arabic gist"
        assert r["can_do"], f"w{week}: passage targets no descriptor"
        assert r["glossary"], f"w{week}: no glossary"
        for g in r["glossary"]:
            assert g.get("word") and g.get("ar"), f"w{week}: glossary not bilingual"
        assert len(r["questions"]) >= 3, f"w{week}: too few questions"
        for q in r["questions"]:
            assert q.get("q") and q.get("q_ar"), f"w{week}: question not bilingual"
            assert len(q["options"]) >= 3, f"w{week}: too few options"
            assert isinstance(q["answer"], int)
            assert 0 <= q["answer"] < len(q["options"]), (
                f"w{week}: answer index {q['answer']} out of range"
            )
            assert len(set(q["options"])) == len(q["options"]), (
                f"w{week}: duplicate options would make two answers correct"
            )


def test_a1_reading_answers_are_not_all_in_the_same_position():
    """Anti-gaming: if the correct option were always first, a student could
    score full marks without reading. (The first draft of this content had
    every answer at index 0 — caught and shuffled deterministically.)"""
    positions = [q["answer"]
                 for week in range(1, curriculum.max_week_for_level("A1") + 1)
                 for q in curriculum.get_reading_for_week(week, "A1")["questions"]]
    assert len(set(positions)) >= 3, f"answers cluster in positions {set(positions)}"
    most_common = max(positions.count(p) for p in set(positions))
    assert most_common < len(positions) * 0.6, (
        "over 60% of answers share one position — guessable without reading"
    )


def test_a1_reading_passages_are_level_appropriate_length():
    """A1 reading descriptors are about VERY short texts; a 300-word wall
    would not be A1 no matter how simple the words."""
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        r = curriculum.get_reading_for_week(week, "A1")
        words = len(r["text"].split())
        assert 30 <= words <= 120, f"A1 w{week} passage is {words} words"
        assert r["word_count"] > 0


def test_a1_reading_is_grounded_in_the_week_it_belongs_to():
    """A passage must recycle the week's OWN authored vocabulary, otherwise it
    is generic filler bolted onto the curriculum rather than part of it."""
    import re
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        r = curriculum.get_reading_for_week(week, "A1")
        text = r["text"].lower()
        vocab = [w["word"].lower() for w in
                 curriculum.get_vocabulary_for_week(week, "A1")]
        used = [v for v in vocab if re.search(r"\b" + re.escape(v) + r"\b", text)]
        assert len(used) >= 8, (
            f"A1 w{week} passage only reuses {len(used)} of the week's "
            f"{len(vocab)} authored words — not grounded in the week"
        )
        assert r["week"] == week and r["cefr"] == "A1"


def test_reading_passages_only_claim_descriptors_of_their_own_level():
    """A passage must not claim to teach another level's descriptor."""
    for level in curriculum.reading_levels():
        library = curriculum.can_do_descriptor_map(level)
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            r = curriculum.get_reading_for_week(week, level)
            if not r:
                continue
            for code in r.get("can_do") or []:
                assert code.startswith(f"{level}."), (
                    f"{level} w{week} claims {code}"
                )
                assert code in library, f"{level} w{week} claims unknown {code}"


def test_mediation_is_authored_for_a1_and_absent_levels_return_none():
    assert "A1" in curriculum.mediation_levels()
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        assert curriculum.get_mediation_for_week(week, "A1"), f"A1 w{week} missing"
    for level in ("A2", "B1", "B2", "C1", "C2"):
        if level not in curriculum.mediation_levels():
            assert curriculum.get_mediation_for_week(1, level) is None


def test_a1_mediation_tasks_are_wellformed_and_assessable():
    """A mediation task is only usable if it has a source to relay, a person
    who needs it, and CHECKABLE key points — the key points are the assessment
    criteria (did the essential information get across?), so a task without
    them would be unmarkable."""
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        m = curriculum.get_mediation_for_week(week, "A1")
        assert m["title"] and m["title_ar"], f"w{week}: title not bilingual"
        assert m["source"].strip(), f"w{week}: nothing to relay"
        assert m["scenario"]["en"] and m["scenario"]["ar"], f"w{week}: scenario"
        assert m["task"]["en"] and m["task"]["ar"], f"w{week}: task"
        assert m["model_answer"]["en"] and m["model_answer"]["ar"], f"w{week}: model"
        assert len(m["key_points"]) >= 3, f"w{week}: too few key points"
        for kp in m["key_points"]:
            assert kp.get("en") and kp.get("ar"), f"w{week}: key point not bilingual"
        # A1.M.2 is specifically about signalling with a short phrase.
        assert len(m["signal_phrases"]) >= 3, f"w{week}: no signal phrases"
        for sp in m["signal_phrases"]:
            assert sp.get("en") and sp.get("ar")
            assert len(sp["en"].split()) <= 6, (
                f"w{week}: signal phrase '{sp['en']}' is not a SHORT phrase"
            )


def test_a1_mediation_key_points_are_grounded_in_the_source():
    """Every fact the student must relay has to be findable in the source they
    were given. Otherwise the task asks them to invent information, which is
    not mediation."""
    import re
    stop = {"a", "an", "the", "is", "are", "was", "were", "he", "she", "it",
            "his", "her", "they", "them", "at", "in", "on", "of", "and", "to",
            "with", "no", "not", "please", "my", "one", "can", "has", "have",
            "got", "there", "years", "old", "very", "well", "but", "does",
            "would", "like", "want", "wants", "today", "from", "you", "i"}
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        m = curriculum.get_mediation_for_week(week, "A1")
        source = m["source"].lower()
        for kp in m["key_points"]:
            toks = [t for t in re.findall(r"[a-z']+", kp["en"].lower())
                    if t not in stop]
            assert any(t in source for t in toks), (
                f"A1 w{week}: key point '{kp['en']}' has no anchor in the "
                f"source the student was given"
            )


def test_a1_mediation_model_answer_covers_every_key_point():
    """The model answer must demonstrate a SUCCESSFUL relay — if it omits a
    required fact, it teaches students to under-report."""
    import re
    stop = {"a", "an", "the", "is", "are", "was", "were", "he", "she", "it",
            "his", "her", "they", "them", "at", "in", "on", "of", "and", "to",
            "with", "no", "not", "please", "my", "one", "can", "has", "have",
            "got", "there", "years", "old", "very", "well", "but", "does",
            "would", "like", "want", "wants", "today", "from", "you", "i"}
    for week in range(1, curriculum.max_week_for_level("A1") + 1):
        m = curriculum.get_mediation_for_week(week, "A1")
        model = m["model_answer"]["en"].lower()
        for kp in m["key_points"]:
            toks = [t for t in re.findall(r"[a-z']+", kp["en"].lower())
                    if t not in stop]
            assert any(t in model for t in toks), (
                f"A1 w{week}: model answer omits key point '{kp['en']}'"
            )


def test_mediation_tasks_only_claim_descriptors_of_their_own_level():
    for level in curriculum.mediation_levels():
        library = curriculum.can_do_descriptor_map(level)
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            m = curriculum.get_mediation_for_week(week, level)
            if not m:
                continue
            for code in m.get("can_do") or []:
                assert code.startswith(f"{level}."), f"{level} w{week} claims {code}"
                assert code in library, f"{level} w{week} claims unknown {code}"


def test_every_week_resolves_its_can_do_goals_bilingually():
    """Every one of the 90 weeks must resolve at least one CEFR can-do goal to
    a real bilingual "I can ..." descriptor.

    Phase 11A-4 regression guard: weeks carry bare codes ("A1.P.1") which mean
    nothing to a student, and the goals were invisible during study -- shown
    only on the Phase-9 progress screen and the certificate, i.e. after the
    fact. `get_can_do_for_week` returns codes; this resolves them.
    """
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            goals = curriculum.get_can_do_details_for_week(week, level)
            assert goals, f"{level} week {week} resolves no can-do goals"
            for g in goals:
                assert g.get("code"), f"{level} w{week}: goal without code"
                assert g.get("en"), f"{level} w{week}: {g.get('code')} has no English"
                assert g.get("ar"), f"{level} w{week}: {g.get('code')} has no Arabic"
                assert g.get("mode") in (
                    "reception", "production", "interaction", "mediation"
                ), f"{level} w{week}: {g.get('code')} has odd mode {g.get('mode')}"


def test_can_do_descriptor_map_skips_the_overview_string_keys():
    """can_do.json mixes list-valued modes with plain string keys
    (overview_en/overview_ar). Those must never be treated as descriptors."""
    m = curriculum.can_do_descriptor_map("A1")
    assert m, "A1 descriptor library is empty"
    assert "overview_en" not in m and "overview_ar" not in m
    assert all(code.startswith("A1.") for code in m), sorted(m)[:5]


def test_get_can_do_details_skips_unknown_codes(monkeypatch):
    """An unrecognised code is dropped, not rendered raw to the student."""
    monkeypatch.setattr(curriculum, "get_can_do_for_week",
                        lambda w, l="A1": ["A1.P.1", "A1.NOPE.9"])
    goals = curriculum.get_can_do_details_for_week(1, "A1")
    assert [g["code"] for g in goals] == ["A1.P.1"]


def test_every_authored_grammar_pattern_is_reachable_and_practisable():
    """All 90 authored grammar patterns must be reachable, and each must
    carry the fields the practice page turns into a real exercise.

    Phase 11A-3 regression guard: grammar used to reach students ONLY as a
    passive Wednesday #cheat-sheets post -- no page, no exercise, no
    completion -- so a student could finish a level having never practised a
    single grammar point.
    """
    weeks = 0
    practice_items = 0
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            g = curriculum.get_grammar_pattern(week, level)
            assert g, f"{level} week {week} has no grammar pattern"
            assert g.get("pattern_name"), f"{level} w{week}: no pattern_name"
            assert g.get("formula"), f"{level} w{week}: no formula"
            # What makes it an EXERCISE rather than a cheat sheet:
            practice = g.get("practice_fill_blank") or []
            assert practice, f"{level} w{week}: no practice_fill_blank"
            for p in practice:
                assert p.get("sentence") and p.get("answer"), (
                    f"{level} w{week}: practice item missing sentence/answer"
                )
            practice_items += len(practice)
            weeks += 1
    assert weeks == 90, f"expected 90 authored grammar weeks, found {weeks}"
    assert practice_items >= 90, "every week must have practisable items"


def test_every_authored_listening_item_is_reachable():
    """All 450 authored listening items must be reachable through the public
    accessor, for every week of every level.

    Regression guard: the week files' `listening` array had no accessor and
    no consumer at all -- the practice site built dictation from
    `vocabulary` instead -- so the curated dictation set and all 450 Arabic
    hints reached nobody.
    """
    total = 0
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            items = curriculum.get_listening_for_week(week, level)
            assert items, f"{level} week {week} has no authored listening items"
            for item in items:
                assert item.get("say_en"), f"{level} w{week}: item missing say_en"
                assert item.get("expected"), f"{level} w{week}: item missing expected"
                assert item.get("hint_ar"), f"{level} w{week}: item missing hint_ar"
            total += len(items)
    assert total == 450, f"expected 450 authored listening items, found {total}"


def test_get_listening_for_day_delivers_the_full_week_set_on_every_day():
    """Only 5 items are authored per week against 7 days, so every day must
    surface the complete set (rotated for variety) -- otherwise coverage
    would depend on which days a student happens to practise, and 2 days a
    week would have no authored listening at all."""
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            expected = {i["expected"] for i in curriculum.get_listening_for_week(week, level)}
            for day_index in range(7):
                day_items = curriculum.get_listening_for_day(week, day_index, level)
                assert {i["expected"] for i in day_items} == expected, (
                    f"{level} week {week} day {day_index} does not surface the "
                    f"full authored listening set"
                )


def test_get_listening_for_day_rotates_order_by_day():
    """Rotation gives day-to-day variety without dropping any item."""
    day0 = curriculum.get_listening_for_day(1, 0, "A1")
    day1 = curriculum.get_listening_for_day(1, 1, "A1")
    assert [i["expected"] for i in day0] != [i["expected"] for i in day1]
    assert sorted(i["expected"] for i in day0) == sorted(i["expected"] for i in day1)


def test_get_listening_for_unknown_week_returns_empty():
    assert curriculum.get_listening_for_week(999, "A1") == []
    assert curriculum.get_listening_for_day(999, 0, "ZZ") == []


def test_get_vocabulary_for_day_loses_zero_words_across_every_authored_week():
    """ZERO-LOSS INVARIANT: the 7 day slices must reconstruct the week's
    vocabulary list EXACTLY -- same words, same order, same count.

    Regression guard for a real, measured content-loss bug: the old split
    used `max(1, len(words) // 7)` and never assigned the integer-division
    remainder to any day, so the last `len % 7` words of EVERY week were
    unreachable for every student, forever. Across the 90 authored weeks
    that silently discarded 354 of 2,909 words (12.2%); A2 lost 14.9% and
    one week lost 6 words.

    Asserting exact reconstruction (not just "no word is missing") also
    pins down non-overlap and authored order in one check, and correctly
    tolerates weeks that intentionally teach the same word twice as two
    senses (e.g. "impact" as noun and verb) because it compares lists.
    """
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            week_words = curriculum.get_vocabulary_for_week(week, level)
            assert week_words, f"{level} week {week} has no authored vocabulary"
            rebuilt = []
            for day_index in range(7):
                rebuilt.extend(curriculum.get_vocabulary_for_day(week, day_index, level))
            assert rebuilt == week_words, (
                f"{level} week {week}: the 7 daily slices do not reconstruct the "
                f"week's vocabulary. Authored {len(week_words)} words, students "
                f"see {len(rebuilt)} -- "
                f"{len(week_words) - len(rebuilt)} word(s) are unreachable."
            )


def test_get_vocabulary_for_day_balances_days_within_one_word():
    """No day may carry 2+ more words than another: the remainder is spread
    one-per-day, never dumped onto a single day (which would make one day
    brutal and is not how the authored content is paced)."""
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            sizes = [
                len(curriculum.get_vocabulary_for_day(week, d, level))
                for d in range(7)
            ]
            assert max(sizes) - min(sizes) <= 1, (
                f"{level} week {week}: unbalanced day sizes {sizes}"
            )


def test_get_vocabulary_for_day_handles_short_weeks_without_empty_days():
    """A week with fewer than 7 words must still give every day something
    AND still surface every authored word (union == full list)."""
    key = "A1_1"
    original = curriculum._weekly_data.get(key)
    try:
        curriculum._weekly_data[key] = {
            "vocabulary": [{"word": "one"}, {"word": "two"}, {"word": "three"}]
        }
        seen = set()
        for day_index in range(7):
            day_words = curriculum.get_vocabulary_for_day(1, day_index, "A1")
            assert day_words, f"day {day_index} is empty on a 3-word week"
            seen.update(w["word"] for w in day_words)
        assert seen == {"one", "two", "three"}
    finally:
        if original is None:
            curriculum._weekly_data.pop(key, None)
        else:
            curriculum._weekly_data[key] = original


def test_get_vocabulary_for_day_wraps_day_index():
    """day_index % 7 means day 7 (index 7) must equal day 0 (index 0)."""
    words_day0 = curriculum.get_vocabulary_for_day(1, 0, "A1")
    words_day7 = curriculum.get_vocabulary_for_day(1, 7, "A1")
    assert words_day0 == words_day7


def test_get_vocabulary_for_day_empty_week_returns_empty():
    assert curriculum.get_vocabulary_for_day(999, 0, "A1") == []


# ============================================================
#  QUIZ WORDS (spaced repetition)
# ============================================================

def test_get_quiz_words_respects_count():
    words = curriculum.get_quiz_words(5, count=10, level="A1")
    assert len(words) <= 10


def test_get_quiz_words_pulls_from_current_and_previous_two_weeks():
    """Week 1 should only draw from week 1 (no earlier weeks exist)."""
    week1_only = set(w["word"] for w in curriculum.get_vocabulary_for_week(1, "A1"))
    quiz_words = curriculum.get_quiz_words(1, count=100, level="A1")
    for w in quiz_words:
        assert w["word"] in week1_only


def test_get_quiz_words_empty_for_unknown_level():
    assert curriculum.get_quiz_words(1, count=10, level="L99") == []


# ============================================================
#  SPEAKING MISSIONS / WRITING PROMPTS
# ============================================================

def test_every_week_has_all_seven_speaking_missions():
    day_names = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            for day in day_names:
                mission = curriculum.get_speaking_mission(week, day, level)
                assert mission, f"{level} week {week} missing speaking mission for {day}"
                assert mission.get("prompt")


def test_get_speaking_mission_unknown_day_returns_none():
    assert curriculum.get_speaking_mission(1, "Blursday", "A1") is None


def test_every_week_has_seven_writing_prompts():
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            for day_index in range(7):
                prompt = curriculum.get_writing_prompt(week, day_index, level)
                assert prompt, f"{level} week {week} missing writing prompt for day {day_index}"


def test_get_writing_prompt_out_of_range_returns_none():
    assert curriculum.get_writing_prompt(1, 999, "A1") is None


# ============================================================
#  ACCENT DRILLS
# ============================================================

def test_get_accent_drill_returns_none_for_unknown_level():
    assert curriculum.get_accent_drill(1, 0, "L99") is None


def test_get_accent_drill_clamps_week_to_valid_range():
    """Week 999 on L0 (8 weeks) should clamp to week 8, not silently
    return None or raise — callers rely on always getting *some* content
    for a level that has content authored, even for an out-of-range week."""
    clamped = curriculum.get_accent_drill(999, 0, "A1")
    week10 = curriculum.get_accent_drill(10, 0, "A1")
    assert clamped == week10


def test_get_accent_focus_l0_falls_back_to_phoneme_weeks_if_missing():
    """L0 has a legacy hardcoded fallback (config.PHONEME_WEEKS) — verify
    the real JSON content takes priority, and that the function never
    returns None for L0 (content exists for all 8 weeks)."""
    for week in range(1, 11):
        assert curriculum.get_accent_focus(week, "A1") is not None


def test_get_accent_focus_unknown_level_returns_none_not_fabricated():
    """Only L0 has the legacy PHONEME_WEEKS fallback. A level with no
    accent content authored must return None, never a fabricated guess."""
    assert curriculum.get_accent_focus(1, "L99") is None


# ============================================================
#  GRAMMAR PATTERNS
# ============================================================

def test_get_grammar_pattern_returns_none_for_unknown_level():
    assert curriculum.get_grammar_pattern(1, "L99") is None


def test_every_week_has_a_grammar_pattern():
    for level in ("A1", "A2", "B1", "B2", "C1", "C2"):
        for week in range(1, curriculum.max_week_for_level(level) + 1):
            pattern = curriculum.get_grammar_pattern(week, level)
            assert pattern, f"{level} week {week} missing grammar pattern"


# ============================================================
#  DAILY CONTENT BUNDLE
# ============================================================

def test_get_daily_content_returns_all_task_keys():
    daily = curriculum.get_daily_content(1, "Saturday", 0, "A1")
    expected_keys = {
        "week", "day_name", "day_index", "level", "vocabulary",
        "speaking_mission", "writing_prompt", "accent_drill",
        "accent_focus", "grammar_pattern", "theme",
    }
    assert expected_keys.issubset(daily.keys())


def test_get_daily_content_threads_level_through_correctly():
    """Regression guard: get_daily_content() previously silently defaulted
    every level to L0 content internally. Confirm L1's daily content is
    genuinely different from L0's, not a hidden L0 fallback."""
    a1_daily = curriculum.get_daily_content(1, "Saturday", 0, "A1")
    a2_daily = curriculum.get_daily_content(1, "Saturday", 0, "A2")
    assert a1_daily["theme"] != a2_daily["theme"]
    assert a1_daily["vocabulary"] != a2_daily["vocabulary"]


def test_get_daily_content_clamps_vocab_speaking_writing_past_max_week():
    """Found via boundary-condition stress testing: get_accent_drill()/
    get_accent_focus()/get_grammar_pattern() already clamped week
    internally, but get_vocabulary_for_day()/get_speaking_mission()/
    get_writing_prompt() did not -- so a member still within their
    level's own declared duration_weeks range (config.LEVELS' L0 says
    (8, 12), but curated content only covers 8 weeks) got real repeated
    week-8 accent/grammar content but generic non-curated filler for
    vocab/speaking/writing instead of week 8 repeating like everything
    else. Confirm week 15 for L0 (max week 8) now returns identical
    task content to week 8 itself, for every task type."""
    week_10 = curriculum.get_daily_content(10, "Saturday", 0, "A1")
    week_15 = curriculum.get_daily_content(15, "Saturday", 0, "A1")
    assert week_15["vocabulary"] == week_10["vocabulary"]
    assert week_15["vocabulary"] != []
    assert week_15["speaking_mission"] == week_10["speaking_mission"]
    assert week_15["speaking_mission"] is not None
    assert week_15["writing_prompt"] == week_10["writing_prompt"]
    assert week_15["writing_prompt"] is not None
    # The returned "week" key itself is clamped too (it's what theme/
    # grammar-name lookups key off of internally) -- callers that want to
    # display the member's REAL week number (e.g. bot.py's daily task
    # post header) already use their own separate, unclamped
    # member_week_number() value for that, not this dict's "week" key.
    assert week_15["week"] == 10


# ============================================================
#  PRACTICE PLATFORM URL BUILDERS
# ============================================================

def test_practice_platform_day_url_shape():
    url = curriculum.practice_platform_day_url(3, 0, "A2")
    assert url == f"{config.PRACTICE_PLATFORM_URL}/a2/week3/day1/"


def test_practice_platform_day_url_day_index_to_day_number():
    """day_index is 0=Saturday..6=Friday; the URL uses day1=Saturday..day7=Friday."""
    url_day0 = curriculum.practice_platform_day_url(1, 0, "A1")
    url_day6 = curriculum.practice_platform_day_url(1, 6, "A1")
    assert "/day1/" in url_day0
    assert "/day7/" in url_day6


def test_practice_platform_day_url_clamps_week():
    url = curriculum.practice_platform_day_url(999, 0, "A1")
    assert "/week10/" in url  # A1 max week is 10


def test_practice_platform_task_url_known_tasks():
    for task_id, expected_slug in (
        ("accent", "accent"), ("vocab", "vocab"),
        ("shadow", "shadowing"), ("listening", "listening"),
    ):
        url = curriculum.practice_platform_task_url(task_id, 1, 0, "A1")
        assert url is not None
        assert url.endswith(f"/{expected_slug}")


def test_practice_platform_task_url_unmapped_tasks_return_none():
    """speaking/writing/community have no matching practice-site page —
    must return None, never a fabricated/guessed link."""
    for task_id in ("speaking", "writing", "community"):
        assert curriculum.practice_platform_task_url(task_id, 1, 0, "A1") is None


def test_practice_platform_task_url_is_extensionless():
    """Verified live: the .html-suffixed path 404s on the custom domain;
    the extensionless form works everywhere. Must never regress to
    appending .html."""
    url = curriculum.practice_platform_task_url("vocab", 1, 0, "A1")
    assert not url.endswith(".html")


# ============================================================
#  THEME / MISC
# ============================================================

def test_get_theme_falls_back_to_vocab_themes_for_missing_week():
    """get_theme() falls back to config.VOCAB_THEMES only when the week
    key isn't in _weekly_data at all (e.g. week 999); every real week
    should return its own JSON-sourced theme, not the L0-only fallback
    table, for L1/L2/L3 as well as L0."""
    for level in ("A2", "B1", "C1"):
        theme = curriculum.get_theme(1, level)
        assert theme and theme != "General"


def test_is_loaded_true_after_load_all():
    assert curriculum.is_loaded() is True
