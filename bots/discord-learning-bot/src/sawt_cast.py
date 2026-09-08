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
        # ── v1 LAUNCH DECISION (2026-09-07, owner-approved) ─────────────────
        # Maya is TEMPORARILY voiced by Kokoro instead of Mai's Chatterbox clone.
        # WHY: the clone engine is the pipeline's slowest AND flakiest part —
        # measured in CI it took ~24 min for 13 lines and randomly failed a line
        # (token-repetition -> forced EOS -> no audio), which crashed the whole
        # gated render. Kokoro-only makes the render ~3-4 min, single-engine, and
        # glitch-free, so we can SHIP a real daily episode now. Mai's real cloned
        # voice is a planned upgrade on the working system — restore by setting
        # engine=ENGINE_CLONE + clone_ref=CLONE_REF_MAI (kept below, commented).
        # ─────────────────────────────────────────────────────────────────────
        "gender": "female",
        "engine": ENGINE_KOKORO,
        "voice_id": "af_bella",         # warm, expressive young female — distinct
                                        # from Sara(af_aoede)/Mrs.Adel(af_kore)/Nour(af_nova)
        # "engine": ENGINE_CLONE, "clone_ref": CLONE_REF_MAI,  # ← restore for Mai's real voice
        "speed_factor": 1.0,
        "match": ("maya", "mai"),
        "role": "The protagonist. Curious, brave, thinks out loud.",
        "benchmark": {"note": "v1: Kokoro af_bella (temporary); Mai's clone to be "
                              "restored once the daily pipeline is proven live"},
    },
    # ── NATURALNESS RE-CAST (2026-09-08, owner feedback) ───────────────────
    # The owner found Maya (af_bella) and the Narrator (am_santa) natural, but the
    # rest robotic. Re-measured every candidate at the ACTUAL slow delivery speed
    # and matched the LIKED voices' profile — the tell for "robotic" was low PITCH
    # VARIATION (monotone): af_bella=6.0 / am_santa=7.0 semitones, while the old
    # picks were the flattest (am_echo 5.05, am_adam 5.67, and af_aoede/af_kore had
    # near-zero spectral flatness = synthetic timbre). New picks match the liked
    # profile (pitchVar ~6-7, flatness under the 0.012 gate) AND stay pitch-distinct.
    "leo": {
        "display": "Leo",
        "gender": "male",
        "engine": ENGINE_KOKORO,
        "voice_id": "am_fenrir",        # ~121Hz, expressive (pitchVar 6.20) — was am_adam (monotone 5.67)
        "speed_factor": 1.0,
        "match": ("leo",),
        "role": "Cautious, loyal friend. Voice of hesitation and warning.",
        "benchmark": {"pitch_var": 6.20, "flatness": 0.0038, "median_hz": 121},
    },
    "stranger": {
        "display": "The Stranger",
        "gender": "male",
        "engine": ENGINE_KOKORO,
        "voice_id": "am_onyx",          # ~86Hz, deep + very clean — was am_echo (monotone 5.05).
                                        # NOT am_michael: it fails the naturalness gate (0.014>0.012).
        "speed_factor": 0.94,           # deliberate, but not so slow it turns robotic
        "match": ("stranger", "figure", "shadow", "keeper"),
        "role": "Mysterious presence. Speaks rarely, slowly, and never explains.",
        "benchmark": {"pitch_var": 5.70, "flatness": 0.0001, "median_hz": 86},
    },
    "sara": {
        "display": "Sara",
        "gender": "female",
        "engine": ENGINE_KOKORO,
        "voice_id": "af_heart",         # ~186Hz, Kokoro's warmest female (pitchVar 6.68) — was af_aoede
        "speed_factor": 1.02,
        "match": ("sara", "sarah"),
        "role": "Bright, quick-thinking friend. Optimistic and funny.",
        "benchmark": {"pitch_var": 6.68, "flatness": 0.0097, "median_hz": 186},
    },
    "mrs_adel": {
        "display": "Mrs. Adel",
        "gender": "female",
        "engine": ENGINE_KOKORO,
        "voice_id": "af_river",         # ~171Hz, warm/steady mentor (6.17) — was af_kore (synthetic 0.0012)
        "speed_factor": 0.96,
        "match": ("mrs", "mrs.", "adel", "teacher", "elder", "grandmother"),
        "role": "Older mentor. Calm, gentle, knows more than she says.",
        "benchmark": {"pitch_var": 6.17, "flatness": 0.0008, "median_hz": 171},
    },
    "child": {
        "display": "Nour",
        "gender": "female",
        "engine": ENGINE_KOKORO,
        "voice_id": "af_alloy",         # ~138Hz, clean + expressive (5.88) — was af_nova.
                                        # NOT af_jessica/af_nicole (excluded: glitches / naturalness).
        "speed_factor": 1.04,
        "match": ("nour", "child", "kid", "little"),
        "role": "A curious child. Asks the questions everyone else is afraid to.",
        "benchmark": {"pitch_var": 5.88, "flatness": 0.0026, "median_hz": 138},
    },
}

