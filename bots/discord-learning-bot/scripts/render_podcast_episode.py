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

Co-host lines are synthesised with Kokoro (af_heart / am_adam). Owner lines use
the owner's cloned voice via Chatterbox + a reference clip when one is supplied;
without a clip (or without chatterbox installed) the owner's lines gracefully
fall back to a Kokoro voice so an episode can still be produced.

Usage:
    python3.12 scripts/render_podcast_episode.py \
        --script episode.txt \
        --level A1 \
        --out episode.mp3 \
        [--ref-clip owner_voice_ref.wav] \
        [--kokoro-dir ./kokoro]

The Kokoro model directory must contain kokoro-v1.0.onnx and voices-v1.0.bin.
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

# Kokoro voices for the fallback path (co-hosts, and owner when no clone clip).
FALLBACK_VOICE = "af_heart"

# Pace descriptor (from config.PODCAST_LEVEL_PROFILES) -> Kokoro speed factor.
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


class _KokoroSynth:
    """Thin wrapper over kokoro-onnx for the co-host (and fallback) voices."""

    def __init__(self, model_dir: str):
        from kokoro_onnx import Kokoro
        model_dir = pathlib.Path(model_dir)
        self.k = Kokoro(str(model_dir / "kokoro-v1.0.onnx"),
                        str(model_dir / "voices-v1.0.bin"))

    def say(self, text: str, voice_id: str, speed: float):
        samples, sr = self.k.create(text, voice=voice_id or FALLBACK_VOICE,
                                    speed=speed, lang="en-us")
        return samples, sr


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


class _CloneSynth:
    """Owner voice clone via Chatterbox + a reference clip. Optional: if the
    engine or clip is missing, the caller falls back to Kokoro."""

    def __init__(self, ref_clip: str):
        # Known chatterbox-tts bug (resemble-ai/chatterbox#198): its constructor
        # calls perth.PerthImplicitWatermarker(), which resolves to None when the
        # perth watermarking dep doesn't fully initialize → "'NoneType' object is
        # not callable" at from_pretrained. The watermark is inaudible and purely
        # optional for us, so neutralize it with a no-op before building the model.
        try:
            import perth  # type: ignore

            class _NoWatermark:
                def apply_watermark(self, wav, *a, **k):
                    return wav

            perth.PerthImplicitWatermarker = _NoWatermark
        except Exception:
            pass

        from chatterbox.tts import ChatterboxTTS  # type: ignore
        # Normalise the reference clip to a format Chatterbox reliably loads.
        self.ref_clip = _to_clean_wav(ref_clip)
        # from_pretrained takes the device positionally (per ResembleAI's app).
        self.model = ChatterboxTTS.from_pretrained("cpu")

    def _one(self, text: str):
        import numpy as np
        wav = self.model.generate(text, audio_prompt_path=self.ref_clip)
        # Chatterbox returns a torch tensor shaped (1, N); normalise to 1-D numpy.
        try:
            arr = wav.squeeze(0).detach().cpu().numpy()
        except (AttributeError, TypeError):
            arr = np.asarray(wav).squeeze()
        return np.asarray(arr, dtype="float32").reshape(-1)

    def say(self, text: str, speed: float):
        import numpy as np
        sr = int(getattr(self.model, "sr", 24000))
        # Chatterbox caps input length (~300 chars). Split long lines on
        # sentence boundaries and concatenate with a short pause so a long turn
        # doesn't get truncated.
        parts, buf = [], ""
        for tok in re.split(r"(?<=[.!?])\s+", text.strip()):
            if not tok:
                continue
            if buf and len(buf) + len(tok) + 1 > 280:
                parts.append(buf)
                buf = tok
            else:
                buf = f"{buf} {tok}".strip()
        if buf:
            parts.append(buf)
        if not parts:
            parts = [text.strip()]
        pieces = []
        for i, p in enumerate(parts):
            if i:
                pieces.append(np.zeros(int(sr * 0.15), dtype="float32"))
            pieces.append(self._one(p))
        return np.concatenate(pieces), sr


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


