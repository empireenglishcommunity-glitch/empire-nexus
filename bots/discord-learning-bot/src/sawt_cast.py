"""Empire English Chronicles — THE CAST REGISTRY (single source of truth).

Which character speaks with which voice, at what pace. The story generator and the
audio renderer both read THIS file, so it is structurally impossible for the writer
to invent a character the renderer cannot voice (spec R2.7, R6.2).

HOW THIS CAST WAS CHOSEN — by measurement, not by adjective (spec R2.3)
----------------------------------------------------------------------
The previous cast was picked by ear from amateur reference clips and three of four
voices were rejected by the owner as unclear. This one was selected with
`scripts/benchmark_story_voices.py`, scoring every American Kokoro voice against
`src/audio_standards.py`. Three findings drove the result:

1. **Every Kokoro voice scored WER 0.0** at normal speed — perfect intelligibility —
   against 5.45% measured on a real cloned-voice episode. That is the whole reason
   for the engine switch: deterministic, repeatable clarity.

2. **The ranking CHANGES with delivery speed.** `am_eric` ranked #1 at speed 1.0 but
   degraded to WER 0.04 when slowed for learners; `af_river` and `af_sarah` FAILED
   outright at slow speed (0.077 / 0.083). Voices are therefore benchmarked at the
   speed they will actually be used at — this is precisely the class of mistake that
   produced "sometimes good, sometimes bad".

3. **`am_michael` fails the naturalness gate** (flatness 0.014-0.015 at both speeds,
   limit 0.012). It had previously been used for the narrator — and the owner still
   reported that narrator as unclear. The metric agreed with his ear.

4. **Some voices GLITCH when slowed** — internal discontinuities (audible clicks),
   measured with the hard-cut detector. It is both voice- AND speed-dependent:
   `am_adam` gave 0 clicks at speed 0.70 but 3 at 0.644. Worst offenders measured
   `am_puck` 5-9 and `af_jessica` 6; they were dropped from an earlier draft cast.

   **However — the de-click repair stage in the render chain takes EVERY cast voice
   to 0 clicks after mastering** (verified for all six: raw 0-3 → 0 after
   master+declick). So a small source-glitch count is NOT disqualifying; the
   authoritative measurement is the MASTERED output, which is what the quality gate
   inspects. Prefer glitch-free sources, but do not reject a voice the owner likes
   over a glitch the pipeline provably repairs.

5. **WER must be measured over a realistic PASSAGE, not short sentences.** On a
   14-word sentence a single ASR hallucination is 7.1% WER — which made all nine
   candidate voices look identical and "failing". The same voice over a 60-word
   passage measures **0.0000**. Short-sentence worst-case WER is measurement noise;
   score voices on passage-length text, as episodes actually are.

Distinctness (spec R2.5) was then maximised over the six glitch-free voices. Because
only three glitch-free male voices exist, the cast uses all three; the closest pair
is `am_onyx` (Narrator, 83Hz) and `am_echo` (The Stranger, 103Hz) at MFCC 22.8 with
a 20Hz pitch gap. They are assigned to characters who rarely converse (the Stranger
speaks ~2 lines an episode, in a very different register), and this pair is flagged
for the owner's listening checkpoint. **Honest note:** there is no validated MFCC
threshold for "distinct enough" — the ear is the arbiter, which is what the
checkpoint is for. Distinctness always comes from genuinely DIFFERENT VOICES, never
from processing one voice into several.

PROHIBITED (spec R2.4) — both were tried and measurably made things worse:
  * never pitch-shift a voice reference (displaces formants → synthetic timbre);
  * never time-stretch rendered speech (phase vocoder smears consonants → unclear).
Pace is set NATIVELY at synthesis time via `speed` below.
"""

# Engine identifiers.
ENGINE_KOKORO = "kokoro"     # deterministic studio TTS — the default for all AI cast
ENGINE_CLONE = "clone"       # Chatterbox voice clone — used ONLY for real people

# Mai's consented voice reference (see content/voice-clone-consent.md).
CLONE_REF_MAI = "voices/mai_voice.ogg"

