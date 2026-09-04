#!/usr/bin/env python3.12
"""Sawt (صوت) — OFFLINE podcast episode renderer.

This is the "render offline, publish inside" half of Podcast Studio Phase 3.
The Discord bot runs in a 512MB / 0.5-CPU container and CANNOT host a TTS engine
in-process (see the spec's Phase 3 decision and src/sawt_tts.py). So the heavy
synthesis happens HERE — in GitHub Actions (.github/workflows/podcast-render.yml)
or on any machine with the engines installed — and the finished MP3 is handed
back to the owner to attach to an episode with /create-episode.

Design guarantee: this renderer and the bot NEVER diverge on how a script is
split or which voice a speaker gets, because both import the SAME two functions
from the bot's own module:

    src.sawt_tts.parse_script(script)  -> [(speaker_label, text), ...]
    src.sawt_tts.voice_for(label)      -> {"role", "engine", ["voice_id"], ...}

Every speaker is voiced by ONE engine — Chatterbox Multilingual — which clones a
reference clip into whichever language each run needs. The owner speaks (English
AND Arabic) in the owner's own cloned voice from --ref-clip; each co-host gets a
distinct reference voice. Because it is multilingual, Arabic text is spoken AS
ARABIC rather than read out letter-by-letter (the failure of the English-only
engines).

Each line is split into Arabic-script vs English runs (split_by_language) and
each run is synthesised with the correct language_id ("ar"/"en"), then stitched.

Usage:
    python3.12 scripts/render_podcast_episode.py \
        --script episode.txt \
        --level A1 \
        --out episode.mp3 \
        [--ref-clip owner_voice_ref.wav]
"""
import argparse
import os
import pathlib
import re
import sys
import time

# Make the bot's `src` package importable whether this is run from the bot dir
# or the repo root. We only import the PURE helpers (parse_script / voice_for),
# which pull in nothing heavy.
BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src import sawt_tts  # noqa: E402  (parse_script + voice_for — no heavy deps)

# Pace descriptor (from config.PODCAST_LEVEL_PROFILES) -> a delivery-speed hint.
# Lower = slower delivery. Graded so an A1 episode is markedly slower than C2.
PACE_SPEED = {
    "very_slow": 0.72,
    "slow": 0.82,
    "moderate": 0.92,
    "natural": 1.0,
    "fast": 1.08,
    "native": 1.15,
}
DEFAULT_SPEED = 1.0

# Pauses (seconds) inserted into the stitched episode.
PAUSE_BETWEEN_SPEAKERS = 0.55   # a beat when the speaker changes
PAUSE_SAME_SPEAKER = 0.28       # a shorter beat between a speaker's own lines
PAUSE_MARKER = 0.9              # an explicit [PAUSE] marker in the script


# Arabic script Unicode blocks: Arabic (0600–06FF), Supplement (0750–077F),
# Extended-A (08A0–08FF), Presentation Forms-A (FB50–FDFF), Forms-B (FE70–FEFF).
_ARABIC_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")


def _is_arabic_char(ch: str) -> bool:
    return bool(_ARABIC_RE.match(ch))


def split_by_language(text: str) -> list:
    """Split a mixed Arabic/English line into ordered (lang, run) pairs so each
    run is synthesised with the correct Chatterbox language_id.

    lang is "ar" for Arabic-script runs and "en" for everything else (Latin,
    digits, punctuation). Neutral characters (spaces, punctuation, digits) are
    attached to the RUN THEY FOLLOW so trailing punctuation stays with its word
    and a shared separator doesn't create an empty run. Returns [] for blank
    text. Runs preserve original order, so "Good morning صباح الخير." →
    [("en","Good morning "), ("ar","صباح الخير"), ("en",".")]."""
    text = text or ""
    if not text.strip():
        return []
    runs = []
    cur_lang = None
    cur = []
    for ch in text:
        if _is_arabic_char(ch):
            lang = "ar"
        elif ch.strip() == "":
            # Whitespace/neutral: keep it in the current run rather than forcing
            # a language flip on a space.
            lang = cur_lang if cur_lang is not None else "en"
        else:
            # Latin letters, digits, punctuation → English side. Neutral-ish
            # punctuation stays with whatever run is open.
            lang = "en" if (ch.isascii() and (ch.isalnum() or ch in "'\"")) \
                else (cur_lang if cur_lang is not None else "en")
        if cur_lang is None:
            cur_lang = lang
        if lang != cur_lang:
            runs.append((cur_lang, "".join(cur)))
            cur = [ch]
            cur_lang = lang
        else:
            cur.append(ch)
    if cur:
        runs.append((cur_lang, "".join(cur)))
    # Drop runs that are only whitespace/punctuation with no speakable content,
    # merging their text into a neighbour so nothing is lost audibly.
    merged = []
    for lang, run in runs:
        if not run.strip():
            if merged:
                merged[-1] = (merged[-1][0], merged[-1][1] + run)
            elif runs:
                # leading neutral run — attach to the next by keeping it
                merged.append((lang, run))
            continue
        # A run with no letters/digits at all (pure punctuation) → fold into prev
        has_word = any(c.isalnum() or _is_arabic_char(c) for c in run)
        if not has_word and merged:
            merged[-1] = (merged[-1][0], merged[-1][1] + run)
        else:
            merged.append((lang, run))
    return [(l, r) for l, r in merged if r.strip()]


def _level_speed(level: str) -> float:
    """Map a CEFR level to a Kokoro speed via its podcast pace descriptor.
    Kept import-light: only pulls config when actually rendering."""
    try:
        from src import config
        pace = config.podcast_level_profile(level).get("pace", "natural")
    except Exception:
        pace = "natural"
    return PACE_SPEED.get(pace, DEFAULT_SPEED)


def plan(script: str) -> dict:
    """Engine-free plan (delegates to the bot's planner) so the workflow can
    print what it's about to render before touching any model."""
    return sawt_tts.plan_episode(script)


