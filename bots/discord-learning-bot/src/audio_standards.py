"""Empire English Chronicles — THE AUDIO QUALITY STANDARD (single source of truth).

Every threshold that decides whether an episode is fit for a student lives HERE,
and nowhere else. `scripts/audio_qa.py` measures against these numbers, the render
pipeline gates on them, and CI enforces them.

WHY THIS FILE EXISTS
--------------------
The podcast used to render and publish audio without ever measuring it, on a
stochastic engine — so quality was a lottery ("sometimes good, sometimes bad").
A teaching podcast cannot ship audio a learner may not be able to hear. These
numbers turn quality from an opinion into a pass/fail fact.

THE RULE ON CHANGING A THRESHOLD
--------------------------------
Never loosen a number to make a failing episode pass. If a threshold is genuinely
wrong, change it deliberately here AND record the reason in
`docs/AUDIO-STANDARDS.md`. A silently-relaxed gate is the same as no gate.

See `.kiro/specs/eec-chronicles-quality/requirements.md` (R1) for the full contract.
"""

# ── PRIMARY: can the learner actually hear the words? ────────────────────────
# Word Error Rate of an ASR transcript against the script the audio was rendered
# from. This is the ONLY metric that directly tests the product's core promise, so
# it is the primary gate. 5% leaves headroom for the ASR's own mistakes (no ASR is
# perfect) while still catching dropped, doubled, mumbled or hallucinated words —
# all of which the old cloning engine produced.
WER_MAX = 0.05

# ── Naturalness ──────────────────────────────────────────────────────────────
# Mean spectral flatness of the VOICE. Low = tonal/voice-like; high = noisy or
# over-processed.
#
# ⚠️ THE METHOD IS PART OF THE STANDARD. A flatness number is meaningless without
# stating how it was measured — measured two ways, the same clip gives 0.031 or
# 0.0002. Both orderings agreed, but the thresholds differ by 100x, so method and
# threshold MUST be pinned together. The pinned method is:
#     STFT n_fft=1024, hop=256 → spectral_flatness → mean over SPEECH frames only
#     (frames at/above the 60th percentile of frame energy), on VOICE-ONLY audio.
# Silence and music are excluded because they dominate the spectrum and hide the
# voice — which is the defect we are trying to catch.
#
# EMPIRICAL basis (measured with the pinned method on the real cast, against the
# owner's own verdict):
#     mai_voice     0.0002  → ACCEPTED ("the only cast I like")
#     female_us_1   0.0101  → never heard by the owner
#     owner_voice   0.0176  → rejected as "unclear"
#     male_us_1     0.0342  → rejected
#     male_us_2     0.0355  → rejected
# 0.012 sits in the gap: everything the owner rejected fails, the voice he accepted
# passes with a wide margin.
#
# ⚠️ HONEST CAVEAT: this is fitted to FOUR judged voices. It is a useful screen, NOT
# proof of beauty. It is therefore a SCREEN, while the authoritative acceptance
# test for voice quality remains (a) WER for intelligibility and (b) the owner's
# listening checkpoint. Revalidate this threshold when the Kokoro cast is
# benchmarked (spec task 1.2 / checkpoint 1.14).
#
# NOTE: this metric — not frequency bandwidth — is what tracked the owner's
# preference (see BANDWIDTH_IS_DIAGNOSTIC_ONLY below).
FLATNESS_MAX = 0.012

# The pinned measurement parameters (changing these invalidates FLATNESS_MAX).
FLATNESS_N_FFT = 1024
FLATNESS_HOP = 256
FLATNESS_SPEECH_PERCENTILE = 60

# ── Speech flow: no audible cuts ─────────────────────────────────────────────
# Count of abrupt waveform discontinuities (clicks / chopped words). The old
# assembly concatenated trimmed chunks with no crossfade and measured 237-386 per
# episode — roughly 12 per spoken line, which is what "sudden cut" sounded like.
# With proper crossfading this should be ~0; 2 allows for rare edge cases without
# tolerating a chopped-sounding episode.
HARD_CUTS_MAX = 2

# Detector tuning (documented so the count is reproducible, not magic):
#   - a discontinuity must exceed BOTH an absolute floor and a large multiple of
#     the LOCAL variation, so ordinary loud speech transients don't register;
#   - nearby flagged samples are collapsed into ONE cluster, so a single click is
#     counted once rather than dozens of times.
HARD_CUT_DELTA_FLOOR = 0.12      # absolute sample-to-sample jump
HARD_CUT_MAD_FACTOR = 12.0       # x local median-absolute-deviation
HARD_CUT_CLUSTER_MS = 20.0       # samples within this window = one event

