"""Empire English Chronicles — THE STORY BIBLE (recurring characters + genres).

Where `sawt_cast` answers "who speaks with which voice", this module answers
"who ARE these people, and what kind of story are we telling this arc". It is the
narrative source of truth the generator draws on so the series feels *authored*,
not freshly hallucinated every day:

  * CHARACTERS — the recurring cast's story-facing identity (who they are, how they
    behave, what they want). Every character is keyed to a real `sawt_cast` entry,
    so the writer can never introduce someone the renderer cannot voice (R6.2).

  * GENRES — a small, learner-safe palette (mystery, adventure, everyday,
    wonder/sci-fi, legend). Each genre carries a default MOOD (a real
    `podcast_lab` mood) and setting seeds, so a new arc gets a concrete premise and
    the audio has a bed that fits.

  * THE SIGNATURE — two touches that make the whole series cohere across arcs:
      - a recurring MOTIF (a small object/symbol that quietly reappears), giving
        long-time listeners something to notice;
      - the LISTENER ECHO — the idea that a past audience choice can be referenced
        later, so votes feel consequential.
    These are exposed as data + helpers here; the generator weaves them in, and the
    validator can check for them.

Pure data and pure functions only — no LLM calls, no file/network I/O — so it is
trivially testable and safe to import anywhere.
"""
from __future__ import annotations

from . import sawt_cast


# --- Recurring characters -------------------------------------------------------
#
# Keyed by the SAME keys as sawt_cast.CAST, so voice + identity never drift apart.
# `archetype` is the slot a genre can cast into; `want` gives the writer a spine
# for the character's choices; `arc_role` says how central they usually are.
CHARACTERS = {
    "narrator": {
        "cast_key": "narrator",
        "archetype": "host",
        "want": "to guide the listener and make them feel the story is for them",
        "arc_role": "constant",
        "traits": ["warm", "patient", "a little playful"],
    },
    "maya": {
        "cast_key": "maya",
        "archetype": "protagonist",
        "want": "to understand things others walk past, and to do the brave thing",
        "arc_role": "lead",
        "traits": ["curious", "brave", "thinks out loud"],
    },
    "leo": {
        "cast_key": "leo",
        "archetype": "loyal-friend",
        "want": "to keep the people he loves safe, even when it means saying 'wait'",
        "arc_role": "lead",
        "traits": ["cautious", "loyal", "dry humour"],
    },
    "sara": {
        "cast_key": "sara",
        "archetype": "spark",
        "want": "to try the idea nobody else dares to say out loud",
        "arc_role": "recurring",
        "traits": ["bright", "quick", "funny"],
    },
    "mrs_adel": {
        "cast_key": "mrs_adel",
        "archetype": "mentor",
        "want": "to help the young ones find the answer themselves",
        "arc_role": "recurring",
        "traits": ["gentle", "wise", "knows more than she says"],
    },
    "stranger": {
        "cast_key": "stranger",
        "archetype": "enigma",
        "want": "unknown — and that is the point",
        "arc_role": "guest",
        "traits": ["mysterious", "cold", "never explains"],
    },
    "child": {
        "cast_key": "child",
        "archetype": "innocent",
        "want": "to ask the question everyone else is afraid to ask",
        "arc_role": "guest",
        "traits": ["curious", "fearless", "honest"],
    },
}

# The two leads who anchor most arcs (kept small so a learner can follow).
CORE_LEADS = ["maya", "leo"]


# --- Genre palette --------------------------------------------------------------
#
# Small and warm on purpose: NO horror, NO real violence — this is a learner
# podcast. Each genre names a real podcast_lab MOOD (so a bed exists) and a set of
# setting seeds a new arc can be built from. `hook` is the engine of that genre.
GENRES = {
    "mystery": {
        "mood": "mystery",
        "hook": "something small is out of place, and no one else has noticed",
        "settings": ["an old library after closing", "a quiet seaside town",
                     "a locked room in a museum", "a train that never stops"],
        "curiosity": "unanswered-question",
    },
    "adventure": {
        "mood": "triumph",     # canonical podcast_lab mood; bold, forward-moving
        "hook": "a map, a message, or a chance pulls them somewhere new",
        "settings": ["a mountain village", "a busy foreign market", "a river delta",
                     "an island reached only at low tide"],
        "curiosity": "ticking-clock",
    },
    "everyday": {
        "mood": "warm",
        "hook": "an ordinary day turns on one small, human decision",
        "settings": ["a school on exam week", "a family cafe", "a new neighbourhood",
                     "a first day at a new job"],
        "curiosity": "two-branches",
    },
    "wonder": {
        "mood": "wonder",
        "hook": "something gently impossible happens, and it seems to want something",
        "settings": ["a town where the lights hum at night", "a garden that changed",
                     "a radio that answers back", "a star that appeared this week"],
        "curiosity": "reframing-reveal",
    },
    "legend": {
        "mood": "eerie",
        "hook": "an old local story turns out to be truer than anyone admits",
        "settings": ["a village with an old rule", "a bridge with a name",
                     "a festival that repeats", "a well nobody uses"],
        "curiosity": "reframing-reveal",
    },
}