# Reference-voice clips per speaker role, PER LANGUAGE. This is the key accent
# fix: an English-speaker reference cloned into Arabic sounds non-natively
# accented, so for Arabic runs we use ResembleAI's own NATIVE ARABIC demo
# prompts (ar_f / ar_m1) and for English runs a native English prompt. Each
# co-host therefore sounds native in BOTH languages while staying a distinct
# person. The owner's clips are supplied at runtime (see _build_ref_map): ideally
# a native-Arabic recording of the owner for `ar` and an English one for `en`.
COHOST_REF_URLS = {
    "cohost_f": {
        "en": "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/en_f1.flac",
        # native female Arabic prompt → naturally-accented Arabic
        "ar": "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/ar_f/ar_prompts2.flac",
    },
    "cohost_m": {
        # no en_m demo clip exists; it_m1 is a distinct MALE English-ish timbre
        "en": "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/it_m1.flac",
        # native male Arabic prompt
        "ar": "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/ar_m1.flac",
    },
}


# ── STORYTELLING CAST (Empire Chronicles) ────────────────────────────────────
# The narrative podcast uses named CHARACTERS, not podcast "roles". Each script
# speaker label is matched (case-insensitive substring) to a voice "slot":
#   * "owner"   → the owner's cloned voice   (reference = --ref-clip)
#   * "mai"     → Mai's cloned voice         (reference = --ref-mai, consented)
#   * "builtin" → the model's native American English voice (NO reference clip)
# Each slot also carries generation tweaks so distinct characters that share a
# slot still sound a little different (pitch of delivery via exaggeration, pace
# via cfg_weight). Voice cloning copies the REFERENCE's accent, so American
# clarity for non-cloned characters comes from the built-in American voice.
#
# Matching is ordered: the FIRST character whose "match" token appears in the
# label wins, so specific names beat generic ones. Unknown speakers fall back to
# the narrator (owner). This bank is data — new characters are added here.
CHARACTER_VOICES = {
    # The recurring host/narrator — the owner's voice threads every episode.
    "narrator": {"slot": "owner", "match": ("narrator", "host", "(you)", "owner"),
                 "exaggeration": 0.55, "cfg_weight": 0.4},
    # Female lead — Mai's real, clean, expressive voice.
    "maya":     {"slot": "mai", "match": ("maya", "mai"),
                 "exaggeration": 0.7, "cfg_weight": 0.4},
    # Male character — built-in American voice, a touch more measured.
    "leo":      {"slot": "builtin_m", "match": ("leo",),
                 "exaggeration": 0.6, "cfg_weight": 0.35},
    # A spare built-in female character voice for one-off roles.
    "extra_f":  {"slot": "builtin_f", "match": ("woman", "girl"),
                 "exaggeration": 0.65, "cfg_weight": 0.4},
    # A spare built-in male voice for unnamed male one-off roles.
    "extra_m":  {"slot": "builtin_m", "match": ("man", "stranger", "guard"),
                 "exaggeration": 0.6, "cfg_weight": 0.4},
}
# Whole-word match keeps names clean: a token matches only as a standalone word
# (so "man" won't fire inside "woman"/"Alien"). Names are still substring-safe.
_DEFAULT_CHARACTER = "narrator"


def character_for(speaker_label: str) -> dict:
    """Map a script speaker label to a storytelling character voice entry.
    First matching token wins (specific names before generic words); unknown
    labels fall back to the narrator. Returns {"name", "slot", params...}."""
    low = (speaker_label or "").lower()
    words = set(re.findall(r"[a-z()]+", low))
    for name, entry in CHARACTER_VOICES.items():
        for token in entry["match"]:
            # Whole-word match (token is one of the label's words) OR the token
            # is itself the full label — avoids "man" firing inside "woman".
            if token in words or token == low.strip():
                return {"name": name, **entry}
    d = CHARACTER_VOICES[_DEFAULT_CHARACTER]
    return {"name": _DEFAULT_CHARACTER, **d}


def _to_clean_wav(ref_clip: str) -> str:
    """Chatterbox's reference loader is finicky about container formats: hand it
    an m4a (even one misnamed .wav) and its loader returns None → "'NoneType'
    object is not callable" at generate time. So ALWAYS re-decode the clip to a
    real 24kHz mono PCM WAV with librosa/soundfile (present for Kokoro) — we do
    NOT trust the file extension, because an upload/download can name m4a bytes
    ".wav". Always returns a freshly written .clean.wav."""
    import pathlib
    import librosa
    import numpy as np
    import soundfile as sf
    # librosa uses ffmpeg/audioread to decode whatever the real container is,
    # regardless of the filename's suffix.
    y, _sr = librosa.load(ref_clip, sr=24000, mono=True)
    if y is None or len(y) == 0:
        raise ValueError(f"reference clip {ref_clip!r} decoded to no audio")
    sr = 24000
    y = y.astype("float32")
    before = len(y) / sr

    # ── Reference cleanup (so the clone copies a CLEAN voice, not breaths/noise) ──
    # 1) high-pass ~70Hz to kill rumble/DC.
    try:
        import scipy.signal as ss
        b, a = ss.butter(2, 70 / (sr / 2), btype="high")
        y = ss.lfilter(b, a, y).astype("float32")
    except Exception:                                            # noqa: BLE001
        pass
    # 2) trim leading/trailing silence + breath.
    try:
        y2, _ = librosa.effects.trim(y, top_db=30)
        if len(y2) > sr * 0.5:      # keep only if trimming left real speech
            y = y2
    except Exception:                                            # noqa: BLE001
        pass
    # 3) gentle noise gate: duck (not zero) frames near the noise floor so quiet
    #    breaths/hiss between words don't get cloned, while speech stays natural.
    hop = int(sr * 0.02)
    n = len(y) // hop
    if n >= 4:
        fr = y[:n * hop].reshape(n, hop)
        e = np.sqrt((fr ** 2).mean(axis=1) + 1e-12)
        thr = float(np.percentile(e, 10)) * 3.0
        gain = np.ones(n, dtype="float32")
        gain[e < thr] = 0.25
        g = np.repeat(gain, hop)
        g = np.concatenate([g, np.ones(len(y) - len(g), dtype="float32")])
        k = max(1, int(sr * 0.01))
        g = np.convolve(g, np.ones(k) / k, mode="same").astype("float32")
        y = (y * g).astype("float32")
    # 4) peak-normalise to ~-1 dBFS.
    peak = float(np.max(np.abs(y))) if len(y) else 0.0
    if peak > 0:
        y = (y * (0.89 / peak)).astype("float32")

    out = str(pathlib.Path(ref_clip).with_suffix(".clean.wav"))
    sf.write(out, y, sr, format="WAV", subtype="PCM_16")
    print(f"  cleaned reference clip → {out} "
          f"({before:.1f}s→{len(y)/sr:.1f}s, HPF+trim+gate+norm)")
    return out


