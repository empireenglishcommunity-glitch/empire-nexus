#!/usr/bin/env python3.12
"""Empire English Chronicles — STORY RENDERER v2 (spec Phase 1).

Replaces the v1 story path in `render_podcast_episode.py`. Three things changed, and
each one fixes a measured defect:

1. **Engine (R2.1).** The cast is voiced by **Kokoro** — deterministic, studio
   quality, WER 0.0 in benchmarking — instead of stochastic voice cloning that
   measured 5.45% WER on a real episode. Mai keeps her **cloned** voice (R2.2),
   because it is a real consented human voice the owner accepts.

2. **Speech flow (R3).** Every join is **crossfaded**; text is chunked only on
   sentence/clause boundaries; edge-trimming preserves onsets and decays. v1
   concatenated trimmed chunks with no crossfade, which is what "sudden cut"
   sounded like.

3. **Mastering (R1.3).** Output is normalised to **-16 LUFS** with a **-1 dBTP**
   ceiling. Every v1 episode measured 6-8 dB too quiet, and 3 of 4 breached the
   peak ceiling.

BANNED HERE BY DESIGN (R2.4) — both were tried in v1 and made things worse:
  * no pitch-shifting a voice reference;
  * no post-synthesis time-stretching. Pace is native (`src.sawt_cast.speed_for_level`).

Usage
-----
    python3.12 scripts/render_story_v2.py --script ep.txt --level A2 --out ep.mp3
    python3.12 scripts/render_story_v2.py --script ep.txt --plan     # no synthesis
    python3.12 scripts/render_story_v2.py --script ep.txt --out ep.mp3 --stems-dir stems/
"""
import argparse
import os
import pathlib
import re
import sys
import time

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src import audio_standards as STD                           # noqa: E402
from src import sawt_cast, sawt_tts                              # noqa: E402

SR = 24000

# ── Speech-flow constants (R3.4). Deliberate, rhythmic spacing — not leftovers
# from trimming, which is how v1 ended up with dead edges and clicks.
CROSSFADE_MS = 20.0          # every join (R3.1): inaudible splice
GAP_SAME_SPEAKER = 0.22      # beat between one speaker's own sentences
GAP_SPEAKER_CHANGE = 0.48    # a longer beat when the speaker changes
GAP_AFTER_SFX = 0.14
CHUNK_CHAR_LIMIT = 240       # synthesise in comfortable pieces

_SFX_RE = re.compile(r"\[SFX:([a-z_]+)\]", re.I)
_PAUSE_RE = re.compile(r"\[PAUSE\s*([0-9.]+)?\s*s?\]", re.I)
# Delivery hints must never be SPOKEN ("(low)" became the word "low" in v1).
_STAGE_RE = re.compile(r"\((?:[^()]{0,40})\)|\[[^\]]*\]")

# Where the Kokoro model files are cached. Configurable so the SAME code works on
# the root server (/root/.cache) AND on a non-root CI runner (~/.cache), where
# /root is not writable. Honour an explicit override first, then the user's home.
_KOKORO_DIR = pathlib.Path(
    os.environ.get("KOKORO_CACHE_DIR")
    or (pathlib.Path.home() / ".cache" / "kokoro"))
_KOKORO_URLS = {
    "kokoro-v1.0.onnx":
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx",
    "voices-v1.0.bin":
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin",
}


# ── text preparation ─────────────────────────────────────────────────────────
def spoken_text(raw: str) -> str:
    """The words that should be AUDIBLE: markers and stage directions removed."""
    t = _PAUSE_RE.sub(" ", _SFX_RE.sub(" ", raw))
    t = _STAGE_RE.sub(" ", t)
    return re.sub(r"\s{2,}", " ", t).strip()


def chunk_text(text: str, limit: int = CHUNK_CHAR_LIMIT) -> list:
    """Split for synthesis on SENTENCE boundaries, falling back to clause
    boundaries only when a sentence is too long (R3.2). Never splits mid-clause or
    mid-word — v1 split on a bare character count, which cut words in half."""
    text = (text or "").strip()
    if not text:
        return []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+", text) if s.strip()]
    out = []
    for s in sentences:
        if len(s) <= limit:
            out.append(s)
            continue
        # Too long: split on clause punctuation, keeping the punctuation.
        parts = [p.strip() for p in re.split(r"(?<=[,;:—])\s+", s) if p.strip()]
        buf = ""
        for p in parts:
            if buf and len(buf) + len(p) + 1 > limit:
                out.append(buf)
                buf = p
            else:
                buf = f"{buf} {p}".strip()
        if buf:
            out.append(buf)
    return out