# Rotation order — arcs step through this so genres never repeat back-to-back and
# the series feels varied over a month rather than a week.
GENRE_ROTATION = ["mystery", "everyday", "adventure", "wonder", "legend"]

# Arc length window (spec 4.3 / R6.1). Default sits inside 5–7.
ARC_MIN_EPISODES = 5
ARC_MAX_EPISODES = 7
ARC_DEFAULT_EPISODES = 6


# --- The signature: motif + listener echo --------------------------------------
#
# A recurring symbol that can appear quietly in any arc. Long-time listeners start
# to notice it; new listeners never feel lost, because it is only ever texture.
MOTIF = {
    "name": "the brass key",
    "note": ("A small brass key with a worn ribbon. It turns up where it shouldn't, "
             "opens more than it should, and is never fully explained. Use it as "
             "quiet texture — a glimpse, a mention — not as the plot itself."),
}


# --- Helpers --------------------------------------------------------------------

def next_genre(previous_genre: str | None) -> str:
    """The next genre in the rotation, guaranteed different from `previous_genre`.

    Rotation gives variety over time; the explicit 'different from last' guard makes
    task 4.3 (a new arc has a DIFFERENT genre) structurally true even if the
    rotation list is ever reordered."""
    if previous_genre not in GENRE_ROTATION:
        return GENRE_ROTATION[0]
    i = GENRE_ROTATION.index(previous_genre)
    nxt = GENRE_ROTATION[(i + 1) % len(GENRE_ROTATION)]
    if nxt == previous_genre:                        # single-item list edge case
        return nxt
    return nxt


def genre_mood(genre: str) -> str:
    """The default podcast_lab mood for a genre (falls back to 'warm')."""
    return GENRES.get(genre, {}).get("mood", "warm")


def setting_for(genre: str, arc_index: int) -> str:
    """Pick a setting seed for a new arc, deterministically rotated by arc index so
    two arcs of the same genre don't reuse the same setting immediately."""
    seeds = GENRES.get(genre, {}).get("settings") or ["a small town"]
    return seeds[arc_index % len(seeds)]


def speaking_names() -> list:
    """Display names the writer may use — delegated to the cast registry so the two
    can never disagree."""
    return sawt_cast.speaking_names()


def character_brief() -> str:
    """A story-facing description of the recurring cast for the generation prompt.

    Richer than sawt_cast.cast_brief(): includes each character's WANT, which is
    what lets the writer make them act consistently across episodes."""
    order = ["narrator", "maya", "leo", "sara", "mrs_adel", "stranger", "child"]
    lines = []
    for key in order:
        c = CHARACTERS.get(key)
        if not c:
            continue
        e = sawt_cast.CAST[c["cast_key"]]
        traits = ", ".join(c["traits"])
        lines.append(f"- {e['display']} ({e['gender']}, {c['archetype']}): "
                     f"{traits}. Wants {c['want']}.")
    return "\n".join(lines)


def leads_for_arc(genre: str) -> list:
    """Display names of the leads to anchor an arc. Maya + Leo always anchor; a
    genre may add a natural third so casts feel a little different per arc."""
    leads = list(CORE_LEADS)
    third = {"mystery": "mrs_adel", "adventure": "sara", "everyday": "sara",
             "wonder": "child", "legend": "mrs_adel"}.get(genre)
    if third and third not in leads:
        leads.append(third)
    return [sawt_cast.CAST[k]["display"] for k in leads]


def new_arc_seed(previous_genre: str | None, arc_index: int) -> dict:
    """Everything needed to OPEN a new arc: a different genre, a concrete setting, a
    premise hook, its default mood, the leads, and how many episodes it should run.
    Consumed by generate_daily_story when an arc resolves (task 4.3)."""
    genre = next_genre(previous_genre)
    g = GENRES[genre]
    return {
        "genre": genre,
        "setting": setting_for(genre, arc_index),
        "premise": g["hook"],
        "mood": g["mood"],
        "curiosity": g["curiosity"],
        "leads": leads_for_arc(genre),
        "planned_episodes": ARC_DEFAULT_EPISODES,
    }