# Per-language generation settings for ChatterboxMultilingualTTS.generate().
# Two goals:
#   1. EMOTION: exaggeration > 0.5 (0.5 is flat/neutral) with a lower cfg_weight
#      keeps delivery warm and well-paced (ResembleAI's own guidance). Arabic
#      uses cfg_weight=0.0 — the documented language-transfer setting that stops
#      the reference accent bleeding into Arabic (→ natively-accented Arabic).
#   2. ANTI-HALLUCINATION: the model can otherwise repeat a phrase or emit stray
#      breaths/hums on short/cross-language segments (we measured a doubled
#      "I am from the Emirates" + hum in a gap). Lower `temperature` and a
#      higher `repetition_penalty` (default 1.2) suppress that, and a small
#      `min_p` trims low-probability garbage tokens. These are real generate()
#      kwargs (verified against resemble-ai/chatterbox mtl_tts.py).
GEN_SETTINGS = {
    "en": {"exaggeration": 0.6, "cfg_weight": 0.4, "temperature": 0.6,
           "repetition_penalty": 1.6, "min_p": 0.08, "top_p": 0.95},
    "ar": {"exaggeration": 0.55, "cfg_weight": 0.0, "temperature": 0.5,
           "repetition_penalty": 2.0, "min_p": 0.10, "top_p": 0.90},
}


# ── Arabic diacritization (tashkeel) ─────────────────────────────────────────
# Undiacritized Arabic is pronunciation-ambiguous: the TTS guesses vowels/shadda
# and gets words like "تشرفنا" wrong (missing the shadda). We restore diacritics
# on Arabic runs at render time with text2tashkeel (offline ONNX, no API key),
# which fixes the internal vowels + shaddas that drive pronunciation. Lazy,
# cached, and fully graceful: if it can't load/run, we use the raw Arabic.
_DIACRITIZER = None
_DIACRITIZER_TRIED = False


def _diacritize_arabic(text: str) -> str:
    """Return `text` with Arabic diacritics restored, or unchanged on any error.
    The diacritizer model is loaded once and reused."""
    global _DIACRITIZER, _DIACRITIZER_TRIED
    if not text or not text.strip():
        return text
    if not _DIACRITIZER_TRIED:
        _DIACRITIZER_TRIED = True
        try:
            import text2tashkeel as t2t  # type: ignore
            _DIACRITIZER = t2t.Diacritizer()
            print("  diacritizer: text2tashkeel loaded (Arabic tashkeel on)")
        except Exception as e:                                   # noqa: BLE001
            print(f"  diacritizer: unavailable ({type(e).__name__}) — raw Arabic")
            _DIACRITIZER = None
    if _DIACRITIZER is None:
        return text
    try:
        out = _DIACRITIZER.diacritize(text)
        return out or text
    except Exception:                                            # noqa: BLE001
        return text


def _chunk_text(text: str, limit: int = 280) -> list:
    """Split text into pieces under `limit` chars on sentence boundaries, so a
    long turn isn't truncated by the model's ~300-char input cap."""
    parts, buf = [], ""
    for tok in re.split(r"(?<=[.!?؟])\s+", (text or "").strip()):
        if not tok:
            continue
        if buf and len(buf) + len(tok) + 1 > limit:
            parts.append(buf)
            buf = tok
        else:
            buf = f"{buf} {tok}".strip()
    if buf:
        parts.append(buf)
    return parts or ([text.strip()] if text.strip() else [])


def _trim_and_gate(samples, sr):
    """Clean a single synthesized segment: trim silence/breath at the head and
    tail and gate very-low-energy frames to remove stray breaths/hums the model
    sometimes emits at segment edges. Speech-safe (conservative threshold)."""
    import numpy as np
    if not len(samples):
        return samples
    x = np.asarray(samples, dtype="float32")
    # Frame energy at 20ms.
    fr = max(1, int(sr * 0.02))
    n = len(x) // fr
    if n < 2:
        return x
    frames = x[:n * fr].reshape(n, fr)
    energy = np.sqrt((frames ** 2).mean(axis=1) + 1e-9)
    peak = float(energy.max())
    if peak <= 0:
        return x
    # A frame counts as "voice" if it's above ~4% of this segment's peak.
    thr = peak * 0.04
    voiced = energy > thr
    if not voiced.any():
        return x
    first = int(np.argmax(voiced))
    last = int(n - 1 - np.argmax(voiced[::-1]))
    # Keep a small 60ms pad around the speech so we don't clip onsets/offsets.
    pad = int(sr * 0.06)
    a = max(0, first * fr - pad)
    b = min(len(x), (last + 1) * fr + pad)
    return x[a:b]


