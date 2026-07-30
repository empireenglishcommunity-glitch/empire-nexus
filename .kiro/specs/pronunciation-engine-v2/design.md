# Nutq 2 — Design

**Status:** DRAFT — awaiting owner approval. No code until approved.
Traceability: every section maps to R1–R14 in `requirements.md`.

---

## 1. Guiding idea: swap the brain, keep the body

Nutq 1 is two layers. We keep one and replace the other:

- **KEEP — the delivery pipeline (body):** page recorder → `POST /api/submit-recording`
  / `POST /api/pronunciation-check` → flag gate → on-page score panel →
  heard-vs-target → "try again" → `pronunciation_scores` storage. Proven and live.
- **REPLACE — the scoring brain:** today's *Whisper transcription + word
  comparison* becomes a **self-hosted, phoneme-level acoustic scorer**.

Because the JSON contract (`pronunciation {...}`) stays identical (R7), **the dojo
needs no change.**

---

## 2. Architecture (R3, R4, R14)

```
 Practice page (dojo, unchanged)
        │  audio + week/day/exercise
        ▼
 empire-english-bot  ── api_server.py
   score_recording_bytes()  ── best-effort, ≤8s timeout, flag-gated (unchanged wrapper)
        │  HTTP (internal Docker network)
        ▼
 nutq-scorer   (NEW, separate container)
   • loads the phoneme model ONCE at startup
   • POST /score {audio_b64, reference_text, level} → JSON result
   • hard mem_limit (~1 GB), CPU-only, stateless
```

- **Separate container** (`nutq-scorer`) so the ML runtime is isolated from the
  bot; a crash/slowness there can never take RAM/CPU from the bot (R4). Docker
  `mem_limit` + `restart: unless-stopped`.
- **Stateless** → scale by running more replicas or moving to a bigger host, no
  rewrite (R14). For the pilot: a single instance on the current box.
- **Internal-only** networking (not exposed publicly); the bot calls it over the
  compose network. Auth via a shared secret header.

---

## 3. Scoring pipeline (R1, R2, R6, R10)

1. **Reference → expected phonemes (G2P).** Convert the day's exact target text to
   a phoneme sequence using an open-source grapheme-to-phoneme step
   (eSpeak-NG / `phonemizer`, or `g2p_en`). Cached per (text) — small.
2. **Audio → recognized phonemes (acoustic model).** Run the recording through the
   chosen open-source **phoneme recognizer** (candidates in §4).
3. **Align** expected vs recognized with a weighted edit-distance alignment
   (Needleman–Wunsch) → per-phoneme: correct / substituted / deleted / inserted.
4. **Score.** Accuracy = weighted % of correctly produced phonemes, aggregated to
   **per-word** accuracy, then an overall 0–100. (Optional later: a Completeness
   sub-score = fraction of reference words attempted.)
5. **Map to words.** Words with failed phonemes become the "focus on" list and the
   heard-vs-target highlight (R7/R8) — now driven by *sounds*, not word identity.
6. **Fairness (R6).** Known Arabic-speaker substitutions (/p/↔/b/, /v/↔/f/, θ/ð, …)
   score as **partial credit**, not zero. A gentle floor + level leniency are
   applied to the *wording/tone*, but a wrong read still yields a low number (R2).
   All thresholds are **calibrated** in Phase 3, not guessed.

**Output contract (identical to Nutq 1, R7):**
```json
{ "scored": true, "score": 63, "is_beginner_grace": false,
  "feedback_en": "...", "feedback_ar": "...",
  "missed_words": ["through"], "transcript": "<phoneme-informed 'we heard'>",
  "expected": "<target text>" }
```

---

## 4. Model candidates (Phase 0 measures + selects — R3, R4)

CPU-only, ≤~1 GB RAM, short-clip latency target ≤~4 s on 2 vCPU:

| Candidate | Approach | Footprint | Notes |
|---|---|---|---|
| **wav2vec2-phoneme (base), quantized to ONNX int8** | acoustic phoneme CTC | ~0.1–0.3 GB | Fast on CPU via ONNX Runtime; strong quality; recommended primary |
| **allosaurus** | universal phoneme recognizer | ~0.2–0.4 GB | Very light, simple API; good fallback |
| wav2vec2-phoneme (large) | acoustic phoneme CTC | ~1–2 GB | Best quality but likely too heavy for the current box — deferred to a bigger host |

**Selection rule:** Phase 0 benchmarks the top two on real Arabic-accented English
clips for (a) RSS memory, (b) latency, (c) does-it-catch-a-wrong-read. We commit to
whichever passes R4 with the best R2 behavior. No model choice is finalized before
that measurement.

---

## 5. Integration points (R5, R7, R9)

- `pronunciation_scorer.py`: replace the internals of `score_recording_bytes()`
  (transcription + `compare_words`) with a call to the `nutq-scorer` service,
  returning the **same `ScoringResult`** shape. The best-effort wrapper, timeout,
  flag gate, `store` flag, and accent/shadow scope in `api_server.py` are
  **unchanged**.
- `_pronunciation_expected_text()` extended so shadow scores against the shadow
  passage and day-7 assessment scores against the shown passage (or cleanly skips)
  — closing the drift gaps found in review (R10).
- Groq Whisper is retained only as an optional "we heard" transcript for display
  and (later) for the out-of-scope speaking task — never for the score.

---

## 6. Feedback generation (R8)
Warm bilingual feedback is generated from the phoneme error list via **templates**
(deterministic, free, offline): e.g. "Great rhythm! Focus on the **th** in
*through* — put your tongue between your teeth." + Egyptian-Arabic equivalent. An
LLM refinement is optional and must degrade to the template if unavailable (R3).

---

## 7. Storage & scale (R11, R14)
- Reuse `pronunciation_scores` (score, missed_words, feedback, expected, heard).
  Optional additive column `phoneme_detail` (JSON) for future insight — read-only,
  non-breaking.
- Scorer is stateless; horizontal scale = more replicas behind the internal call.
  A load-based "run another instance / bigger host" playbook is documented, not
  built, for v1.

---

## 8. Safety & rollout (R5, R12, R13)
- Backup before any server change; scorer deployed as an additive container (the
  bot keeps working even if the scorer isn't up — best-effort).
- Flag OFF → pilot BioRoMa + Mai → live-verify R1/R2 (read wrong → low + sound
  correction; read well → high) → enable all.
- Privacy unchanged; nothing posted publicly.

---

## 9. Risks & honest tradeoffs
- **Accuracy ceiling on a small box:** a light model is "very good + tunable," not
  "absolute best." If Phase 0/3 shows it's not good enough for Arabic L0, the
  documented next step is a bigger host (separate cost decision) — the design is
  portable so that's a config change, not a rewrite.
- **Latency:** CPU inference is a few seconds; mitigated by the existing async
  best-effort pattern and the "🎧 checking…" indicator.
- **G2P/phoneme mismatch:** eSpeak phoneme set vs the model's phoneme set must
  align; Phase 0 validates the mapping.
