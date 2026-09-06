# Empire English Chronicles — Production-Quality Podcast System

## Requirements

**Status:** DRAFT — awaiting owner approval before implementation
**Owner:** Mahmoud Ashri (EEC)
**Author:** Kiro
**Created:** 2026-09-06

---

## 1. Why this spec exists

A daily storytelling podcast ("Empire English Chronicles") is already built and
running: it generates a script with an LLM, renders it to audio offline, posts it
to a Discord channel, collects 🅰️/🅱️ votes, and continues the story the way the
audience voted. The plumbing works.

**The product does not.** Audio quality is inconsistent — some lines are clear,
others are muffled, unnatural, or audibly chopped. The owner's verdict after
listening to four rendered episodes: only one cast voice (Mai's) is acceptable;
the rest are "unclear". For an English-**teaching** product this is fatal: a
learner cannot learn pronunciation from audio they cannot cleanly hear.

### 1.1 Root causes (measured, not assumed)

An audit of the committed voice references and the four rendered episodes found:

| # | Finding | Evidence |
|---|---------|----------|
| RC1 | **Quality was optimised against the wrong metric.** Effort went into high-frequency "bandwidth". The voice the owner *likes* has the **lowest** bandwidth of the whole cast and the **highest** naturalness. | `mai_voice` >3.4 kHz = **1.1%**, spectral flatness **0.0309** (best). `male_us_2` >3.4 kHz = **39.4%**, flatness **0.0772** (worst, rejected). |
| RC2 | **Post-processing introduced the defects it tried to fix.** A reference clip was pitch-shifted +4 semitones (displaces formants → synthetic timbre) and the narrator was slowed with a phase-vocoder time-stretch (smears transients → mushy consonants → *unclear speech*). | `male_us_1` built by pitch-shift; narrator rendered at `speed 0.86` via `librosa.effects.time_stretch`. |
| RC3 | **Audible hard cuts.** Every line is chunked, each chunk edge-trimmed, then concatenated with **no crossfade**. Each join is a click/cut. | Rigorously measured discontinuities per episode: **6 / 2 / 2 / 2** (Ep1–Ep4). ⚠️ **Correction:** an earlier audit claimed "237–386"; that came from a crude percentile **sample** count which inflates one click into dozens of hits. The defect is real, the number was wrong — see `docs/AUDIO-STANDARDS.md`. |
| RC7 | **Bare `[SFX:x]` lines were spoken aloud.** A standalone `[SFX:shimmer]` line matches the `Speaker: text` pattern (speaker `[SFX`, text `shimmer]`), so it was parsed as dialogue: the narrator literally said "shimmer]" / "creak]" in published episodes, and the effect never played. | Found by the Phase 0 harness; fixed in `sawt_tts.parse_script()` with regression tests. |
| RC8 | **Every episode is too quiet and often over the peak ceiling, and none respects its CEFR duration window.** Systematic, invisible, never measured. | Loudness **−21.8 to −24.3 LUFS** (target −16); true peak **−0.35 to −0.41 dBTP** on 3 of 4 (limit −1.0); duration **98–161 s** vs the A2 window **300–420 s**. |
| RC4 | **The engine is stochastic and there is no quality gate.** Voice cloning samples with temperature, so the same line renders differently each run — and the pipeline generates → renders → commits → posts **without ever measuring the output**. | `podcast-daily.yml` has no verification step; nothing reads the rendered audio back. |
| RC5 | **Wrong engine for a teaching product.** The ecosystem already standardised on **Kokoro** TTS for the practice site (9,360 clips, studio-quality, deterministic, voices chosen *by ASR measurement*). The podcast instead used experimental voice cloning. | `src/sawt_tts.py` already declares a Kokoro voice registry (`af_heart`, `am_adam`) — Kokoro was the original design intent. |
| RC6 | **Scripts fought the audio.** LLM output had characters narrating their own actions, parenthetical delivery hints that got *spoken* ("(low)", "(through comm)"), and invented sound effects that resolve to silence. | Partially fixed already; retained here as a standing requirement. |

**RC4 is the direct answer to "why is it good sometimes and bad other times".**
It is not luck. It is a stochastic generator with no gate. That is the single most
important thing this spec fixes.

### 1.2 Additional product gaps

| # | Gap |
|---|-----|
| G1 | One never-ending serial. No variety of stories, settings, or genres. |
| G2 | Students are spectators, not participants — their own names never appear. |
| G3 | Engagement is incidental; nothing structurally guarantees a cliffhanger that makes a learner want tomorrow's episode. |
| G4 | The audio asset library is **3 files** (`knock`, `creak`, one music bed). A system producing an episode every day, forever, cannot be built on three sounds. |
| G5 | The podcast is not tied to the CEFR curriculum the rest of Empire English runs on, so it teaches nothing on purpose. |

---

## 2. Scope

**In scope:** audio quality standards and their automated enforcement; the TTS
engine and voice cast; speech-flow/assembly; an owned royalty-free audio library
("the Podcast Lab"); the story engine (arcs, variety, engagement); student
personalisation; CEFR alignment; and end-to-end automation with fail-closed
safety.

**Out of scope (this spec):** the Discord posting/voting mechanics and the
approval/reveal flow (already built and working); non-story podcast formats
(`solo_ai` / `owner_group` episodes); Arabic-language episodes (see R7.4 —
deferred, with a hook reserved).

---

## 3. Non-negotiable principles

These outrank convenience anywhere in the design.

- **P1 — Crystal-clear speech is the product.** This is a teaching podcast. Any
  line a learner cannot cleanly hear is a defect, not a stylistic choice.
- **P2 — Nothing ships unmeasured.** No episode reaches a student without passing
  an automated quality gate. Fail-closed, always.
- **P3 — Deterministic over clever.** Prefer a repeatable engine and repeatable
  settings over a variable one that occasionally sounds better.
- **P4 — Never guess about a person.** Student gender/name is used only from
  confirmed data; unknown means *not cast*, never inferred. (Consistent with the
  existing "never guess gender" rule in `database.py`.)
- **P5 — Own the assets.** Every sound, music bed, and voice reference is
  licence-cleared and committed in-repo. No runtime dependency on an external
  fetch, no expiring URL.
- **P6 — Fully automatic.** The daily happy path requires zero human action. A
  human is involved only to approve the launch or to handle an escalated failure.
- **P7 — Measure, don't assume.** Every quality claim in this system must be
  reproducible by a script that anyone can re-run.

---

## 4. Functional requirements

### R1 — Measurable audio quality standards

**R1.1** The system SHALL define a single machine-readable standard (thresholds in
one config module) covering every metric in R1.3, so quality is a number, not an
opinion.

**R1.2** A reusable analysis tool SHALL compute all metrics for any audio file and
exit non-zero on violation, runnable locally and in CI.

**R1.3** An episode SHALL satisfy all of the following to be publishable:

| Metric | Threshold | Rationale |
|---|---|---|
| **Intelligibility (WER)** | ASR transcript vs script **word error rate ≤ 5%** | The direct test of "can a learner hear the words". Catches dropped, mumbled, doubled, and hallucinated words. |
| **Naturalness** | mean spectral flatness **≤ 0.012**, measured by the **pinned method** on **voice-only** audio | Separates the accepted voice (0.0002) from all three rejected ones (0.0176–0.0355). ⚠️ The measurement method is part of the standard — the same clip measures 0.031 or 0.0002 depending on method, so threshold and method are pinned together. Gates only on voice stems: on a mastered mix the music bed hides the defect (mixes measure ~0.013 while their own bad voices measure 0.018–0.036). |
| **Hard cuts** | **≤ 2** waveform discontinuities per episode | Proper crossfading should give ~0; 2 tolerates rare edge cases. Targets RC3 (baseline 2–6). |
| **Loudness** | integrated **−16 LUFS ± 1.0 LU** | Podcast standard; identical perceived volume every day. |
| **True peak** | **≤ −1.0 dBTP** | No clipping on any playback device. |
| **Dead air** | no unintended silence **> 2.5 s** | Excludes deliberate `[PAUSE n s]` markers. |
| **Duration** | within the episode's CEFR profile `duration_min`/`duration_max` | Ties length to the learner's level (`PODCAST_LEVEL_PROFILES`). |
| **Music bed** | present, and speech **≥ 12 dB** above the bed during speech | Music must never compete with teaching content. |
| **Per-line floor** | every spoken line ≥ 0.4 s and non-silent | Catches a line that failed to synthesise. |

**R1.4** Frequency bandwidth SHALL be **reported but MUST NOT be a pass/fail
gate** — RC1 proved it is not the driver of perceived quality. It is diagnostic
only.

**R1.5** The standard SHALL be documented in human-readable form alongside the
thresholds, including *why* each threshold has its value, so a future session
cannot silently loosen it.

---

### R2 — Voice cast and engine

**R2.1** The system SHALL use **Kokoro TTS** as the primary engine for the
Narrator and all AI characters: deterministic (same input → same output),
studio-quality, and already proven in this ecosystem.

**R2.2** **Mai's cloned voice SHALL be retained** for her character. It is the one
voice the owner accepts, and it is a real community member's voice (consent on
file in `content/voice-clone-consent.md`).

