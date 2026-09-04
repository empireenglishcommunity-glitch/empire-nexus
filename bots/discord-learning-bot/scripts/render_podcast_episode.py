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


# Reference-voice clips for each speaker role. Chatterbox Multilingual clones the
# voice in the reference clip for EVERY language, so a single clip per speaker
# gives that speaker one consistent voice across English and Arabic. The co-host
# defaults are ResembleAI's own multilingual demo prompts (distinct male/female
# speakers), so the two co-hosts and the owner all sound different. The owner's
# role uses the uploaded owner clip (passed via --ref-clip), so the owner speaks
# both English and Arabic in the owner's OWN voice.
COHOST_REF_URLS = {
    # female co-host — ResembleAI's own English demo prompt (en_f1). The model
    # clones the TIMBRE and re-synthesises in whatever language_id we ask, so
    # this voice speaks Arabic too.
    "cohost_f": "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/en_f1.flac",
    # male co-host — a distinct MALE demo prompt. There is no en_m demo clip, so
    # we use it_m1 (Italian male): only the timbre is cloned, and it's rendered
    # in English/Arabic like any other reference, giving a clearly different
    # (male) voice from the female co-host and the owner.
    "cohost_m": "https://storage.googleapis.com/chatterbox-demo-samples/mtl_prompts/it_m1.flac",
}


def _to_clean_wav(ref_clip: str) -> str:
    """Chatterbox's reference loader is finicky about container formats: hand it
    an m4a (even one misnamed .wav) and its loader returns None → "'NoneType'
    object is not callable" at generate time. So ALWAYS re-decode the clip to a
    real 24kHz mono PCM WAV with librosa/soundfile (present for Kokoro) — we do
    NOT trust the file extension, because an upload/download can name m4a bytes
    ".wav". Always returns a freshly written .clean.wav."""
    import pathlib
    import librosa
    import soundfile as sf
    # librosa uses ffmpeg/audioread to decode whatever the real container is,
    # regardless of the filename's suffix.
    y, _sr = librosa.load(ref_clip, sr=24000, mono=True)
    if y is None or len(y) == 0:
        raise ValueError(f"reference clip {ref_clip!r} decoded to no audio")
    out = str(pathlib.Path(ref_clip).with_suffix(".clean.wav"))
    sf.write(out, y, 24000, format="WAV", subtype="PCM_16")
    print(f"  converted reference clip → {out} ({len(y)/24000:.1f}s, 24kHz mono PCM)")
    return out


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


class _MultilingualSynth:
    """One Chatterbox Multilingual model that voices EVERY speaker in EVERY
    language. Each speaker is a reference clip (owner clip for the owner, a
    distinct demo voice per co-host); the model clones that voice for whichever
    language_id ("en"/"ar") each run needs — so the owner speaks Arabic in the
    owner's own voice, and co-hosts keep a consistent voice across languages."""

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
        # Normalise every reference clip to a clean WAV the loader accepts.
        self.ref_by_role = {role: _to_clean_wav(p)
                            for role, p in ref_by_role.items() if p}
        self.model = ChatterboxMultilingualTTS.from_pretrained("cpu")
        self.sr = int(getattr(self.model, "sr", 24000))

    def _one(self, text: str, lang: str, ref: str):
        import numpy as np
        # cfg_weight 0.5 is the balanced default; the ResembleAI cog notes 0 is
        # better for pure "language transfer" (voice in a language it never spoke).
        kwargs = {"language_id": lang, "exaggeration": 0.5,
                  "temperature": 0.8, "cfg_weight": 0.5}
        if ref:
            kwargs["audio_prompt_path"] = ref
        wav = self.model.generate(text, **kwargs)
        try:
            arr = wav.squeeze(0).detach().cpu().numpy()
        except (AttributeError, TypeError):
            arr = np.asarray(wav).squeeze()
        return np.asarray(arr, dtype="float32").reshape(-1)

    def say_runs(self, runs: list, role: str):
        """Synthesize an ordered list of (lang, text) runs in one speaker's voice
        and concatenate them with short beats. Returns (samples, sr)."""
        import numpy as np
        ref = self.ref_by_role.get(role, "")
        pieces = []
        for lang, run in runs:
            for j, chunk in enumerate(_chunk_text(run)):
                if pieces:
                    pieces.append(np.zeros(int(self.sr * 0.12), dtype="float32"))
                pieces.append(self._one(chunk, lang, ref))
        if not pieces:
            return np.zeros(0, dtype="float32"), self.sr
        return np.concatenate(pieces), self.sr


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
    """Peak-normalise to a safe headroom so episodes have consistent loudness."""
    import numpy as np
    peak = float(np.max(np.abs(samples))) if len(samples) else 0.0
    if peak > 0:
        samples = samples * (0.97 / peak)
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


def _build_ref_map(segments: list, owner_ref: str, work_dir: str) -> dict:
    """Assign every speaker role present in the episode a reference clip:
    owner → the uploaded owner clip; co-hosts → distinct downloaded demo voices.
    A role with no available clip is omitted (the model uses its built-in voice)."""
    roles = {sawt_tts.voice_for(label)["role"] for label, _ in segments}
    ref = {}
    if "owner" in roles and owner_ref and os.path.exists(owner_ref):
        ref["owner"] = owner_ref
    for role in ("cohost_f", "cohost_m"):
        if role in roles and role in COHOST_REF_URLS:
            dest = os.path.join(work_dir, f"cohost_ref_{role}.flac")
            got = _download(COHOST_REF_URLS[role], dest)
            if got:
                ref[role] = got
    return ref


def render(script: str, level: str, out_path: str,
           kokoro_dir: str = "", ref_clip: str = "") -> dict:
    """Render a full multi-speaker, multilingual episode to `out_path` (MP3).

    Every speaker is voiced by Chatterbox Multilingual: the owner in the owner's
    cloned voice (from --ref-clip), co-hosts in distinct reference voices. Each
    line is split into Arabic/English runs and each run synthesised with the
    right language_id, so Arabic is spoken as Arabic (not letter-by-letter) and
    the owner's Arabic is in the owner's own voice.

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
    ref_map = _build_ref_map(segments, ref_clip, work_dir)
    print(f"  reference voices: "
          + ", ".join(f"{r}={pathlib.Path(p).name}" for r, p in ref_map.items())
          + (" (none)" if not ref_map else ""))

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

    audio = _normalize(np.concatenate(pieces))
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
                    help="owner voice reference clip for cloning (optional)")
    ap.add_argument("--plan", action="store_true",
                    help="print the render plan and exit (no synthesis)")
    args = ap.parse_args()

    script = pathlib.Path(args.script).read_text(encoding="utf-8")

    p = plan(script)
    voices = ", ".join(f"{r}×{n}" for r, n in p["voices"].items())
    print(f"Plan: {p['segment_count']} segments · voices {voices} · "
          f"needs_clone={p['needs_clone']} · level {args.level}")
    if args.plan:
        return 0
    if p["segment_count"] == 0:
        raise SystemExit("Script has no parseable `Speaker: text` lines.")

    render(script, args.level, args.out, args.kokoro_dir, args.ref_clip)
    return 0


if __name__ == "__main__":
    sys.exit(main())
