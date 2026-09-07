# Empire English Chronicles — Implementation Plan

**Status:** DRAFT — awaiting owner approval. **No implementation until approved.**
**Companion documents:** [`requirements.md`](./requirements.md) · [`design.md`](./design.md)

---

## How this plan is ordered (and why)

The order is deliberate and is itself a fix for what went wrong:

1. **Measure first (Phase 0).** We cannot fix quality we cannot measure. Every
   later phase is judged by this harness. This is why "sometimes good, sometimes
   bad" was invisible for so long.
2. **Then the biggest lever (Phase 1).** The engine and speech-flow changes are
   where the audible quality actually comes from.
3. **Then make it impossible to regress (Phase 2).** The gate goes in *before* any
   content work, so nothing unverified can ever reach a student again.
4. **Then supply the system (Phase 3)** — a daily machine needs a real library.
5. **Then the writing (Phase 4)** and **the students in it (Phase 5)**.
6. **Then bind it to the syllabus (Phase 6)** and **harden the automation (Phase 7)**.

**Owner checkpoints (🔔) are built in.** Phase 1 ends with a listening test,
because the owner's ear is the acceptance criterion for voice quality — no amount
of green metrics substitutes for it.

Each phase ends in a reviewable PR and leaves `main` working.

---

## Phase 0 — Measurement harness and the written standard  ✅ COMPLETE

*Goal: quality becomes a number that anyone can reproduce.*

- [x] **0.1** Create the quality-standard module: all R1.3 thresholds in one place,
      with a comment on each explaining **why** it has that value (R1.1, R1.5).
- [x] **0.2** Build the audio analysis tool: computes WER (via ASR), spectral
      flatness, hard-cut/discontinuity count, integrated LUFS, true peak, dead-air
      spans, duration, speech-to-bed ratio, per-line presence; reports bandwidth as
      **diagnostics only** (R1.2, R1.4).
- [x] **0.3** Make it CLI-runnable on any file and exit non-zero on violation.
- [x] **0.4** Prove the harness both ways: it must FAIL on deliberately degraded
      fixtures (injected clicks, wrong loudness, dropped words) and PASS on a
      known-good reference (R4.6 groundwork).
- [x] **0.5** Baseline the four existing episodes and record the numbers, so
      improvement is provable rather than claimed.
- [x] **0.6** Write `STANDARDS.md` — the human-readable quality contract.
- [x] **0.7** Tests for the harness itself.

**Exit criteria:** the tool reproduces the audit findings (≈237–386 hard cuts,
flatness spread across voices), fails on bad fixtures, passes on good, and the
baseline is committed.

---

## Phase 1 — Audio engine and speech flow  🔔 *owner listening checkpoint*

*Goal: every voice is crystal clear, deterministically, with no audible cuts.*

- [ ] **1.1** Integrate Kokoro as the primary synthesis engine for the render path
      (R2.1), keeping the offline-render architecture.
- [ ] **1.2** Build the voice benchmark: score every candidate Kokoro voice on
      representative story sentences for intelligibility, naturalness, and pace;
      commit the results table (R2.3).
- [ ] **1.3** Choose the cast **from the benchmark numbers** — narrator + each
      recurring character — and record why each won.
- [ ] **1.4** Retain Mai's cloned voice for her character (R2.2).
- [ ] **1.5** Build the single character→voice registry (engine, voice id, native
      speed) as the one source of truth (R2.7).
- [ ] **1.6** **Remove the banned transforms**: delete post-synthesis
      time-stretching and reference pitch-shifting; set pace natively (R2.4).
- [ ] **1.7** Implement crossfaded assembly (15–25 ms) at every join (R3.1).
- [ ] **1.8** Implement sentence/clause-boundary chunking; never split mid-clause
      (R3.2).
- [ ] **1.9** Make edge-trimming onset/decay-preserving (R3.3) and compose the
      timing model (R3.4).
- [ ] **1.10** Implement the mastering chain: −16 LUFS, ≤ −1 dBTP, no default
      presence boost (§5).
- [ ] **1.11** **Test the engine-mix risk** (R2.6): a two-voice scene with a Kokoro
      voice and Mai's clone; match loudness/spectrum; record the finding and
      escalate with options if they cannot sit together.
- [ ] **1.12** Re-render the existing episodes and compare against the Phase 0
      baseline: hard cuts must drop to ≤ 2 and every voice must clear the
      thresholds.