**R2.3** Each cast voice SHALL be selected **by measurement**, not by adjective:
candidates are scored against R1.3 (intelligibility + naturalness) on
representative story sentences, and the winner per role is recorded with its
scores.

**R2.4** Voice references SHALL NEVER be pitch-shifted, and rendered speech SHALL
NEVER be time-stretched after synthesis (RC2). Pace SHALL be set **natively at
synthesis time** (Kokoro exposes a speed parameter).

**R2.5** Distinct characters SHALL be distinguishable by **distinct voices**, not
by post-processing a shared voice. Every character maps to its own voice id.

**R2.6** The engine-mixing risk SHALL be tested explicitly, not assumed: a
Kokoro-voiced narrator and Mai's cloned voice in the same episode MUST be verified
to sit together tonally (matched loudness/EQ), with the result recorded. If they
cannot be reconciled, escalate to the owner with options rather than shipping a
mismatch.

**R2.7** A per-character voice registry SHALL be the single source of truth for
which voice speaks which character (no duplicate lists).

---

### R3 — Speech flow (no hard cuts)

**R3.1** Every audio join SHALL use a short crossfade (target 15–25 ms) so no
splice is audible.

**R3.2** Text SHALL be split for synthesis **only at sentence or clause
boundaries** — never mid-clause, never mid-word.

