# Empire English Chronicles — Design

**Status:** DRAFT — awaiting owner approval
**Companion documents:** [`requirements.md`](./requirements.md) · [`tasks.md`](./tasks.md)

---

## 1. Design goals, in priority order

1. **Clarity of speech** beats every other consideration (P1).
2. **Determinism** — the same script must produce the same audio (P3). This is
   what turns "sometimes good" into "always good".
3. **Fail-closed** — unverified audio never reaches a learner (P2).
4. **Zero-touch daily operation** (P6).
5. **Engagement** — a learner should want tomorrow's episode.
6. **CEFR harmony** — the podcast teaches the same syllabus as everything else.

---

## 2. Architecture overview

```
                    ┌───────────────────────── DAILY, AUTOMATIC ─────────────────────────┐
                    │                                                                     │
 story state ──▶ ① STORY ENGINE ──▶ script ──▶ ② SCRIPT VALIDATOR ──┐                    │
 (arc, recap,       (LLM + bible +              (audio contract,     │ reject → regenerate│
  vote, cast)        CEFR profile +              cliffhanger,        │ (bounded)          │
                     curriculum vocab +          continuity,         │                    │
                     student roster)             cast/SFX legality)  │                    │
                                                                     ▼                    │
                                          ③ AUDIO ENGINE (Kokoro cast + Mai clone)        │
                                                       │                                  │
                                          ④ ASSEMBLY (crossfades, timing, mix)            │
                                             + PODCAST LAB assets (music/ambience/SFX)    │
                                                       │                                  │
                                          ⑤ MASTERING (loudness → −16 LUFS, peak ≤ −1)    │
                                                       │                                  │
                                          ⑥ QUALITY GATE  ──fail──▶ retry (line → full)   │
                                                       │                 │                │
                                                       │            still failing         │
                                                       │                 ▼                │
                                                    pass          ALERT OWNER, DO NOT POST │
                                                       │                                  │
                    ⑦ COMMIT (audio + script + metrics report) ──▶ ⑧ BOT POSTS to #podcast │
                    └─────────────────────────────────────────────────────────────────────┘
                                                       │
                                        students vote 🅰️/🅱️ → winning choice → story state
```

The existing Discord/voting/approval layer (⑧ and after) is unchanged and out of
scope. Everything upstream of it is what this design replaces or adds.

---

## 3. Audio engine (R2)

### 3.1 Decision: Kokoro primary, Mai cloned

| | Kokoro TTS | Chatterbox voice cloning |
|---|---|---|
| Output for identical input | **Deterministic** | Stochastic (temperature sampling) |
| Quality consistency | High, studio-trained voices | Varies with reference + run |
| Clarity | Designed for intelligibility | Inherits reference defects |
| Already proven here | **Yes** — 9,360 practice-site clips | No |
| Can voice a *real person* | No | **Yes** |

**Decision:** Kokoro voices every character **except** Mai's; Mai keeps her cloned
voice (R2.2). This directly attacks RC4/RC5 (the inconsistency) while preserving
the one voice the owner accepts.

`src/sawt_tts.py` already declares Kokoro voice ids, so this returns the system to
its original intent rather than inventing something new.

### 3.2 Voice selection is measured, not asserted (R2.3)

A benchmark harness renders a fixed set of representative story sentences through
every candidate Kokoro voice and scores each on:

