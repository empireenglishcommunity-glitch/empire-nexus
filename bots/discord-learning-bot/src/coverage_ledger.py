"""Coverage Ledger — proves every authored content atom reaches a student.

WHY THIS EXISTS
---------------
A 2026-08-24 audit answered the owner's question "if a student finishes A1
through the daily tasks, did they get ALL of A1's content?" with **no**:

  * 354 of 2,909 vocabulary words were unreachable (the day split used
    `len // 7` and never assigned the remainder) — 88 of 90 weeks affected.
  * 450 authored `listening` items had no consumer anywhere in the codebase.
  * 90 grammar patterns (1,208 sub-items) were a passive Wednesday post —
    no page, no exercise, no completion, no mastery.
  * The day index's "pattern" card rendered nothing at all for every CEFR
    level, because its data file only existed for the retired legacy levels.
  * `phoneme_focus` and `grammar_point` were authored per week and shown
    nowhere.

Every one of those was content the business paid to author and no student
could ever see. They were all invisible because nothing was *checking*.

So the fix is not another one-off audit — it is this ledger, run as a test.
It enumerates every authored atom, resolves the delivery route that actually
puts it in front of a student, and **fails the build if any atom has no
route**. "Authored but never delivered" becomes structurally impossible.

WHAT COUNTS AS "DELIVERED"
--------------------------
A route must be a real student-facing surface, not merely a field that some
code can read. Every route below is exercised by the accompanying tests
against the real content files, so a route that silently stops returning
content fails the gate.

Two deliberate distinctions:

  * DELIVERY coverage (this module's hard gate) — can a student reach the
    atom at all? Must be 100%.
  * DESCRIPTOR coverage (reported, with a pinned baseline) — does the level
    actually teach every CEFR descriptor it claims? A1–B2 currently do not:
    reading and mediation have no task yet, so 25 descriptors are taught by
    no week. That is real, known, tracked debt (spec Phase 11B), not a
    delivery bug, so it is pinned to an exact expected set: the gate fails
    if it grows AND fails if it shrinks without updating the baseline, so
    the number can never drift silently in either direction.
"""

import json
import logging
import pathlib

from . import config, curriculum, database

logger = logging.getLogger(__name__)

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")

# CEFR descriptors that NO week currently teaches. Pinned deliberately: these
# are the reading (`.R.`) and mediation (`.M.`) gaps that exist because those
# two CEFR modes have no task yet (spec Phase 11B), plus A1.P.5 (short notes
# and messages). Update this set ONLY when a week genuinely starts teaching
# the descriptor -- never to make a failing test pass.
# A1 IS NOW COMPLETE: all 15 A1 descriptors are taught. A1.R.1/A1.R.4 closed by
# the A1 reading passages, A1.M.1/A1.M.2 by the A1 mediation tasks, and A1.P.5
# by turning week 3's weak gap-fill prompt into a real short-note task.
#
# Every remaining gap has a NAMED, specific requirement below — no gap is
# allowed to sit here as a vague "todo". `DESCRIPTOR_GAP_PLAN` must cover every
# entry in this set (enforced by a test), so the honest answer to "what is left
# and what does it need?" is always in the code.
KNOWN_UNTAUGHT_DESCRIPTORS = frozenset({
    # EMPTY. Every descriptor every level publishes is now targeted by at least
    # one week of that level, with content that actually exists and is reachable.
    #
    # How it got here:
    #   * reading and mediation authored for A1-B2 (Phase 11B), closing every
    #     `.R.` gap a passage could close and every `.M.` gap;
    #   * the interaction gaps (B1.I.1, B2.I.1, B2.I.5) closed via speaking
    #     missions, because interaction cannot be proven by a passage or a
    #     relay task;
    #   * A1.P.5 closed by turning week 3's weak gap-fill into a real
    #     short-note task;
    #   * the five extended-listening descriptors (A2.R.2, B1.R.1, B1.R.2,
    #     B2.R.1, B2.R.2) closed by the `broadcast` exercise in Phase 11D --
    #     about a minute of connected speech a week, with the gist question
    #     asked BEFORE the transcript unlocks so the answer comes from the ear.
    #
    # Keep it empty. If a descriptor becomes untaught again, a test fails and
    # names it. Add to this set ONLY when a descriptor genuinely has no week
    # teaching it -- never to make a failing test pass, and never as a place to
    # park something that is partly taught: that is what
    # TAUGHT_WITH_RESERVATION below is for.
})

