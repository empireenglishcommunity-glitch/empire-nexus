#!/usr/bin/env python3.12
"""Empire English Chronicles — VOICE BENCHMARK (spec task 1.2).

Scores every candidate voice on the kind of content it will actually speak, so the
cast is chosen by MEASUREMENT rather than by adjective. Writes a committed results
table so the choice is auditable and re-derivable.

WHY THIS EXISTS
---------------
The previous cast was picked by ear from amateur reference clips, and three of four
voices were rejected by the owner as unclear. The ecosystem already learned this
lesson on the practice site (`benchmark_voices.py`): score voices with ASR, and
score them on the SURFACE they will actually be used for — a voice that wins on
long sentences can lose badly on short utterances.

WHAT IS MEASURED (all from src/audio_standards.py)
-------------------------------------------------
* intelligibility — ASR word error rate against known text  (PRIMARY)
* naturalness     — spectral flatness, pinned method, voice-only
* pace            — words per minute, to match the CEFR profile
* loudness/peak   — sanity only; mastering fixes these later

Usage
-----
    python3.12 scripts/benchmark_story_voices.py --out content/voice-benchmark.json
    python3.12 scripts/benchmark_story_voices.py --voices am_michael,am_adam --quick
"""
import argparse
import json
import pathlib
import sys
import time

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src import audio_standards as STD                           # noqa: E402

# Load the QA analyser by path (it lives in scripts/, not the src package).
import importlib.util                                            # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "audio_qa", BOT_DIR / "scripts" / "audio_qa.py")
qa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(qa)

KOKORO_DIR = pathlib.Path("/root/.cache/kokoro")
MODEL_URLS = {
    "kokoro-v1.0.onnx":
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin":
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}

# The content the cast will ACTUALLY speak. Scoring on anything else is how a voice
# that "wins" the benchmark ends up sounding wrong in production.
#   * narration — long, descriptive, slow, scene-setting
#   * dialogue  — short, emotional, conversational
#   * teaching  — the clear, simple sentences a learner must catch every word of
BENCH_TEXTS = {
    "narration": (
        "The night was cold, and the long hallway was completely silent. "
        "Maya stopped walking and looked at the old wooden door in front of her."),
    "dialogue": (
        "Wait. Did you hear that sound? I think someone is standing behind us."),
    "teaching": (
        "Listen carefully. She opened the door slowly, and then she stepped inside."),
}

# American voices only — the programme is taught in American English.
CANDIDATE_MALE = ["am_michael", "am_adam", "am_eric", "am_liam", "am_onyx",
                  "am_fenrir", "am_echo", "am_puck"]
CANDIDATE_FEMALE = ["af_heart", "af_bella", "af_nicole", "af_sarah", "af_kore",
                    "af_aoede", "af_jessica", "af_nova", "af_river", "af_alloy"]


def ensure_model():
    """Download the Kokoro model/voice files once, into a cache."""
    import urllib.request
    KOKORO_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in MODEL_URLS.items():
        p = KOKORO_DIR / name
        if not p.exists():
            print(f"  downloading {name} …", flush=True)
            urllib.request.urlretrieve(url, str(p))
    return KOKORO_DIR / "kokoro-v1.0.onnx", KOKORO_DIR / "voices-v1.0.bin"


def load_engine():
    from kokoro_onnx import Kokoro
    model, voices = ensure_model()
    return Kokoro(str(model), str(voices))


def score_voice(engine, voice, transcriber, speed=1.0, work_dir=None):
    """Render every benchmark text in `voice` and measure it. Returns a dict of
    per-surface metrics plus the aggregate used for ranking."""
    import numpy as np
    import soundfile as sf

    work = pathlib.Path(work_dir or "/tmp")
    work.mkdir(parents=True, exist_ok=True)
    per_surface, wers, flats, wpms = {}, [], [], []
    glitch_total = 0

    for surface, text in BENCH_TEXTS.items():
        samples, sr = engine.create(text, voice=voice, speed=speed, lang="en-us")
        samples = np.asarray(samples, dtype="float32")
        path = work / f"bench_{voice}_{surface}.wav"
        sf.write(str(path), samples, sr)

        dur = len(samples) / sr
        words = len(qa.normalise_words(text))
        wpm = (words / dur * 60.0) if dur > 0 else 0.0

        hyp = transcriber(path)
        wer = qa.word_error_rate(text, hyp) if hyp is not None else None
        flat = qa.measure_flatness(samples, sr)
        # GLITCHES: internal discontinuities (audible clicks). Some voices are
        # perfectly intelligible yet click when slowed — measured, am_puck gave 5
        # and af_jessica 6 at production speed while am_onyx gave 0. A voice that
        # clicks is unusable no matter how well it scores elsewhere.
        glitches, _ = qa.measure_hard_cuts(samples, sr)

        per_surface[surface] = {
            "wer": None if wer is None else round(wer, 4),
            "flatness": round(flat, 5),
            "glitches": glitches,
            "wpm": round(wpm, 1),
            "duration_s": round(dur, 2),
            "transcript": hyp,
        }
        if wer is not None:
            wers.append(wer)
        flats.append(flat)
        wpms.append(wpm)
        glitch_total += glitches

    mean_wer = (sum(wers) / len(wers)) if wers else None
    mean_flat = sum(flats) / len(flats)
    return {
        "voice": voice,
        "speed": speed,
        "surfaces": per_surface,
        "mean_wer": None if mean_wer is None else round(mean_wer, 4),
        "worst_wer": None if not wers else round(max(wers), 4),
        "mean_flatness": round(mean_flat, 5),
        "mean_wpm": round(sum(wpms) / len(wpms), 1),
        "glitches": glitch_total,
        "passes_glitches": glitch_total == 0,
        # Gate view: would this voice pass the standard as a voice stem?
        "passes_wer": None if mean_wer is None else bool(max(wers) <= STD.WER_MAX),
        "passes_flatness": bool(mean_flat <= STD.FLATNESS_MAX),
    }


