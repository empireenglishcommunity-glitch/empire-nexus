# Empire English Chronicles — Audio Quality Standard

**The contract every episode must satisfy before a student can hear it.**

- Thresholds (machine-readable): [`src/audio_standards.py`](../src/audio_standards.py)
- Measurement tool: [`scripts/audio_qa.py`](../scripts/audio_qa.py)
- Spec: [`.kiro/specs/eec-chronicles-quality/`](../../../.kiro/specs/eec-chronicles-quality/)

---

## Why this document exists

This is a **teaching** podcast. If a learner cannot cleanly hear a word, the
product has failed at its only job. Before this standard existed the pipeline
generated → rendered → published audio **without ever measuring it**, on a
stochastic engine — so quality was a lottery, and the owner's verdict on four
shipped episodes was that only one of the cast voices was acceptable.

This document turns "sounds fine to me" into a number that anybody can re-check.

---

## The rule about changing a threshold

> **Never loosen a threshold to make a failing episode pass.**
> If a threshold is genuinely wrong, change it deliberately in
> `src/audio_standards.py` **and** record the reason here, with the measurement
> that justifies it. A silently-relaxed gate is the same as having no gate.

---

## The standard

| # | Metric | Threshold | Gating? | Why this number |
|---|--------|-----------|:-------:|-----------------|
| 1 | **Intelligibility (WER)** | **≤ 0.05** | ✅ **primary** | ASR transcript vs the script, word error rate. The only metric that directly tests "can a learner hear the words". 5% leaves headroom for the ASR's own mistakes while still catching dropped, doubled, mumbled and hallucinated words. |
| 2 | **Naturalness (spectral flatness)** | **≤ 0.012** | ✅ *voice stems only* | Empirically separates the voice the owner accepted from the three he rejected (see §Naturalness). |
| 3 | **Hard cuts** | **≤ 2** per episode | ✅ | Abrupt waveform discontinuities = audible clicks / chopped words. Proper crossfading should give ~0. |
| 4 | **Loudness** | **−16 LUFS ± 1.0** | ✅ | Standard podcast delivery target (ITU-R BS.1770). Without it, one episode blasts and the next is inaudible. |
| 5 | **True peak** | **≤ −1.0 dBTP** | ✅ | Headroom so no device — or Discord's re-encode — clips into distortion. Measured on a 4× oversampled signal to catch inter-sample peaks. |
| 6 | **Dead air** | **≤ 2.5 s** unintended | ✅ | Longer reads as "the audio broke". Deliberate `[PAUSE n s]` markers are excluded via the script's pause budget. |
| 7 | **Speech above bed** | **≥ 12 dB** | ✅ | Music must never compete with teaching content. (Proxy measurement — see §Known limitations.) |
| 8 | **Duration** | inside the level's CEFR window | ✅ | Read from `config.PODCAST_LEVEL_PROFILES`, so length follows the learner's level rather than an independent idea of length. |
| 9 | **Per-line floor** | ≥ 0.4 s, non-silent | ✅ | Catches a line whose synthesis silently failed. |
| — | **Bandwidth >3.4 kHz** | reported only | ❌ **never** | See §The bandwidth trap. |

**Fail-closed:** if a *critical* metric (`wer`, `hard_cuts`, `loudness_lufs`,
`true_peak_dbtp`) cannot be measured — e.g. no ASR engine installed — the result is
**FAIL**, not pass. "We couldn't check" must never read as "it's fine".

---

## The bandwidth trap (read this before "improving" audio)

Frequency bandwidth is **reported but never gates**, because optimising it actively
misled this project. Measured on the real cast, against the owner's own verdict:

| Voice | Energy >3.4 kHz | Owner's verdict |
|---|---|---|
| `mai_voice` | **1.1%** (lowest) | ✅ **accepted** — "the only cast I like" |
| `owner_voice` | 10.9% | ❌ rejected as unclear |
| `male_us_1` | 27.0% | ❌ rejected |
| `male_us_2` | **39.4%** (highest) | ❌ rejected (worst) |

The correlation is **inverted**. Chasing bandwidth produced EQ-boosted voices that
measured "better" and sounded worse. Naturalness and intelligibility are the real
levers.

Two techniques are **banned by design** for the same reason — both were introduced
to "improve" quality and measurably degraded it:

- **No pitch-shifting a voice reference** — displaces formants, giving a synthetic
  timbre. (This is what made one character sound wrong.)
- **No post-synthesis time-stretching** — a phase vocoder smears transients and
  destroys consonant clarity. (This is what made the narrator unclear.) Set pace
  **natively at synthesis time** instead.

---

## Naturalness: the method is part of the standard

A flatness number is meaningless without stating how it was measured — **the same
clip measures 0.031 or 0.0002** depending on method. Both orderings agreed, but the
thresholds differ ~100×, so method and threshold are pinned together:

