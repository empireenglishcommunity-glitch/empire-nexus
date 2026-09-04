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

from src import sawt_story  # noqa: E402

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


async def _run(out_dir: pathlib.Path, winning_choice: str) -> int:
    state = _load_state(out_dir)
    episode_number = int(state.get("episode_number", 0)) + 1
    # The winning choice comes from the CLI (the bot fills it after voting) or,
    # failing that, from whatever the bot last wrote into the state file.
    choice = winning_choice or state.get("winning_choice", "")
    prev_recap = state.get("recap", "")

    print(f"Generating Empire Chronicles episode {episode_number} "
          f"(continuing: {choice!r})")
    ep = await sawt_story.generate_episode(
        previous_summary=prev_recap, winning_choice=choice,
        episode_number=episode_number)
    if not ep:
        print("::error::story generation returned nothing (LLM unavailable?)")
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
    }
    (out_dir / "episode-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Advance state: next episode continues from THIS recap. The winning_choice
    # is reset — the bot writes the real winner after voting closes.
    _save_state(out_dir, {
        "episode_number": episode_number,
        "recap": ep["recap"],
        "winning_choice": "",
    })

    print(f"  wrote {script_path.name} — '{ep['title']}'")
    print(f"  vote A: {ep['vote_a']}")
    print(f"  vote B: {ep['vote_b']}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default="content/podcast-scripts",
                    help="where to write the script + meta + state files")
    ap.add_argument("--winning-choice", default="",
                    help="the audience's winning choice to continue from "
                         "(overrides story-state.json)")
    args = ap.parse_args()
    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    return asyncio.run(_run(out_dir, args.winning_choice))


if __name__ == "__main__":
    sys.exit(main())