- [ ] **1.13** Tests: registry integrity, no banned transform can be reintroduced,
      crossfade present at joins, chunking never splits mid-clause.
- [ ] 🔔 **1.14 OWNER CHECKPOINT** — deliver short samples of **every** cast voice
      plus one full episode. **Do not proceed until the owner confirms all voices
      are acceptable** (spec acceptance criterion 4).

**Exit criteria:** metrics pass on re-rendered episodes **and** the owner approves
the voices by ear.

---

## Phase 2 — The quality gate, wired in and fail-closed  ✅ COMPLETE

*Goal: an unverified or bad episode can no longer reach a student.*

- [x] **2.1** Wire the Phase 0 harness into the render pipeline as a mandatory
      post-master stage (R4.1).
- [x] **2.2** Implement per-line metrics so failures can be localised.
- [x] **2.3** Implement the retry ladder: line-level re-render → full re-render →
      escalate, with bounded attempts (R4.2, R9.6).
- [x] **2.4** Implement fail-closed behaviour: on final failure **do not publish**,
      alert the owner with failing metrics, leave story state untouched (R4.3,
      R9.4).
- [x] **2.5** Write the per-episode metrics report alongside the episode (R4.4).
- [x] **2.6** Add the gate to CI so a code change that degrades audio fails the
      build (R4.5).
- [x] **2.7** Prove fail-closed end-to-end: inject a corrupted episode and show it
      is blocked, not posted, and the owner is alerted (acceptance criterion 2).
- [x] **2.8** Tests for gate pass/fail, retry ladder, and escalation.

**Exit criteria:** a deliberately bad episode is provably blocked; a good one
passes; the gate runs in CI.

---

## Phase 3 — The Podcast Lab (owned audio library)

*Goal: the automatic system always has the right, licence-clear sound available.*

- [x] **3.1** Create the library structure (`music/`, `ambience/`, `sfx/`,
      `stings/`, `voices/`) and the `LIBRARY.json` manifest schema (R5.1, R5.3).
- [x] **3.2** Build the ingest tool: normalise format/sample-rate/loudness per
      category, trim, write manifest entries (R5.5).
- [x] **3.3** Build the licence/manifest checker: fails on any unlisted file,
      missing licence/attribution, or disallowed licence; also reports library size
      against the budget (R5.4, R5.7).
- [x] **3.4** Generate `CREDITS.md` from the manifest, and emit CC-BY attribution
      automatically into episode posts (R5.4).