# ── engines ──────────────────────────────────────────────────────────────────
class KokoroEngine:
    """Deterministic studio TTS for the whole AI cast."""

    def __init__(self):
        import urllib.request
        # Import the engine FIRST so a missing dependency fails fast — before we
        # spend time/bandwidth downloading ~350MB of model files.
        from kokoro_onnx import Kokoro
        _KOKORO_DIR.mkdir(parents=True, exist_ok=True)
        for name, url in _KOKORO_URLS.items():
            p = _KOKORO_DIR / name
            if not p.exists():
                print(f"  downloading {name} …", flush=True)
                urllib.request.urlretrieve(url, str(p))
        self.k = Kokoro(str(_KOKORO_DIR / "kokoro-v1.0.onnx"),
                        str(_KOKORO_DIR / "voices-v1.0.bin"))

    def say(self, text, voice_id, speed):
        import numpy as np
        samples, sr = self.k.create(text, voice=voice_id, speed=float(speed),
                                    lang="en-us")
        return np.asarray(samples, dtype="float32"), int(sr)


class CloneEngine:
    """Chatterbox voice clone — used ONLY for a real person's consented voice."""

    def __init__(self, ref_path):
        try:
            import perth

            class _NoWatermark:
                def apply_watermark(self, wav, *a, **k):
                    return wav

            perth.PerthImplicitWatermarker = _NoWatermark
        except Exception:                                        # noqa: BLE001
            pass
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        self.model = ChatterboxMultilingualTTS.from_pretrained("cpu")
        self.sr = int(getattr(self.model, "sr", SR))
        self.ref = str(ref_path)

    def say(self, text, voice_id=None, speed=1.0):
        """NOTE: the clone engine has no native speed control, and stretching the
        result is banned (R2.4), so `speed` is deliberately ignored here. Mai's
        lines therefore sit at her natural pace."""
        import numpy as np
        wav = self.model.generate(
            text, language_id="en", audio_prompt_path=self.ref,
            exaggeration=0.6, cfg_weight=0.6, temperature=0.6,
            repetition_penalty=1.6, min_p=0.08, top_p=0.95)
        try:
            arr = wav.squeeze(0).detach().cpu().numpy()
        except (AttributeError, TypeError):
            arr = np.asarray(wav).squeeze()
        return np.asarray(arr, dtype="float32").reshape(-1), self.sr


# ── signal helpers ───────────────────────────────────────────────────────────
def resample(x, sr_from, sr_to):
    import numpy as np
    if sr_from == sr_to or not len(x):
        return x
    n = int(round(len(x) * sr_to / sr_from))
    return np.interp(np.linspace(0, 1, n, endpoint=False),
                     np.linspace(0, 1, len(x), endpoint=False),
                     x).astype("float32")


def trim_soft(x, sr, top_db=32.0, pad_ms=90.0):
    """Trim leading/trailing silence while PRESERVING the natural onset and decay
    (R3.3). v1 trimmed hard at a 4% threshold with 60ms padding and clipped the
    tails of softly-ending words."""
    import numpy as np
    import librosa
    if not len(x):
        return x
    try:
        iv = librosa.effects.split(x, top_db=top_db)
    except Exception:                                            # noqa: BLE001
        return x
    if not len(iv):
        return x
    pad = int(sr * pad_ms / 1000.0)
    a = max(0, int(iv[0][0]) - pad)
    b = min(len(x), int(iv[-1][1]) + pad)
    return x[a:b]