- **intelligibility** — ASR word error rate against the known text (primary),
- **naturalness** — spectral flatness (the metric that actually predicted the
  owner's preference — RC1),
- **pace** — measured words-per-minute against the CEFR profile target.

The winner per role is recorded in a committed results file with its scores, so
the choice is auditable and re-derivable. This mirrors the existing
`benchmark_voices.py` approach used for the practice site — including its hard-won
lesson: **score voices on the kind of content they will actually speak** (a voice
that wins on sentences can lose badly on short utterances).

### 3.3 Prohibited transforms (R2.4)

Two techniques are **banned by design**, because measurement showed they caused
the reported defects:

- **No pitch-shifting a voice reference** — displaces formants, yields a synthetic
  timbre (this is what made Leo/The Stranger sound wrong).
- **No post-synthesis time-stretching** — a phase vocoder smears transients and
  destroys consonant clarity (this is what made the narrator unclear).

Slow, deliberate narration is achieved with Kokoro's **native speed parameter** at
synthesis time, which changes delivery without degrading the signal.

### 3.4 Character → voice mapping

One registry is the single source of truth (R2.7), keyed by character, holding:
voice engine, voice id, native speed, and role notes. The story bible (§6.2)
references the same character keys, so the writer and the renderer can never
disagree about who exists or how they sound.

Distinctness comes from **different voices** (R2.5) — never from processing one
voice into several.

### 3.5 Engine-mix risk (R2.6)

Mixing a studio TTS voice with a cloned human voice may sound mismatched. This is
treated as a **risk to test, not an assumption**: an early task renders a two-voice
scene and evaluates the pairing (loudness matching and a gentle spectral match are
applied so both sit in the same "room"). If they cannot be reconciled, the finding
is escalated with options — including re-recording Mai — rather than shipped.

---

## 4. Assembly and speech flow (R3)

### 4.1 Splicing

Every join — chunk-to-chunk, line-to-line, speech-to-SFX — uses an equal-power
**crossfade of 15–25 ms**, replacing today's bare `concatenate`. This is the fix
for the measured 237–386 discontinuities per episode (RC3).

### 4.2 Chunking

Text is split for synthesis at **sentence boundaries**, falling back to clause
boundaries (`,` `;` `—`) only when a sentence exceeds the engine's comfortable
input length. Splitting mid-clause or mid-word is forbidden.

### 4.3 Edge handling

Trimming is conservative and **onset/decay-preserving**: leading silence is removed
but a word's natural tail is kept. Silence between lines is *composed* (§4.4)
rather than left over from trimming.

### 4.4 Timing model

Deliberate, rhythmic spacing rather than incidental gaps:

| Boundary | Beat |
|---|---|
| Within one speaker's turn | short |
| Speaker change | longer |
| Scene change / dramatic beat | `[PAUSE n s]` from the script |
| Before a cliffhanger | long, script-marked |

### 4.5 Sound design placement (R3.5)

Effects are placed in the gaps around speech, or ducked well under it. Speech is
never masked: the mix maintains **≥ 12 dB** of headroom for speech over the bed
(R1.3), enforced by the gate.

---

## 5. Mastering (R1.3)

A fixed, ordered chain, applied once to the assembled programme:

1. High-pass ~80 Hz (remove rumble).
2. Gentle, transparent dynamics for consistency (no aggressive compression —
   over-processing was itself a defect).
3. De-ess only if measurement shows sibilance excess.
4. **Loudness normalise to −16 LUFS integrated** (podcast standard).
5. **True-peak limit to ≤ −1.0 dBTP.**
6. Short fades at programme start/end.

Deliberately **no** broad "presence/air" EQ boost by default: RC1 showed bandwidth
is not the driver of perceived quality, and the boost added harshness without
fixing clarity. Bandwidth is reported as diagnostics only (R1.4).

---

## 6. Story engine (R6)

### 6.1 Arc model

```
STORY (arc)  ──▶ episodes 1..N (N target 5–7)  ──▶ resolution  ──▶ next STORY (new genre/setting)
```

Arc state persists: arc id, genre, setting, premise, cast in play, episode index,
running recap, established facts, last winning choice. An arc **must resolve** at
its planned length rather than drifting forever (G1/R6.1).

### 6.2 Story bible

A committed data file defining, for every recurring character: key, display name,
gender, role archetype, personality, speech habits, and the voice registry key
(§3.4). The bible is the shared contract between generator and renderer (R6.2), so
"a character the audio engine cannot voice" becomes structurally impossible.

Guest/one-off characters are allowed only from a small set of pre-voiced archetype
slots, for the same reason.

### 6.3 Generation contract

The generator receives: arc state + running recap + winning choice + CEFR profile
(pace/vocab band/duration) + this week's curriculum vocabulary + the assigned
student cast names + the legal SFX/mood vocabulary from the Podcast Lab. It returns
a strict object: title, script, recap, `vote_a`, `vote_b`, plus the mood/ambience
it wants for the scene.

### 6.4 Script validator (R6.5, R6.7)

Generated episodes are rejected — and regenerated, bounded — unless they satisfy
*mechanical* checks:

| Check | Rejects |
|---|---|
| Audio contract | characters narrating action; parenthetical stage directions; non-library SFX |
| Cast legality | speakers not in the bible/registry |
| Cliffhanger | an ending that resolves the tension instead of suspending it |
| Choice quality | A/B that are near-identical, trivially unequal, or not actionable |
| Continuity | contradicting an established fact or the winning choice |
| Level fit | sentence length / vocabulary outside the CEFR band; duration estimate outside the window |
| Personalisation safety | a student-named character in a negative role (R8.7) |

**Engagement is enforced by these checks**, which is what turns "hopefully
engaging" into a guarantee (G3).

### 6.5 Curiosity design (R6.4, G3)

Structural devices the generator is instructed to use and the validator checks
for: an unanswered question planted early; a *ticking clock*; a reveal that
reframes what came before; and an A/B choice where **both** branches are
attractive. The closing line always states that tomorrow follows the audience's
vote — the habit loop.

---

## 7. Podcast Lab — the owned audio library (R5)

### 7.1 Layout

```
content/podcast-lab/
  music/        # beds by mood: mystery, warm, tension, playful, wonder, sad, triumph…
  ambience/     # room tone, street, night, rain, school, market, indoors…
  sfx/          # foley by situation: door, footsteps, phone, water, crowd, paper…
  stings/       # intro/outro/transition marks
  voices/       # voice references (Mai's clone source; benchmark fixtures)
  LIBRARY.json  # machine-readable manifest: every asset + metadata
  CREDITS.md    # human-readable attributions (generated from LIBRARY.json)
```

### 7.2 Manifest and licence enforcement (R5.3, R5.4)

`LIBRARY.json` holds per asset: `file`, `description`, `category`, `tags`
(mood/situation), `duration`, `source`, `licence`, `attribution`. A check fails the
build if any file on disk is missing from the manifest, any manifest entry lacks a
licence or attribution, or a licence is outside the allowed set (CC0 /
public domain / CC-BY). `CREDITS.md` is **generated** from the manifest, so
attribution can never drift from reality, and CC-BY credits are emitted
automatically into the episode post.

### 7.3 Ingest normalisation (R5.5)

Every asset is normalised on ingest: consistent container/sample rate, mono where
appropriate, trimmed, and loudness-normalised per category (beds sit lower than
foley). The mixer then never compensates for inconsistent sources — a precondition
for deterministic mixes.

### 7.4 Generator-visible vocabulary (R5.6)

The set of legal `[SFX:…]` names and mood names is **derived from the manifest**
and injected into the generation prompt, and the validator rejects anything
outside it. This structurally ends invented effects that render as silence (RC6).

### 7.5 Sourcing and size (R5.2, R5.7)

Assets are gathered from established royalty-free sources (CC0/public-domain
libraries, `freepd.com`, CC-BY composers, Wikimedia), recorded with attribution.
Storage is compressed (OGG) with a documented size budget and a growth report,
respecting the ecosystem's standing decision against Git LFS.

---

## 8. CEFR alignment (R7)

The podcast reads the **same** configuration the rest of Empire English uses —
`config.PODCAST_LEVEL_PROFILES` — rather than inventing difficulty:

| Profile field | Used for |
|---|---|
| `pace` | Kokoro native speed (§3.3) — a graded delivery rate |
| `vocab` | vocabulary band instruction in the generation prompt |
| `duration_min/max` | episode length target **and** a gate threshold (R1.3) |
| `arabic_ratio` | **reserved hook** for future Arabic scaffolding (R7.4) |

**Target level is derived from live data** (R7.2): today every active student is
A1, so episodes target the A1/A2 band. The resolver reads the active student
distribution rather than hardcoding, so the podcast follows the community as it
grows.

**Curriculum tie-in (R7.3):** `curriculum.get_vocabulary_for_week()` supplies the
week's target words (via `member_week_number()` for the cohort), which the
generator must weave naturally into dialogue — reinforcement through story, never
a word list. Student-facing wording stays **"CEFR-aligned, not certified."**

---

## 9. Student personalisation (R8)

### 9.1 The cast roster (solves the R8.4 blocker)

Live data makes raw `discord_name` unusable: all 22 members have `gender = ''`,
and names include handles (`BioRoMa`) and Arabic script (`ياسمين`). So
personalisation is driven by an explicit **roster**, not by guessing:

| Field | Meaning |
|---|---|
| `discord_id` | link to the member |
| `story_name` | confirmed, story-safe first name (Latin script) |
| `gender` | `male` \| `female` — **confirmed only** |
| `opted_out` | student's choice to be excluded |
| `last_featured_at`, `times_featured` | fairness/rotation bookkeeping |

Populated through an owner-facing flow (bulk review + per-student correction),
seeded from `members` where data is already trustworthy. The existing `gender`
column remains the source of truth for gender where set.

### 9.2 Casting rules

- **Gender-matched only** (R8.2): a female student's name may only be attached to
  a female character, and vice-versa.
- **No guessing** (R8.3/P4): unknown gender or unusable name ⇒ **not cast**.
- **Fair rotation** (R8.5): pick from eligible students with the oldest
  `last_featured_at`, so everyone gets turns over time.
- **Opt-out honoured** (R8.6).
- **Dignity** (R8.7): student-named characters are always positive/neutral roles;
  the validator rejects a script that casts a student name as antagonist or gives
  it embarrassing dialogue.
- **Graceful degradation** (R8.4): with an empty roster the generator simply writes
  name-free stories — the feature never blocks the daily episode.

### 9.3 Privacy posture (R8.8)

Only a first name enters a script; nothing else about the student is used, and the
content is served only inside their own community channel.

---

## 10. Quality gate (R4) — the centrepiece

### 10.1 Placement

The gate runs **after mastering, before commit/post**. Nothing bypasses it (R4.1).

### 10.2 What it does

1. Computes every R1.3 metric on the final audio (plus per-line checks).
2. Transcribes the audio with ASR and compares to the script → **WER**, the direct
   intelligibility test.
3. Writes a metrics report next to the episode (R4.4).
4. **Pass** → allow commit/post. **Fail** → retry path.

### 10.3 Retry ladder (R4.2)

```
attempt 1: full render
   └─ fail → identify offending LINES from per-line metrics
attempt 2: re-render only those lines, re-assemble, re-gate   (cheapest effective fix)
   └─ fail → full re-render
attempt 3: full re-render
   └─ still fail → DO NOT PUBLISH · alert owner with the failing metrics · leave state untouched
```

Bounded attempts respect the runtime/cost ceiling (R9.6). Because Kokoro is
deterministic, a persistent failure indicates a *script/text* problem rather than
sampling luck — so the report includes the offending text, which is the actionable
information.

### 10.4 Self-verification (R4.6)

The gate is tested in **both** directions — proven to fail on deliberately
degraded audio (clicks injected, loudness wrong, words dropped) and to pass on a
known-good reference. A gate never shown to fail is not trusted.

### 10.5 CI enforcement (R4.5)

The gate and the library/licence checks run in CI, so a regression in the audio
chain fails the build instead of reaching students.

---

## 11. Data model changes

| Store | Change |
|---|---|
| **Story state** (file, committed) | extend to arc-aware: arc id, genre, setting, premise, episode index, established facts, recap, winning choice |
| **Cast roster** (new table) | §9.1 fields, with rotation bookkeeping |
| **Episode metrics** (file, committed) | per-episode gate report (metrics, attempts, pass/fail) |
| **Voice registry** (code/data) | character → engine/voice id/speed (§3.4) |
| **Story bible** (data) | recurring characters and archetype slots (§6.2) |
| **`LIBRARY.json`** (data) | audio asset manifest (§7.2) |
| `podcast_episodes` | unchanged (existing schema is adequate) |

---

## 12. Failure modes and responses

| Failure | Response |
|---|---|
| LLM unavailable / returns unusable script | bounded regeneration; then keep yesterday's state and alert. Never post a malformed episode. |
| Script fails the validator | regenerate with the violation fed back, bounded |
| A line synthesises badly | line-level re-render (§10.3) |
| Episode fails the gate after all retries | **do not publish**, alert owner, state untouched (R4.3) |
| Audio asset missing/corrupt | fail the licence/manifest check in CI; at runtime fall back to a safe default bed and report |
| Roster empty / student ineligible | name-free story (R8.4) |
| Two runs collide | idempotency guard; state advances only on a verified episode (R9.2/R9.3) |
| Repo growing too large | size report from the library check (R5.7) |

---

## 13. Explicit non-goals

- Not building a TTS model — using proven engines.
- Not replacing the Discord posting/voting/approval layer.
- Not enabling Arabic episodes yet (hook reserved — R7.4).
- Not per-level episode variants yet (single target band derived from live data;
  the design leaves room to add variants later).
- Not chasing frequency bandwidth as a quality target (RC1/R1.4).