- [x] **3.5** Source and ingest the initial library to the R5.2 floor: **≥ 12 music
      beds** (≥ 6 moods), **≥ 10 ambiences**, **≥ 60 SFX**, **≥ 6 stings** — all
      CC0/public-domain/CC-BY, each with recorded attribution.
      _Done (PR #525): 101 assets — music 14, ambience 14, SFX 67, stings 6; 7.62 MB;_
      _all 10 moods covered; CC0/PD/CC-BY only; reproducible `source_*.py` scripts._
- [x] **3.6** Expose the legal SFX/mood vocabulary to the generator from the
      manifest, and enforce it in the validator (R5.6).
- [x] **3.7** Implement mood-aware scoring: the story's requested mood selects an
      appropriate bed/ambience.
      _Done in Phase 4: `podcast_lab.select_asset/select_bed_path/select_ambience_path/`_
      _`resolve_sfx_path` map a mood (with an adjacency fallback chain) to a real_
      _asset; all three renderers now import `podcast_lab` and score by mood._
- [x] **3.8** Tests: manifest↔disk parity, licence completeness, ingest
      normalisation, generator vocabulary derived from the manifest.

**Exit criteria:** the library meets the floor, every asset has complete licence
metadata, the checker passes, and the generator can only request sounds that exist.

---

## Phase 4 — Story engine v2: arcs, variety, engagement

*Goal: different stories, genuinely engaging, with cliffhangers that pull learners back.*

- [x] **4.1** Define the story bible (recurring characters + archetype slots), keyed
      to the voice registry (R6.2). _`src/sawt_bible.py`: CHARACTERS keyed to
      `sawt_cast`, 5 genres each mapped to a canonical library mood, motif +
      listener-echo signature._
- [x] **4.2** Extend story state to be arc-aware (arc id, genre, setting, premise,
      episode index, established facts) (R6.1, R9.3). _`src/sawt_arc.py`;
      `story-state.json` upgraded in place with a back-compatible `normalize()`._
- [x] **4.3** Implement arc lifecycle: run 5–7 episodes, **resolve**, then start a
      new arc with a different genre/setting (R6.1, R6.3). _Default 6-episode arcs,
      exactly one opener + one finale, genre rotates with no back-to-back repeat._
- [x] **4.4** Rewrite the generation contract: bible + arc state + CEFR profile +
      curriculum vocab + student cast + legal SFX/moods in, strict object out
      (§6.3). _`sawt_story.build_story_prompt` is arc-aware; cast + SFX vocab now
      DERIVED from `sawt_cast` + `podcast_lab` (ended the `[SFX:shimmer]` drift)._
- [x] **4.5** Implement the script validator: audio contract, cast legality,
      cliffhanger presence, A/B choice quality, continuity, level fit, and
      personalisation safety (R6.5, R6.7, R8.7). _`src/sawt_script_validator.py`;
      never raises (crash = soft-pass); student-safety hook ready for Phase 5._
- [x] **4.6** Implement bounded regeneration that feeds the specific violation back
      to the generator. _`sawt_story.generate_episode` retries 3× with the exact
      validator problems appended to the prompt._
- [x] **4.7** Implement the curiosity devices and check for them (unanswered
      question, ticking clock, reframing reveal, two attractive branches) (§6.5).
- [x] **4.8** Enforce recap-at-open and vote-prompt-at-close (R6.8). _Validator
      requires both; the Discord post now surfaces the recap + arc subtitle._
- [x] **4.9** Tests: validator rejects each violation class; arcs resolve on
      schedule; continuity is preserved; genres rotate. _+39 tests
      (`test_sawt_bible`, `test_sawt_arc`, `test_sawt_script_validator`,
      `test_podcast_lab_mood`, `test_sawt_story`); full suite 2879 passed._

**Exit criteria:** two distinct arcs exist with different genres, each
self-contained; the validator provably rejects weak or non-compliant episodes.
_Met: the arc engine produces different-genre arcs on a fixed lifecycle (proven in
`test_sawt_arc`), and the validator rejects every violation class (proven in
`test_sawt_script_validator`)._

**Follow-up flagged to owner (not in this PR):** the daily workflow still renders
with the v1 engine (now mood-aware) rather than the GATED v2 path, because the
gated path needs `kokoro-onnx` installed + its model cached at a non-root-writable
path on the CI runner. Migrating production to the gated renderer is a separate,
owner-approved change.

---

## Phase 5 — Student personalisation (names in the story)

*Goal: learners hear their own names — correctly, fairly, and safely.*

- [x] **5.1** Create the cast-roster table (story name, gender, opt-out, rotation
      bookkeeping) with migration (§9.1). _`story_roster` table + accessors in
      `src/database.py` (upsert/get/eligible/mark_featured/set_opt_out)._
- [x] **5.2** Build the owner-facing roster flow: review/confirm/correct story names
      and genders in bulk, seeded from `members` where trustworthy (R8.4).
      _`/roster [seed]`, `/roster-confirm`, `/roster-name`, `/roster-optout`,
      `/roster-optin` in `src/ops_commands.py`._
- [x] **5.3** Implement gender-matched casting with **no inference**: unknown ⇒ not
      cast (R8.2, R8.3, P4). _`sawt_roster.seed_from_members` skips unknown gender;
      `upsert_story_roster` refuses a row without a known gender._
- [x] **5.4** Implement fair rotation by least-recently-featured (R8.5) and
      opt-out (R8.6). _`eligible_story_roster` orders by last_featured_at;
      bookkeeping advanced ONLY on emit._
- [x] **5.5** Implement graceful degradation: empty roster ⇒ name-free stories, the
      daily episode never blocks (R8.4). _`select_cameos` returns [] on any
      problem; the generator/renderer never require cameos._
- [x] **5.6** Enforce dignity rules in the validator: a student-named character is
      never an antagonist and never gets embarrassing dialogue (R8.7). _Expanded
      hook in `sawt_script_validator.py` (never antagonist; no demeaning words
      spoken-by or addressed-to the guest)._
- [x] **5.7** Enforce the privacy posture: first name only, own community only
      (R8.8). _First-name-only stored + validated (rejects a following surname);
      single-GUILD_ID scope by construction._
- [x] **5.8** Tests: gender matching, zero-inference guarantee, rotation fairness,
      opt-out honoured, degradation path, dignity rejection. _`tests/test_sawt_roster.py`
      (13 tests)._

**Exit criteria:** names appear correctly gender-matched and rotating, opt-outs are
honoured, and there is **no** case of a guessed gender.

---

## Phase 6 — CEFR alignment with Empire English

*Goal: the podcast teaches the same syllabus as everything else.*

- [ ] **6.1** Drive pace, vocabulary band, and duration from
      `config.PODCAST_LEVEL_PROFILES` (R7.1).
- [ ] **6.2** Implement the target-level resolver from **live** student data (today
      A1-dominant), never hardcoded (R7.2).
- [ ] **6.3** Weave the current curriculum week's vocabulary into episodes via
      `curriculum.get_vocabulary_for_week()` / `member_week_number()` — naturally,
      never as a word list (R7.3).
- [ ] **6.4** Enforce duration against the level's window in the gate (R1.3/R7.1).
- [ ] **6.5** Reserve the Arabic-support hook (`arabic_ratio`) without enabling it
      (R7.4).
- [ ] **6.6** Ensure student-facing wording says **"CEFR-aligned, not certified."**
      (R7.5).
- [ ] **6.7** Tests: profile drives the render; target level follows live data;
      curriculum words actually appear; duration gate reflects the level.

**Exit criteria:** episode length/pace/vocabulary demonstrably follow the target
level's profile and reinforce the current curriculum week.

---

## Phase 7 — Full automation, observability, rollout

*Goal: it runs itself, forever, safely.*

- [ ] **7.1** Make the scheduled pipeline fully hands-off end-to-end: generate →
      validate → render → gate → commit → post (R9.1).
- [ ] **7.2** Guarantee idempotency and safe re-runs; no double-posting, no state
      corruption (R9.2).
- [ ] **7.3** Advance story state **only** on a verified episode (R9.3).
- [ ] **7.4** Alerting on every escalation path, with actionable detail (R9.4).
- [ ] **7.5** Per-episode observability record: inputs, metrics, attempts, outcome
      (R9.5).
- [ ] **7.6** Enforce the runtime/cost ceiling per episode (R9.6).
- [ ] **7.7** Preserve flags + approval + `/reveal-podcast` behaviour (R9.7).
- [ ] **7.8** **Five-day unattended soak test**: five consecutive episodes generated
      and rendered with zero human action, all passing the gate first time
      (acceptance criterion 1).
- [ ] **7.9** Update `empire-chronicle` (STATUS/SYSTEM-MAP) and the ops guide with
      how the system works, the standards, and the runbook for a failure.
- [ ] 🔔 **7.10 OWNER CHECKPOINT** — final review, then `/reveal-podcast` to launch
      to students.

**Exit criteria:** all nine spec acceptance criteria demonstrably met.

---

## Cross-cutting rules for every phase

- **No phase is "done" without tests**, and tests must be shown to fail on the
  pre-fix code where that is meaningful.
- **Never loosen a threshold to make something pass.** If a threshold is wrong,
  change it deliberately in `STANDARDS.md` with the reason recorded.
- **Never post to students** anything that has not passed the gate.
- **Re-derive numbers; never copy them** from prose (an existing ecosystem rule).
- **One PR per phase**, `main` always working, and the owner's listening verdict
  is the final word on voice quality.

---

## Risks

| Risk | Mitigation |
|---|---|
| Kokoro voices may not please the owner either | Phase 1 selects **by measurement** and ends with a listening checkpoint before anything else is built on top |
| Kokoro + Mai's clone may sound mismatched | Explicit test task (1.11); escalate with options (incl. re-recording Mai) rather than shipping a mismatch |
| ASR errors could cause false gate failures | Threshold set with headroom (WER ≤ 5%); harness validated both directions in 0.4 |
| Library growth bloats the repo | Compressed assets, documented budget, size report in the checker (3.3) |
| Student names could embarrass someone | Confirmed-data-only, dignity validator, opt-out, first-name-only (Phase 5) |
| Automation could run away on retries | Bounded attempts + per-episode ceiling (2.3, 7.6) |
| Scope is large | Phased; each phase independently valuable and shippable, quality gate lands early (Phase 2) |