class _MultilingualSynth:
    """One Chatterbox Multilingual model that voices EVERY speaker in EVERY
    language. Each speaker maps to a PER-LANGUAGE reference clip so both its
    English and its Arabic sound native; the owner uses their own recording(s).
    Anti-hallucination generate() settings + per-segment trim/gate suppress the
    stray breaths, hums, and repeated phrases the model can otherwise emit."""

    def __init__(self, ref_by_role: dict):
        # Same perth watermarker bug as the English model (resemble-ai/chatterbox
        # #198): neutralize the watermarker before constructing so from_pretrained
        # doesn't die with "'NoneType' object is not callable".
        try:
            import perth  # type: ignore

            class _NoWatermark:
                def apply_watermark(self, wav, *a, **k):
                    return wav

            perth.PerthImplicitWatermarker = _NoWatermark
        except Exception:
            pass

        from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # type: ignore
        # ref_by_role: {role: {"en": path, "ar": path}}. Normalise each clip to a
        # clean WAV the loader accepts; skip missing ones.
        self.ref_by_role = {}
        for role, by_lang in ref_by_role.items():
            cleaned = {}
            for lang, p in (by_lang or {}).items():
                if p:
                    cleaned[lang] = _to_clean_wav(p)
            if cleaned:
                self.ref_by_role[role] = cleaned
        self.model = ChatterboxMultilingualTTS.from_pretrained("cpu")
        self.sr = int(getattr(self.model, "sr", 24000))

    def _ref_for(self, role: str, lang: str) -> str:
        """Best reference clip for (role, lang): the language-specific one if we
        have it, else the other language's clip (better a real voice than none)."""
        by_lang = self.ref_by_role.get(role, {})
        return by_lang.get(lang) or by_lang.get("en") or by_lang.get("ar") or ""

    def _one(self, text: str, lang: str, ref: str):
        import numpy as np
        # Per-language emotion + anti-hallucination settings (see GEN_SETTINGS).
        s = GEN_SETTINGS.get(lang, GEN_SETTINGS["en"])
        kwargs = {"language_id": lang, "exaggeration": s["exaggeration"],
                  "temperature": s["temperature"], "cfg_weight": s["cfg_weight"],
                  "repetition_penalty": s["repetition_penalty"],
                  "min_p": s["min_p"], "top_p": s["top_p"]}
        if ref:
            kwargs["audio_prompt_path"] = ref
        wav = self.model.generate(text, **kwargs)
        try:
            arr = wav.squeeze(0).detach().cpu().numpy()
        except (AttributeError, TypeError):
            arr = np.asarray(wav).squeeze()
        arr = np.asarray(arr, dtype="float32").reshape(-1)
        return _trim_and_gate(arr, self.sr)

    def say_runs(self, runs: list, role: str):
        """Synthesize an ordered list of (lang, text) runs in one speaker's voice
        and concatenate them with short beats. Arabic runs are diacritized first
        so they're pronounced correctly; each run uses the role's native ref for
        that language. Returns (samples, sr)."""
        import numpy as np
        pieces = []
        for lang, run in runs:
            text = _diacritize_arabic(run) if lang == "ar" else run
            ref = self._ref_for(role, lang)
            for j, chunk in enumerate(_chunk_text(text)):
                if pieces:
                    pieces.append(np.zeros(int(self.sr * 0.12), dtype="float32"))
                pieces.append(self._one(chunk, lang, ref))
        if not pieces:
            return np.zeros(0, dtype="float32"), self.sr
        return np.concatenate(pieces), self.sr


# ── Synthesized cinematic sound design (100% generated — no licensed assets) ──
def _filt(x, sr, low=None, high=None):
    """Band/low/high-pass filter. Uses scipy when available; otherwise falls
    back to a simple FFT brick-wall filter so the renderer (and its tests) never
    hard-depend on scipy. `low`/`high` are cutoff Hz (either may be None)."""
    import numpy as np
    x = np.asarray(x, dtype="float32")
    if len(x) < 8:
        return x
    try:
        import scipy.signal as ss
        nyq = sr / 2.0
        if low and high:
            b, a = ss.butter(2, [low / nyq, high / nyq], btype="band")
        elif high:
            b, a = ss.butter(2, high / nyq, btype="low")
        elif low:
            b, a = ss.butter(2, low / nyq, btype="high")
        else:
            return x
        return ss.lfilter(b, a, x).astype("float32")
    except Exception:                                            # noqa: BLE001
        # FFT fallback (no scipy): zero the bins outside [low, high].
        spec = np.fft.rfft(x)
        freqs = np.fft.rfftfreq(len(x), 1.0 / sr)
        mask = np.ones(len(spec), dtype=bool)
        if low:
            mask &= freqs >= low
        if high:
            mask &= freqs <= high
        spec = spec * mask
        return np.fft.irfft(spec, n=len(x)).astype("float32")


def _sd_reverb(x, sr, decay=0.3, mix=0.25):
    """A cheap Schroeder-ish reverb tail for space/atmosphere."""
    import numpy as np
    out = x.copy()
    for delay_ms, g in ((37, 0.7), (53, 0.6), (71, 0.5), (97, 0.4)):
        d = int(sr * delay_ms / 1000.0)
        if d < len(x):
            echo = np.zeros_like(x)
            echo[d:] = x[:-d] * g * decay
            out = out + echo
    return (1 - mix) * x + mix * out


def _sd_intro_sting(sr, seconds=3.2):
    """A warm, cinematic intro sting: a soft rising chord swell + a shimmer, so
    every episode opens with the same recognizable 'brand' sound."""
    import numpy as np
    n = int(sr * seconds)
    t = np.arange(n) / sr
    # Minor-add chord (A2, E3, A3, C4) swelling in — warm but slightly mysterious.
    freqs = [110.0, 164.81, 220.0, 261.63]
    sig = np.zeros(n, dtype="float32")
    for f in freqs:
        sig += np.sin(2 * np.pi * f * t) / len(freqs)
    # High shimmer that fades in then out.
    shimmer = 0.15 * np.sin(2 * np.pi * 1320 * t) * np.exp(-((t - seconds*0.6)**2) / 0.4)
    sig = sig + shimmer
    # Swell envelope: fade in, hold, fade out.
    env = np.minimum(t / 0.8, 1.0) * np.minimum((seconds - t) / 1.0, 1.0)
    env = np.clip(env, 0, 1)
    sig = (sig * env).astype("float32")
    sig = _sd_reverb(sig, sr, decay=0.5, mix=0.35)
    pk = float(np.max(np.abs(sig))) or 1.0
    return (sig * (0.5 / pk)).astype("float32")


