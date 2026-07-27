# Design — Weekly Assessment ("Itqan")

How the feature actually works, end to end. Grounded in the existing system:
the **bot + API** (`empire-nexus/bots/discord-learning-bot/src/`) and the
**Darb practice site** (`empire-dojo/site/`). Gated behind a new feature flag
`itqan_weekly_assessment` (OFF until rollout).

---

## 1. Architecture at a glance

```
Student's phone ──▶ Darb practice site (empire-dojo)
                      │  /assessment page (new): timed, one-at-a-time,
                      │  Kokoro audio, voice recording, no copy/paste
                      ▼
                    Bot API (api_server.py)  — session-gated (Darb token)
                      │  /api/assessment/*  (status, start, item, finish)
                      ▼
   ┌───────────────── assessment engine (new modules) ─────────────────┐
   │ generation (curriculum + SRS spiral)  scoring (objective + AI)     │
   │ pass logic (consistency + mastery)    anti-cheat + attempts        │
   └───────────────────────────────────────────────────────────────────┘
                      │                         │
                      ▼                         ▼
              SQLite (new tables)        Discord (🏅 Week Champions post,
                                         private DM)  +  Telegram (owner report)
```

New bot modules (proposed):
- `assessment.py` — generation, scoring, pass logic, attempt lifecycle.
- API routes added to `api_server.py` under `/api/assessment/*`.
- Calendar changes in `darb.py` (add the assessment stop + unlock rule).
- Outcome hooks in `bot.py` (Champions post, private DM, badge, SRS re-inject).
- Owner report via `ops_hub`/`ops_monitoring`; override commands in `bot.py`.

New page in `empire-dojo/site/`: `assessment/` (+ `js/assessment.js`), reusing
existing `DarbSession`, `RecorderUI`, and `TTS`/Kokoro audio helpers.

---

## 2. Data model (new tables)

The old `assessments` table (from the removed feature) is **deprecated** and
left untouched. New tables:

**`assessment_attempts`** — one row per attempt.
| column | meaning |
|---|---|
| `id` (PK) | attempt id |
| `discord_id`, `level`, `week` | who / which content week |
| `attempt_no` | 1,2,3… (retakes) |
| `started_at`, `finished_at` | timestamps (Dubai) |
| `status` | `in_progress` / `scored` / `flagged` (needs owner) |
| `consistency_pct` | did they do week W's daily tasks (0–100) |
| `mastery_pct` | test performance (0–100) |
| `result` | `mastered` / `distinction` / `not_yet` |
| `time_expired` | bool |
| `integrity_flags` | JSON (tab-away count, paste attempts, etc.) |

**`assessment_items`** — one row per question in an attempt (for feedback +
"most-missed" reporting).
`attempt_id, item_no, skill (listening|vocab|pronunciation|speaking|writing),
source_week, prompt_ref, expected, answer, auto_score, ai_score, correct(bool),
feedback`.

**`week_mastery`** — durable record + badge source of truth.
`discord_id, level, week, mastered(bool), distinction(bool), mastered_at,
best_attempt_id`. Unique on `(discord_id, level, week)`.

**Config** (in `settings`, owner-tunable): `mastery_pass_pct` (default 70),
`consistency_pass_pct` (default 70), `distinction_pct` (default 90),
`retake_cooldown_min` (default 720 = 12h), `spiral_recent_weight` (default 0.65),
`assessment_time_limit_min` (default 15).

---

## 3. Unlock logic (calendar) — R1

- The Darb calendar (`darb.build_calendar`) gains a **per-week assessment stop**
  rendered after the week's 7 days.
- **Unlock rule:** week W's assessment unlocks when **every day of week W has at
  least one completion.** Reuse `get_calendar_mastery`: for each `(W, day)` in
  1..7, require `day_tier ≥ 1` (i.e., the day was completed at least once). This
  reuses the exact "done at least once" signal already computed.
- State returned to the page per week: `locked` (with `days_remaining` list) /
  `available` / `mastered` / `not_yet` (attempted, not passed) / `flagged`.
- Personal calendar anchoring is already join-based (existing Darb behavior) — no
  change needed; unlock is purely completion-based, so late finishers still
  unlock (R1.5).

## 4. Question generation (spiral) — R3, R4

`assessment.generate_blueprint(discord_id, level, week)` builds the item set:
- **Item budget:** ~10–12 items total (keeps it ~10–15 min).
- **Split:** `spiral_recent_weight` (65%) from week W, remainder from weeks
  1..W-1.
- **Prior-week selection:** pull from the student's **SRS weak-item queue**
  (`vocab_srs` + missed-item history) so older content is chosen by *what
  they're likely to have forgotten*. Fallback to random from covered weeks if
  the queue is thin.