# Descriptors that needed SPOKEN input at length rather than a reading passage.
# All now closed by the broadcast exercise; kept as a named (now empty) set
# because a test pins it against KNOWN_UNTAUGHT_DESCRIPTORS, so if one of them
# ever regresses it must be re-listed here and explained rather than quietly
# reappearing as a generic gap.
GAPS_NEEDING_EXTENDED_LISTENING = frozenset()

# What each remaining gap NEEDS in order to close honestly. Empty because there
# are no untaught descriptors left; a test pins its keys to
# KNOWN_UNTAUGHT_DESCRIPTORS so the two cannot drift apart.
DESCRIPTOR_GAP_PLAN = {}

# ---------------------------------------------------------------------------
#  TAUGHT, BUT NOT AS WELL AS THE WORDS OF THE DESCRIPTOR IMPLY
# ---------------------------------------------------------------------------
# A descriptor being "taught" is binary in `untaught_descriptors`: some week
# targets it with real content, or no week does. That is the right test for
# coverage and the wrong test for honesty, because it cannot express "we teach
# this, and here is the specific respect in which our version falls short of
# what the descriptor literally says".
#
# Without somewhere to record that, there are only two options for a descriptor
# like B2.R.2, and both of them are lies:
#
#   * tick it, and claim students have practised understanding FILMS when what
#     they have practised is synthesized voices reading film dialogue;
#   * leave it in KNOWN_UNTAUGHT_DESCRIPTORS, and print "not taught by any
#     week" about sixteen authored weeks of news bulletins and drama scenes.
#
# So: this is the third state. Every entry must name what IS taught, what the
# reservation is, and precisely what would remove it. `format_report` prints
# this block directly under the coverage summary, so anybody reading the ledger
# sees the reservation in the same breath as the claim, and a test asserts each
# entry is genuinely taught and genuinely documented.
#
# This is deliberately hard to add to. A reservation is a debt, not an excuse:
# if something can be fixed by authoring more content, author it instead.
TAUGHT_WITH_RESERVATION = {
    "B2.R.2": {
        "descriptor": "Can understand most TV news and current-affairs "
                      "programmes and the majority of films in standard dialect.",
        "taught_by": "10 B2 weeks of extended listening: news bulletins, a "
                     "studio discussion, a panel and an investigation "
                     "(multi-voice, broadcast register), plus 5 drama scenes "
                     "written the way film dialogue behaves -- contractions, "
                     "ellipsis, interruption, unfinished sentences and meaning "
                     "that is implied rather than stated.",
        "reservation": "The news and current-affairs half is delivered in full. "
                       "The FILM half is not, and cannot be by synthesis: our "
                       "audio is Kokoro TTS, one clean voice per speaker turn "
                       "with no overlapping speech, no background noise, no "
                       "regional accents and no emotional prosody. In real "
                       "films, sarcasm, tension and irony are carried by HOW a "
                       "line is delivered, and a student who understands every "
                       "one of our scenes has still never had to read tone off "
                       "a real actor's voice.",
        "removed_by": "Authentic recorded audio for the drama scenes -- human "
                      "actors, or licensed clips -- with the existing "
                      "comprehension items re-pointed at tone and implication. "
                      "The scripts and the page need no changes; only the audio "
                      "source does.",
        # Scenes that must carry authentic human audio before this reservation
        # lifts. Declared in content/cefr/authentic_audio.json; see
        # `authentic_scenes()` and `reservation_is_closed()` below.
        "requires_authentic_scenes": ["b2-w3", "b2-w5", "b2-w7", "b2-w15", "b2-w16"],
    },
    # Same class of reservation as B2.R.2, at C1: the descriptor names FILMS.
    # Recorded on the owner's explicit decision (2026-08-27) to accept the
    # reservation rather than report the descriptor untaught. C1.R.2 IS taught
    # -- six C1 drama-scene broadcasts written thick with slang and idiom, with
    # questions that target what an idiom is DOING rather than what its words
    # mean -- so the SLANG half of the descriptor is delivered. What synthesis
    # cannot deliver is the same thing it cannot deliver at B2: an actor's tone.
    "C1.R.2": {
        "descriptor": "Can follow films employing a considerable degree of "
                      "slang and idiomatic usage.",
        "taught_by": "6 C1 weeks of extended listening written as drama scenes "
                     "-- multi-voice, thick with slang and idiom, contractions "
                     "and ellipsis -- with comprehension items that ask what an "
                     "idiom is DOING in the exchange rather than what the words "
                     "literally mean, which is the skill the descriptor names.",
        "reservation": "The SLANG and idiomatic half is delivered in full. The "
                       "FILM half is not, and cannot be by synthesis, for the "
                       "same reason as B2.R.2: our audio is Kokoro TTS, one "
                       "clean voice per turn with no overlapping speech, no "
                       "regional accents and no emotional prosody. In a real "
                       "film an idiom's force -- whether it is a joke, a threat "
                       "or a kindness -- is carried by HOW the line is "
                       "delivered, and a student who understands every one of "
                       "our scenes has still never had to read that off a real "
                       "actor's voice.",
        "removed_by": "Authentic recorded audio for the C1 drama scenes -- "
                      "human actors, or licensed clips -- with the existing "
                      "comprehension items re-pointed at tone and delivery. As "
                      "with B2.R.2 the scripts and the page need no changes; "
                      "only the audio source does.",
        "requires_authentic_scenes": ["c1-w2", "c1-w7", "c1-w11", "c1-w14",
                                      "c1-w15", "c1-w16"],
    },
}