def _sd_ambient(sr, seconds, kind="room"):
    """A soft ambient bed to sit UNDER narration. 'room' = airy hiss + low hum
    (a quiet indoor space); very low level so speech stays clear."""
    import numpy as np
    n = int(sr * seconds)
    rng = np.random.default_rng(7)
    noise = rng.standard_normal(n).astype("float32")
    # Low-pass the noise heavily → soft 'air', not hiss.
    air = _filt(noise, sr, high=900)
    # A barely-there low hum for 'presence'.
    t = np.arange(n) / sr
    hum = 0.04 * np.sin(2 * np.pi * 60 * t).astype("float32")
    bed = air / (np.max(np.abs(air)) or 1.0) * 0.5 + hum
    return (bed * 0.06).astype("float32")     # ~ -24 dB under speech


def _sd_tap(sr):
    """A single 'tap' knock (short filtered transient)."""
    import numpy as np
    n = int(sr * 0.12)
    t = np.arange(n) / sr
    click = (np.exp(-t * 60) * np.sin(2 * np.pi * 180 * t)).astype("float32")
    click = _filt(click, sr, low=120, high=2500)
    return _sd_reverb(click, sr, decay=0.4, mix=0.3) * 0.5


def _sd_creak(sr):
    """A slow door-creak: pitch-rising filtered noise."""
    import numpy as np
    n = int(sr * 1.1)
    rng = np.random.default_rng(3)
    noise = rng.standard_normal(n).astype("float32")
    t = np.arange(n) / sr
    # sweep a narrow band-pass upward → 'creeeak'
    out = np.zeros(n, dtype="float32")
    for f0 in np.linspace(300, 900, 6):
        out += _filt(noise, sr, low=max(80, f0 - 60), high=f0 + 60)
    env = np.minimum(t/0.2, 1.0) * np.minimum((1.1 - t)/0.3, 1.0)
    out = out / (np.max(np.abs(out)) or 1.0) * np.clip(env, 0, 1)
    return _sd_reverb(out.astype("float32"), sr, mix=0.35) * 0.35


def _sd_shimmer(sr):
    """A soft 'magic'/blue-light shimmer (bell-like partials, quick fade)."""
    import numpy as np
    n = int(sr * 1.4)
    t = np.arange(n) / sr
    sig = np.zeros(n, dtype="float32")
    for f in (880, 1320, 1760, 2640):
        sig += np.sin(2 * np.pi * f * t) * np.exp(-t * 3)
    sig = sig / (np.max(np.abs(sig)) or 1.0)
    return _sd_reverb(sig.astype("float32"), sr, decay=0.6, mix=0.4) * 0.3


# ── REAL audio assets (CC/public-domain, in content/sfx/) ────────────────────
# We prefer REAL recorded sound effects + music over synthesized tones. Each SFX
# name maps to an audio file; if the file is missing we fall back to a synth
# generator so the renderer never hard-fails. The narrator should NOT read
# onomatopoeia ("tap tap") — use the [SFX:knock] marker so a REAL knock plays.
_SFX_DIR = str(BOT_DIR / "content" / "sfx")
SFX_FILES = {
    "knock": "knock.ogg",     # a real door knock (replaces spoken "tap tap tap")
    "tap": "knock.ogg",       # alias
    "creak": "creak.ogg",     # a real door-handle creak
}
# Named background-music beds (real CC tracks). Scores the whole episode, ducked.
MUSIC_FILES = {
    "mystery": "music_mystery.ogg",   # Rafael Krux "Lights" (CC-BY) — attribute!
}
# Synth fallbacks if an asset file is absent (keeps the pipeline resilient).
_SFX_SYNTH = {"tap": _sd_tap, "knock": _sd_tap, "creak": _sd_creak,
              "shimmer": _sd_shimmer}
_SFX_RE = re.compile(r"\[SFX:([a-z_]+)\]", re.I)


def _load_audio(path, sr):
    """Load an audio file → mono float32 at `sr`. Returns None on any failure.
    Tries soundfile first (reads WAV/OGG/FLAC natively via libsndfile — no ffmpeg
    needed), then librosa (which can decode more formats but needs an audio
    backend). Resamples with numpy if the file's rate differs from `sr`."""
    import numpy as np
    # 1) soundfile — native OGG/WAV/FLAC, present wherever the renderer runs.
    try:
        import soundfile as sf
        y, file_sr = sf.read(path, dtype="float32", always_2d=False)
        if y is not None and len(y):
            if getattr(y, "ndim", 1) > 1:
                y = y.mean(axis=1)
            y = np.asarray(y, dtype="float32")
            if file_sr != sr:
                y = _resample(y, file_sr, sr)
            return y.astype("float32")
    except Exception:                                            # noqa: BLE001
        pass
    # 2) librosa fallback (mp3/m4a via audioread/ffmpeg).
    try:
        import librosa
        y, _ = librosa.load(path, sr=sr, mono=True)
        return y.astype("float32") if y is not None and len(y) else None
    except Exception:                                            # noqa: BLE001
        return None


def load_sfx(name, sr):
    """Return the REAL sound effect for `name` (mono float32 @ sr). Falls back to
    a synthesized version if the asset file is missing."""
    import numpy as np
    fn = SFX_FILES.get(name.lower())
    if fn:
        y = _load_audio(os.path.join(_SFX_DIR, fn), sr)
        if y is not None:
            pk = float(np.max(np.abs(y))) or 1.0
            return (y * (0.7 / pk)).astype("float32")
    synth = _SFX_SYNTH.get(name.lower())
    return synth(sr) if synth else np.zeros(0, dtype="float32")


def load_music(name, sr):
    """Return a background-music bed (mono float32 @ sr), or None if unavailable."""
    fn = MUSIC_FILES.get((name or "").lower())
    if not fn:
        return None
    return _load_audio(os.path.join(_SFX_DIR, fn), sr)


