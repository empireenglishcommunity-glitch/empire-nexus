#!/usr/bin/env python3.12
"""Empire Chronicles — daily episode GENERATOR (offline half of the daily loop).

Run by the scheduled GitHub Actions workflow (podcast-daily.yml) each day. It:
  1. reads the running story state (content/podcast-scripts/story-state.json):
     the last recap + the audience's winning A/B choice, and the episode number;
  2. asks the LLM (src.sawt_story) to write the NEXT episode continuing that
     choice — returning a title, a cast-labelled script, a recap, and the next
     A/B vote options;
  3. writes the script to content/podcast-scripts/chronicles-epNN.txt (the file
     the renderer consumes) and an episode-meta.json (title + vote options) that
     the bot reads when it posts the episode;
  4. advances story-state.json so tomorrow continues from THIS episode's recap
     (the winning choice is filled in by the bot once voting closes).

It never renders audio (the workflow's render step does that) and never posts.

Usage:
    python3.12 scripts/generate_daily_story.py \
        --out-dir content/podcast-scripts \
        [--winning-choice "open the door"]
"""
import argparse
import asyncio
import json
import pathlib
import sys

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src import sawt_story, sawt_arc  # noqa: E402

try:                                                              # Phase 5 (optional)
    from src import sawt_roster
except Exception:                                                 # noqa: BLE001
    sawt_roster = None

try:                                                              # Phase 6 (optional)
    from src import sawt_syllabus
except Exception:                                                 # noqa: BLE001
    sawt_syllabus = None

STATE_FILE = "story-state.json"


def _load_state(out_dir: pathlib.Path) -> dict:
    p = out_dir / STATE_FILE
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                        # noqa: BLE001
            pass
    # Fresh series.
    return {"episode_number": 0, "recap": "", "winning_choice": ""}