> STFT `n_fft=1024`, `hop=256` → `spectral_flatness` → **mean over speech frames
> only** (frames at/above the 60th percentile of frame energy), on **voice-only**
> audio.

Measured that way, against the owner's verdict:

| Voice | Flatness | Verdict |
|---|---|---|
| `mai_voice` | 0.0002 | ✅ accepted |
| `female_us_1` | 0.0101 | (never heard) |
| `owner_voice` | 0.0176 | ❌ rejected — "unclear" |
| `male_us_1` | 0.0342 | ❌ rejected |
| `male_us_2` | 0.0355 | ❌ rejected |

`≤ 0.012` sits in the gap: everything rejected fails, the accepted voice passes with
a wide margin.

**Honest caveat.** This is fitted to **four** judged voices, so it is a *screen*,
not proof of beauty. The authoritative acceptance tests for voice quality remain
(a) **WER** for intelligibility and (b) **the owner's ear** at the Phase 1 listening
checkpoint. Revalidate this threshold when the Kokoro cast is benchmarked.

**It only gates on voice-only stems.** On a mastered mix the music bed dominates the
spectrum and hides exactly the defect we need to catch — proof: the four mastered
episodes measure ~0.013 (apparently excellent) while their own voice references
measure 0.018–0.036 (three rejected). On a mix it is therefore reported as
diagnostic only.

---

## Baseline: the four episodes that prompted this work

Measured 2026-09-06 with `scripts/audio_qa.py` (WER not included — these predate
the ASR wiring). **Every episode fails**, and the failures are systematic, not
random:

| Episode | Duration | Hard cuts | Loudness | True peak | Failing |
|---|---|---|---|---|---|
| Ep1 "The Locked Door" | 160.8 s | **6** | **−24.3 LUFS** | −2.6 dBTP | cuts, loudness, duration |
| Ep2 "The Door Opens" | 140.6 s | 2 | **−21.8 LUFS** | **−0.38 dBTP** | loudness, peak, duration |
| Ep3 "Secret of the Symbols" | 98.5 s | 2 | **−21.9 LUFS** | **−0.35 dBTP** | loudness, peak, duration |
| Ep4 "The Memory Box" | 126.2 s | 2 | **−22.9 LUFS** | **−0.41 dBTP** | loudness, peak, duration |

**What the baseline revealed:**

1. **Every episode is 6–8 dB too quiet** (−21.8 to −24.3 vs −16 LUFS). A
   consistent, invisible defect nobody had noticed.
2. **Three of four exceed the true-peak ceiling**, risking clipping through
   Discord's transcode.
3. **Every episode is far shorter than its CEFR window** (98–161 s vs A2's
   300–420 s). Length was never tied to the learner's level.
4. On a real WER run, Ep3 measured **0.0545** and the diff exposed **four script
   words absent from the audio** ("what do you want") — a genuine dropped-content
   defect that had shipped unnoticed.

### Correction to an earlier claim

An earlier audit reported "237–386 hard cuts per episode". That figure came from a
crude percentile-based **sample** count, which inflates a single click into dozens
of hits. The rigorous detector — absolute floor **and** a large multiple of local
variation, with nearby hits collapsed into one event — measures **2–6 per episode**.
The defect was real; the number was wrong. **Re-derive numbers, never copy them.**

---

## A real bug this standard caught immediately

A bare `[SFX:shimmer]` line **matches the `Speaker: text` pattern** — speaker
`[SFX`, text `shimmer]` — so it was parsed as dialogue. The narrator therefore
**literally said "shimmer]" and "creak]"** in published episodes, while the sound
effect never played.

Fixed in `src/sawt_tts.parse_script()` (and mirrored in the QA tool's reference
extraction): any line beginning with a bracket is a stage direction and is never
spoken. Regression tests pin both.

---

## Known limitations (stated, not hidden)

- **Speech-above-bed is a proxy.** Without separate stems it compares loud frames
  (speech) against quiet frames (bed alone). It reliably catches a bed mixed too
  loud; it is not a true stem-based measurement.
- **Naturalness needs voice stems.** Whole-mix flatness cannot judge a voice
  (above). Per-line stem metrics land with the pipeline gate.
- **WER inherits ASR error.** Some measured error is the speech recogniser's, not
  the audio's — which is why the threshold carries headroom, and why a failure
  report includes the actual word diff so a human can see what happened.
- **The naturalness threshold is fitted to four voices.** Revalidate as the cast
  grows.

---

## How to run it

```bash
# full check (needs an ASR engine for WER)
python3.12 scripts/audio_qa.py --audio episode.mp3 --script episode.txt --level A2

# a voice reference / per-line stem (naturalness gates here)
python3.12 scripts/audio_qa.py --audio content/sfx/voices/mai_voice.ogg --voice-only --no-asr

# machine-readable report for the pipeline
python3.12 scripts/audio_qa.py --audio ep.mp3 --script ep.txt --json report.json
```

Exit codes: **0** = PASS · **1** = FAIL · **2** = could not run.