def render(script: str, level: str, out_path: str,
           kokoro_dir: str, ref_clip: str = "") -> dict:
    """Render a full multi-speaker episode to `out_path` (MP3).

    Returns {ok, segment_count, duration_seconds, out_path, cloned}. Raises only
    on a genuinely unrecoverable error (no engine at all, no segments)."""
    import numpy as np
    import soundfile as sf

    segments = sawt_tts.parse_script(script)
    if not segments:
        raise SystemExit("No speaker lines found in the script "
                         "(expected `Speaker: text`).")

    speed = _level_speed(level)
    kokoro = _KokoroSynth(kokoro_dir)

    # Owner clone is opt-in and best-effort. If it can't load, owner lines fall
    # back to a Kokoro voice so the episode still renders.
    clone = None
    if ref_clip and os.path.exists(ref_clip):
        try:
            clone = _CloneSynth(ref_clip)
            print(f"  owner voice clone: enabled (ref {ref_clip})")
        except Exception as e:                                   # noqa: BLE001
            import traceback
            print(f"  owner voice clone: UNAVAILABLE ({type(e).__name__}: {e}) "
                  f"— owner lines fall back to Kokoro {FALLBACK_VOICE}")
            traceback.print_exc()
    else:
        print("  owner voice clone: no reference clip — owner lines use Kokoro")

    pieces = []
    target_sr = None
    cloned_segments = 0
    prev_role = None
    t0 = time.time()

    for i, (label, text) in enumerate(segments, 1):
        v = sawt_tts.voice_for(label)
        role = v["role"]

        # Inter-segment pause.
        gap = PAUSE_BETWEEN_SPEAKERS if role != prev_role else PAUSE_SAME_SPEAKER
        # An explicit [PAUSE] line becomes a longer beat and no speech.
        if text.strip().upper() == "[PAUSE]":
            gap = PAUSE_MARKER
            speak = None
        else:
            speak = text.replace("[PAUSE]", " ")

        if target_sr is not None and pieces:
            pieces.append(np.zeros(int(target_sr * gap), dtype="float32"))

        if speak:
            use_clone = clone is not None and v["engine"] == "clone"
            samples = sr = None
            if use_clone:
                try:
                    samples, sr = clone.say(speak, speed)
                    cloned_segments += 1
                except Exception as e:                           # noqa: BLE001
                    # A per-segment clone failure must not lose the whole
                    # episode — fall back to Kokoro for just this line.
                    print(f"  ⚠️ clone failed on segment {i} "
                          f"({type(e).__name__}: {e}) — Kokoro for this line")
                    samples = None
            if samples is None:
                # Clone lines have no Kokoro voice_id of their own; use the
                # fallback voice for the owner when cloning is off/failed.
                voice_id = v.get("voice_id") or FALLBACK_VOICE
                samples, sr = kokoro.say(speak, voice_id, speed)

            samples = np.asarray(samples, dtype="float32")
            if target_sr is None:
                target_sr = sr
                # A leading pause was skipped above (no prior sample rate); if
                # this isn't the first segment, insert it now.
                if i > 1:
                    pieces.append(np.zeros(int(target_sr * gap), dtype="float32"))
            elif sr != target_sr:
                samples = _resample(samples, sr, target_sr)
            pieces.append(samples)

        prev_role = role
        if i % 10 == 0 or i == len(segments):
            print(f"  [{i}/{len(segments)}] rendered", flush=True)

    if not pieces or target_sr is None:
        raise SystemExit("Nothing synthesised (script had only pauses?).")

    audio = _normalize(np.concatenate(pieces))
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), audio, target_sr, format="MP3")
    dur = len(audio) / target_sr

    print(f"\n  wrote {out} — {dur/60:.1f} min, {len(segments)} segments, "
          f"{cloned_segments} cloned, in {time.time()-t0:.1f}s")
    return {"ok": True, "segment_count": len(segments),
            "duration_seconds": int(dur), "out_path": str(out),
            "cloned": cloned_segments}


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True,
                    help="path to the reviewed episode script (text file)")
    ap.add_argument("--level", default="A1", help="CEFR level (A1–C2) for pace")
    ap.add_argument("--out", default="episode.mp3", help="output MP3 path")
    ap.add_argument("--kokoro-dir", default="./kokoro",
                    help="dir with kokoro-v1.0.onnx and voices-v1.0.bin")
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
