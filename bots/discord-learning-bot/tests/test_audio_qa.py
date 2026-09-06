"""Tests for the Empire English Chronicles audio quality harness (spec Phase 0).

Two jobs:
  1. the metrics are correct and reproducible;
  2. **the gate can actually FAIL** — a gate never shown to fail is not a gate
     (spec R4.6). So each check is exercised in BOTH directions using synthetic
     audio, which keeps these tests fast and dependency-light (no speech model).

ASR is injected as a fake transcriber, so intelligibility (WER) is tested without
downloading a model.
"""
import importlib.util
import pathlib

import numpy as np
import pytest
import soundfile as sf

from src import audio_standards as STD

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load_qa():
    spec = importlib.util.spec_from_file_location(
        "audio_qa", BOT_DIR / "scripts" / "audio_qa.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


qa = _load_qa()
SR = 24000


# ── synthetic audio helpers ──────────────────────────────────────────────────
def _speechish(seconds=3.0, sr=SR, seed=0):
    """A voice-like signal: a moving fundamental plus harmonics, amplitude-
    modulated like syllables. Tonal (low spectral flatness), so it stands in for
    clean speech without needing a real recording."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(sr * seconds)) / sr
    f0 = 140 + 12 * np.sin(2 * np.pi * 0.7 * t)          # slight pitch movement
    phase = 2 * np.pi * np.cumsum(f0) / sr
    sig = np.zeros_like(t)
    for k, amp in ((1, 1.0), (2, 0.5), (3, 0.28), (4, 0.14)):
        sig += amp * np.sin(k * phase)
    syll = 0.55 + 0.45 * np.sin(2 * np.pi * 3.2 * t)      # syllable envelope
    sig = sig * syll
    sig += 0.002 * rng.standard_normal(len(t))            # a touch of air
    sig /= np.max(np.abs(sig)) or 1.0
    return (sig * 0.3).astype("float32")


def _write(tmp_path, y, name="a.wav", sr=SR):
    p = tmp_path / name
    sf.write(str(p), y, sr)
    return p


def _at_lufs(y, sr, target):
    """Scale `y` so its integrated loudness is ~`target` LUFS."""
    import pyloudnorm as pyln
    meter = pyln.Meter(sr)
    cur = meter.integrated_loudness(y.astype("float64"))
    return (y * (10 ** ((target - cur) / 20.0))).astype("float32")


def _fake_transcriber(text):
    return lambda _path: text


# ── the standard itself ──────────────────────────────────────────────────────
def test_standard_is_complete_and_sane():
    s = STD.summary()
    for key in ("wer_max", "flatness_max", "hard_cuts_max", "lufs_target",
                "true_peak_max_dbtp", "dead_air_max_s", "min_line_seconds",
                "critical_metrics"):
        assert key in s, f"standard lost {key}"
    # Bandwidth must NEVER become a gate (the metric that misled this project).
    assert STD.BANDWIDTH_IS_DIAGNOSTIC_ONLY is True
    # Intelligibility must be a critical (fail-closed) metric.
    assert "wer" in STD.CRITICAL_METRICS
    assert 0 < STD.WER_MAX < 0.25
    assert STD.MAX_RENDER_ATTEMPTS >= 1


def test_duration_window_follows_cefr_profile():
    """Episode length must come from the same CEFR profile the rest of Empire
    English uses, and must be stricter for lower levels."""
    a1 = STD.duration_window("A1")
    b1 = STD.duration_window("B1")
    assert a1[0] < a1[1] and b1[0] < b1[1]
    assert b1[1] >= a1[1], "higher levels should allow longer episodes"


# ── WER (intelligibility) ────────────────────────────────────────────────────
def test_wer_perfect_and_imperfect():
    assert qa.word_error_rate("hello there maya", "hello there maya") == 0.0
    # one substitution in three words
    assert qa.word_error_rate("hello there maya", "hello their maya") == pytest.approx(1 / 3)
    # a dropped word is caught
    assert qa.word_error_rate("open the locked door", "open the door") == pytest.approx(0.25)


def test_script_to_text_ignores_labels_and_directions():
    """The reference must contain only words that should be AUDIBLE."""
    script = ("Narrator: The door opened. [SFX:creak]\n"
              "[SFX:shimmer]\n"
              "[Maya pauses, breath shallow]\n"
              "Maya: (whisper) Who is there?\n"
              "[PAUSE 2s]\n")
    text = qa.script_to_text(script).lower()
    assert "the door opened" in text
    assert "who is there" in text
    # markers, stage directions and speaker labels must not appear
    for bad in ("sfx", "creak", "shimmer", "pause", "whisper", "narrator", "maya:"):
        assert bad not in text, f"{bad!r} leaked into the spoken reference"


def test_script_to_text_bare_sfx_line_regression():
    """REGRESSION: a bare '[SFX:shimmer]' line matches the 'Speaker: text' shape
    (speaker '[SFX', text 'shimmer]'). It used to be treated as dialogue, so the
    narrator SAID 'shimmer]' in published episodes. It must be ignored."""
    assert qa.script_to_text("[SFX:shimmer]") == ""
    assert qa.script_to_text("[SFX:creak]\n[PAUSE 2s]") == ""


def test_pause_budget_read_from_script():
    assert qa.script_pause_budget("a [PAUSE 2s] b") == 2.0
    assert qa.script_pause_budget("a [PAUSE] b") == 1.0
    assert qa.script_pause_budget("no markers") == 0.0


# ── hard-cut detection (the "sudden cut" defect) ─────────────────────────────
def test_hard_cuts_clean_audio_has_none(tmp_path):
    y = _speechish(3.0)
    count, _ = qa.measure_hard_cuts(y, SR)
    assert count == 0, "clean synthetic speech should have no discontinuities"


def _inject_clicks(y, positions, height=0.6):
    """Inject unambiguous click artifacts — a single-sample step, which is what an
    un-crossfaded splice between two trimmed segments actually produces."""
    out = y.copy()
    for pos in positions:
        out[pos] = np.clip(out[pos] + height, -1.0, 1.0)
    return out


def test_hard_cuts_detects_injected_clicks():
    """Splicing without a crossfade creates exactly the artifact students heard."""
    y = _inject_clicks(_speechish(3.0),
                       [int(SR * 0.5), int(SR * 1.5), int(SR * 2.5)])
    count, where = qa.measure_hard_cuts(y, SR)
    assert count >= 3, f"expected >=3 cuts, found {count} at {where}"


def test_hard_cuts_counts_one_event_once():
    """A single click must count once, not once per affected sample."""
    y = _inject_clicks(_speechish(2.0), [SR])
    count, _ = qa.measure_hard_cuts(y, SR)
    assert count == 1, f"one click counted as {count} events"


# ── loudness + true peak ─────────────────────────────────────────────────────
def test_loudness_measures_target(tmp_path):
    y = _at_lufs(_speechish(4.0), SR, STD.LUFS_TARGET)
    lufs = qa.measure_loudness(y, SR)
    assert lufs is not None
    assert abs(lufs - STD.LUFS_TARGET) <= STD.LUFS_TOLERANCE


def test_true_peak_detects_hot_signal():
    quiet = _speechish(1.0) * 0.1
    hot = _speechish(1.0) / (np.max(np.abs(_speechish(1.0))) or 1.0) * 0.999
    assert qa.measure_true_peak(quiet, SR) < STD.TRUE_PEAK_MAX_DBTP
    assert qa.measure_true_peak(hot, SR) > STD.TRUE_PEAK_MAX_DBTP


# ── dead air ─────────────────────────────────────────────────────────────────
def test_dead_air_detects_long_silence():
    y = np.concatenate([_speechish(1.0), np.zeros(int(SR * 4.0), dtype="float32"),
                        _speechish(1.0)])
    worst, runs = qa.measure_dead_air(y, SR)
    assert worst >= 3.5, (worst, runs)


def test_dead_air_ignores_short_gaps():
    y = np.concatenate([_speechish(1.0), np.zeros(int(SR * 0.3), dtype="float32"),
                        _speechish(1.0)])
    worst, _ = qa.measure_dead_air(y, SR)
    assert worst < STD.DEAD_AIR_MAX_S


# ── naturalness: gates only on voice-only audio ──────────────────────────────
def test_flatness_gates_only_on_voice_only_audio(tmp_path):
    """A mastered mix (music bed) cannot be judged for voice naturalness — the bed
    masks it. Reported as diagnostic there, gating on a voice stem."""
    noisy = (np.random.default_rng(1).standard_normal(SR * 2) * 0.2).astype("float32")
    p = _write(tmp_path, noisy, "noise.wav")
    mix = qa.analyze(p, use_asr=False, voice_only=False)
    stem = qa.analyze(p, use_asr=False, voice_only=True)
    assert mix["metrics"]["flatness"]["status"] == qa.INFO
    # White noise is maximally un-voice-like, so as a stem it must FAIL.
    assert stem["metrics"]["flatness"]["status"] == qa.FAIL


def test_flatness_method_parameters_are_pinned():
    """The threshold is only meaningful with the method it was derived from, so the
    parameters live in the standard and the analyser must use them."""
    for attr in ("FLATNESS_N_FFT", "FLATNESS_HOP", "FLATNESS_SPEECH_PERCENTILE"):
        assert hasattr(STD, attr), f"standard lost the pinned parameter {attr}"


# ── the gate, end to end, in BOTH directions (spec R4.6) ────────────────────
def _good_episode(tmp_path, seconds=330.0):
    """A synthetic 'good' episode: correct loudness, safe peak, no cuts, and a
    duration inside the A2 window."""
    y = _at_lufs(_speechish(seconds, seed=3), SR, STD.LUFS_TARGET)
    y = np.clip(y, -0.85, 0.85).astype("float32")
    return _write(tmp_path, y, "good.wav")


SCRIPT = "Narrator: hello there maya this is a test of the system\n"
SPOKEN = "hello there maya this is a test of the system"


def test_gate_passes_known_good(tmp_path):
    p = _good_episode(tmp_path)
    r = qa.analyze(p, script_text=SCRIPT, level="A2",
                   transcriber=_fake_transcriber(SPOKEN))
    assert r["passed"] is True, r["failures"] or r["unmeasured_critical"]


def test_gate_fails_on_dropped_words(tmp_path):
    """The primary defect this catches: audio that omits script content."""
    p = _good_episode(tmp_path)
    r = qa.analyze(p, script_text=SCRIPT, level="A2",
                   transcriber=_fake_transcriber("hello there maya"))
    assert r["passed"] is False
    assert "wer" in r["failures"]


def test_gate_fails_on_wrong_loudness(tmp_path):
    y = _at_lufs(_speechish(330.0, seed=4), SR, -26.0)      # far too quiet
    p = _write(tmp_path, y, "quiet.wav")
    r = qa.analyze(p, script_text=SCRIPT, level="A2",
                   transcriber=_fake_transcriber(SPOKEN))
    assert r["passed"] is False
    assert "loudness_lufs" in r["failures"]


def test_gate_fails_on_hard_cuts(tmp_path):
    y = _at_lufs(_speechish(330.0, seed=5), SR, STD.LUFS_TARGET)
    y = _inject_clicks(np.clip(y, -0.7, 0.7),
                       [int(SR * 20 * i) for i in range(1, 8)])
    p = _write(tmp_path, y, "cuts.wav")
    r = qa.analyze(p, script_text=SCRIPT, level="A2",
                   transcriber=_fake_transcriber(SPOKEN))
    assert r["passed"] is False
    assert "hard_cuts" in r["failures"]


def test_gate_fails_on_wrong_duration_for_level(tmp_path):
    """A 10-second 'episode' cannot satisfy an A2 learner's profile."""
    y = _at_lufs(_speechish(10.0, seed=6), SR, STD.LUFS_TARGET)
    p = _write(tmp_path, np.clip(y, -0.85, 0.85), "short.wav")
    r = qa.analyze(p, script_text=SCRIPT, level="A2",
                   transcriber=_fake_transcriber(SPOKEN))
    assert r["passed"] is False
    assert "duration_s" in r["failures"]


def test_gate_is_fail_closed_when_asr_missing(tmp_path):
    """'We could not check' must NEVER read as 'it is fine'."""
    p = _good_episode(tmp_path)
    r = qa.analyze(p, script_text=SCRIPT, level="A2", use_asr=False)
    assert r["passed"] is False
    assert "wer" in r["unmeasured_critical"]
    assert not r["failures"], "should fail on unmeasured-critical, not a metric"


def test_report_is_serialisable_and_human_readable(tmp_path):
    import json
    p = _good_episode(tmp_path)
    r = qa.analyze(p, script_text=SCRIPT, level="A2",
                   transcriber=_fake_transcriber(SPOKEN))
    json.dumps(r)                                  # must not raise
    text = qa.format_report(r)
    assert "VERDICT" in text and "wer" in text


def test_bandwidth_is_reported_but_never_fails(tmp_path):
    """Bandwidth misled this project; it must be visible and non-authoritative."""
    p = _good_episode(tmp_path)
    r = qa.analyze(p, script_text=SCRIPT, level="A2",
                   transcriber=_fake_transcriber(SPOKEN))
    bw = r["metrics"]["bandwidth_above_3k4_pct"]
    assert bw["status"] == qa.INFO
    assert "bandwidth_above_3k4_pct" not in r["failures"]