**R3.3** Edge-trimming SHALL preserve natural onsets and decays; a word's tail
MUST NOT be clipped (RC3).

**R3.4** Inter-line timing SHALL be rhythmic and intentional: a longer beat when
the speaker changes, a shorter one within a speaker's own turn, and deliberate
dramatic pauses only where the script marks them.

**R3.5** Sound effects SHALL be placed **around** speech, never overlapping a
spoken word in a way that masks it (P1).

---

### R4 — Automated quality gate (fail-closed)

**R4.1** The render pipeline SHALL run the R1 analysis on every rendered episode
**before** the episode can be committed or posted.

**R4.2** On failure the system SHALL retry automatically: first at **line level**
(re-render only the offending lines), then a full re-render, up to a bounded
number of attempts.

**R4.3** If an episode still fails, the system SHALL **NOT publish it**. It SHALL
alert the owner with the failing metrics and keep the previous day's state intact.
A missing episode is acceptable; a bad episode is not.

**R4.4** Every gate run SHALL write a machine-readable report (metrics, pass/fail,
attempts) stored alongside the episode for auditability.

**R4.5** The gate SHALL be enforced in CI as well, so a code change that degrades
audio quality fails the build rather than reaching students.

**R4.6** The gate MUST verify its own correctness in both directions: it is proven
to FAIL on known-bad audio and PASS on known-good audio. A gate that cannot fail
is not a gate.

