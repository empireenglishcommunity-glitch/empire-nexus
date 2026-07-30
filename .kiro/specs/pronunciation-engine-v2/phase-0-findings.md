# Nutq 2 — Phase 0 feasibility findings (GO)

Ran in an **isolated sandbox** (separate machine from production; nothing on the
live server was touched). Ground truth = dojo TTS clips + their exact text from
`audio-manifest.json`. Method: score a clip against its **own** text (a correct
read) vs a **different** day's text (a wrong read) — the gap proves the engine
measures *sounds*, not words.

## Chosen candidate: allosaurus (universal phoneme recognizer)
Open-source, CPU-only, self-contained model. Selected as the **fit-now** engine
for the current small box.

## Results vs requirements
| Gate | Requirement | Measured | Verdict |
|---|---|---|---|
| Catches a wrong read (R2) | wrong << correct | correct ≈ **72–86**, wrong ≈ **10–21** (~60-pt gap) | ✅ |
| Memory (R4) | ≤ ~1 GB, isolated | RSS **~0.8–0.95 GB** (model + torch) | ✅ |
| Latency (R5) | ≤ ~8 s | **0.15–0.6 s** on 8 vCPU (a few s on 2 vCPU) | ✅ |
| Free & owned (R3) | no API / per-use cost | fully local | ✅ |

Packaged-service parity (`scorer.score_audio`, per-word + Arabic partial credit):
- Day1 own **79.7** / wrong 21.3 · Day2 own **85.6** / wrong 19.5 · Day4 own
  **74.4** / wrong 19.2 — wrong reads correctly flag the mismatched words.

## Honest caveats (→ handled in later phases)
- Correct reads score ~75–86, not ~100 — a mix of the small universal model's
  noise and phoneme-notation mapping. **Phase 3 calibrates** so a clean read lands
  high (real Arabic-accented samples), tuning the `scorer.calibrate` hook.
- Phase 0 used **clean TTS clips**, not real student audio. Feasibility (fits +
  fast + discriminates) is proven; accent fairness is a Phase 3 task.
- The higher-accuracy wav2vec2 model (~2.2 GB) does **not** fit the current box —
  it's the "when hardware grows" option; the design swaps models via config.

## Decision
**GO** to Phase 1 (build the `nutq-scorer` service). Higher-accuracy model and
final calibration are later, gated steps.