class _StorySynth:
    """English-only, character-based synthesizer for the storytelling podcast.
    Each character maps to a voice SLOT with its own reference clip (a cloned
    voice) or no clip (the model's native American voice). Slots + per-character
    params keep characters distinct and clear."""

    def __init__(self, slot_refs: dict):
        try:
            import perth  # type: ignore

            class _NoWatermark:
                def apply_watermark(self, wav, *a, **k):
                    return wav

            perth.PerthImplicitWatermarker = _NoWatermark
        except Exception:
            pass

        from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # type: ignore
        # slot_refs: {slot_name: clip_path}. Clean each; builtin_* slots have no
        # clip (None) → the model's native American English voice.
        self.slot_refs = {}
        for slot, p in (slot_refs or {}).items():
            self.slot_refs[slot] = _to_clean_wav(p) if p else ""
        self.model = ChatterboxMultilingualTTS.from_pretrained("cpu")
        self.sr = int(getattr(self.model, "sr", 24000))

    def _one(self, text: str, ref: str, exaggeration: float, cfg_weight: float):
        import numpy as np
        s = GEN_SETTINGS["en"]
        kwargs = {"language_id": "en", "exaggeration": exaggeration,
                  "temperature": s["temperature"], "cfg_weight": cfg_weight,
                  "repetition_penalty": s["repetition_penalty"],
                  "min_p": s["min_p"], "top_p": s["top_p"]}
        if ref:
            kwargs["audio_prompt_path"] = ref
        wav = self.model.generate(text, **kwargs)
        try:
            arr = wav.squeeze(0).detach().cpu().numpy()
        except (AttributeError, TypeError):
            arr = np.asarray(wav).squeeze()
        arr = np.asarray(arr, dtype="float32").reshape(-1)
        return _trim_and_gate(arr, self.sr)

    def say(self, text: str, character: dict):
        """Synthesize one character's line (English), chunked. Returns samples."""
        import numpy as np
        ref = self.slot_refs.get(character["slot"], "")
        exg = character.get("exaggeration", 0.6)
        cfg = character.get("cfg_weight", 0.4)
        pieces = []
        for chunk in _chunk_text(text):
            if pieces:
                pieces.append(np.zeros(int(self.sr * 0.1), dtype="float32"))
            pieces.append(self._one(chunk, ref, exg, cfg))
        if not pieces:
            return np.zeros(0, dtype="float32")
        return np.concatenate(pieces)


def _resample(samples, sr_from, sr_to):
    """Linear resample so every segment shares one sample rate before stitching.
    A podcast is speech, so linear interpolation is perceptually fine here."""
    import numpy as np
    if sr_from == sr_to:
        return samples
    n_to = int(round(len(samples) * sr_to / sr_from))
    if n_to <= 1:
        return samples
    x_old = np.linspace(0.0, 1.0, num=len(samples), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=n_to, endpoint=False)
    return np.interp(x_new, x_old, samples).astype("float32")


def _normalize(samples):
    """Peak-normalise to a safe headroom + gentle fade-in/out for a polished,
    story-like open and close (no abrupt starts/stops)."""
    import numpy as np
    if not len(samples):
        return samples.astype("float32")
    peak = float(np.max(np.abs(samples)))
    if peak > 0:
        samples = samples * (0.97 / peak)
    # ~120ms fades at the very start and end.
    fade = min(int(0.12 * 24000), len(samples) // 2)
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype="float32")
        samples[:fade] *= ramp
        samples[-fade:] *= ramp[::-1]
    return samples.astype("float32")


def _download(url: str, dest: str) -> str:
    """Download a reference clip; return dest on success, '' on failure."""
    import urllib.request
    try:
        urllib.request.urlretrieve(url, dest)
        return dest
    except Exception as e:                                       # noqa: BLE001
        print(f"  ⚠️ could not fetch co-host reference {url} ({e})")
        return ""


def _build_ref_map(segments: list, owner_ref_en: str, owner_ref_ar: str,
                   work_dir: str) -> dict:
    """Build a PER-LANGUAGE reference map {role: {"en": path, "ar": path}}:
    owner → the owner's own recording(s) (a native-Arabic clip for `ar` gives the
    best Arabic; falls back to whichever owner clip exists); co-hosts → native
    English + native Arabic demo prompts. Roles with no clip are omitted (the
    model uses its built-in voice)."""
    roles = {sawt_tts.voice_for(label)["role"] for label, _ in segments}
    ref = {}
    if "owner" in roles:
        owner = {}
        if owner_ref_en and os.path.exists(owner_ref_en):
            owner["en"] = owner_ref_en
        if owner_ref_ar and os.path.exists(owner_ref_ar):
            owner["ar"] = owner_ref_ar
        # If only one owner clip was given, use it for both languages.
        if owner.get("en") and not owner.get("ar"):
            owner["ar"] = owner["en"]
        if owner.get("ar") and not owner.get("en"):
            owner["en"] = owner["ar"]
        if owner:
            ref["owner"] = owner
    for role in ("cohost_f", "cohost_m"):
        if role in roles and role in COHOST_REF_URLS:
            by_lang = {}
            for lang, url in COHOST_REF_URLS[role].items():
                dest = os.path.join(work_dir, f"cohost_{role}_{lang}.flac")
                got = _download(url, dest)
                if got:
                    by_lang[lang] = got
            if by_lang:
                ref[role] = by_lang
    return ref


def _build_slot_refs(segments, owner_ref, mai_ref):
    """Which voice slots does this story need, and what clip backs each? Cloned
    slots (owner/mai) use the given clips; builtin_* slots use the native voice
    (no clip). A cloned slot with no clip is dropped (→ built-in fallback)."""
    slots = {character_for(lbl)["slot"] for lbl, _ in segments}
    refs = {}
    if "owner" in slots and owner_ref and os.path.exists(owner_ref):
        refs["owner"] = owner_ref
    if "mai" in slots and mai_ref and os.path.exists(mai_ref):
        refs["mai"] = mai_ref
    # builtin_m / builtin_f need no reference (native American voice).
    for s in slots:
        if s.startswith("builtin"):
            refs[s] = ""
    return refs