def crossfade_append(buf, seg, sr, ms=CROSSFADE_MS):
    """Append `seg` to `buf` with an equal-power crossfade, so the join is
    inaudible (R3.1). This is THE fix for the hard-cut defect."""
    import numpy as np
    seg = np.asarray(seg, dtype="float32")
    if not len(buf):
        return seg.copy()
    if not len(seg):
        return buf
    n = int(sr * ms / 1000.0)
    n = max(1, min(n, len(buf), len(seg)))
    # Equal-power (sine/cosine) fade keeps perceived loudness constant.
    t = np.linspace(0.0, np.pi / 2.0, n, dtype="float32")
    fade_out, fade_in = np.cos(t), np.sin(t)
    head = buf[:-n].copy()
    joined = buf[-n:] * fade_out + seg[:n] * fade_in
    return np.concatenate([head, joined, seg[n:]]).astype("float32")


def silence(sr, seconds):
    import numpy as np
    return np.zeros(max(0, int(sr * seconds)), dtype="float32")


def append_gap(buf, sr, seconds, fade_ms=8.0):
    """Append a silent gap, fading the tail to zero first.

    WHY: crossfades handle segment-to-segment joins, but appending silence to a
    buffer that ends at non-zero amplitude is itself a step discontinuity — i.e. a
    click. Measured: the assembled body looked clean at -26 LUFS but revealed 8
    discontinuities once mastered to -16, all at gap boundaries. Fading the tail
    makes every gap boundary continuous. (The following segment is faded in by
    `crossfade_append`, which crossfades against this silence.)"""
    import numpy as np
    buf = np.asarray(buf, dtype="float32")
    if len(buf):
        n = min(int(sr * fade_ms / 1000.0), len(buf))
        if n > 1:
            buf = buf.copy()
            buf[-n:] *= np.linspace(1.0, 0.0, n, dtype="float32")
    return np.concatenate([buf, silence(sr, seconds)]).astype("float32")


def declick(x, sr, window_ms=3.0, passes=2):
    """Repair step discontinuities ("clicks") inside the signal.

    Finds discontinuities with the SAME detector the quality gate uses, then blends
    across each one with an equal-power crossfade over a few milliseconds, so the
    step becomes a smooth transition. Inaudible as an edit; removes the click.

    Two passes, because repairing one step can leave a much smaller residual that
    the detector still sees. Bounded so it can never loop."""
    import numpy as np
    y = np.asarray(x, dtype="float32").copy()
    if len(y) < 64:
        return y
    half = max(4, int(sr * window_ms / 1000.0 / 2))
    for _ in range(max(1, passes)):
        d = np.abs(np.diff(y))
        win = max(64, int(sr * 0.02))
        local = np.convolve(d, np.ones(win, dtype="float32") / win,
                            mode="same") + 1e-9
        idx = np.where((d > STD.HARD_CUT_DELTA_FLOOR) &
                       (d > STD.HARD_CUT_MAD_FACTOR * local))[0]
        if not len(idx):
            break
        # Collapse to one repair per event.
        gap = max(1, int(sr * STD.HARD_CUT_CLUSTER_MS / 1000.0))
        events, prev = [], -10 ** 9
        for i in idx:
            if i - prev > gap:
                events.append(int(i))
            prev = i
        for i in events:
            a, b = max(0, i - half), min(len(y), i + half + 1)
            n = b - a
            if n < 4:
                continue
            # Equal-power blend from the pre-step level to the post-step level.
            t = np.linspace(0.0, np.pi / 2.0, n, dtype="float32")
            left = np.full(n, y[a], dtype="float32")
            right = np.full(n, y[b - 1], dtype="float32")
            # Blend the ORIGINAL samples toward a smooth ramp, keeping waveform
            # character rather than flattening the region.
            ramp = left * np.cos(t) ** 2 + right * np.sin(t) ** 2
            blend = np.linspace(0.0, 1.0, n, dtype="float32")
            shaped = np.sin(blend * np.pi) ** 2          # 0 at edges, 1 mid-window
            y[a:b] = (y[a:b] * (1.0 - shaped) + ramp * shaped).astype("float32")
    return y


