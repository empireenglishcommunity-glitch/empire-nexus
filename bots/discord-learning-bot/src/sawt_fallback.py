"""Empire English Chronicles — guaranteed FALLBACK episode (Phase: reliability).

The daily build must ALWAYS be able to produce a valid, gate-passing episode — even
when the (free-tier) LLM is rate-limited or returns nothing usable. This module
composes a hand-written, self-contained episode that:

  * uses ONLY the legal cast (Narrator / Maya / Leo / Sara / Mrs. Adel / Nour);
  * opens with a Narrator recap ("Last time …") and closes with a clear A/B vote
    prompt + a cliffhanger;
  * lands a curiosity device (an open question + a ticking clock) and touches the
    brass-key motif lightly;
  * is padded/trimmed to the TARGET LEVEL's word window so the render lands inside
    the CEFR duration gate.

It is deterministic given (episode_number) so the same day reproduces the same
fallback, and it ROTATES through several distinct vignettes so repeated fallbacks
don't feel identical. It costs nothing and never calls a network.

The result is the SAME episode dict shape sawt_story produces (title, script,
recap, facts, mood, vote_a, vote_b, motif_used), so callers can use it
interchangeably with a generated episode.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("empire-bot.sawt.fallback")

# A small bank of self-contained mystery vignettes. Each is a list of (speaker,
# line) beats. Kept simple, warm, and level-friendly; the composer pads with extra
# descriptive Narrator/dialogue beats to reach the target length for the level.
_VIGNETTES = [
    {
        "title": "The Door That Waited",
        "setting": "the old library after closing time",
        "beats": [
            ("Narrator", "Maya and Leo were still inside the library when the lights went low."),
            ("Maya", "Leo, the front door is locked. But look — that small door behind the shelves is open."),
            ("Leo", "It was closed a minute ago. I am sure of it. How did it open by itself?"),
            ("Narrator", "A thin, cold breeze came from the dark doorway. On the floor lay a small brass key with a worn ribbon."),
            ("Maya", "A key? It does not fit any lock I can see. Why is it here, and who left it?"),
            ("Leo", "We only have a few minutes before the night guard comes. We should not stay too long."),
            ("Narrator", "From somewhere beyond the door, a soft sound echoed — like a page turning on its own."),
            ("Sara", "There you are! I have been looking everywhere. Please, do not go in there alone."),
            ("Maya", "Sara, you feel it too, don't you? Something in this room is waiting for us."),
        ],
        "vote_a": "Step through the open door",
        "vote_b": "Take the key and leave the library",
    },
    {
        "title": "The Light Under the Stairs",
        "setting": "the quiet school hall at dusk",
        "beats": [
            ("Narrator", "Last time, Maya and Leo found a strange blue light under the old stairs."),
            ("Leo", "The light is still there. It was not here yesterday, and no lamp is on."),
            ("Maya", "Listen — someone is humming. A slow, sad song. Do you hear it, or is it only me?"),
            ("Narrator", "Near the bottom step, half hidden, lay a small brass key that no one remembered leaving."),
            ("Maya", "The same little key again. It keeps finding us. What does it want us to open?"),
            ("Sara", "We have maybe ten minutes before the gate is locked for the night. We must be quick."),
            ("Leo", "Then we decide now. Do we follow the light, or do we go back while we still can?"),
            ("Narrator", "The humming stopped. In the sudden quiet, the blue light grew a little brighter."),
        ],
        "vote_a": "Follow the blue light down",
        "vote_b": "Go back up before the gate locks",
    },
    {
        "title": "The Message on the Window",
        "setting": "Mrs. Adel's small shop on a rainy evening",
        "beats": [
            ("Narrator", "Previously, a strange message appeared on the misted shop window — and then faded."),
            ("Mrs. Adel", "Come in, children, out of the rain. I saw the words too. I did not write them."),
            ("Maya", "It said 'the key remembers'. Mrs. Adel, what does that mean? Who wrote it?"),
            ("Narrator", "On the counter, beside the old clock, sat a small brass key with a worn ribbon."),
            ("Leo", "That clock is running fast. We have only minutes before it strikes the hour."),
            ("Mrs. Adel", "When it strikes, the shop lights go out on their own. It happens every night now."),
            ("Maya", "Then we have to choose quickly. Do we read the message again, or follow the key?"),
            ("Narrator", "The clock ticked louder, and the misted window slowly began to shine with new words."),
        ],
        "vote_a": "Wait and read the new message",
        "vote_b": "Follow where the key leads",
    },
]

# Extra descriptive beats used to pad an episode up to the level's word target
# without adding new named characters or breaking the audio contract.
_PAD_NARRATION = [
    "The room felt very still, as if it were holding its breath.",
    "Outside, the wind pushed gently at the windows, and then went quiet again.",
    "Every small sound seemed louder now — a creak, a breath, a distant step.",
    "The shadows on the wall moved slowly, though nothing else did.",
    "For a moment, no one spoke, and the silence had a weight of its own.",
    "A faint, warm smell drifted by, like old paper and rain.",
    "Somewhere far off, a clock counted the minutes they did not have.",
    "The light flickered once, steadied, and seemed to lean toward the door.",
]
_PAD_DIALOGUE = [
    ("Maya", "Stay close. Whatever happens, we decide this together."),
    ("Leo", "I do not like this, but I will not leave you here alone."),
    ("Maya", "Breathe. Think. There is always a clue if we look carefully."),
    ("Leo", "Listen — there it is again. We are not imagining it."),
    ("Maya", "Whatever is behind this, it has been waiting a long time."),
]


def _spoken_word_count(beats) -> int:
    return sum(len(text.split()) for _spk, text in beats)


def _target_words(level: str) -> int:
    """The middle of the level's word window, so the render lands safely inside the
    duration gate. Falls back to a mid A2 value if anything is unreadable."""
    try:
        from . import sawt_script_validator as v
        lo, hi = v._level_word_window(level)
        return int(lo + (hi - lo) * 0.45)
    except Exception:                                            # noqa: BLE001
        return 640


def build_fallback_episode(episode_number: int = 1, level: str = None,
                           mood: str = "mystery",
                           previous_summary: str = "") -> dict:
    """Compose a guaranteed-valid fallback episode for `level`, sized to its CEFR
    word window. Deterministic per episode_number; rotates the vignette bank."""
    lvl = level or "A2"
    idx = (int(episode_number) - 1) % len(_VIGNETTES)
    v = _VIGNETTES[idx]

    # Opening recap (satisfies recap-at-open for episode_number > 1).
    recap_line = ("Narrator",
                  "Welcome to Empire English Chronicles. Last time, the story left "
                  "our friends with a small mystery they could not explain.")
    beats = [recap_line] + list(v["beats"])

    # Pad toward the level's word target with descriptive, on-theme beats — never
    # adding a new named character (keeps the cast legal).
    target = _target_words(lvl)
    pi = di = 0
    guard = 0
    while _spoken_word_count(beats) < target and guard < 200:
        guard += 1
        if guard % 2 == 1:
            beats.insert(len(beats) - 1,
                         ("Narrator", _PAD_NARRATION[pi % len(_PAD_NARRATION)]))
            pi += 1
        else:
            spk, line = _PAD_DIALOGUE[di % len(_PAD_DIALOGUE)]
            beats.insert(len(beats) - 1, (spk, line))
            di += 1

    # Cliffhanger + vote close (curiosity: open question '?' + ticking clock).
    beats.append(("Narrator",
                  "A sound came from the dark, and the minutes were running out. "
                  "What would they do before it was too late?"))
    beats.append(("Narrator",
                  f"Vote below. Tomorrow, the story continues the way you choose. "
                  f"Vote A: {v['vote_a']}. Vote B: {v['vote_b']}."))

    script = "\n".join(f"{spk}: {text}" for spk, text in beats)
    return {
        "title": v["title"],
        "script": script,
        "recap": (f"In {v['setting']}, Maya and Leo find the brass key again and "
                  f"must choose whether to follow the mystery or step back."),
        "facts": ["the brass key keeps reappearing",
                  f"the friends were in {v['setting']}"],
        "mood": (mood or "mystery"),
        "vote_a": v["vote_a"],
        "vote_b": v["vote_b"],
        "motif_used": True,
        "is_fallback": True,
    }