# Unknown speakers fall back to the narrator rather than silently inheriting another
# character's voice (the old cloning engine's worst failure mode).
DEFAULT_CHARACTER = "narrator"


# ── GUEST LEARNER VOICES (Phase 5 cameos) ────────────────────────────────────
# Brief student cameos are voiced by dedicated GUEST voices, gender-matched, and
# deliberately DISTINCT from the fixed cast's voices so a guest never sounds like
# a lead. These Kokoro voices are not used by any CAST entry above. A cameo is
# assigned a stable voice by its name (hash), so the same guest keeps one voice
# within an episode. Gender comes from the roster (KNOWN only — never guessed).
GUEST_VOICES = {
    # Natural, gate-safe voices distinct from the fixed cast (and never the
    # excluded am_michael/af_jessica/af_nicole/am_puck). Guests are brief, so a
    # little overlap in register is fine — the ear cares most about naturalness.
    "female": ["af_sarah", "bf_isabella", "bf_emma"],
    "male": ["am_liam", "am_eric", "bm_george"],
}
GUEST_SPEED_FACTOR = 1.0

# Process-level cameo registry: {first_name_lower: {"display","gender","voice_id"}}.
# The generator/renderer registers the episode's cameos so character_for() can map
# a cameo speaker label to a real gender-matched guest voice instead of the
# narrator fallback. Cleared per render.
_CAMEO_REGISTRY: dict = {}


def register_cameos(cameos: list) -> None:
    """Register this episode's student cameos so their lines get a gender-matched
    guest voice. `cameos` is a list of {story_name, gender}. Genders other than
    male/female are IGNORED (never guessed) — such a cameo would fall back to the
    narrator rather than be assigned a gendered voice."""
    _CAMEO_REGISTRY.clear()
    for c in (cameos or []):
        name = (c.get("story_name") or "").strip()
        gender = (c.get("gender") or "").strip().lower()
        if not name or gender not in ("female", "male"):
            continue
        pool = GUEST_VOICES.get(gender) or []
        if not pool:
            continue
        # Stable per-name assignment (deterministic across attempts/retries).
        idx = (sum(ord(ch) for ch in name.lower())) % len(pool)
        _CAMEO_REGISTRY[name.lower()] = {
            "display": name, "gender": gender, "voice_id": pool[idx],
        }


def clear_cameos() -> None:
    """Forget any registered cameos (call at the end of a render)."""
    _CAMEO_REGISTRY.clear()


def _cameo_entry_for(low: str, words: set) -> dict:
    """Return a synthetic cast-style entry for a registered cameo speaker, or None.
    Matches on the cameo's first name as a whole word so 'Amina:' resolves but an
    unrelated line does not."""
    for name_low, info in _CAMEO_REGISTRY.items():
        if name_low == low or name_low in words:
            return {
                "key": f"cameo:{name_low}",
                "display": info["display"],
                "gender": info["gender"],
                "engine": ENGINE_KOKORO,
                "voice_id": info["voice_id"],
                "speed_factor": GUEST_SPEED_FACTOR,
                "match": (name_low,),
                "role": "A guest learner making a brief, friendly appearance.",
            }
    return None

# CEFR pace → native synthesis speed. The practice site's measured per-level word-
# rate targets are the reference; Kokoro's American voices run ~185-215 wpm at
# speed 1.0, so these factors bring each level near its target. Set natively at
# synthesis time — NEVER by stretching rendered audio.
# NOTE on the slow end (2026-09-08): Kokoro is trained near speed 1.0 and turns
# audibly ROBOTIC (and more glitch-prone) when pushed much below ~0.75. The old
# very_slow=0.62 / slow=0.70 were a big part of the "robotic" complaint. Raised the
# slow end toward Kokoro's natural range while keeping it clearly learner-paced;
# the CEFR duration windows still hold (verified — target_length/word-window are
# derived from these same numbers, so they move together).
PACE_SPEED = {
    "very_slow": 0.74,      # A1  (was 0.62 — too robotic)
    "slow": 0.82,           # A2  (was 0.70)
    "moderate": 0.90,       # B1
    "natural": 0.96,        # B2
    "fast": 1.0,            # C1
    "native": 1.08,         # C2
}
DEFAULT_PACE_SPEED = 0.82


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
    # Phase 5: a registered student cameo gets a gender-matched GUEST voice rather
    # than the narrator fallback, so a learner's line doesn't sound like the host.
    cameo = _cameo_entry_for(low, words)
    if cameo is not None:
        return cameo
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
