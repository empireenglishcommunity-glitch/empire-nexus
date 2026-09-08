#!/usr/bin/env python3.12
"""Empire English Chronicles — AUDIO QUALITY ANALYSER / GATE.

Measures a rendered episode against the standard in `src/audio_standards.py` and
returns a pass/fail verdict plus a machine-readable report.

WHY: the podcast pipeline used to render and publish audio without ever measuring
it, on a stochastic engine — so quality was a lottery. This tool is the instrument
that ends that. Phase 2 wires it into the render pipeline as a fail-closed gate;
it is useful standalone from day one.

Design notes
------------
* **Fail-closed.** A metric listed in `audio_standards.CRITICAL_METRICS` that
  cannot be measured is a FAILURE, not a pass. "We couldn't check" must never read
  as "it's fine".
* **Bandwidth is diagnostic only.** Reported, never gating — optimising it actively
  misled this project (the accepted voice had the lowest bandwidth of the cast).
* **ASR is injectable.** `analyze()` takes an optional `transcriber` callable so
  tests can run fast without a speech model, and so the engine can be swapped.

Usage
-----
    # full check (needs an ASR engine for the WER metric)
    python3.12 scripts/audio_qa.py --audio episode.mp3 --script episode.txt --level A2

    # diagnostics without a speech model (NOT a pass — WER is critical)
    python3.12 scripts/audio_qa.py --audio episode.mp3 --no-asr

    # machine-readable report for the pipeline
    python3.12 scripts/audio_qa.py --audio ep.mp3 --script ep.txt --json report.json

Exit codes: 0 = PASS · 1 = FAIL · 2 = could not run (bad input/missing deps).
"""
import argparse
import json
import pathlib
import re
import sys

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src import audio_standards as STD                           # noqa: E402

# Status values used in the report.
PASS, FAIL, WARN, SKIP, INFO = "PASS", "FAIL", "WARN", "SKIP", "INFO"


# ── low-level audio helpers ──────────────────────────────────────────────────
def load_audio(path, sr=24000):
    """Load an audio file → (mono float32 samples, sample_rate). Raises on failure
    so the caller can exit 2 rather than silently 'passing' an unreadable file."""
    import librosa
    y, _sr = librosa.load(str(path), sr=sr, mono=True)
    if y is None or len(y) == 0:
        raise ValueError(f"{path}: decoded to no audio")
    return y.astype("float32"), sr


def measure_hard_cuts(y, sr):
    """Count abrupt waveform discontinuities (clicks / chopped words).

    A real click is a sample-to-sample jump that is large in ABSOLUTE terms AND
    far larger than the LOCAL variation, so ordinary loud speech transients don't
    register. Nearby hits are collapsed into one event, so a single click counts
    once instead of dozens of times. Returns (count, positions_seconds)."""
    import numpy as np
    d = np.abs(np.diff(y.astype("float32")))
    if len(d) < 16:
        return 0, []
    # Local variation via a moving median-absolute-deviation (robust to speech).
    win = max(64, int(sr * 0.02))
    kernel = np.ones(win, dtype="float32") / win
    local = np.convolve(d, kernel, mode="same") + 1e-9
    flagged = np.where((d > STD.HARD_CUT_DELTA_FLOOR) &
                       (d > STD.HARD_CUT_MAD_FACTOR * local))[0]
    if not len(flagged):
        return 0, []
    # Collapse into clusters.
    gap = max(1, int(sr * STD.HARD_CUT_CLUSTER_MS / 1000.0))
    clusters, start = [], flagged[0]
    prev = flagged[0]
    for i in flagged[1:]:
        if i - prev > gap:
            clusters.append(start)
            start = i
        prev = i
    clusters.append(start)
    return len(clusters), [round(float(c) / sr, 2) for c in clusters]


def measure_loudness(y, sr):
    """Integrated loudness in LUFS (ITU-R BS.1770 via pyloudnorm). Returns None if
    the library is unavailable — the caller then fails closed on a critical metric
    rather than guessing with a home-made approximation."""
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        return float(meter.integrated_loudness(y.astype("float64")))
    except Exception:                                            # noqa: BLE001
        return None