def _mix_under(voice, bed, sr, level=0.5):
    """Mix an ambient bed UNDER a voice track (bed tiled/truncated to length)."""
    import numpy as np
    if bed is None or len(bed) == 0:
        return voice
    if len(bed) < len(voice):
        bed = np.tile(bed, int(np.ceil(len(voice) / len(bed))))
    bed = bed[:len(voice)] * level
    return (voice + bed).astype("float32")


def _duck_music(voice, music, sr, base=0.22, ducked=0.09,
                intro=3.0, outro=3.0):
    """Score a story with a MUSIC bed that automatically ducks under speech —
    like a film. The music plays at `base` level during silence and drops to
    `ducked` while someone is talking (sidechain compression, done by tracking
    the voice envelope). An `intro`/`outro` of music at full base level tops and
    tails the episode. Returns the voice+music mix (same length as voice+outro)."""
    import numpy as np
    if music is None or len(music) == 0:
        return voice
    total = len(voice) + int(sr * outro)
    # Tile/trim the music to the full length.
    if len(music) < total:
        music = np.tile(music, int(np.ceil(total / len(music))))
    music = music[:total].astype("float32").copy()
    # Voice envelope (smoothed) → duck amount. Pad voice to total length.
    v = np.concatenate([voice, np.zeros(total - len(voice), dtype="float32")])
    win = max(1, int(sr * 0.15))
    env = np.convolve(np.abs(v), np.ones(win) / win, mode="same")
    vpk = float(env.max()) or 1.0
    speaking = env > (vpk * 0.06)
    gain = np.where(speaking, ducked, base).astype("float32")
    # Smooth the gain so ducking is gradual, not clicky (~250ms).
    sw = max(1, int(sr * 0.25))
    gain = np.convolve(gain, np.ones(sw) / sw, mode="same").astype("float32")
    # Music intro fade-in + let the intro breathe before speech.
    fin = min(int(sr * 1.0), total)
    music[:fin] *= np.linspace(0, 1, fin, dtype="float32")
    fout = min(int(sr * 2.0), total)
    music[-fout:] *= np.linspace(1, 0, fout, dtype="float32")
    mixed = v + music * gain
    return mixed.astype("float32")


def render_story(script: str, out_path: str, owner_ref: str = "",
                 mai_ref: str = "", sound_design: bool = True,
                 music: str = "mystery") -> dict:
    """Render a STORYTELLING episode (Empire Chronicles): English-only, a named
    CAST (narrator=owner clone, characters=Mai clone / built-in American), scored
    like a short film with a REAL cinematic music bed that ducks under speech,
    plus REAL inline [SFX:knock|creak] sound effects. `music` selects a bed from
    MUSIC_FILES (or "" / "none" for no music). Returns a result dict."""
    import numpy as np
    import soundfile as sf

    segments = sawt_tts.parse_script(script)
    if not segments:
        raise SystemExit("No speaker lines found (expected `Speaker: text`).")

    work_dir = str(pathlib.Path(out_path).resolve().parent)
    pathlib.Path(work_dir).mkdir(parents=True, exist_ok=True)

    slot_refs = _build_slot_refs(segments, owner_ref, mai_ref)
    print("  cast slots: " + ", ".join(
        f"{s}={'clip' if p else 'builtin'}" for s, p in slot_refs.items()))
    synth = _StorySynth(slot_refs)
    sr = synth.sr
    print("  story engine: loaded (Chatterbox Multilingual, English cast)")

    pieces = []
    prev_slot = None
    t0 = time.time()
    for i, (label, text) in enumerate(segments, 1):
        ch = character_for(label)
        gap = PAUSE_BETWEEN_SPEAKERS if ch["slot"] != prev_slot else PAUSE_SAME_SPEAKER
        if pieces:
            pieces.append(np.zeros(int(sr * gap), dtype="float32"))
        # Inline SFX markers: play the REAL effect where it appears, strip the
        # marker from the spoken text (so the narrator never reads "tap tap").
        for m in _SFX_RE.finditer(text):
            fx = load_sfx(m.group(1), sr)
            if len(fx):
                pieces.append(fx)
                pieces.append(np.zeros(int(sr * 0.15), dtype="float32"))
        clean_text = _SFX_RE.sub(" ", text).strip()
        if clean_text:
            pieces.append(synth.say(clean_text, ch))
        prev_slot = ch["slot"]
        if i % 5 == 0 or i == len(segments):
            print(f"  [{i}/{len(segments)}] rendered ({time.time()-t0:.0f}s)",
                  flush=True)

    body = np.concatenate(pieces) if pieces else np.zeros(0, dtype="float32")
    body = _trim_and_gate(body, sr)

    used_music = None
    if sound_design:
        # A subtle ambient room bed adds 'presence' under the whole piece.
        body = _mix_under(body, _sd_ambient(sr, len(body) / sr), sr, level=1.0)
        bed = load_music(music, sr) if music and music.lower() != "none" else None
        if bed is not None:
            used_music = music
            # A ~3s music intro plays alone, THEN speech starts (music ducks).
            intro = int(sr * 3.0)
            voice = np.concatenate([np.zeros(intro, dtype="float32"), body])
            audio = _duck_music(voice, bed, sr, base=0.24, ducked=0.10,
                                intro=3.0, outro=3.0)
        else:
            # No music available → keep the synth intro sting as a fallback.
            sting = _sd_intro_sting(sr)
            audio = np.concatenate([sting, body]).astype("float32")
            audio = np.concatenate([audio, np.zeros(int(sr * 0.8), dtype="float32")])
    else:
        audio = np.concatenate([body, np.zeros(int(sr * 0.8), dtype="float32")])

    audio = _normalize(audio)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), audio, sr, format="MP3")
    dur = len(audio) / sr
    print(f"\n  wrote {out} — {dur/60:.1f} min, {len(segments)} lines, "
          f"cast={sorted(slot_refs)}, music={used_music or 'none'}, "
          f"sound_design={sound_design}, in {time.time()-t0:.1f}s")
    return {"ok": True, "segment_count": len(segments),
            "duration_seconds": int(dur), "out_path": str(out),
            "music": used_music}


