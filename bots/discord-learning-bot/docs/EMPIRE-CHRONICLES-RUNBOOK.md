# Empire English Chronicles — System Map & Ops Runbook

A fully-automatic, serialized storytelling podcast for the Empire English
community. One short, CEFR-aligned episode is generated, quality-gated, and
published every day; the audience votes A/B and the next day's episode continues
the winning choice. This is the operator's guide: how it works, the quality
standard it must meet, and what to do when a run fails.

> Student-facing framing: episodes are **CEFR-aligned, not certified** — pitched
> at the community's level and the current curriculum week to *support* learning,
> not to assess it.

---

## 1. The build (OWNER-TRIGGERED — no daily schedule)

> **This is owner-triggered, not automated.** Reliable free-tier LLM generation
> could not be guaranteed every single day, so instead of a fragile daily cron the
> owner starts each episode when they want one. There is **no schedule** and **no
> failure alerting** — you run it, and you see the pass/fail outcome directly in the
> run log. Fail-closed still holds: nothing is committed or posted unless the QA
> gate passes.

**How to make an episode:** GitHub → Actions → "podcast daily (empire chronicles)"
→ **Run workflow** (optionally set a winning-choice override). Then:

```
Run workflow (manual)  →  GitHub Actions: podcast-daily.yml
  1. Generate   scripts/generate_daily_story.py
       • reads content/podcast-scripts/story-state.json (episode #, recap,
         winning vote, arc position)
       • resolves the CEFR target level + curriculum week from LIVE data
         (sawt_syllabus) and this week's vocabulary to weave in
       • picks student cameos (sawt_roster) — first-name-only, gender-matched,
         opt-in, least-recently-featured
       • writes chronicles-epNN.txt + episode-meta.json, advances story-state
  2. Render+Gate  scripts/render_episode_gated.py  (GATED — the fail-closed core)
       • synthesises the cast (Kokoro, isolated venv), assembles + masters
       • runs the QA gate; emits the MP3 ONLY if every critical metric passes
       • advances the cameo rotation ONLY on a passing emit (R9.3)
  3. Observability  scripts/record_episode_run.py  (always, pass or fail → DB)
  4. Commit  the script + MP3 + meta back to the repo (only if the gate passed)

Bot side (discord.py, when a new episode has been committed):
  • daily_story_post() reads the newest committed episode and posts it to the
    HIDDEN #podcast channel for owner approval, with 🅰️/🅱️ vote reactions.
  • Students see nothing until the owner runs /reveal-podcast.
```

If any stage fails, **nothing is written/committed**, the previous state is
untouched, and you see exactly why in the run log. Fail-closed. (No automatic
alerting — the run is owner-triggered, so the outcome is in front of you.)

---

## 2. The quality standard (the gate)

The single source of truth is `src/audio_standards.py` (and `docs/AUDIO-STANDARDS.md`).
An episode is emitted only if ALL critical metrics pass, measured on the
**delivered MP3**:

| Metric | Requirement | Why |
|---|---|---|
| `wer` (ASR word error rate) | ≤ 5% | intelligibility |
| `hard_cuts` | ≤ 2 | no clicks / chopped words |
| `loudness_lufs` | −16 ± 1 LU | consistent, comfortable level |
| `true_peak_dbtp` | ≤ −1.0 dBTP | no clipping on real devices |
| `duration_s` | within the level's CEFR window | length follows the learner's level |
| `dead_air_s` | ≤ the standard's max | no long silences |

Bounds that stop a runaway (R9.6): `MAX_RENDER_ATTEMPTS=3`,
`MAX_SPOKEN_LINES=120`, generation `MAX_REGEN_ATTEMPTS=3`, and the workflow's
`timeout-minutes: 120`.

**Never loosen a threshold to make an episode pass.** If a threshold is genuinely
wrong, change it deliberately in `audio_standards.py` with the reason recorded.

---

## 3. Observability (R9.5)