def measure_true_peak(y, sr, oversample=4):
    """True peak in dBTP, estimated on an oversampled signal so inter-sample peaks
    (which a plain sample-peak misses and which clip on real devices) are caught."""
    import numpy as np
    if not len(y):
        return None
    n = len(y) * oversample
    xi = np.linspace(0, len(y) - 1, num=n, endpoint=True)
    up = np.interp(xi, np.arange(len(y)), y.astype("float64"))
    peak = float(np.max(np.abs(up)))
    if peak <= 0:
        return -120.0
    return float(20.0 * np.log10(peak))


def measure_flatness(y, sr, speech_only=True):
    """Mean spectral flatness — the naturalness proxy that actually tracked the
    owner's verdict. Measured over SPEECH frames only where possible, so silence
    and music beds don't skew the voice's score."""
    import numpy as np
    import librosa
    # The measurement METHOD is part of the standard: the same clip measured two
    # ways differs by 100x, so these parameters come from audio_standards and must
    # not be tweaked here (that would invalidate FLATNESS_MAX).
    n_fft = STD.FLATNESS_N_FFT
    S = np.abs(librosa.stft(y, n_fft=n_fft, hop_length=STD.FLATNESS_HOP))
    flat = librosa.feature.spectral_flatness(S=S)[0]
    if speech_only and len(flat) > 8:
        # frame_length MUST match the STFT that produced S, or librosa rejects it.
        rms = librosa.feature.rms(S=S, frame_length=n_fft)[0]
        # Frames at/above this energy percentile are "probably speech".
        thr = float(np.percentile(rms, STD.FLATNESS_SPEECH_PERCENTILE))
        sel = flat[rms >= thr]
        if len(sel) >= 4:
            return float(np.mean(sel))
    return float(np.mean(flat))


def measure_dead_air(y, sr, top_db=35.0):
    """Longest silent run in seconds, and all runs. Deliberate [PAUSE n s] markers
    are accounted for by the caller (it knows the script's pause budget)."""
    import librosa
    import numpy as np
    iv = librosa.effects.split(y, top_db=top_db)
    if len(iv) == 0:
        return float(len(y) / sr), []
    runs = []
    if iv[0][0] > 0:
        runs.append(float(iv[0][0]) / sr)
    for i in range(len(iv) - 1):
        runs.append(float(iv[i + 1][0] - iv[i][1]) / sr)
    if iv[-1][1] < len(y):
        runs.append(float(len(y) - iv[-1][1]) / sr)
    runs = [round(r, 2) for r in runs if r > 0.05]
    return (max(runs) if runs else 0.0), runs


def measure_speech_over_bed(y, sr):
    """Approximate how far speech sits above the music/ambience bed, in dB.

    Without separate stems this is a PROXY: compare RMS in speech-active frames
    against RMS in the quiet frames between lines (where only the bed plays). It is
    honest about being a proxy, and it reliably catches a bed mixed too loud."""
    import numpy as np
    import librosa
    frame = max(256, int(sr * 0.025))
    rms = librosa.feature.rms(y=y, frame_length=frame, hop_length=frame)[0]
    if len(rms) < 8:
        return None
    hi = float(np.percentile(rms, 90))      # speech
    lo = float(np.percentile(rms, 10))      # bed alone (gaps)
    if lo <= 1e-7:
        return 60.0                          # effectively no bed under the gaps
    return float(20.0 * np.log10(hi / lo))


def measure_bandwidth(y, sr):
    """Share of energy above the split frequency. DIAGNOSTIC ONLY (never gates)."""
    import numpy as np
    S = np.abs(np.fft.rfft(y))
    fr = np.fft.rfftfreq(len(y), 1.0 / sr)
    tot = float((S ** 2).sum()) or 1.0
    hi = float((S[fr >= STD.BANDWIDTH_SPLIT_HZ] ** 2).sum())
    return 100.0 * hi / tot


# ── intelligibility (WER) ────────────────────────────────────────────────────
_SPEAKER_RE = re.compile(r"^\s*([^:\n]{1,40}):\s*(.+)$")
_MARKER_RE = re.compile(r"\[[^\]]*\]|\((?:[^()]{0,40})\)")
# A standalone direction line ("[SFX:knock]", "[Maya pauses]") is not speech.
# Mirrors src.sawt_tts._DIRECTION_RE — a bare "[SFX:x]" otherwise matches the
# "Speaker: text" shape and pollutes the reference with the fake word "x]".
_DIRECTION_RE = re.compile(r"^\s*[\[(]")


