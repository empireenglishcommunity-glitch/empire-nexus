# Nutq — Design (CONSOLIDATED, FINAL)

**Status:** DRAFT — awaiting owner approval. Traceability → R1–R14 in
`requirements.md`. Pivot history → `decision-log.md`.

---

## 1. Idea: keep the body, use the best available brain (with a safety-net brain)

```
 Practice page (dojo, UNCHANGED)
        │ audio + week/day/exercise
        ▼
 empire-english-bot / api_server.py
   submit-recording / pronunciation-check   (best-effort, ≤8s, flag-gated — UNCHANGED wrappers)
        ▼
   ┌─────────────────  ENGINE SELECTOR  ─────────────────┐
   │ eligible? (flag on · task=shadow · within cost policy)│
   │   ├─ usage-guard OK & Azure reachable → AZURE (primary)│
   │   └─ else                              → LOCAL (fallback)│
   └──────────────────────────────────────────────────────┘
        ▼                                   ▼
   Azure Pronunciation Assessment      nutq-scorer (allosaurus)
   (REST, accurate per-phoneme)        (already deployed, dormant)
        └───────────────► same ScoringResult / pronunciation JSON ◄───────┘
```

Everything downstream (on-page panel, try-again, storage) is unchanged (R7).

## 2. Azure Pronunciation Assessment client (R1, R2, R8, R13)
- **REST** (short-audio endpoint) — no heavy SDK/native deps in the bot container.
  `POST https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1`
  with header `Pronunciation-Assessment: <base64 JSON {ReferenceText, GradingSystem:HundredMark, Granularity:Phoneme, Dimension:Comprehensive}>`,
  `Ocp-Apim-Subscription-Key: $AZURE_SPEECH_KEY`, audio body (16k mono wav; we already
  convert via ffmpeg).
- Parse `NBest[0]`: `PronunciationAssessment` (AccuracyScore, FluencyScore,
  CompletenessScore, PronScore) + `Words[]` (word, AccuracyScore, ErrorType) +
  per-word `Phonemes[]` (Phoneme, AccuracyScore).
- Map → `ScoringResult`: score = PronScore (or AccuracyScore); missed_words = words
  with ErrorType∈{Mispronunciation,Omission} or low AccuracyScore; the worst
  phoneme → the specific tip (now RELIABLE).
- Config: `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`, `NUTQ_AZURE_ENABLED`.
- Timeout < the endpoint's 8s budget; any failure → return None → selector falls
  back to local (R5/R6).

## 3. Engine selector + cost policy (R3, R5)
A small module decides, per request, whether to use Azure or local:
1. Only for **shadow** (R3/R8). Accent → local or unscored.
2. **Daily graded:** first shadow submission of the day per student → Azure-eligible.
3. **Try-again:** allow ≤2 Azure re-checks/day/student; further re-checks → local.
4. **Weekly assessment:** one Azure-eligible scored reading.
5. If not Azure-eligible for any reason → local engine.
Counters live in the DB keyed by (discord_id, local-date) and (discord_id, iso-week).

## 4. Usage guard (R4) — never a surprise bill
- New table `azure_usage(month TEXT PRIMARY KEY, audio_seconds REAL)`.
- Before an Azure call: if `audio_seconds >= 0.9 * 5*3600` (16,200 s) → skip Azure,
  use local. After a successful call: add the clip's duration.
- Also cap any single clip sent to Azure (e.g., trim/limit to ~30 s) so a stuck
  mic can't burn quota.

## 5. Feedback (R8) — reliable now
- From Azure's per-phoneme AccuracyScores, pick the lowest-scoring phoneme in a
  mispronounced word → map to the bilingual `PHONEME_TIP` (th, p/b, v/f, r, l, …),
  which is now backed by a **reliable** signal.
- **Fallback (local) feedback (R5):** show the band (Excellent / Good / Keep
  practising) + warm encouragement, **without** naming a specific sound (local
  per-phoneme detail is unreliable) — honest, not misleading.

## 6. Where the code lives
- Bot: `src/pronunciation_azure.py` (REST client + parser), `src/pronunciation_engine.py`
  (selector + guard + policy), small edits to `score_recording_bytes` to call the
  selector. `config.py` gets the Azure envs + free-tier constant. DB helpers for
  counters + usage.
- Local fallback: the existing `services/nutq-scorer` (unchanged; used via its
  HTTP client already wired in Phase 2).

## 7. Safety & rollout (R6, R11, R12)
- Backup before any server change. `.env` gets the Azure key/region (owner-created
  free resource). Flag OFF → pilot BioRoMa/Mai → live-verify accuracy → all.
- Best-effort everywhere: Azure fail → local; local fail → scored:false; completion
  + #showcase always proceed.

## 8. Honest trade-offs
- Uses a managed API (not fully self-hosted). Chosen because it's the only path to
  professional accuracy that is **$0 now** and cheaper than a capable self-hosted
  setup until large scale (decision-log.md). The guard caps cost; the local engine
  guarantees continuity if we ever stop Azure.
- Fallback quality is lower (that's why its feedback is coarser) — it's a safety
  net, not the main experience.