def rank(results):
    """Rank by the metric that matters most first: intelligibility (worst-case,
    not average — a voice that fails on one surface fails the learner on that
    surface), then naturalness."""
    def key(r):
        w = r["worst_wer"] if r["worst_wer"] is not None else 9.0
        # Glitches rank FIRST: a voice that clicks is unusable regardless of how
        # well it scores on intelligibility or naturalness.
        return (0 if r.get("glitches", 0) == 0 else 1, w, r["mean_flatness"])
    return sorted(results, key=key)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--voices", default="",
                    help="comma-separated voice ids (default: all American candidates)")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="native synthesis speed to benchmark at")
    ap.add_argument("--out", default="content/voice-benchmark.json",
                    help="where to write the results table")
    ap.add_argument("--work-dir", default="/tmp/voicebench",
                    help="scratch dir for rendered samples")
    ap.add_argument("--quick", action="store_true",
                    help="skip ASR (naturalness/pace only — NOT enough to choose a cast)")
    args = ap.parse_args()

    voices = ([v.strip() for v in args.voices.split(",") if v.strip()]
              or CANDIDATE_MALE + CANDIDATE_FEMALE)

    print(f"Benchmarking {len(voices)} voice(s) on "
          f"{len(BENCH_TEXTS)} surfaces at speed {args.speed} …")
    engine = load_engine()

    if args.quick:
        def transcriber(_p):
            return None
        print("  (--quick: ASR skipped — intelligibility will be unscored)")
    else:
        from faster_whisper import WhisperModel
        model = WhisperModel("base.en", device="cpu", compute_type="int8")

        def transcriber(p):
            try:
                segs, _ = model.transcribe(str(p), language="en")
                return " ".join(s.text for s in segs).strip()
            except Exception:                                    # noqa: BLE001
                return None

    results, t0 = [], time.time()
    for i, v in enumerate(voices, 1):
        try:
            r = score_voice(engine, v, transcriber, speed=args.speed,
                            work_dir=args.work_dir)
            results.append(r)
            print(f"  [{i}/{len(voices)}] {v:12s} worst_wer={r['worst_wer']} "
                  f"flat={r['mean_flatness']} wpm={r['mean_wpm']} "
                  f"({time.time()-t0:.0f}s)", flush=True)
        except Exception as e:                                   # noqa: BLE001
            print(f"  [{i}/{len(voices)}] {v:12s} FAILED: {type(e).__name__}: {e}")

    ranked = rank(results)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "engine": "kokoro-onnx v1.0",
        "speed": args.speed,
        "standard": STD.summary(),
        "surfaces": {k: v for k, v in BENCH_TEXTS.items()},
        "ranked": ranked,
    }
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")

    print(f"\n  === RANKING (best first: worst-case WER, then naturalness) ===")
    print(f"  {'voice':13s} {'worst WER':>9s} {'flatness':>9s} {'glitch':>6s} "
          f"{'wpm':>6s}  gate")
    for r in ranked:
        gate = ("WER✓" if r["passes_wer"] else "WER✗") + \
               (" FLAT✓" if r["passes_flatness"] else " FLAT✗") + \
               (" GLITCH✓" if r.get("passes_glitches") else
                f" GLITCH✗({r.get('glitches')})")
        print(f"  {r['voice']:13s} {str(r['worst_wer']):>9s} "
              f"{r['mean_flatness']:>9.5f} {r.get('glitches',0):>6d} "
              f"{r['mean_wpm']:>6.1f}  {gate}")
    print(f"\n  results → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
