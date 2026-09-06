"""Empire English Chronicles — ARC-AWARE STORY STATE + LIFECYCLE.

`sawt_bible` says what KINDS of stories exist; this module tracks the ONE running
story's position inside them: which arc we're in, its genre/setting/premise, how
many episodes it has run, the facts it has established, and — the whole point of a
serial — WHEN an arc should resolve and a new one begin.

State shape (persisted by generate_daily_story to content/podcast-scripts/story-state.json):

    {
      "episode_number": int,        # global episode counter (back-compat)
      "recap": str,                 # last episode's recap (seeds continuity)
      "winning_choice": str,        # audience's last A/B winner (filled by the bot)
      "arc": {
        "arc_id": int,              # 1-based; increments each new arc
        "genre": str,               # a sawt_bible.GENRES key
        "setting": str,             # concrete place the arc lives in
        "premise": str,             # the arc's engine (one line)
        "mood": str,                # canonical podcast_lab mood for the bed
        "curiosity": str,           # the arc's default curiosity device
        "leads": [str],             # display names anchoring the arc
        "episode_in_arc": int,      # 1-based index WITHIN the arc
        "planned_episodes": int,    # target length (5-7)
        "established_facts": [str],  # continuity the writer must not contradict
        "previous_genre": str|None   # so the NEXT arc differs (task 4.3)
      },
      "motif_seen": bool,           # has 'the brass key' appeared in this arc yet
      "past_choices": [str]         # recent winning choices (listener-echo)
    }

Pure logic + a couple of light helpers; no LLM, no I/O. generate_daily_story owns
reading/writing the file — this module only computes the next state.
"""
from __future__ import annotations

from . import sawt_bible

# How many past winning choices to remember for the listener-echo signature.
MAX_PAST_CHOICES = 8
# Cap established facts so the prompt never grows without bound; keep the freshest.
MAX_FACTS = 12


def _blank_arc() -> dict:
    """A placeholder arc marking 'no arc yet' — episode_in_arc 0 forces a fresh arc
    to be opened on the next episode."""
    return {
        "arc_id": 0, "genre": None, "setting": "", "premise": "", "mood": "warm",
        "curiosity": "", "leads": [], "episode_in_arc": 0, "planned_episodes": 0,
        "established_facts": [], "previous_genre": None,
    }


def normalize(state: dict | None) -> dict:
    """Upgrade any older/partial state to the full arc-aware shape WITHOUT losing
    data. A pre-Phase-4 file ({episode_number, recap, winning_choice}) upgrades
    cleanly: it keeps its episode number and recap and simply gains a blank arc,
    so the next episode opens arc 1. Never raises."""
    s = dict(state or {})
    s.setdefault("episode_number", 0)
    s.setdefault("recap", "")
    s.setdefault("winning_choice", "")
    s.setdefault("motif_seen", False)
    s.setdefault("past_choices", [])
    arc = dict(s.get("arc") or {})
    base = _blank_arc()
    base.update({k: arc[k] for k in base if k in arc})
    s["arc"] = base
    return s


def start_new_arc(state: dict, arc_index_hint: int | None = None) -> dict:
    """Open a fresh arc with a genre DIFFERENT from the last one (task 4.3), a
    concrete setting, premise, mood and leads seeded from the bible. Resets the
    per-arc counters and clears the motif flag. Returns a NEW state dict."""
    s = normalize(state)
    prev_arc = s["arc"]
    previous_genre = prev_arc.get("genre") or prev_arc.get("previous_genre")
    new_arc_id = int(prev_arc.get("arc_id", 0)) + 1
    idx = arc_index_hint if arc_index_hint is not None else (new_arc_id - 1)
    seed = sawt_bible.new_arc_seed(previous_genre, idx)
    s["arc"] = {
        "arc_id": new_arc_id,
        "genre": seed["genre"],
        "setting": seed["setting"],
        "premise": seed["premise"],
        "mood": seed["mood"],
        "curiosity": seed["curiosity"],
        "leads": seed["leads"],
        "episode_in_arc": 0,          # opened but no episode run yet; the next
                                      # plan_next_episode bumps this to 1 (opener)
        "planned_episodes": int(seed["planned_episodes"]),
        "established_facts": [],
        "previous_genre": previous_genre,
    }
    s["motif_seen"] = False
    return s