---

### R5 — The Podcast Lab (owned audio library)

**R5.1** The repository SHALL contain an in-house, licence-cleared audio library
sufficient for indefinite daily production, organised by category:
**music beds** (by mood), **ambiences/room tones**, **foley/sound effects**,
**stings/transitions**, and **voice references**.

**R5.2** Target initial coverage: **≥ 12 music beds** across at least 6 moods,
**≥ 10 ambiences**, **≥ 60 sound effects** across common story situations, and
**≥ 6 stings/transitions**. (Numbers are a floor, not a cap.)

**R5.3** Every asset SHALL carry machine-readable metadata: filename, human
description, category, mood/tags, source, licence, and required attribution.

**R5.4** Only **CC0 / public-domain / CC-BY** assets are permitted. A build check
SHALL fail if any asset lacks complete licence metadata, and CC-BY attribution
SHALL be emitted automatically wherever an episode using it is published.

**R5.5** All assets SHALL be normalised to a consistent format and loudness on
ingest, so the mixer never has to compensate for an inconsistent source.

**R5.6** The story generator SHALL only be able to request effects that **exist**
in the library (RC6), and the library SHALL be discoverable by the generator by
tag/mood so it can score a scene appropriately.

**R5.7** Repository size SHALL be respected: assets stored compressed, with a
documented size budget and a check that reports growth. (The ecosystem has an
existing decision against Git LFS — see `empire-chronicle`.)

---

### R6 — Story engine: variety, engagement, cliffhangers

**R6.1** Content SHALL be organised as **self-contained story arcs** (target 5–7
episodes) that reach a real resolution, after which a **new story** begins — a
different setting, cast mix, and genre.

**R6.2** A **story bible** SHALL define recurring characters (name, traits, voice,
speech habits) so the world stays consistent across episodes and arcs, and SHALL
be the source of truth shared by the generator and the renderer.

**R6.3** Genre variety SHALL be explicit (e.g. mystery, adventure, everyday-life,
light comedy, gentle sci-fi) and rotated so the feed never feels repetitive.

**R6.4** Every episode SHALL end on a genuine cliffhanger with a **meaningful**
A/B choice — the two options must lead to materially different next episodes.

**R6.5** Engagement SHALL be **structurally enforced**, not hoped for: a validator
SHALL reject a generated episode that lacks a cliffhanger, has a trivial or
duplicated A/B choice, resolves its own tension, or fails the "curiosity" checks
defined in the design.

**R6.6** Continuity SHALL be maintained across episodes (previous recap, the
winning choice, established facts) and MUST NOT contradict earlier episodes in the
same arc.

**R6.7** Scripts SHALL obey the audio contract (RC6): the Narrator describes
action; characters speak only their spoken words; no parenthetical stage
directions; only library-backed sound effects.

**R6.8** Every episode SHALL open with a brief recap and close with the vote
prompt, so a student who missed a day can still follow.

---

### R7 — CEFR alignment (harmony with Empire English)

**R7.1** Episode language SHALL be graded by the learner-facing CEFR profile
already in `config.PODCAST_LEVEL_PROFILES` (pace, vocabulary band, duration
window) rather than an independent notion of difficulty.

**R7.2** Episodes SHALL be pitched at the level band the active student body
actually occupies (today: **17 of 17 active students are A1**), and the target
band SHALL be derived from live data, not hardcoded.

**R7.3** Each episode SHALL naturally reinforce vocabulary from the current
curriculum week via `curriculum.get_vocabulary_for_week()` — woven into the story,
never presented as a word list.