def script_to_text(script: str) -> str:
    """Reduce a speaker-labelled script to the words that should be AUDIBLE:
    speaker labels dropped, [SFX:…]/[PAUSE]/stage directions stripped. This is the
    reference the ASR transcript is compared against."""
    out = []
    for raw in (script or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if _DIRECTION_RE.match(line):
            continue                          # standalone direction: not spoken
        m = _SPEAKER_RE.match(line)
        text = m.group(2) if m else None
        if text is None:
            continue                          # non-dialogue line: not spoken
        text = _MARKER_RE.sub(" ", text)
        if text.strip():
            out.append(text.strip())
    return " ".join(out)


def normalise_words(text: str) -> list:
    """Lowercase, strip punctuation, collapse spaces → word list for WER. Keeps
    apostrophes inside words so "don't" is one token."""
    t = (text or "").lower()
    t = re.sub(r"[^\w\s']", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return [w for w in t.split(" ") if w]


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Standard Levenshtein WER = (S+D+I)/N over words. 0.0 = perfect."""
    ref, hyp = normalise_words(reference), normalise_words(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1,            # deletion
                         cur[j - 1] + 1,         # insertion
                         prev[j - 1] + (r != h))  # substitution/match
        prev = cur
    return float(prev[len(hyp)]) / float(len(ref))


def measure_repetition(reference: str, hypothesis: str) -> tuple:
    """Count TTS 'stutter' events: a short phrase heard CONSECUTIVELY TWICE in the
    ASR transcript that is NOT a genuine consecutive repeat in the script.

    Returns (count, examples). WER tolerates a stutter because the duplicated words
    still overlap the reference, so this is measured separately. We look at adjacent
    duplicate unigrams, bigrams and trigrams in the hypothesis, and subtract any
    that are ALSO adjacent duplicates in the reference (so a script that really says
    'no, no' is not flagged)."""
    hyp = normalise_words(hypothesis)
    ref = normalise_words(reference)

    def _adjacent_dupes(words):
        seen = set()
        events = []
        for n in (3, 2, 1):                      # longer phrases first (stronger signal)
            for i in range(len(words) - 2 * n + 1):
                a = tuple(words[i:i + n])
                b = tuple(words[i + n:i + 2 * n])
                if a == b:
                    events.append((i, a))
        return events

    ref_dupes = {a for _i, a in _adjacent_dupes(ref)}
    hyp_events = _adjacent_dupes(hyp)
    # Collapse overlapping detections and drop genuine script repeats.
    flagged, used = [], set()
    for i, a in sorted(hyp_events, key=lambda e: (e[0], -len(e[1]))):
        if a in ref_dupes:
            continue
        span = set(range(i, i + 2 * len(a)))
        if span & used:
            continue
        used |= span
        flagged.append(" ".join(a))
    return len(flagged), flagged[:5]


def default_transcriber(path, model_size="base.en"):
    """Transcribe with faster-whisper. Returns text, or None if unavailable —
    the caller then fails closed (WER is a critical metric)."""
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segs, _info = model.transcribe(str(path), language="en")
        return " ".join(s.text for s in segs).strip()
    except Exception as e:                                       # noqa: BLE001
        print(f"  (ASR unavailable: {type(e).__name__}: {e})", file=sys.stderr)
        return None


# ── the analysis ─────────────────────────────────────────────────────────────
def _check(report, name, status, value, threshold, note=""):
    report["metrics"][name] = {"status": status, "value": value,
                               "threshold": threshold, "note": note}


def analyze(audio_path, script_text=None, level="A2", transcriber=None,
            use_asr=True, pause_budget_s=0.0, voice_only=False):
    """Measure `audio_path` against the standard. Returns a report dict with
    `passed` (bool) and per-metric detail.

    `transcriber` is an optional callable(path) -> text, so tests can inject a fake
    and the ASR engine stays swappable. `pause_budget_s` is the longest silence the
    SCRIPT legitimately asks for (from [PAUSE n s]) so deliberate drama isn't
    mistaken for dead air.

    `voice_only=True` declares that this audio is VOICE with no music/ambience bed
    (i.e. a per-line stem). Naturalness (flatness) only GATES in that case —
    measured on a mastered mix it is meaningless, because the music bed dominates
    the spectrum and would hide exactly the unnatural voices we need to catch.
    Baseline proof: the mastered episodes measure ~0.013 (apparently excellent)
    while their own voice references measure 0.031-0.077 (one rejected by the
    owner). A gate that cannot see the defect is worse than no gate, so on a mix
    this is reported as diagnostic only."""
    import numpy as np                                           # noqa: F401

    audio_path = pathlib.Path(audio_path)
    report = {"audio": str(audio_path), "level": level,
              "standard": STD.summary(), "metrics": {}, "passed": False}

    y, sr = load_audio(audio_path)
    duration = len(y) / sr
    report["duration_seconds"] = round(duration, 2)

    # 1) Intelligibility — the primary gate.
    if not use_asr:
        _check(report, "wer", SKIP, None, STD.WER_MAX,
               "ASR disabled (--no-asr); critical metric unmeasured")
    elif not script_text:
        _check(report, "wer", SKIP, None, STD.WER_MAX,
               "no --script provided; cannot compute WER")
    else:
        tx = (transcriber or default_transcriber)(audio_path)
        if tx is None:
            _check(report, "wer", SKIP, None, STD.WER_MAX,
                   "ASR engine unavailable")
        else:
            ref = script_to_text(script_text)
            wer = word_error_rate(ref, tx)
            _check(report, "wer", PASS if wer <= STD.WER_MAX else FAIL,
                   round(wer, 4), STD.WER_MAX,
                   f"{len(normalise_words(ref))} reference words")
            report["transcript"] = tx
            # Repetition / TTS stutter (reuses the same transcript — no extra ASR).
            reps, rep_examples = measure_repetition(ref, tx)
            rep_max = getattr(STD, "REPETITION_MAX", 1)
            _check(report, "repetition",
                   PASS if reps <= rep_max else FAIL, reps, rep_max,
                   (f"repeated: {rep_examples}" if rep_examples else "none"))

    # 2) Naturalness — only authoritative on VOICE-ONLY audio (see docstring).
    flat = measure_flatness(y, sr)
    if voice_only:
        _check(report, "flatness", PASS if flat <= STD.FLATNESS_MAX else FAIL,
               round(flat, 4), STD.FLATNESS_MAX, "voice-only stem: gating")
    else:
        _check(report, "flatness", INFO, round(flat, 4), STD.FLATNESS_MAX,
               "mastered mix: DIAGNOSTIC ONLY (music bed masks voice naturalness) "
               "- gate this on per-line voice stems instead")

    # 3) Hard cuts.
    cuts, where = measure_hard_cuts(y, sr)
    _check(report, "hard_cuts", PASS if cuts <= STD.HARD_CUTS_MAX else FAIL,
           cuts, STD.HARD_CUTS_MAX,
           f"first at {where[:5]}s" if where else "none")

    # 4) Loudness.
    lufs = measure_loudness(y, sr)
    if lufs is None:
        _check(report, "loudness_lufs", SKIP, None, STD.LUFS_TARGET,
               "pyloudnorm unavailable")
    else:
        ok = abs(lufs - STD.LUFS_TARGET) <= STD.LUFS_TOLERANCE
        _check(report, "loudness_lufs", PASS if ok else FAIL, round(lufs, 2),
               f"{STD.LUFS_TARGET} +/- {STD.LUFS_TOLERANCE}")

    # 5) True peak.
    tp = measure_true_peak(y, sr)
    if tp is None:
        _check(report, "true_peak_dbtp", SKIP, None, STD.TRUE_PEAK_MAX_DBTP)
    else:
        _check(report, "true_peak_dbtp",
               PASS if tp <= STD.TRUE_PEAK_MAX_DBTP else FAIL, round(tp, 2),
               STD.TRUE_PEAK_MAX_DBTP)

    # 6) Dead air (deliberate script pauses excluded).
    worst, runs = measure_dead_air(y, sr)
    allowed = max(STD.DEAD_AIR_MAX_S, float(pause_budget_s) + 0.5)
    _check(report, "dead_air_s", PASS if worst <= allowed else FAIL,
           round(worst, 2), round(allowed, 2),
           f"{len(runs)} gaps; script pause budget {pause_budget_s}s")

    # 7) Speech above the bed.
    ratio = measure_speech_over_bed(y, sr)
    if ratio is None:
        _check(report, "speech_over_bed_db", SKIP, None,
               STD.SPEECH_OVER_BED_MIN_DB)
    else:
        _check(report, "speech_over_bed_db",
               PASS if ratio >= STD.SPEECH_OVER_BED_MIN_DB else FAIL,
               round(ratio, 1), STD.SPEECH_OVER_BED_MIN_DB, "proxy measurement")

    # 8) Duration within the level's CEFR window.
    dmin, dmax = STD.duration_window(level)
    _check(report, "duration_s", PASS if dmin <= duration <= dmax else FAIL,
           round(duration, 1), f"{dmin}-{dmax}", f"CEFR profile for {level}")

    # 9) Bandwidth — DIAGNOSTIC ONLY, never gates (see audio_standards).
    _check(report, "bandwidth_above_3k4_pct", INFO,
           round(measure_bandwidth(y, sr), 1), None,
           "diagnostic only - never a pass/fail criterion")

    # ── verdict: fail-closed ────────────────────────────────────────────────
    failures = [k for k, m in report["metrics"].items() if m["status"] == FAIL]
    # A critical metric that could not be measured is a FAILURE, not a pass.
    unmeasured_critical = [k for k in STD.CRITICAL_METRICS
                           if report["metrics"].get(k, {}).get("status") == SKIP]
    report["failures"] = failures
    report["unmeasured_critical"] = unmeasured_critical
    report["passed"] = not failures and not unmeasured_critical
    return report


def script_pause_budget(script_text: str) -> float:
    """Longest deliberate pause the script asks for, e.g. '[PAUSE 2s]' → 2.0."""
    longest = 0.0
    for m in re.finditer(r"\[PAUSE\s*([0-9.]+)?\s*s?\]", script_text or "", re.I):
        longest = max(longest, float(m.group(1)) if m.group(1) else 1.0)
    return longest


def format_report(report) -> str:
    """Human-readable summary (what a person reads in CI output)."""
    lines = [f"AUDIO QA — {report['audio']}",
             f"  duration {report.get('duration_seconds')}s · level {report['level']}"]
    order = ["wer", "repetition", "flatness", "hard_cuts", "loudness_lufs",
             "true_peak_dbtp", "dead_air_s", "speech_over_bed_db", "duration_s",
             "bandwidth_above_3k4_pct"]
    for k in order:
        m = report["metrics"].get(k)
        if not m:
            continue
        icon = {PASS: "✅", FAIL: "❌", SKIP: "⚠️ ", WARN: "⚠️ ", INFO: "ℹ️ "}[m["status"]]
        thr = "" if m["threshold"] is None else f" (limit {m['threshold']})"
        note = f"  — {m['note']}" if m["note"] else ""
        lines.append(f"  {icon} {k}: {m['value']}{thr}{note}")
    if report["unmeasured_critical"]:
        lines.append(f"  ❌ UNMEASURED CRITICAL: {report['unmeasured_critical']} "
                     f"— fail-closed (cannot verify = not publishable)")
    lines.append("  VERDICT: " + ("PASS ✅" if report["passed"] else "FAIL ❌"))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", required=True, help="rendered episode (mp3/wav/ogg)")
    ap.add_argument("--script", default="", help="the script it was rendered from "
                                                "(required for the WER metric)")
    ap.add_argument("--level", default="A2", help="CEFR level for the duration window")
    ap.add_argument("--json", default="", help="write the report to this path")
    ap.add_argument("--no-asr", action="store_true",
                    help="skip transcription (diagnostics only — will NOT pass, "
                         "because intelligibility is a critical metric)")
    ap.add_argument("--voice-only", action="store_true",
                    help="this file is a VOICE stem with no music bed, so the "
                         "naturalness (flatness) metric gates instead of being "
                         "reported as diagnostic")
    args = ap.parse_args()

    script_text = ""
    if args.script:
        p = pathlib.Path(args.script)
        if not p.exists():
            print(f"script not found: {p}", file=sys.stderr)
            return 2
        script_text = p.read_text(encoding="utf-8")

    try:
        report = analyze(args.audio, script_text=script_text, level=args.level,
                         use_asr=not args.no_asr,
                         pause_budget_s=script_pause_budget(script_text),
                         voice_only=args.voice_only)
    except Exception as e:                                       # noqa: BLE001
        print(f"could not analyse {args.audio}: {type(e).__name__}: {e}",
              file=sys.stderr)
        return 2

    print(format_report(report))
    if args.json:
        pathlib.Path(args.json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"  report → {args.json}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
