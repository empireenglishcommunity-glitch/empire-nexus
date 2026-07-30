# nutq-scorer

Self-hosted, phoneme-level pronunciation scorer for **Nutq 2**. Open-source,
CPU-only, no external API, no per-use cost (spec: `pronunciation-engine-v2`).

It replaces the *scoring brain* of Nutq 1 (Whisper transcription + word
comparison, which measured *which words* were said, not *how well*). This engine
compares the **sounds produced** against the day's exact target text.

## How it works
```
reference text --G2P (g2p_en)--> expected phonemes
recording      --allosaurus----> recognized phonemes
        │
        └── Needleman-Wunsch alignment (Arabic-substitution aware)
                 → per-word accuracy + overall 0-100 score + "focus on" words
```
- **Beginner-kind but honest:** known Arabic-speaker substitutions (p/b, f/v, θ/s,
  ð/d, …) get *partial* credit; a genuinely wrong read still scores low.
- **Calibration** (`scorer.calibrate`) is tuned on real Arabic-accented samples in
  Phase 3; Phase 1 ships an honest near-identity default.

## API (internal only)
- `GET /health` → `{ok, model_loaded}`
- `POST /score` → JSON `{audio_b64, reference_text, level, filename}` →
  `{ok, score, raw_score, missed_words, per_word, feedback_en, feedback_ar,
    heard_phonemes, expected}`

Auth: send `X-Nutq-Token: $NUTQ_SCORER_TOKEN`. If the env var is unset, auth is
disabled (dev only) and a warning is logged.

## Run locally
```bash
docker build -t nutq-scorer .
docker run --rm -e NUTQ_SCORER_TOKEN=secret -p 8080:8080 nutq-scorer
curl localhost:8080/health
```

## Footprint (measured, Phase 0)
- RSS ~0.8–0.95 GB (model + torch); `mem_limit: 1200m` leaves margin.
- Latency: sub-second on 8 vCPU; a few seconds on a 2-core box — well within the
  bot's ≤8 s best-effort budget.

## Safety
- Isolated container; the bot calls it best-effort with a timeout. If it's slow,
  down, or errors, the bot shows "couldn't score this time" and the student flow
  (completion, #showcase) is **never** affected.
- Serialized inference (single-worker executor) so only one model runs at a time.

## Scale playbook (grow with the student count)
1. **Vertical:** raise `mem_limit` / move to a bigger host for a larger, higher-
   accuracy model (e.g. wav2vec2-phoneme) — a config change, not a rewrite.
2. **Horizontal:** run N identical `nutq-scorer` replicas behind a simple
   round-robin (the service is stateless); the bot picks any instance.
3. Inference is CPU-bound and serialized per instance → capacity ≈ N replicas ×
   (1 / avg-latency) scorings/sec.

## Tests
```bash
pip install pytest
pytest tests/ -q      # scoring-math tests; no model/torch needed
```