**R7.4** Arabic support SHALL be deferred but **designed for**: the CEFR profile
already carries an `arabic_ratio` per level, and the design MUST reserve a clean
hook so Arabic scaffolding (heaviest at A1) can be enabled later without a
rewrite. Current episodes remain English-only by the owner's earlier decision.

**R7.5** Student-facing wording SHALL follow the ecosystem standard: **"CEFR-aligned,
not certified."**

---

### R8 — Student personalisation (names in the story)

**R8.1** Students' **first names** SHALL appear in the stories as friendly
side-characters so learners feel part of the world.

**R8.2** Names SHALL be **gender-matched**: a student's first name may only be
cast in a character of the same gender. This is a professionalism requirement.

**R8.3** **No guessing (P4).** A student SHALL be cast only from confirmed data.
Where gender is unknown the student is simply **not cast** — never inferred from
the name.

**R8.4** ⚠️ **Known blocker:** all 22 members currently have `gender = ''`, and
`discord_name` is frequently not a usable first name (real examples: `BioRoMa`,
`ياسمين`, `Narimel`). The system SHALL therefore maintain a curated **cast roster**
— a confirmed first name (Latin script, story-safe), gender, and opt-out flag —
populated through an owner-facing flow, and SHALL degrade gracefully to
name-free stories while the roster is empty.

**R8.5** Casting SHALL **rotate fairly** so every eligible student appears over
time, tracking who has been used and preferring those least recently featured.

**R8.6** Students SHALL be able to **opt out**, and an opted-out student is never
cast.

**R8.7** A named student character SHALL never be portrayed negatively (no
villain, victim of ridicule, or morally bad actor) and SHALL never be given
dialogue that could embarrass a real person.

**R8.8** A student's name SHALL only appear in content served to their own
community, and no personal data beyond a first name SHALL enter a script.

---

### R9 — Full automation and operational safety

**R9.1** The daily happy path SHALL require **zero human action**: generate →
render → quality-gate → commit → post.

**R9.2** The pipeline SHALL be **idempotent** and safe to re-run; a retry MUST NOT
double-post or corrupt story state.

**R9.3** Story state (arc, episode number, recap, winning choice, casting history)
SHALL be persisted durably and advance only on a **verified** episode.

**R9.4** Every stage SHALL fail **closed and loudly**: on any unrecoverable error
the system alerts the owner and leaves the previous good state untouched.

**R9.5** The system SHALL be observable: a per-episode record of generation inputs,
gate metrics, attempts, and outcome, retained for review.

**R9.6** Cost/runtime SHALL be bounded — a per-episode ceiling on synthesis work
and retries, so an automatic system cannot run away.

**R9.7** All existing feature-flag and approval behaviour SHALL be preserved:
episodes post to the podcast channel for owner approval, and students only gain
access via `/reveal-podcast`.

---

## 5. Acceptance criteria for the whole spec

The system is done when all of the following are demonstrably true:

1. **Five consecutive episodes**, generated and rendered with **no human
   intervention**, all pass the R1 gate on the first attempt.
2. A deliberately corrupted episode is **blocked** by the gate and **not posted**,
   and the owner is alerted (proving R4.3 and R4.6).
3. Measured hard cuts per episode: **≤ 2** (from 237–386).
4. Every cast voice passes the intelligibility and naturalness thresholds, and the
   owner confirms by listening that **all** voices are acceptable — not just Mai's.
5. Two different story arcs exist, each self-contained, with different genres.
6. Student first names appear, correctly gender-matched, rotating, honouring
   opt-outs, and with zero cases of a guessed gender.
7. Every audio asset in the Podcast Lab has complete licence metadata and the
   licence check passes.
8. Episode length, pace, and vocabulary demonstrably follow the CEFR profile of
   the target level, and reinforce the current curriculum week.
9. The full test suite passes, and the quality gate runs in CI.