# ---------------------------------------------------------------------------
#  AUTHENTIC AUDIO — how a film reservation closes itself
# ---------------------------------------------------------------------------
# A reservation is a debt, and a debt needs a defined way to be paid. Both film
# reservations are closed by the same thing: real recorded voices for the drama
# scenes. Rather than require someone to remember to hand-edit this file on that
# day, the closure is DECLARATIVE — record the scene, list it in
# content/cefr/authentic_audio.json, and the reservation lifts on the next run.
#
# Deliberately a declaration and not a detection: nothing can automatically prove
# a recording features human actors. What IS checked automatically lives in
# empire-dojo/scripts/verify_authentic_audio.py — it fails if a listed scene's
# file is missing or is still one of our own TTS renders, which catches the
# realistic mistake (declaring a scene that was never actually replaced).

_AUTHENTIC_AUDIO_PATH = (pathlib.Path(__file__).resolve().parent.parent
                         / "content" / "cefr" / "authentic_audio.json")


def authentic_scenes() -> set:
    """Scene ids declared as authentic human recordings (e.g. {'b2-w3'}).

    Never raises: a missing or malformed manifest simply means nothing is
    authentic yet, which keeps the reservations printed — the safe direction.
    """
    try:
        with open(_AUTHENTIC_AUDIO_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {str(s).strip().lower() for s in (data.get("scenes") or []) if s}
    except (OSError, ValueError):
        return set()


def reservation_is_closed(code: str, declared: set | None = None) -> bool:
    """True when every scene a reservation depends on has authentic audio.

    A reservation with no `requires_authentic_scenes` can never auto-close: it
    has no defined completion condition, so it stays until someone states one.
    """
    entry = TAUGHT_WITH_RESERVATION.get(code) or {}
    required = {s.lower() for s in entry.get("requires_authentic_scenes") or []}
    if not required:
        return False
    return required <= (authentic_scenes() if declared is None else declared)


def open_reservations() -> dict:
    """The reservations still outstanding, i.e. not yet closed by real audio."""
    declared = authentic_scenes()
    return {code: dict(entry)
            for code, entry in TAUGHT_WITH_RESERVATION.items()
            if not reservation_is_closed(code, declared)}


def _atom_rows(level: str) -> list[dict]:
    """Every authored atom for a level, with the route that delivers it.

    One row per atom kind per week: {kind, week, authored, delivered, route,
    tracked_as}. `delivered` is computed by actually calling the delivery
    accessor, so a broken accessor shows up as a shortfall rather than a
    green tick.
    """
    rows = []
    for week in range(1, curriculum.max_week_for_level(level) + 1):
        # --- vocabulary: split across the 7 days, must lose nothing ---
        authored_vocab = curriculum.get_vocabulary_for_week(week, level)
        seen_vocab = []
        for day_index in range(7):
            seen_vocab.extend(curriculum.get_vocabulary_for_day(week, day_index, level))
        rows.append({
            "kind": "vocabulary", "week": week,
            "authored": len(authored_vocab), "delivered": len(seen_vocab),
            "route": "practice site vocab page (curriculum.get_vocabulary_for_day)",
            "tracked_as": "vocab",
        })

        # --- accent drills: one per day ---
        authored_drills = len(
            (curriculum._accent_data.get(level, {}).get(week, {}) or {}).get("daily_drills", []) or []
        )
        delivered_drills = sum(
            1 for day_index in range(7)
            if curriculum.get_accent_drill(week, day_index, level)
        )
        rows.append({
            "kind": "accent_drills", "week": week,
            "authored": authored_drills, "delivered": delivered_drills,
            "route": "practice site accent + shadowing pages (curriculum.get_accent_drill)",
            "tracked_as": "accent/shadow",
        })

        # --- listening: 5 authored per week, every day gets the full set ---
        authored_listening = curriculum.get_listening_for_week(week, level)
        delivered_listening = {
            item.get("expected")
            for day_index in range(7)
            for item in curriculum.get_listening_for_day(week, day_index, level)
        }
        rows.append({
            "kind": "listening", "week": week,
            "authored": len(authored_listening),
            "delivered": len({i.get("expected") for i in authored_listening} & delivered_listening),
            "route": "practice site listening page dictation (curriculum.get_listening_for_day)",
            "tracked_as": "listening",
        })

        # --- speaking missions: one per day ---
        day_names = ("Saturday", "Sunday", "Monday", "Tuesday", "Wednesday",
                     "Thursday", "Friday")
        authored_missions = len(
            (curriculum._weekly_data.get(f"{level}_{week}", {}) or {}).get("speaking_missions", {}) or {}
        )
        delivered_missions = sum(
            1 for name in day_names if curriculum.get_speaking_mission(week, name, level)
        )
        rows.append({
            "kind": "speaking_missions", "week": week,
            "authored": authored_missions, "delivered": delivered_missions,
            "route": "practice site speaking page (curriculum.get_speaking_mission)",
            "tracked_as": "speaking",
        })

        # --- writing prompts: one per day, Discord-only by design (!6) ---
        authored_prompts = len(
            (curriculum._weekly_data.get(f"{level}_{week}", {}) or {}).get("writing_prompts", []) or []
        )
        delivered_prompts = sum(
            1 for day_index in range(7)
            if curriculum.get_writing_prompt(week, day_index, level)
        )
        rows.append({
            "kind": "writing_prompts", "week": week,
            "authored": authored_prompts, "delivered": delivered_prompts,
            "route": "Discord writing task !6 (curriculum.get_writing_prompt)",
            "tracked_as": "writing",
        })

        # --- grammar: one authored pattern per week (weekly exercise) ---
        pattern = curriculum.get_grammar_pattern(week, level)
        rows.append({
            "kind": "grammar_pattern", "week": week,
            "authored": 1, "delivered": 1 if pattern else 0,
            "route": "practice site grammar page (curriculum.get_grammar_pattern)",
            "tracked_as": "grammar",
        })
        # The rich sub-items are what make it an exercise rather than a
        # cheat sheet, so they are ledgered separately.
        sub_authored = sum(len(pattern.get(f) or []) for f in
                           ("examples", "common_errors", "practice_fill_blank")) if pattern else 0
        rows.append({
            "kind": "grammar_sub_items", "week": week,
            "authored": sub_authored, "delivered": sub_authored if pattern else 0,
            "route": "practice site grammar page (examples/errors/fill-blank)",
            "tracked_as": "grammar",
        })

        # --- reading (Phase 11B, weekly, rolled out level by level) ---
        # A level with no authored passages contributes authored=0, so the
        # gate stays honestly green while the rollout is in progress: nothing
        # is authored, therefore nothing is orphaned. The moment a passage IS
        # authored, it must be reachable.
        passage = curriculum.get_reading_for_week(week, level)
        has_passage = bool(passage and passage.get("text"))
        authored_reading = 1 if (level in curriculum.reading_levels()
                                 and week in (curriculum._reading_data.get(level) or {})) else 0
        rows.append({
            "kind": "reading_passage", "week": week,
            "authored": authored_reading,
            "delivered": 1 if (authored_reading and has_passage) else 0,
            "route": "practice site reading page (curriculum.get_reading_for_week)",
            "tracked_as": "reading",
        })
        q_authored = len((passage or {}).get("questions") or [])
        rows.append({
            "kind": "reading_questions", "week": week,
            "authored": q_authored,
            "delivered": sum(
                1 for q in ((passage or {}).get("questions") or [])
                if q.get("q") and q.get("options")
                and isinstance(q.get("answer"), int)
                and 0 <= q["answer"] < len(q["options"])
            ),
            "route": "practice site reading page comprehension quiz",
            "tracked_as": "reading",
        })
        g_authored = len((passage or {}).get("glossary") or [])
        rows.append({
            "kind": "reading_glossary", "week": week,
            "authored": g_authored,
            "delivered": sum(1 for g in ((passage or {}).get("glossary") or [])
                             if g.get("word")),
            "route": "practice site reading page — words to help you",
            "tracked_as": "reading",
        })

        # --- mediation (Phase 11B, weekly, rolled out level by level) ---
        med = curriculum.get_mediation_for_week(week, level)
        has_med = bool(med and med.get("source") and (med.get("key_points") or []))
        authored_med = 1 if (level in curriculum.mediation_levels()
                             and week in (curriculum._mediation_data.get(level) or {})) else 0
        rows.append({
            "kind": "mediation_task", "week": week,
            "authored": authored_med,
            "delivered": 1 if (authored_med and has_med) else 0,
            "route": "practice site mediation page (curriculum.get_mediation_for_week)",
            "tracked_as": "mediation",
        })
        # The key points ARE the assessment criteria — a task with a source but
        # no checkable points would be unmarkable, so they are ledgered.
        kp = (med or {}).get("key_points") or []
        rows.append({
            "kind": "mediation_key_points", "week": week,
            "authored": len(kp),
            "delivered": sum(1 for p in kp if p.get("en")),
            "route": "practice site mediation page — did you pass on everything?",
            "tracked_as": "mediation",
        })
        sig = (med or {}).get("signal_phrases") or []
        rows.append({
            "kind": "mediation_signal_phrases", "week": week,
            "authored": len(sig),
            "delivered": sum(1 for s in sig if s.get("en")),
            "route": "practice site mediation page — if you do not understand",
            "tracked_as": "mediation",
        })

        # --- extended listening (Phase 11D, weekly, rolled out level by level)
        bc = curriculum.get_broadcast_for_week(week, level)
        has_bc = curriculum.broadcast_is_deliverable(bc)
        authored_bc = 1 if (level in curriculum.broadcast_levels()
                            and week in (curriculum._broadcast_data.get(level) or {})) else 0
        rows.append({
            "kind": "broadcast_script", "week": week,
            "authored": authored_bc,
            "delivered": 1 if (authored_bc and has_bc) else 0,
            "route": "practice site extended listening page (curriculum.get_broadcast_for_week)",
            "tracked_as": "broadcast",
        })
        # Segments are the actual spoken audio. A segment with no text is a
        # silent turn, so it is authored-but-undelivered rather than ignored.
        segs = (bc or {}).get("segments") or []
        rows.append({
            "kind": "broadcast_segments", "week": week,
            "authored": len(segs),
            "delivered": sum(1 for s in segs if (s.get("text") or "").strip()),
            "route": "practice site extended listening page — audio playback",
            "tracked_as": "broadcast",
        })
        # The gist question is the one item that carries the descriptor: it is
        # asked before the transcript unlocks, so it is what proves the student
        # understood by EAR. Ledgered separately from the detail questions so a
        # script that quietly lost it shows up as a shortfall.
        gist = (bc or {}).get("gist_question") or {}
        rows.append({
            "kind": "broadcast_gist_question", "week": week,
            "authored": 1 if authored_bc else 0,
            "delivered": 1 if (gist.get("q") and gist.get("options")
                               and isinstance(gist.get("answer"), int)
                               and 0 <= gist["answer"] < len(gist["options"])) else 0,
            "route": "practice site extended listening page — main-point question",
            "tracked_as": "broadcast",
        })
        bq = (bc or {}).get("questions") or []
        rows.append({
            "kind": "broadcast_questions", "week": week,
            "authored": len(bq),
            "delivered": sum(
                1 for q in bq
                if q.get("q") and q.get("options")
                and isinstance(q.get("answer"), int)
                and 0 <= q["answer"] < len(q["options"])
            ),
            "route": "practice site extended listening page — detail questions",
            "tracked_as": "broadcast",
        })
        bg = (bc or {}).get("glossary") or []
        rows.append({
            "kind": "broadcast_glossary", "week": week,
            "authored": len(bg),
            "delivered": sum(1 for g in bg if g.get("word")),
            "route": "practice site extended listening page — words to listen for",
            "tracked_as": "broadcast",
        })

        # --- week-level fields that used to have no surface at all ---
        week_data = curriculum._weekly_data.get(f"{level}_{week}", {}) or {}
        for field, route in (
            ("phoneme_focus", "practice site accent page — this week's sound focus"),
            ("grammar_point", "practice site grammar page — 'In short' gloss"),
        ):
            value = week_data.get(field)
            rows.append({
                "kind": field, "week": week,
                "authored": 1 if value else 0,
                "delivered": 1 if value else 0,
                "route": route, "tracked_as": "-",
            })

        # --- can-do goals: shown during study, not only after ---
        codes = curriculum.get_can_do_for_week(week, level)
        resolved = curriculum.get_can_do_details_for_week(week, level)
        rows.append({
            "kind": "can_do_goals", "week": week,
            "authored": len(codes), "delivered": len(resolved),
            "route": "daily task message + day index goals card",
            "tracked_as": "-",
        })
    return rows


def shortfalls(level: str) -> list[dict]:
    """Atom rows where fewer atoms are delivered than authored."""
    return [r for r in _atom_rows(level) if r["delivered"] < r["authored"]]


def untaught_descriptors(level: str) -> set:
    """Descriptors in the level's library that NO week of that level targets.

    A DESCRIPTOR-coverage gap, not a delivery gap: the descriptor exists and
    is honestly published, but no week teaches it — so the level cannot claim
    full CEFR coverage until a week does.
    """
    library = set(curriculum.can_do_descriptor_map(level))
    taught = set()
    for week in range(1, curriculum.max_week_for_level(level) + 1):
        taught.update(curriculum.get_can_do_for_week(week, level))
        # Task content can also target descriptors the week file does not
        # list. Reading passages carry their own `can_do` (that is the whole
        # point of adding the mode: to close the `.R.` descriptors), and a
        # descriptor is only counted as taught if the passage is actually
        # authored AND reachable -- claiming it from an empty file would make
        # this report lie.
        passage = curriculum.get_reading_for_week(week, level)
        if passage and passage.get("text"):
            taught.update(passage.get("can_do") or [])
        med = curriculum.get_mediation_for_week(week, level)
        if med and med.get("source") and (med.get("key_points") or []):
            taught.update(med.get("can_do") or [])
        # Phase 11D — extended listening. Only a script with real spoken
        # segments AND a gist question counts: a file that plays silence, or one
        # that never asks for the main point, teaches none of the descriptors it
        # names.
        bc = curriculum.get_broadcast_for_week(week, level)
        if curriculum.broadcast_meets_descriptor_bar(bc, level):
            taught.update(bc.get("can_do") or [])
    return library - taught


def unevidenceable_descriptors(level: str) -> dict:
    """{code: why} for descriptors a student at this level can never PROVE.

    `untaught_descriptors` asks "does a week target this?". That is necessary and
    not sufficient, and the gap between the two is where C1 and C2 were quietly
    sitting: both reported "20 descriptors — OK" while eleven of their forty
    could not be evidenced by any exercise a student could actually do.

    Two ways a descriptor ends up unprovable:

      * its only evidence routes are exercises with NO CONTENT at this level.
        C1.M.1-M.4 could only be proven by `mediation`, and C1 has no mediation
        tasks, so a C1 student's certificate would show them unevidenced for
        ever and the level completion contract could never be satisfied.
      * it has no evidence route at all.

    Reported separately from `untaught_descriptors` because the fix is different:
    an untaught descriptor needs a week to target it, an unevidenceable one needs
    the exercise to exist at that level.
    """
    library = curriculum.can_do_descriptor_map(level)
    routes: dict = {}
    for week in range(1, curriculum.max_week_for_level(level) + 1):
        for code, exercises in curriculum.descriptor_evidence_map(week, level).items():
            routes.setdefault(code, set()).update(exercises)

    out = {}
    for code in library:
        allowed = routes.get(code) or set()
        if not allowed:
            out[code] = "no exercise can evidence it at all"
            continue
        real = {e for e in allowed
                if curriculum.exercise_has_content(e, level)}
        if not real:
            missing = ", ".join(sorted(allowed))
            out[code] = (f"only provable by [{missing}], which has no authored "
                         f"content at {level}")
    return out


def report() -> dict:
    """The full ledger: per-level totals, shortfalls, and descriptor gaps."""
    levels = {}
    totals = {}
    all_shortfalls = []
    all_untaught = set()
    all_unprovable: dict = {}
    for level in CEFR_LEVELS:
        rows = _atom_rows(level)
        by_kind = {}
        for r in rows:
            k = by_kind.setdefault(r["kind"], {"authored": 0, "delivered": 0,
                                              "route": r["route"],
                                              "tracked_as": r["tracked_as"]})
            k["authored"] += r["authored"]
            k["delivered"] += r["delivered"]
        short = [r for r in rows if r["delivered"] < r["authored"]]
        untaught = untaught_descriptors(level)
        unprovable = unevidenceable_descriptors(level)
        all_shortfalls.extend({**r, "level": level} for r in short)
        all_untaught |= untaught
        for kind, v in by_kind.items():
            t = totals.setdefault(kind, {"authored": 0, "delivered": 0})
            t["authored"] += v["authored"]
            t["delivered"] += v["delivered"]
        levels[level] = {
            "weeks": curriculum.max_week_for_level(level),
            "by_kind": by_kind,
            "shortfalls": short,
            "untaught_descriptors": sorted(untaught),
            "unevidenceable_descriptors": unprovable,
            "descriptors_in_library": len(curriculum.can_do_descriptor_map(level)),
        }
        all_unprovable.update({f"{level}:{k}": v for k, v in unprovable.items()})
    authored = sum(v["authored"] for v in totals.values())
    delivered = sum(v["delivered"] for v in totals.values())
    return {
        "levels": levels,
        "totals": totals,
        "authored_atoms": authored,
        "delivered_atoms": delivered,
        "orphaned_atoms": authored - delivered,
        "shortfalls": all_shortfalls,
        "untaught_descriptors": sorted(all_untaught),
        "unevidenceable_descriptors": all_unprovable,
        # Only the reservations still OUTSTANDING. One whose scenes now carry
        # authentic audio has been paid off and stops being reported, so the
        # ledger reflects reality without anyone editing this file that day.
        "taught_with_reservation": open_reservations(),
        "reservations_closed_by_authentic_audio": sorted(
            code for code in TAUGHT_WITH_RESERVATION
            if reservation_is_closed(code)),
        "tracked_exercises": list(database.TRACKED_EXERCISES),
        "weekly_exercises": list(database.WEEKLY_EXERCISES),
    }


def format_report(rep: dict = None) -> str:
    """Human-readable ledger (used by the CLI and by failure messages)."""
    rep = rep or report()
    out = ["CONTENT COVERAGE LEDGER", "=" * 72, ""]
    out.append(f"{'atom kind':<22}{'authored':>10}{'delivered':>11}{'gap':>7}   route")
    out.append("-" * 110)
    for kind in sorted(rep["totals"]):
        t = rep["totals"][kind]
        gap = t["authored"] - t["delivered"]
        sample_route = ""
        for lvl in rep["levels"].values():
            if kind in lvl["by_kind"]:
                sample_route = lvl["by_kind"][kind]["route"]
                break
        flag = "" if gap == 0 else "  <== ORPHANED"
        out.append(f"{kind:<22}{t['authored']:>10}{t['delivered']:>11}{gap:>7}   {sample_route}{flag}")
    out.append("-" * 110)
    out.append(f"{'TOTAL':<22}{rep['authored_atoms']:>10}{rep['delivered_atoms']:>11}"
               f"{rep['orphaned_atoms']:>7}")
    out.append("")
    if rep["orphaned_atoms"]:
        out.append("ORPHANED ATOMS (authored but not reaching students):")
        for s in rep["shortfalls"][:40]:
            out.append(f"  {s['level']} week {s['week']:>2} {s['kind']}: "
                       f"{s['delivered']}/{s['authored']}")
    else:
        out.append("DELIVERY: 100% — every authored atom has a student-facing route.")
    out.append("")
    out.append("DESCRIPTOR COVERAGE (does each level teach what it claims?)")
    for level, data in rep["levels"].items():
        n = len(data["untaught_descriptors"])
        u = len(data.get("unevidenceable_descriptors") or {})
        bits = []
        if n:
            bits.append(f"{n} NOT taught by any week")
        if u:
            bits.append(f"{u} taught but NOT PROVABLE")
        mark = " · ".join(bits) if bits else "OK"
        out.append(f"  {level}: {data['descriptors_in_library']:>2} descriptors — {mark}")
    if rep["untaught_descriptors"]:
        out.append("")
        out.append("  Still untaught, and what each one needs:")
        for code in rep["untaught_descriptors"]:
            need = DESCRIPTOR_GAP_PLAN.get(code, "NO PLAN RECORDED — fix this")
            out.append(f"    {code:<8} {need}")
        out.append("  (reading authored for: "
                   + ", ".join(curriculum.reading_levels() or ["none"])
                   + " · mediation authored for: "
                   + ", ".join(curriculum.mediation_levels() or ["none"])
                   + " — remaining levels pending, spec Phase 11B)")
    else:
        out.append("")
        out.append("  Every descriptor every level publishes is taught by at "
                   "least one week of that level.")

    # A descriptor a student can never PROVE is a coverage claim that cannot be
    # cashed. Reported separately from "untaught", because the fix is different:
    # untaught needs a week to target it, unprovable needs the exercise to exist
    # at that level.
    if rep.get("unevidenceable_descriptors"):
        out.append("")
        out.append("PUBLISHED BUT NOT PROVABLE  <== a student can never produce this evidence")
        for key in sorted(rep["unevidenceable_descriptors"]):
            level, code = key.split(":", 1)
            out.append(f"  {level} {code:<8} {rep['unevidenceable_descriptors'][key]}")
        out.append("  Effect: the certificate shows these permanently unevidenced,")
        out.append("  and the level completion contract can never be satisfied.")

    # Printed HERE, immediately under the coverage summary, and never in a
    # separate report: a reservation that a reader has to go looking for is not
    # a disclosure. "OK" above and this block belong on the same screen.
    if rep.get("taught_with_reservation"):
        out.append("")
        out.append("TAUGHT, WITH A STATED RESERVATION")
        out.append("  These are counted as taught above. Each one is genuinely "
                   "taught, and each falls")
        out.append("  short of what the descriptor literally says in a specific, "
                   "recorded way.")
        for code, r in sorted(rep["taught_with_reservation"].items()):
            out.append("")
            out.append(f"  {code} — {_wrap(r.get('descriptor', ''), 6)}")
            out.append(f"      taught by:  {_wrap(r.get('taught_by', ''), 18)}")
            out.append(f"      shortfall:  {_wrap(r.get('reservation', ''), 18)}")
            out.append(f"      closed by:  {_wrap(r.get('removed_by', ''), 18)}")
    return "\n".join(out)


def _wrap(text: str, indent: int, width: int = 88) -> str:
    """Soft-wrap a long reservation string for terminal reading."""
    words = (text or "").split()
    lines, current = [], ""
    for w in words:
        if current and len(current) + 1 + len(w) > width - indent:
            lines.append(current)
            current = w
        else:
            current = f"{current} {w}".strip()
    if current:
        lines.append(current)
    pad = " " * indent
    return f"\n{pad}".join(lines)


def main():  # pragma: no cover - CLI convenience
    logging.basicConfig(level=logging.WARNING)
    curriculum.load_all()
    rep = report()
    print(format_report(rep))
    return 1 if rep["orphaned_atoms"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