def _planned(arc: dict) -> int:
    """The arc's planned length, clamped to the hard 5-7 window."""
    planned = int(arc.get("planned_episodes") or sawt_bible.ARC_DEFAULT_EPISODES)
    return max(sawt_bible.ARC_MIN_EPISODES,
               min(sawt_bible.ARC_MAX_EPISODES, planned))


def is_finale_episode(arc: dict) -> bool:
    """True when THIS arc episode (at its current episode_in_arc) is the one that
    should RESOLVE the arc — i.e. it has reached the planned length, or hit the
    hard 5-7 ceiling. The finale IS the planned-last episode, not a following one."""
    if not arc.get("genre"):
        return False
    ep = int(arc.get("episode_in_arc", 0))
    return ep >= _planned(arc) or ep >= sawt_bible.ARC_MAX_EPISODES


def plan_next_episode(state: dict) -> dict:
    """Decide the arc context for the NEXT episode to be generated, given the state
    left by the previous one. Returns a dict:

        {
          "state": <updated state to persist AFTER generation>,
          "arc": <the arc block for this episode>,
          "is_arc_opener": bool,     # first episode of a (possibly new) arc
          "is_arc_finale": bool,     # this episode should RESOLVE the arc
          "episode_number": int,     # global counter for this episode
        }

    Lifecycle rules:
      * no arc yet  -> open arc 1 (opener).
      * arc due to resolve -> this episode is the FINALE; after it, the next call
        will open a new arc.
      * otherwise   -> continue the current arc (advance episode_in_arc)."""
    s = normalize(state)
    global_ep = int(s.get("episode_number", 0)) + 1

    if not s["arc"].get("genre"):
        # No arc yet -> open arc 1 (episode_in_arc becomes 0).
        s = start_new_arc(s, arc_index_hint=0)

    if int(s["arc"].get("episode_in_arc", 0)) <= 0:
        # A freshly-opened arc (first arc, or one opened by the previous finale via
        # apply_generated) -> its first run is the OPENER.
        s["arc"]["episode_in_arc"] = 1
    else:
        # Continue the current arc: advance the within-arc index by one.
        s["arc"]["episode_in_arc"] = int(s["arc"].get("episode_in_arc", 1)) + 1

    arc = s["arc"]
    is_opener = int(arc["episode_in_arc"]) == 1
    is_finale = is_finale_episode(arc)

    s["episode_number"] = global_ep
    return {
        "state": s,
        "arc": dict(arc),
        "is_arc_opener": is_opener,
        "is_arc_finale": is_finale,
        "episode_number": global_ep,
    }


def apply_generated(state: dict, *, recap: str, facts: list | None = None,
                    was_finale: bool, motif_used: bool = False) -> dict:
    """Fold a freshly-generated episode back into the state that will be persisted.

      * always store the new recap;
      * merge any newly-established facts (deduped, capped);
      * remember whether the motif has appeared this arc;
      * if this episode was the arc FINALE, immediately open the next arc so the
        NEXT day starts fresh with a different genre (task 4.3).
    The winning_choice is intentionally left as-is (the bot fills it after voting)."""
    s = normalize(state)
    s["recap"] = (recap or "").strip()
    if facts:
        merged = list(s["arc"].get("established_facts", []))
        for f in facts:
            f = (f or "").strip()
            if f and f not in merged:
                merged.append(f)
        s["arc"]["established_facts"] = merged[-MAX_FACTS:]
    if motif_used:
        s["motif_seen"] = True
    if was_finale:
        s = start_new_arc(s)          # rotate to a new genre for tomorrow
    return s


def record_winning_choice(state: dict, choice: str) -> dict:
    """Store the audience's winning choice (called by the bot after voting), and
    push it onto the listener-echo history so a later episode can reference it."""
    s = normalize(state)
    choice = (choice or "").strip()
    s["winning_choice"] = choice
    if choice:
        past = list(s.get("past_choices", []))
        past.append(choice)
        s["past_choices"] = past[-MAX_PAST_CHOICES:]
    return s