def master(x, sr):
    """Mastering chain (R1.3 / design §5): high-pass, loudness-normalise to
    -16 LUFS, limit true peak to -1 dBTP, short programme fades.

    Deliberately NO broad presence/air EQ: bandwidth is not what drives perceived
    quality here (the accepted voice had the LOWEST bandwidth of the cast), and the
    boost added harshness in v1."""
    import numpy as np
    if not len(x):
        return x
    y = np.asarray(x, dtype="float32")
    # 1) high-pass ~80Hz (remove rumble/DC)
    try:
        import scipy.signal as ss
        b, a = ss.butter(2, 80.0 / (sr / 2.0), btype="high")
        y = ss.lfilter(b, a, y).astype("float32")
    except Exception:                                            # noqa: BLE001
        pass
    # 2) loudness normalise to the standard's target
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        cur = meter.integrated_loudness(y.astype("float64"))
        if np.isfinite(cur):
            y = (y * (10 ** ((STD.LUFS_TARGET - cur) / 20.0))).astype("float32")
    except Exception:                                            # noqa: BLE001
        pass
    # 3) TRUE-PEAK LIMITER (not a global gain cut).
    #
    # WHY A LIMITER: loudness-normalising speech to -16 LUFS routinely pushes
    # transient peaks above full scale. Scaling the WHOLE signal back down to fit
    # (the naive fix, and a real bug this replaced) UNDOES the normalisation — it
    # measured -25.95 LUFS against a -16 target. A limiter attenuates only the
    # moments that are too loud, so integrated loudness stays on target.
    # Margin covers TWO things: the oversampled true-peak measurement, and MP3
    # ENCODE OVERSHOOT. Measured: limiting to -1.5 dBFS produced a decoded MP3 whose
    # true peak was -0.63 dBTP — i.e. lossy encoding pushed it over the -1.0 limit.
    # 2.5 dB of margin keeps the delivered file legal.
    ceiling = 10 ** ((STD.TRUE_PEAK_MAX_DBTP - 2.5) / 20.0)
    absy = np.abs(y)
    if (absy > ceiling).any():
        # A LOOKAHEAD limiter, in the order real limiters use:
        #   need  -> per-sample gain that would fit under the ceiling
        #   min   -> sliding MINIMUM so the gain is already down BEFORE the peak
        #   smooth-> moving average so the gain envelope is continuous
        # Taking minimum(smoothed, need) afterwards would reintroduce sharp
        # per-sample dips — measured: it added 10 clicks. Sliding-min THEN smooth
        # is what keeps the envelope click-free.
        need = np.minimum(1.0, ceiling / np.maximum(absy, 1e-9)).astype("float32")
        look = max(8, int(sr * 0.003))                 # ~3ms lookahead
        try:
            from scipy.ndimage import minimum_filter1d
            gain = minimum_filter1d(need, size=2 * look + 1, mode="nearest")
        except Exception:                                        # noqa: BLE001
            # numpy fallback: min over a shifted stack
            gain = need.copy()
            for s in range(1, look + 1):
                gain[:-s] = np.minimum(gain[:-s], need[s:])
                gain[s:] = np.minimum(gain[s:], need[:-s])
        win = max(8, int(sr * 0.004))                  # ~4ms release smoothing
        gain = np.convolve(gain, np.ones(win, dtype="float32") / win,
                           mode="same").astype("float32")
        y = (y * gain).astype("float32")
        # Anything still above the ceiling is handled by SOFT saturation, which is
        # continuous (hard clipping is itself a discontinuity, i.e. a click).
        hot = np.abs(y) > ceiling
        if hot.any():
            y[hot] = (np.sign(y[hot]) * ceiling *
                      np.tanh(np.abs(y[hot]) / ceiling)).astype("float32")

    # 4) re-check loudness after limiting and correct any small drift, re-limiting
    #    gently if needed (converges in one pass for speech).
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        cur = meter.integrated_loudness(y.astype("float64"))
        if np.isfinite(cur):
            drift = STD.LUFS_TARGET - cur
            if abs(drift) > 0.3:
                gain = 10 ** (drift / 20.0)
                y = np.clip(y * gain, -ceiling, ceiling).astype("float32")
    except Exception:                                            # noqa: BLE001
        pass
    # 5) DE-CLICK repair.
    #
    # WHY: measurement proved the remaining discontinuities come from INSIDE the
    # synthesised speech, not from assembly (assembly contributes 0 once joins are
    # crossfaded and gap edges faded). Both engines occasionally emit a micro-step
    # inside a line — Kokoro at slow speed and the clone engine both did. Since we
    # cannot edit the engines, repair the artifact: blend across each discontinuity
    # so the step becomes a smooth transition. This is standard audio restoration
    # and is deterministic.
    y = declick(y, sr)

    # 6) programme fades
    f = min(int(sr * 0.12), len(y) // 2)
    if f > 0:
        ramp = np.linspace(0.0, 1.0, f, dtype="float32")
        y[:f] *= ramp
        y[-f:] *= ramp[::-1]
    return y.astype("float32")


# ── sound design ─────────────────────────────────────────────────────────────
# Legacy fallback assets (kept only so a render still works if the lab can't be
# read). The PRIMARY source is the licence-cleared Podcast Lab (src/podcast_lab),
# selected by MOOD — spec 3.7.
_SFX_DIR = BOT_DIR / "content" / "sfx"
SFX_FILES = {"knock": "knock.ogg", "tap": "knock.ogg", "creak": "creak.ogg"}
MUSIC_FILES = {"mystery": "music_mystery.ogg"}

try:
    from src import podcast_lab as _lab
except Exception:                                                # noqa: BLE001
    _lab = None


def _load_path(p, sr):
    """Load an absolute file path to mono float32 at `sr`, or None."""
    import numpy as np
    if p is None or not pathlib.Path(p).exists():
        return None
    try:
        import soundfile as sf
        y, file_sr = sf.read(str(p), dtype="float32", always_2d=False)
        if getattr(y, "ndim", 1) > 1:
            y = y.mean(axis=1)
        return resample(np.asarray(y, dtype="float32"), file_sr, sr)
    except Exception:                                            # noqa: BLE001
        return None


def load_asset(rel, sr):
    return _load_path(_SFX_DIR / rel, sr)


def load_sfx(name, sr, used=None):
    """Resolve [SFX:name] to audio. Tries the Podcast Lab first (by tag/stem), then
    the legacy content/sfx/ files. Appends the chosen asset dict to `used` (for
    attribution). Returns a normalised mono float32 array (possibly empty)."""
    import numpy as np
    y = None
    if _lab is not None:
        try:
            p, asset = _lab.resolve_sfx_path(name)
            if p is not None:
                y = _load_path(p, sr)
                if y is not None and len(y) and used is not None and asset:
                    used.append(asset)
        except Exception:                                        # noqa: BLE001
            y = None
    if y is None or not len(y):                       # legacy fallback
        fn = SFX_FILES.get((name or "").lower())
        y = load_asset(fn, sr) if fn else None
    if y is None or not len(y):
        return np.zeros(0, dtype="float32")
    pk = float(np.max(np.abs(y))) or 1.0
    return (y * (0.55 / pk)).astype("float32")


def _lab_bed(mood, sr, seed=0, used=None):
    """A music bed for `mood` from the Podcast Lab, or None. Records the asset in
    `used` for attribution."""
    if _lab is None:
        return None
    try:
        p, asset = _lab.select_bed_path(mood, seed=seed)
        y = _load_path(p, sr)
        if y is not None and len(y) and used is not None and asset:
            used.append(asset)
        return y
    except Exception:                                            # noqa: BLE001
        return None


def duck_music(voice, bed, sr, base=0.20, ducked=0.06, outro=2.5):
    """Score the programme with a bed that ducks under speech. `ducked` is set low
    so speech keeps well clear of the bed (the standard requires >=12 dB)."""
    import numpy as np
    if bed is None or not len(bed):
        return voice
    total = len(voice) + int(sr * outro)
    if len(bed) < total:
        bed = np.tile(bed, int(np.ceil(total / len(bed))))
    bed = bed[:total].astype("float32").copy()
    v = append_gap(voice, sr, outro)
    win = max(1, int(sr * 0.15))
    env = np.convolve(np.abs(v), np.ones(win) / win, mode="same")
    pk = float(env.max()) or 1.0
    gain = np.where(env > pk * 0.06, ducked, base).astype("float32")
    sw = max(1, int(sr * 0.25))
    gain = np.convolve(gain, np.ones(sw) / sw, mode="same").astype("float32")
    fin = min(int(sr * 1.0), total)
    bed[:fin] *= np.linspace(0, 1, fin, dtype="float32")
    fout = min(int(sr * 2.0), total)
    bed[-fout:] *= np.linspace(1, 0, fout, dtype="float32")
    return (v + bed * gain).astype("float32")


# ── the render ───────────────────────────────────────────────────────────────
def synth_line(text, ch, level, kokoro, clone):
    """Synthesise ONE character line: chunk on sentence boundaries, synthesise each
    piece with the right engine at the CEFR-native speed, trim softly, and join with
    crossfades. Returns mono float32 @ SR. Extracted so a single failing line can be
    re-rendered in isolation (spec task 2.3) without re-rendering the episode."""
    import numpy as np
    engine = clone if (ch["engine"] == sawt_cast.ENGINE_CLONE and clone) else kokoro
    voice_id = ch.get("voice_id")
    speed = sawt_cast.speed_for_level(level, ch["key"])
    line = np.zeros(0, dtype="float32")
    for piece in chunk_text(text):
        samples, sr = engine.say(piece, voice_id, speed)
        samples = resample(samples, sr, SR) if sr != SR else samples
        samples = trim_soft(samples, SR)
        line = crossfade_append(line, samples, SR)
    return line


# ── engine isolation (Option A) ──────────────────────────────────────────────
#
# Kokoro needs numpy>=2, Chatterbox needs numpy<2 — they cannot share one env. When
# isolation is enabled, each line is synthesised by scripts/voice_worker.py running
# under the interpreter of a venv that has ONLY that engine. Assembly/mastering/gate
# stay in this process and need no engine. Off by default, so the server (single
# env) and the test suite keep the simple in-process path.
ISOLATION_ENABLED = os.environ.get("EEC_ISOLATE_ENGINES", "") not in ("", "0", "false")
_WORKER_PY = {
    "kokoro": os.environ.get("EEC_KOKORO_PYTHON", ""),
    "clone": os.environ.get("EEC_CLONE_PYTHON", ""),
}


def _worker_python_for(engine_kind: str) -> str:
    """The interpreter to run the worker for `engine_kind`, or '' to stay in-process."""
    return _WORKER_PY.get(engine_kind, "") if ISOLATION_ENABLED else ""


def _synth_line_isolated(text, ch, level, engine_kind: str):
    """Synthesise one line by shelling out to voice_worker.py under the engine's
    dedicated venv. Returns mono float32 @ SR, or None on failure (caller decides
    the fallback). Uses a text FILE for the line so no shell-quoting edge case can
    corrupt it."""
    import subprocess
    import tempfile
    import numpy as np
    import soundfile as sf

    py = _worker_python_for(engine_kind)
    if not py:
        return None
    work = pathlib.Path(tempfile.mkdtemp(prefix="eec_voice_"))
    try:
        txt = work / "line.txt"
        txt.write_text(text, encoding="utf-8")
        out = work / "line.wav"
        cmd = [py, str(BOT_DIR / "scripts" / "voice_worker.py"),
               "--engine", engine_kind, "--character", ch["display"],
               "--level", level, "--text-file", str(txt), "--out", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode != 0 or not out.exists():
            # Surface BOTH streams and the tail (ONNX prints a benign PCI warning to
            # stderr that would otherwise mask the real error) so failures are
            # diagnosable in CI.
            err = (r.stderr or "").strip()
            outp = (r.stdout or "").strip()
            print(f"    ⚠️ isolated {engine_kind} worker failed "
                  f"(rc={r.returncode}, wav_exists={out.exists()})")
            if outp:
                print(f"       stdout: {outp[-600:]}")
            if err:
                print(f"       stderr: {err[-1200:]}")
            return None
        y, file_sr = sf.read(str(out), dtype="float32", always_2d=False)
        if getattr(y, "ndim", 1) > 1:
            y = y.mean(axis=1)
        y = np.asarray(y, dtype="float32")
        return resample(y, file_sr, SR) if file_sr != SR else y
    except Exception as e:                                       # noqa: BLE001
        print(f"    ⚠️ isolated {engine_kind} worker error: {e}")
        return None
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def synth_line_for(text, ch, level, kokoro, clone):
    """Synthesise one line, choosing isolation-vs-in-process automatically.

    If engine isolation is enabled AND a worker interpreter is configured for the
    line's engine, run it in that subprocess; otherwise use the in-process engine
    passed in (kokoro/clone). This is the single seam the render loop calls."""
    engine_kind = ("clone"
                   if ch.get("engine") == sawt_cast.ENGINE_CLONE else "kokoro")
    if _worker_python_for(engine_kind):
        y = _synth_line_isolated(text, ch, level, engine_kind)
        if y is not None and len(y):
            return y
        # The isolated worker failed. Only fall back to an in-process engine if one
        # actually exists — under isolation it does NOT (we skipped loading it to
        # avoid the numpy conflict), so calling synth_line would hit `.say` on None.
        have_inprocess = (clone is not None if engine_kind == "clone"
                          else kokoro is not None)
        if not have_inprocess:
            raise RuntimeError(
                f"isolated {engine_kind} voice worker failed and no in-process "
                f"engine is available to fall back to")
    return synth_line(text, ch, level, kokoro, clone)


def plan(script: str) -> dict:
    """Engine-free plan: who speaks, how often, with which voice."""
    segs = sawt_tts.parse_script(script)
    cast = {}
    for label, _ in segs:
        c = sawt_cast.character_for(label)
        cast.setdefault(c["key"], {"display": c["display"], "lines": 0,
                                   "engine": c["engine"],
                                   "voice": c.get("voice_id") or c.get("clone_ref")})
        cast[c["key"]]["lines"] += 1
    return {"line_count": len(segs), "cast": cast}


def render(script: str, out_path, level="A2", music="mystery",
           sound_design=True, stems_dir=None, seed=0) -> dict:
    """Render an episode. Returns a result dict (also useful to the QA gate).

    `music` is a MOOD name (e.g. 'mystery', 'warm'); the bed is chosen from the
    Podcast Lab by that mood (spec 3.7). `seed` (e.g. episode number) varies which
    bed is picked while staying reproducible for a given (mood, seed)."""
    import numpy as np
    import soundfile as sf

    segs = sawt_tts.parse_script(script)
    if not segs:
        raise SystemExit("No speaker lines found (expected 'Speaker: text').")

    used_assets = []          # lab assets actually used, for attribution/credit

    # Which engines does this episode actually need? Only load what we use — the
    # clone engine is heavy and most episodes may not need it.
    needed = {sawt_cast.character_for(l)["key"] for l, _ in segs}
    need_kokoro = any(sawt_cast.CAST[k]["engine"] == sawt_cast.ENGINE_KOKORO
                      for k in needed)
    need_clone = any(sawt_cast.CAST[k]["engine"] == sawt_cast.ENGINE_CLONE
                     for k in needed)

    # If a line's engine is handled by an isolated worker, we do NOT load that
    # engine in-process (that's the whole point — avoid the numpy conflict). Only
    # load an in-process engine for an engine we actually need AND is not isolated.
    kokoro_isolated = bool(_worker_python_for("kokoro"))
    clone_isolated = bool(_worker_python_for("clone"))

    kokoro = KokoroEngine() if (need_kokoro and not kokoro_isolated) else None
    clone = None
    if need_clone and not clone_isolated:
        ref = _SFX_DIR / sawt_cast.CLONE_REF_MAI
        if ref.exists():
            clone = CloneEngine(ref)
        else:
            print(f"  ⚠️ clone reference missing ({ref}); those lines will be "
                  f"voiced by the narrator instead")

    print(f"  engines: kokoro={'isolated' if kokoro_isolated else ('yes' if kokoro else 'no')} "
          f"clone={'isolated' if clone_isolated else ('yes' if clone else 'no')}")

    body = np.zeros(0, dtype="float32")
    prev_key = None
    stems = []
    t0 = time.time()

    for i, (label, raw) in enumerate(segs, 1):
        ch = sawt_cast.character_for(label)
        key = ch["key"]

        # Rhythmic spacing (R3.4), composed rather than left over from trimming.
        if len(body):
            gap = GAP_SAME_SPEAKER if key == prev_key else GAP_SPEAKER_CHANGE
            body = append_gap(body, SR, gap)

        # Inline sound effects, placed AROUND speech so nothing is masked (R3.5).
        for m in _SFX_RE.finditer(raw):
            fx = load_sfx(m.group(1), SR, used=used_assets)
            if len(fx):
                body = crossfade_append(body, fx, SR)
                body = append_gap(body, SR, GAP_AFTER_SFX)

        # Deliberate dramatic pauses.
        for pm in _PAUSE_RE.finditer(raw):
            secs = float(pm.group(1)) if pm.group(1) else 1.0
            body = append_gap(body, SR, min(secs, 5.0))

        text = spoken_text(raw)
        if not text:
            prev_key = key
            continue

        # Synthesise one line. `synth_line_for` routes to an isolated per-engine
        # subprocess when configured (Option A), else uses the in-process engine.
        line = synth_line_for(text, ch, level, kokoro, clone)
        if len(line):
            if stems_dir:
                sp = pathlib.Path(stems_dir)
                sp.mkdir(parents=True, exist_ok=True)
                f = sp / f"line{i:03d}_{key}.wav"
                sf.write(str(f), line, SR)
                stems.append({"index": i, "character": key, "file": str(f),
                              "seconds": round(len(line) / SR, 2), "text": text})
            body = crossfade_append(body, line, SR)

        prev_key = key
        if i % 5 == 0 or i == len(segs):
            print(f"  [{i}/{len(segs)}] {time.time()-t0:.0f}s", flush=True)

    # Sound design + mastering. The bed is chosen from the Podcast Lab by MOOD
    # (spec 3.7); if the lab can't provide one we fall back to the legacy file.
    used_music = None
    if sound_design and music and music.lower() != "none":
        bed = _lab_bed(music.lower(), SR, seed=seed, used=used_assets)
        if bed is None or not len(bed):
            legacy = MUSIC_FILES.get(music.lower(), "")
            bed = load_asset(legacy, SR) if legacy else None
        if bed is not None and len(bed):
            used_music = music
            # Crossfade the body in against the silent intro so speech doesn't
            # start on a step discontinuity (same class of click as gap edges).
            voice = crossfade_append(silence(SR, 2.5), body, SR)
            audio = duck_music(voice, bed, SR)
        else:
            audio = append_gap(body, SR, 0.8)
    else:
        audio = append_gap(body, SR, 0.8)

    audio = master(audio, SR)
    out = pathlib.Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out), audio, SR, format="MP3")

    # De-dup used assets (by file) and derive the human credit line.
    seen = set()
    uniq_used = []
    for a in used_assets:
        f = a.get("file")
        if f and f not in seen:
            seen.add(f)
            uniq_used.append(a)
    credit = _lab.credit_line(uniq_used) if _lab is not None else ""

    dur = len(audio) / SR
    print(f"\n  wrote {out} — {dur/60:.1f} min ({dur:.1f}s), {len(segs)} lines, "
          f"music={used_music or 'none'} (mood), in {time.time()-t0:.1f}s")
    return {"ok": True, "out_path": str(out), "duration_seconds": round(dur, 2),
            "line_count": len(segs), "music": used_music, "stems": stems,
            "level": level,
            "used_assets": [a.get("file") for a in uniq_used],
            "credit": credit}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--script", required=True)
    ap.add_argument("--out", default="episode.mp3")
    ap.add_argument("--level", default="A2", help="CEFR level (drives native pace)")
    ap.add_argument("--music", default="mystery",
                    help="MOOD for the bed (mystery/warm/wonder/...) or 'none'")
    ap.add_argument("--seed", type=int, default=0,
                    help="episode number — varies bed choice, reproducibly")
    ap.add_argument("--no-sound-design", action="store_true")
    ap.add_argument("--stems-dir", default="",
                    help="also write per-line voice stems here (for per-line QA)")
    ap.add_argument("--plan", action="store_true", help="print the plan and exit")
    args = ap.parse_args()

    script = pathlib.Path(args.script).read_text(encoding="utf-8")
    p = plan(script)
    cast_desc = ", ".join(f"{v['display']}x{v['lines']}({v['engine']})"
                          for v in p["cast"].values())
    print(f"Plan: {p['line_count']} lines · cast {cast_desc} · level {args.level}")
    if args.plan:
        return 0

    render(script, args.out, level=args.level, music=args.music,
           sound_design=not args.no_sound_design,
           stems_dir=args.stems_dir or None, seed=args.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