Every run — emitted or failed — is recorded in the `podcast_runs` table
(`slug`, `episode_number`, `level`, `passed`, `attempts`, failing metrics, the key
metric values, and render time). Review it from the ops bot:

```
/story-runs           # last 8 runs (✅ emitted / ❌ failed + why)
/story-runs 20        # more history
```

The renderer also always writes a full `content/podcast-audio/<slug>.qa.json`
report next to the episode (committed on success; diagnosable on failure via the
Actions logs).

---

## 4. Owner controls (ops bot / Discord)

| Command | What it does |
|---|---|
| `/story-status` | current A/B vote tally + how to approve |
| `/story-approve` | close voting, write the winning choice into story-state |
| `/story-runs [n]` | recent pipeline outcomes (observability) |
| `/setup-podcast` | create the hidden #podcast channel + pin the intro |
| `/reveal-podcast` | reveal the channel to students (view + react, no send) |
| `/roster [seed]` | show/seed the student cameo roster |
| `/roster-confirm <id>` | make a student castable (name + gender reviewed) |
| `/roster-name <id> <FirstName>` | correct a story name (first name only) |
| `/roster-optout <id>` / `/roster-optin <id>` | exclude / re-include a student |

Feature flag: the whole daily feature is gated by `sawt_daily_story`
(auto-enabled once on deploy).

---

## 5. Failure runbook

**Symptom: a triggered Actions run failed (red ✗ in the Actions tab).**
1. Open the run → the "Render" step log. Look for
   `❌ attempt … failed: [<metrics>]` and `NOT EMITTED`.
2. The QA report in the log lists each metric's value. Identify the failing one:
   - `wer` high → a mis-heard/awkward line; usually transient — the next daily
     run regenerates. If persistent, inspect the generated script for odd wording.
   - `true_peak_dbtp` / `loudness` → mastering issue; see `render_story_v2.master`
     and the post-encode correction. These are limited/re-checked in the delivered
     domain; a regression here means an episode with unusual dynamics.
   - `hard_cuts` → clicks; the per-line + post-encode declickers should handle
     these. A new failure suggests a stem/engine change.
   - `duration_s` → the script rendered outside the level's window; check the
     level ↔ word-window sync (`sawt_story.target_length` and
     `sawt_script_validator._level_word_window`, both use `OVERHEAD_S=45`).
3. **Fail-closed is safe**: yesterday's episode is untouched and story-state did
   NOT advance for a failed emit. Re-run the workflow (`workflow_dispatch`) once
   the cause is addressed — it's idempotent (same slug UPSERTs; no double-post).

**Symptom: generation returned nothing.**
- Usually the Groq key's per-minute token limit (429). The generator waits out the
  window and falls back through `qwen3.8 → groq/compound → groq/compound-mini`.
  If ALL fail, no episode is written (fail-closed). Check `GROQ_API_KEY` validity.

**Symptom: the bot didn't post an emitted episode.**
- Check `sawt_daily_story` is enabled and the bot ran `daily_story_post` (once/day
  at `SAWT_STORY_HOUR`). The bot de-dups on episode number, so a re-post is a
  no-op.

---

## 6. Key files

| Area | File |
|---|---|
| Quality standard | `src/audio_standards.py`, `docs/AUDIO-STANDARDS.md` |
| Generation (LLM, arc, prompt) | `src/sawt_story.py`, `src/sawt_arc.py`, `src/sawt_bible.py` |
| Script validator | `src/sawt_script_validator.py` |
| Render + gate | `scripts/render_episode_gated.py`, `scripts/render_story_v2.py` |
| Cast + guest voices | `src/sawt_cast.py` |
| CEFR alignment | `src/sawt_syllabus.py` |
| Student cameos | `src/sawt_roster.py` |
| Observability | `scripts/record_episode_run.py`, `scripts/qa_failure_summary.py` |
| Daily entry point | `scripts/generate_daily_story.py` |
| Automation | `.github/workflows/podcast-daily.yml` |
| Compute/LLM strategy | `docs/PODCAST-COMPUTE-AND-LLM-STRATEGY.md` |