# Relative delivery pace, applied on top of the level's CEFR pace (see
# `speed_for_level`). 1.0 = the level's normal pace; below 1.0 = slower/heavier.
# The NARRATOR is deliberately slower — storytelling cadence, and it is the voice a
# learner leans on most.
CAST = {
    "narrator": {
        "display": "Narrator",
        "gender": "male",
        "engine": ENGINE_KOKORO,
        # OWNER-CHOSEN (2026-09-06): picked by ear from three measured-equal options
        # ("I liked this narrator very much"). The warmest and slowest of the three
        # — the most storyteller-like — which is exactly the brief for this role.
        # Measured at narrator speed: 0 glitches, WER 0.0000, flatness 0.00232.
        "voice_id": "am_santa",
        "speed_factor": 0.92,           # slower than the cast: storytelling
        "match": ("narrator", "host", "storyteller", "narration"),
        "role": "Warm, deliberate host. Tells the story and speaks to the audience.",
        "benchmark": {"passage_wer": 0.0, "flatness": 0.00232, "glitches": 0,
                      "owner_approved": True},
    },
    "maya": {
        "display": "Maya",
        "gender": "female",
        "engine": ENGINE_CLONE,         # Mai's REAL voice — the owner's requirement
        "clone_ref": CLONE_REF_MAI,
        "speed_factor": 1.0,
        "match": ("maya", "mai"),
        "role": "The protagonist. Curious, brave, thinks out loud.",
        "benchmark": {"note": "real consented human voice; accepted by the owner"},
    },
    "leo": {
        "display": "Leo",
        "gender": "male",
        "engine": ENGINE_KOKORO,
        "voice_id": "am_adam",          # ~120Hz, classic American male
        "speed_factor": 1.0,
        "match": ("leo",),
        "role": "Cautious, loyal friend. Voice of hesitation and warning.",
        "benchmark": {"worst_wer": 0.0, "flatness": 0.00240, "glitches": 0},
    },
    "stranger": {
        "display": "The Stranger",
        "gender": "male",
        "engine": ENGINE_KOKORO,
        "voice_id": "am_echo",          # ~103Hz — glitch-free at slow speed
        "speed_factor": 0.90,           # slower = colder, more deliberate
        "match": ("stranger", "figure", "shadow", "keeper"),
        "role": "Mysterious presence. Speaks rarely, slowly, and never explains.",
        "benchmark": {"worst_wer": 0.0, "flatness": 0.00272, "glitches": 0},
    },
    "sara": {
        "display": "Sara",
        "gender": "female",
        "engine": ENGINE_KOKORO,
        "voice_id": "af_aoede",         # ~177Hz, bright — glitch-free at slow speed
        "speed_factor": 1.04,
        "match": ("sara", "sarah"),
        "role": "Bright, quick-thinking friend. Optimistic and funny.",
        "benchmark": {"worst_wer": 0.0, "flatness": 0.00062, "glitches": 0},
    },
    "mrs_adel": {
        "display": "Mrs. Adel",
        "gender": "female",
        "engine": ENGINE_KOKORO,
        "voice_id": "af_kore",          # ~144Hz, lower/steadier — glitch-free
        "speed_factor": 0.94,
        "match": ("mrs", "mrs.", "adel", "teacher", "elder", "grandmother"),
        "role": "Older mentor. Calm, gentle, knows more than she says.",
        "benchmark": {"worst_wer": 0.0, "flatness": 0.00129, "glitches": 0},
    },
    "child": {
        "display": "Nour",
        "gender": "female",
        "engine": ENGINE_KOKORO,
        "voice_id": "af_nova",          # ~153Hz — glitch-free at slow speed
        "speed_factor": 1.06,
        "match": ("nour", "child", "kid", "little"),
        "role": "A curious child. Asks the questions everyone else is afraid to.",
        "benchmark": {"worst_wer": 0.0, "flatness": 0.00118, "glitches": 0},
    },
}

# Unknown speakers fall back to the narrator rather than silently inheriting another
# character's voice (the old cloning engine's worst failure mode).
DEFAULT_CHARACTER = "narrator"

# CEFR pace → native synthesis speed. The practice site's measured per-level word-
# rate targets are the reference; Kokoro's American voices run ~185-215 wpm at
# speed 1.0, so these factors bring each level near its target. Set natively at
# synthesis time — NEVER by stretching rendered audio.
PACE_SPEED = {
    "very_slow": 0.62,      # A1
    "slow": 0.70,           # A2   (the speed the cast was benchmarked at)
    "moderate": 0.82,       # B1
    "natural": 0.92,        # B2
    "fast": 1.0,            # C1
    "native": 1.08,         # C2
}
DEFAULT_PACE_SPEED = 0.70


def speed_for_level(level: str, character_key: str = None) -> float:
    """Native synthesis speed for `level`, optionally scaled by the character's own
    `speed_factor` (so the narrator is slower than the cast at every level)."""
    try:
        from . import config                                     # noqa: PLC0415
        pace = config.podcast_level_profile(level).get("pace", "slow")
    except Exception:                                            # noqa: BLE001
        pace = "slow"
    base = PACE_SPEED.get(pace, DEFAULT_PACE_SPEED)
    if character_key and character_key in CAST:
        base *= float(CAST[character_key].get("speed_factor", 1.0))
    return round(base, 3)


def character_for(speaker_label: str) -> dict:
    """Map a script speaker label to its cast entry. Returns the entry plus its
    `key`. Matching is whole-word so "man" cannot fire inside "woman"; unknown
    labels fall back to the narrator."""
    import re
    low = (speaker_label or "").lower().strip()
    words = set(re.findall(r"[a-z.']+", low))
    for key, entry in CAST.items():
        for token in entry["match"]:
            if token in words or token == low:
                return {"key": key, **entry}
    return {"key": DEFAULT_CHARACTER, **CAST[DEFAULT_CHARACTER]}


def speaking_names() -> list:
    """Display names the story generator is allowed to use, in a stable order."""
    return [CAST[k]["display"] for k in CAST]


def cast_brief() -> str:
    """The cast description injected into the generation prompt, so the writer knows
    exactly who exists, their gender, and how they behave."""
    lines = []
    for key in CAST:
        e = CAST[key]
        lines.append(f"- {e['display']} ({e['gender']}) — {e['role']}")
    return "\n".join(lines)


def voices_in_use() -> dict:
    """{character key: engine-qualified voice} — used by tests to prove no two
    characters share a voice (spec R2.5)."""
    out = {}
    for key, e in CAST.items():
        out[key] = (f"{e['engine']}:{e.get('voice_id') or e.get('clone_ref')}")
    return out
