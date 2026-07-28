# Pronunciation Feedback — Design

**Status:** DRAFT — awaiting owner approval.
Implements the requirements in `requirements.md`. Design principle: **reuse the
existing engine; add only the plumbing and the UI.** Scoring is a best-effort
layer on top of a flow that already works — it can never break completion.

---

## 1. What already exists (reused as-is)

| Piece | Where | Reuse |
|---|---|---|
| `transcribe_audio(bytes, filename)` | `pronunciation_scorer.py` | Works on raw bytes (Itqan already calls it). Core of the bytes path. |
| `compare_words()` / fairness logic | `pronunciation_scorer.py` | Beginner-kind scoring (R3) — unchanged. |
| `generate_feedback()` | `pronunciation_scorer.py` | Warm bilingual tips on Groq (R4) — unchanged. |
| `pronunciation_scores` table + `get_pronunciation_average()` | `database.py` | Persistence + `!progress` (R7) — unchanged. |
| `POST /api/submit-recording` | `api_server.py` | The hook point: already receives `audio_data`, `exercise`, `week`, `day`, resolves `discord_id`/`level`, posts to `#showcase`, records completion. |
| `tatawwur_pronunciation` flag | `flag_registry.py` | Re-used as the gate (R10). |

**Only real gap:** `score_recording()` assumes a Discord CDN **URL** (it downloads).
The page has **bytes**. We add a bytes-based entry so no download/round-trip is
needed.

## 2. Backend design

### 2.1 New/adapted scorer entry (bytes)
Add `score_recording_bytes(audio_bytes, filename, expected_text, discord_id,
task_id, level)` (or refactor `score_recording` to accept `audio_bytes OR
audio_url`). It: transcribe → compare → (beginner grace) → feedback → persist →
return a `ScoringResult`. No behavior change to the scoring math.

### 2.2 Expected-text lookup (accent + shadow)
For the recording's exact `(week, day, level)`:
`curriculum.get_daily_content(week, day_name, day_index, level)["accent_drill"]["record_this"]`
(shadowing uses the same `record_this` target — consistent with the old
`_score_pronunciation`). Map `day` (1–7) → `day_index`/`day_name` via the
curriculum's Sat=0 convention. If no expected text exists → skip scoring (R2).

### 2.3 Hook into `/api/submit-recording` (best-effort, after completion)
Order inside the route (only the last step is new):
1. (existing) validate session + inputs.
2. (existing) `process_submission` → completion.
3. (existing) `record_practice_mastery`.
4. (existing) post recording to `#showcase`.
5. **(new)** IF `tatawwur_pronunciation` enabled for this student AND
   `exercise in ("accent","shadow")` AND expected text exists:
   run the bytes scorer inside a **timeout** (R13), wrapped in try/except.
   Attach to the JSON response: `pronunciation: { scored: bool, score, feedback_en,
   feedback_ar, missed_words[], transcript, expected, is_beginner_grace }` — or
   `pronunciation: { scored: false }` on any failure/timeout/disable.
   Completion (steps 2–4) is already committed, so scoring can never undo it (R2).

### 2.4 Response contract (page consumes this)
```
{ ok, exercise_tier, day_tier, day_done, posted, already_done,   // existing
  pronunciation: {                                               // new (optional)
    scored: true,
    score: 82,                    // omitted when is_beginner_grace
    is_beginner_grace: false,
    feedback_en: "...", feedback_ar: "...",
    missed_words: ["through"],
    transcript: "i walk true the park",   // what Whisper heard (R5)
    expected:   "I walk through the park"
  } }
```

## 3. Frontend design (`site/js/darb.js` — `DarbRecording`)

- On "Send to Discord" (the existing action, D4): show a **"🎧 Checking your
  pronunciation…"** spinner in the recorder feedback area after the "Sent!"
  confirmation.
- On response:
  - `pronunciation.scored === true` + grace → warm "great first tries!" note (no
    number).
  - `scored` + number → **score ring** (green ≥80 / amber ≥60 / orange else) +
    bilingual feedback + **missed-word chips** (R4).
  - **Heard-vs-target (R5):** render `expected` with `missed_words` highlighted,
    and a muted line "we heard: {transcript}".
  - **Try again (R6):** a button that resets the recorder in place; re-recording
    + re-sending re-scores and refreshes this panel (no new completion — mastery
    is already once/day, so a redo just updates feedback).
  - `scored === false` → neutral "Saved to #showcase. (Couldn't check
    pronunciation this time.)" — never an error.
- Speaking/vocab/listening pages: unchanged (no pronunciation panel).

## 4. Data & privacy
- Writes to `pronunciation_scores` (existing schema; R7). No new table for the
  core. Feedback is returned only to the authenticated caller's session (R9) and
  never posted publicly.
- R12 (owner insight) is a **read-only aggregate query** over `pronunciation_scores`
  (+ `assessment_items` if useful) surfaced via Empire Ops — no schema change.

## 5. Failure modes (all degrade gracefully — R2)
| Case | Behavior |
|---|---|
| Flag off / not in allowlist | No scoring; response has `pronunciation.scored:false`. Page shows nothing extra. |
| Non-recording exercise (vocab/listening) or speaking | Not scored (R8). |
| No expected text for that (week,day,level) | Skip; `scored:false`. |
| Transcription fails / times out | Completion + post already done; `scored:false`; page shows the neutral note. |
| Groq down for feedback | Engine's own fallback message is used (still returns text). |

## 6. Cost & latency (R13)
- One Groq-Whisper transcription per accent/shadow completion (~2/day/active
  student × 16 ≈ a few dozen/day) — negligible. Feedback = one short Groq call.
- Synchronous with a ~8s budget + spinner; Itqan already imposes similar latency
  on recording items, so this is a known-acceptable UX.

## 7. Out-of-scope (per D7 / non-goals)
- No adaptive-difficulty re-enable. (The old `_score_pronunciation` also triggered
  adaptive; the new path deliberately does NOT — adaptive stays a separate future
  decision.)
- No speaking accuracy scoring.

## 8. Rollback
- Instant: flip `tatawwur_pronunciation` OFF (feature vanishes; flow unaffected).
- Code: each phase is an independent, revertable PR; backend scoring is additive
  and guarded, so reverting the UI or the hook leaves the daily flow intact.
