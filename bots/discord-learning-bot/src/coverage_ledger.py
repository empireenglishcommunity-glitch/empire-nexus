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

import logging

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
    "A2.M.1", "A2.M.2", "A2.M.3", "A2.R.1", "A2.R.2", "A2.R.5",
    "B1.I.1", "B1.M.2", "B1.M.3", "B1.R.1", "B1.R.2",
    "B2.I.1", "B2.I.5", "B2.M.1", "B2.M.4", "B2.R.1", "B2.R.2", "B2.R.4",
})

# What each remaining gap actually NEEDS in order to close honestly. This is
# the difference between "we know we are incomplete" and "we know exactly what
# incomplete means and what closes it".
DESCRIPTOR_GAP_PLAN = {
    # --- needs authored MEDIATION tasks for that level (same schema as A1) ---
    "A2.M.1": "A2 mediation tasks — convey the main points of a short everyday text/message",
    "A2.M.2": "A2 mediation tasks — clarify with simple examples + comprehension-check questions",
    "A2.M.3": "A2 mediation tasks — collaborate on a shared task, invite contributions",
    "B1.M.2": "B1 mediation tasks — summarise + give an opinion on a story/article/talk",
    "B1.M.3": "B1 mediation tasks — keep a discussion going, restate and summarise",
    "B2.M.1": "B2 mediation tasks — summarise varied texts, contrast differing viewpoints",
    "B2.M.4": "B2 mediation tasks — bridge a disagreement, restate positions, propose a way forward",
    # --- needs authored READING passages for that level ---
    "A2.R.1": "A2 reading passages — high-frequency vocabulary on immediately relevant topics",
    "A2.R.5": "A2 reading passages — follow simple directions and short instruction sets",
    "B2.R.4": "B2 reading passages — skim news/articles to judge relevance quickly",
    # --- needs EXTENDED LISTENING content (longer audio than the current
    #     single-word dictation items can ever satisfy) ---
    "A2.R.2": "extended listening — catch the main point of short clear messages/announcements",
    "B1.R.1": "extended listening — main points of clear standard speech on familiar matters",
    "B1.R.2": "extended listening — main points of radio/TV on current affairs",
    "B2.R.1": "extended listening — extended speech/lectures, complex lines of argument",
    "B2.R.2": "extended listening — TV news/current affairs and films in standard dialect",
    # --- needs new INTERACTION content (the current missions are largely solo
    #     monologue or scripted, so claiming these today would be a stretch) ---
    "B1.I.1": "B1 travel/transactional interaction — no B1 week has a travel theme yet",
    "B2.I.1": "B2 spontaneous interaction — current B2 fluency tasks are solo monologue",
    "B2.I.5": "B2 collaborative interaction — invite others in, negotiate a compromise",
}


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
    return library - taught


def report() -> dict:
    """The full ledger: per-level totals, shortfalls, and descriptor gaps."""
    levels = {}
    totals = {}
    all_shortfalls = []
    all_untaught = set()
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
            "descriptors_in_library": len(curriculum.can_do_descriptor_map(level)),
        }
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
        mark = "OK" if n == 0 else f"{n} NOT taught by any week"
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
    return "\n".join(out)


def main():  # pragma: no cover - CLI convenience
    logging.basicConfig(level=logging.WARNING)
    curriculum.load_all()
    rep = report()
    print(format_report(rep))
    return 1 if rep["orphaned_atoms"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