def render(script: str, level: str, out_path: str,
           kokoro_dir: str = "", ref_clip: str = "", ref_clip_ar: str = "") -> dict:
    """Render a full multi-speaker, multilingual episode to `out_path` (MP3).

    Every speaker is voiced by Chatterbox Multilingual, per language:
      * co-hosts use native English + native Arabic reference prompts;
      * the owner uses their own recording(s): `ref_clip` (English) and, ideally,
        `ref_clip_ar` (a native-Arabic recording of the owner) for Arabic runs.
    Each line is split into Arabic/English runs, Arabic is diacritized, and
    anti-hallucination settings + per-segment trimming keep it clean.

    Returns {ok, segment_count, duration_seconds, out_path, cloned}. `kokoro_dir`
    is accepted but unused (kept for CLI/back-compat)."""
    import numpy as np
    import soundfile as sf

    segments = sawt_tts.parse_script(script)
    if not segments:
        raise SystemExit("No speaker lines found in the script "
                         "(expected `Speaker: text`).")

    work_dir = str(pathlib.Path(out_path).resolve().parent)
    pathlib.Path(work_dir).mkdir(parents=True, exist_ok=True)
    ref_map = _build_ref_map(segments, ref_clip, ref_clip_ar, work_dir)
    print("  reference voices: " + (", ".join(
        f"{r}=[{'+'.join(sorted(by))}]" for r, by in ref_map.items())
        or "none"))

    synth = _MultilingualSynth(ref_map)
    print("  multilingual engine: loaded (Chatterbox Multilingual, en+ar)")

    pieces = []
    target_sr = synth.sr
    owner_segments = 0
    prev_role = None
    t0 = time.time()

    for i, (label, text) in enumerate(segments, 1):
        v = sawt_tts.voice_for(label)
        role = v["role"]

        gap = PAUSE_BETWEEN_SPEAKERS if role != prev_role else PAUSE_SAME_SPEAKER
        if text.strip().upper() == "[PAUSE]":
            gap = PAUSE_MARKER
            runs = []
        else:
            runs = split_by_language(text.replace("[PAUSE]", " "))

        if pieces:
            pieces.append(np.zeros(int(target_sr * gap), dtype="float32"))

        if runs:
            samples, sr = synth.say_runs(runs, role)
            if role == "owner":
                owner_segments += 1
            samples = np.asarray(samples, dtype="float32")
            if sr != target_sr:
                samples = _resample(samples, sr, target_sr)
            pieces.append(samples)

        prev_role = role
        if i % 5 == 0 or i == len(segments):
            print(f"  [{i}/{len(segments)}] rendered "
                  f"({time.time()-t0:.0f}s)", flush=True)

    if not pieces:
        raise SystemExit("Nothing synthesised (script had only pauses?).")

    audio = np.concatenate(pieces)
    # Trim any dead air / stray tail after the last speech, then leave ~0.8s.
    audio = _trim_and_gate(audio, target_sr)
    tail = int(target_sr * 0.8)
    audio = np.concatenate([audio, np.zeros(tail, dtype="float32")])
    audio = _normalize(audio)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), audio, target_sr, format="MP3")
    dur = len(audio) / target_sr

    print(f"\n  wrote {out} — {dur/60:.1f} min, {len(segments)} segments, "
          f"{owner_segments} in the owner's voice, in {time.time()-t0:.1f}s")
    return {"ok": True, "segment_count": len(segments),
            "duration_seconds": int(dur), "out_path": str(out),
            "cloned": owner_segments}


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True,
                    help="path to the reviewed episode script (text file)")
    ap.add_argument("--level", default="A1", help="CEFR level (A1–C2) for pace")
    ap.add_argument("--out", default="episode.mp3", help="output MP3 path")
    ap.add_argument("--kokoro-dir", default="",
                    help="(deprecated / ignored — kept for back-compat)")
    ap.add_argument("--ref-clip", default="",
                    help="owner ENGLISH voice reference clip (optional)")
    ap.add_argument("--ref-clip-ar", default="",
                    help="owner ARABIC (MSA) voice reference clip — best Arabic "
                         "quality; falls back to --ref-clip if omitted")
    ap.add_argument("--story", action="store_true",
                    help="STORYTELLING mode (Empire Chronicles): English-only "
                         "named cast + sound design")
    ap.add_argument("--ref-mai", default="",
                    help="Mai's consented voice reference clip (story cast)")
    ap.add_argument("--no-sound-design", action="store_true",
                    help="story mode: skip the music / ambient bed / SFX")
    ap.add_argument("--music", default="mystery",
                    help="story mode: background music bed name "
                         "(mystery | none). Default: mystery")
    ap.add_argument("--plan", action="store_true",
                    help="print the render plan and exit (no synthesis)")
    args = ap.parse_args()

    script = pathlib.Path(args.script).read_text(encoding="utf-8")

    if args.story:
        segs = sawt_tts.parse_script(script)
        cast = {}
        for lbl, _ in segs:
            cast.setdefault(character_for(lbl)["name"], 0)
            cast[character_for(lbl)["name"]] += 1
        print(f"Story plan: {len(segs)} lines · cast "
              + ", ".join(f"{c}×{n}" for c, n in cast.items()))
        if args.plan:
            return 0
        if not segs:
            raise SystemExit("Story script has no parseable `Speaker: text` lines.")
        render_story(script, args.out, owner_ref=args.ref_clip,
                     mai_ref=args.ref_mai,
                     sound_design=not args.no_sound_design,
                     music=args.music)
        return 0

    p = plan(script)
    voices = ", ".join(f"{r}×{n}" for r, n in p["voices"].items())
    print(f"Plan: {p['segment_count']} segments · voices {voices} · "
          f"needs_clone={p['needs_clone']} · level {args.level}")
    if args.plan:
        return 0
    if p["segment_count"] == 0:
        raise SystemExit("Script has no parseable `Speaker: text` lines.")

    render(script, args.level, args.out, args.kokoro_dir, args.ref_clip,
           args.ref_clip_ar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