# ── Loudness: identical perceived volume every single day ────────────────────
# Integrated loudness (ITU-R BS.1770 / LUFS). -16 LUFS is the widely used podcast
# delivery target for mono/stereo speech content. Without this, one episode blasts
# and the next is inaudible — a daily automated feed must be consistent.
LUFS_TARGET = -16.0
LUFS_TOLERANCE = 1.0             # +/- 1.0 LU

# True peak ceiling. -1.0 dBTP keeps headroom so no playback device or lossy
# re-encode (Discord transcodes) clips the audio into distortion.
TRUE_PEAK_MAX_DBTP = -1.0

# ── Dead air ─────────────────────────────────────────────────────────────────
# Longest UNINTENDED silence. Deliberate dramatic pauses are written in the script
# as [PAUSE n s] and are excluded by passing the expected pause budget. Anything
# beyond this reads as "the audio broke".
DEAD_AIR_MAX_S = 2.5

# ── Music must never fight the teaching ──────────────────────────────────────
# How far speech sits above the music/ambience bed, in dB, while someone is
# talking. A learner has to catch every word; a bed that competes with speech is a
# defect in a teaching product even if it sounds cinematic.
SPEECH_OVER_BED_MIN_DB = 12.0

# ── Per-line sanity ──────────────────────────────────────────────────────────
# A rendered line shorter than this (or silent) means synthesis failed for that
# line — the failure mode that used to slip through silently.
MIN_LINE_SECONDS = 0.4

# ── Diagnostics only — NEVER a gate ─────────────────────────────────────────
# Frequency bandwidth (share of energy above 3.4 kHz) is REPORTED but never gates.
# Hard-won lesson: the voice the owner accepted had the LOWEST bandwidth of the
# entire cast (1.1%), while the voice he called worst had the HIGHEST (39.4%).
# Optimising bandwidth actively misled this project. Keep it visible, never
# authoritative.
BANDWIDTH_IS_DIAGNOSTIC_ONLY = True
BANDWIDTH_SPLIT_HZ = 3400.0

# ── Fail-closed policy ───────────────────────────────────────────────────────
# Metrics that MUST be measured for an episode to be publishable. If one of these
# cannot be computed (e.g. no ASR engine installed), the result is a FAILURE, not
# a pass — "we couldn't check" must never read as "it's fine".
CRITICAL_METRICS = ("wer", "hard_cuts", "loudness_lufs", "true_peak_dbtp")

# Bounded retries, so an automatic system can never run away (R9.6).
MAX_RENDER_ATTEMPTS = 3


def duration_window(level: str) -> tuple:
    """Allowed (min_seconds, max_seconds) for an episode at `level`.

    Read from the SAME CEFR profile the rest of Empire English uses
    (config.PODCAST_LEVEL_PROFILES) so episode length follows the learner's level
    instead of an independent idea of length. Falls back to a permissive window if
    config isn't importable (keeps the analyser usable standalone)."""
    try:
        from . import config                                     # noqa: PLC0415
        p = config.podcast_level_profile(level)
        return float(p["duration_min"]), float(p["duration_max"])
    except Exception:                                            # noqa: BLE001
        try:
            import config as _c                                  # noqa: PLC0415
            p = _c.podcast_level_profile(level)
            return float(p["duration_min"]), float(p["duration_max"])
        except Exception:                                        # noqa: BLE001
            return 30.0, 1800.0


def summary() -> dict:
    """The whole standard as data — used by the analyser's report and by tests
    that assert the standard is complete (so a threshold can't be quietly lost)."""
    return {
        "wer_max": WER_MAX,
        "flatness_max": FLATNESS_MAX,
        "hard_cuts_max": HARD_CUTS_MAX,
        "lufs_target": LUFS_TARGET,
        "lufs_tolerance": LUFS_TOLERANCE,
        "true_peak_max_dbtp": TRUE_PEAK_MAX_DBTP,
        "dead_air_max_s": DEAD_AIR_MAX_S,
        "speech_over_bed_min_db": SPEECH_OVER_BED_MIN_DB,
        "min_line_seconds": MIN_LINE_SECONDS,
        "bandwidth_is_diagnostic_only": BANDWIDTH_IS_DIAGNOSTIC_ONLY,
        "critical_metrics": list(CRITICAL_METRICS),
        "max_render_attempts": MAX_RENDER_ATTEMPTS,
    }