def _save_state(out_dir: pathlib.Path, state: dict):
    (out_dir / STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def _run(out_dir: pathlib.Path, winning_choice: str,
               no_cameos: bool = False) -> int:
    raw_state = _load_state(out_dir)
    # Fold in the winning choice (CLI overrides the file the bot wrote) BEFORE
    # planning, so the listener-echo history and continuity see it.
    choice = winning_choice or raw_state.get("winning_choice", "")
    if choice:
        raw_state = sawt_arc.record_winning_choice(raw_state, choice)

    # Arc lifecycle decides this episode's context: which arc, opener/finale, and
    # whether an arc must resolve now (tasks 4.2 / 4.3).
    plan = sawt_arc.plan_next_episode(raw_state)
    arc = plan["arc"]
    episode_number = plan["episode_number"]
    prev_recap = raw_state.get("recap", "")

    # Phase 6: pitch the episode at the level the active student body occupies
    # (live data, never hardcoded) and reinforce this week's curriculum words.
    # Best-effort: falls back to the story default level with no vocabulary when
    # the DB/curriculum isn't readable (e.g. offline CI), so it never blocks.
    level, week, vocabulary = sawt_story.STORY_LEVEL, None, []
    if sawt_syllabus is not None:
        try:
            syl = sawt_syllabus.plan_for_today()
            level = syl.get("level") or level
            week = syl.get("week")
            vocabulary = syl.get("vocabulary") or []
        except Exception as e:                                    # noqa: BLE001
            print(f"  (syllabus resolution skipped: {e})")
    print(f"  CEFR target: level {level}"
          + (f", curriculum week {week}" if week else "")
          + (f", reinforcing {len(vocabulary)} word(s)" if vocabulary else ""))

    print(f"Generating Empire Chronicles episode {episode_number} — "
          f"arc {arc['arc_id']} ({arc['genre']}), "
          f"episode {arc['episode_in_arc']}/{arc['planned_episodes']}"
          f"{' [OPENER]' if plan['is_arc_opener'] else ''}"
          f"{' [FINALE]' if plan['is_arc_finale'] else ''} "
          f"(continuing: {choice!r})")

    # Phase 5: pick a few learner cameos (least-recently-featured, gender-matched,
    # opt-out honoured). Best-effort: any problem or an empty roster yields NO
    # cameos and a name-free episode — it must NEVER block the daily episode.
    cameos = []
    if sawt_roster is not None and not no_cameos:
        try:
            cameos = sawt_roster.select_cameos()
        except Exception as e:                                    # noqa: BLE001
            print(f"  (cameo selection skipped: {e})")
            cameos = []
    if cameos:
        print(f"  guest learners: {', '.join(c['story_name'] for c in cameos)}")

    ep = await sawt_story.generate_episode(
        previous_summary=prev_recap, winning_choice=choice,
        episode_number=episode_number, level=level, arc=arc,
        is_arc_opener=plan["is_arc_opener"], is_arc_finale=plan["is_arc_finale"],
        past_choices=raw_state.get("past_choices", []),
        motif_seen=bool(raw_state.get("motif_seen", False)),
        student_cameos=cameos, vocabulary=vocabulary)
    if not ep:
        print("::error::story generation returned nothing "
              "(LLM unavailable or failed validation)")
        return 1

    slug = f"chronicles-ep{episode_number:02d}"
    script_path = out_dir / f"{slug}.txt"
    script_path.write_text(ep["script"].rstrip() + "\n", encoding="utf-8")

    meta = {
        "episode_number": episode_number,
        "slug": slug,
        "title": ep["title"],
        "script_path": f"content/podcast-scripts/{slug}.txt",
        "vote_a": ep["vote_a"],
        "vote_b": ep["vote_b"],
        "recap": ep["recap"],
        # Sound design + arc context the renderer and the bot post use.
        "mood": ep.get("mood") or arc.get("mood") or "warm",
        "arc_id": arc["arc_id"],
        "genre": arc["genre"],
        "episode_in_arc": arc["episode_in_arc"],
        "is_arc_finale": plan["is_arc_finale"],
        # Phase 6: the CEFR level this episode is pitched at (drives the render
        # pace + the duration gate window) and the curriculum tie-in it reinforces.
        "level": level,
        "curriculum_week": week,
        "vocabulary": vocabulary,
        # Phase 5: the learner cameos woven into this episode. The renderer reads
        # these to voice each guest with a gender-matched voice, and advances the
        # rotation bookkeeping ONLY after the episode actually emits (R9.3).
        "student_cameos": [
            {"discord_id": c.get("discord_id"), "story_name": c["story_name"],
             "gender": c.get("gender")}
            for c in cameos if c.get("story_name")
        ],
    }
    (out_dir / "episode-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Advance state: store the recap + any established facts, remember the motif,
    # and — if this was the arc finale — open the NEXT arc (a different genre) so
    # tomorrow starts fresh. The winning_choice is left for the bot to fill after
    # voting closes (record_winning_choice already reset it if we consumed one).
    new_state = sawt_arc.apply_generated(
        plan["state"], recap=ep["recap"], facts=ep.get("facts") or [],
        was_finale=plan["is_arc_finale"], motif_used=bool(ep.get("motif_used")))
    new_state["winning_choice"] = ""
    _save_state(out_dir, new_state)

    print(f"  wrote {script_path.name} — '{ep['title']}'  (mood: {meta['mood']})")
    print(f"  vote A: {ep['vote_a']}")
    print(f"  vote B: {ep['vote_b']}")
    if plan["is_arc_finale"]:
        print(f"  arc {arc['arc_id']} RESOLVED — next arc will be a new genre")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="content/podcast-scripts",
                    help="where to write the script + meta + state files")
    ap.add_argument("--winning-choice", default="",
                    help="the audience's winning choice to continue from "
                         "(overrides story-state.json)")
    ap.add_argument("--no-cameos", action="store_true",
                    help="disable student-name cameos for this run (Phase 5)")
    args = ap.parse_args()
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_run(out_dir, args.winning_choice, no_cameos=args.no_cameos))


if __name__ == "__main__":
    sys.exit(main())