- **Sources:** `curriculum.py` for the covered weeks — vocabulary lists,
  target phonemes, listening scripts, grammar/theme. Reuses existing
  `generate_vocab_quiz` / `generate_listening_quiz` helpers where possible.
- **Item mix (per attempt, drawn from a larger pool so attempts differ):**
  - Listening (Kokoro reads → choose/type meaning)
  - Vocabulary recall (EN↔AR)
  - Pronunciation (word shown, Kokoro models it, student records → Whisper score)
  - Speaking production (prompt on the week's theme → 30–60s recording →
    Whisper transcript → AI checks target-vocab/grammar use)
  - Writing production (short prompt → AI feedback + band)
- Generation is **deterministic per attempt** (seeded) so a resumed attempt shows
  the same items, but **re-drawn per new attempt** (R8.3).

## 5. Scoring engine — R5, R12, R13

Two independent dimensions:
- **Consistency %** — from existing daily-task tracking for week W (how many of
  the week's expected task-days were done). No new data needed.
- **Mastery %** — weighted average of item scores:
  - Objective items (listening, vocab): exact/forgiving match → 0/100.
  - Pronunciation: Whisper transcript similarity to target → 0–100 (lenient
    bands for beginners).
  - Speaking: Whisper transcript → AI checks *attempt + target-content use +
    rough intelligibility* → 0–100, **graded kindly** (R13.1).
  - Writing: AI (Groq) → 0–100 + feedback, kindly.
- **Pass = `mastery_pct ≥ mastery_pass_pct` AND `consistency_pct ≥
  consistency_pass_pct`.** Distinction if `mastery_pct ≥ distinction_pct`.
- **Borderline handling (R13.2):** if `mastery_pct` is within a small margin of
  the pass line, OR an AI item errored, set attempt `status='flagged'` and
  notify the owner instead of auto-deciding.
- **Graceful degradation (R13.3):** any AI/Whisper failure → that item is
  deferred (not zero), the attempt is `flagged` for the owner, and the student
  sees "your speaking/writing is being reviewed" — never a crash or a false 0.

## 6. The assessment page (Darb site) — R2, R12

New `empire-dojo/site/assessment/` page + `js/assessment.js`:
- Entry gated by `DarbSession`; reads week + unlock state from
  `/api/assessment/status`.
- **Intro screen:** Arabic-first rules, ~time, "one try per sitting", a
  non-scored **sample question**.
- **Runner:** one item at a time, progress "3/10", **countdown timer**
  (auto-submit at 0), **no Back**. Uses **Kokoro audio** (pre-generated clips
  where available, browser TTS fallback) and `RecorderUI` for spoken items.
- **Client anti-cheat:** disable copy/paste + context menu on inputs; use the
  Page Visibility API to count **tab-aways** and send them as integrity flags;
  timer enforced server-side too (client timer is cosmetic).
- **Results screen:** the two scores, band label, per-item **what-was-wrong +
  correct + why**, and (if passed) the **Mastered/Distinction** celebration.
- Served `no-store` (like the other JS) so updates are instant; no SW bump.

## 7. API endpoints — R2, R8, R12

Under `/api/assessment/*`, all session-gated (same pattern as existing Darb
endpoints), CORS-safe:
- `GET /status` → per-week `{state, attempts_used, cooldown_until, last_result}`.
- `POST /start` → validates unlock + cooldown + not-already-mastered; creates an
  `assessment_attempts` row; returns the generated blueprint (items, timer).
- `POST /item` → saves one answer/recording (multipart for audio), objective
  items scored immediately; production items queued for scoring.
- `POST /finish` (or auto on timer) → runs scoring, computes both dimensions,
  writes result, triggers outcome hooks (§8), returns the results payload.
- Server enforces: **one `in_progress` attempt**, the **time limit**, the
  **cooldown**, and **pool re-draw** per attempt (anti-cheat is server-side, not
  trusting the client).

## 8. Outcome flows — R6, R7, R9

On `finish`:
- **Mastered/Distinction:**
  - upsert `week_mastery` (mastered=true, distinction flag, best_attempt_id);
  - award the **"Week W Mastered"** badge (profile/calendar);
  - post to **`🏅 Week Champions`** Discord channel (new channel in the level
    category; created once via a setup step, id stored in `settings`/config,
    env-overridable) — positive-only, names student + week + distinction;
  - update the weeks-mastered streak + progress map.
- **Not yet:**
  - **no** change to daily tasks/streak/calendar (R7.1);
  - send a **private encouraging DM** with the exact review list + retake invite;
  - start the **cooldown**;
  - **re-inject weak items** into the student's SRS/daily queue (R9.2).
- **Flagged:** notify the owner (Empire Ops) with the attempt for a human call;
  student sees a neutral "being reviewed" state.

## 9. Owner report + overrides — R10, R11

- **Report:** a weekly Empire Ops summary (and on-demand admin command
  `!itqan` / a Telegram `/itqan`): per student pass/not-yet/flagged, both scores,
  and the **most-missed items/skills** aggregated from `assessment_items`.
- **Overrides:** admin commands (admin-channel-gated, per session-32 pattern):
  - `!itqan-pass @student <week>` → mark mastered manually.
  - `!itqan-reset @student <week>` → clear attempts so they can retry.

## 10. Motivation & progression — R14

- **Weeks-mastered streak:** consecutive mastered weeks (from `week_mastery`).
- **Progress map:** "Level L — X of N weeks mastered", shown on the dashboard +
  calendar.
- **Level-completion certificate:** when all weeks of a level are mastered,
  generate a shareable certificate (reuse the existing `html2img` service on the
  server to render a PNG; deliver via DM + a download link on the page).
- **Champion teaching clip (optional):** top scorer is invited (DM) to record a
  ~20s tip; if they submit, it's posted in the champions channel.

## 11. Feature flag, config, security

- Flag **`itqan_weekly_assessment`** (registered in `flag_registry.py`, default
  **OFF**). Everything above is inert until enabled (and can be enabled for a
  pilot allowlist first).
- Thresholds/config in `settings` (owner-tunable, §2), no redeploy to tune.
- Security: page + all endpoints gated by the Darb session token; recordings
  analyzed then **discarded** (only scores/feedback stored); admin commands
  gated by `manage_guild` + admin channel.

## 12. Non-functional — R15

- No change to existing daily-task/streak/points/recording code paths (the
  engine is additive and flag-gated).
- Bilingual (Arabic primary), mobile-first, Dubai timezone.
- Budget: Groq Whisper + Groq/Gemini + Kokoro + existing html2img — no new paid
  services or containers.
- Graceful degradation everywhere an external call is made.

---

## Open design choices to confirm during build
1. **Pass thresholds** (start at 70/70, distinction 90) — tune with real data.
2. **Certificate rendering** via the existing `html2img` service vs. a static
   template — decide in the certificate phase.
3. **Champion teaching clip** — include in v1 or defer as a fast follow.


---

## 13. Post-pilot design additions (R16, R17, amendments)

### 13.1 Mastery-based progression gate (R16)
- New config/flag `itqan_progression_gate` (owner-toggle, default OFF until
  rolled out with the feature).
- `darb.build_calendar` gains a **highest-unlocked-week** computation when the
  gate is on: week 1 always open; week `W+1` opens only once
  `week_mastery(W).mastered` is true. Days of a locked future week render
  `state: "gate-locked"` with an Arabic-first reason ("pass Week W's test").
- **Grandfather migration:** on first enable, for each active member set a
  per-member baseline `itqan_gate_baseline_week = ` the week they've already
  reached by the existing date-based calendar, and never lock at/below the
  baseline. The gate only governs openings **beyond** the baseline. Stored in
  `settings`/member field so it's a one-time, reversible stamp.
- Safety valves unchanged (R7/R8): retakes, near-miss rescue, `!itqan-pass`
  override — a pass (earned or manual) immediately opens the next week.
- The daily loop itself is untouched *within* an open week (R15); the gate only
  decides **when the next week opens**.

### 13.2 Full status report + due nudges (R17)
- `database.itqan_status_report(level=None)` → per active student: current week,
  days-done for that week, and assessment state derived from
  `get_calendar_mastery` × `week_mastery` × latest attempt:
  `locked | due | passed | not_yet | flagged`. **DUE** = week's 7 days done AND
  not passed AND (no in-progress attempt).
- Surfaced via `!itqan-due` (Discord, chunked) and `/itqan-due` (Telegram).
- **Nudge job:** a daily task DMs (Arabic, motivational) each student whose state
  is DUE, guarded by a per-(student,week) settings stamp
  (`itqan_nudged_{did}_{level}_{week}`) so it fires **at most once per due week**.

### 13.3 Manual-pass celebration (A2)
- `itqan_admin_pass` stays a pure DB write, but the command/slash handlers now
  call `itqan_outcomes.deliver_manual_pass(...)` after it: DM the student the
  good news, post to `🏅 Week Champions`, and (if it completes the level) send
  the certificate — reusing the earned-pass outcome path.

### 13.4 Flagged alert commands (R17.3)
- The alert body lists paste-ready `!` commands using the **discord id**
  (`!itqan-pass <id> <week>` etc. — `MemberConverter` resolves an id anywhere),
  and notes the `/itqan-…` menu equivalents. `_notify_owner_flagged` logs a
  **success line** so every send is verifiable.
