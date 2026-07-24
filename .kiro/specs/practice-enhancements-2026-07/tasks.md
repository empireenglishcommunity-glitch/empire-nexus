# Practice Experience Enhancements — Tasks

Phased, priority-ordered. Each phase is independently shippable + live-verified.
Order chosen so quick low-risk wins land first, then the interlinked
completion-model work, then the isolated AI feature.

Legend: [ ] todo · [x] done

---

## ✅ Already shipped (outside this spec — for context)
- [x] Catch-up recording bug — `/api/submit-recording` records the **viewed**
  day, not today (empire-nexus #239). Deployed + live-verified.
- [x] Stale mobile CSS — service worker now network-first, cache bumped
  (empire-dojo #45). Deployed + live-verified.
- [x] Balqees reset to a clean slate (calendar Day 1 = today).

---

## Phase A — Vocab UX (E3) — *quick, low-risk, high student impact*
- [x] **A1** Rename the 3 modes with purpose + one-line hint: Flashcards /
  ✍️ Translate (Arabic→English) / 🎧 Listen & Type. (`generate.py`)
- [x] **A2** Forgiving answer matching in `app.js` `checkAnswer`: trim,
  lowercase, strip surrounding punctuation, US/UK spelling map, Levenshtein
  ≤ 1 tolerance with a gentle "almost" note. (R3.2)
- [x] **A3** Add 🔊 replay control to Translate + Listen modes. (R3.3)
- [x] **A4** End screen: rename restart → "🔄 Review again"; add "✅ Done".
  (R3.4)
- [x] **A5** Regenerate pages, `verify_pages.py`, deploy, live-verify a full
  vocab round (including a US/UK variant + a 1-char typo). PR merged.
  (empire-dojo #46 — deployed + live.)

## Phase B — Community task = voice AND general-chat, persistent (E5) — *independent*
- [x] **B1** New `voice_minutes(discord_id, date, minutes)` table + accessors;
  update on voice-state changes so it survives restarts. (R5.3)
- [x] **B2** `verify_community` requires BOTH (10+ voice min today AND a
  `#general-chat` message today). (R5.1)
- [x] **B3** `!done community` returns a bilingual checklist of what's done /
  still pending. (R5.2)
- [x] **B4** Update the community task description / onboarding text. (R5.4)
- [x] **B5** Tests + live-verify (voice only → pending; chat only → pending;
  both → done; restart mid-way → minutes persist). PR merged + bot deployed.
  (empire-nexus #241 — deployed + live.)

## Phase C — Speaking on the practice page (E1) — *interlinked with D/E*
- [x] **C1** `generate.py`: add `gen_speaking` (record → Send to Discord
  pattern, recording-required note, Home/bottom-nav/day-menu include it).
- [x] **C2** `api_server.py`: accept `speaking` in the recording-exercise set;
  mastery records the viewed day (already correct post-#239).
- [x] **C3** `darb.js`: recognise `speaking` in the exercise URL regex; add
  it to the day menu + calendar exercise list.
- [x] **C4** "Green" rule: keep green = 4 core exercises; Speaking is an
  additive tracked exercise (own badge, counts to points/streak + the 7-task
  program) — auto-grandfathers existing green days. (R1.5) *(Revisit
  "require 5" later only if desired.)*
- [x] **C5** Regenerate all pages, `verify_pages.py`, deploy page + bot,
  live-verify: record Speaking → posts to `#lN-showcase` → marks the viewed
  day; existing green days stay green. PR merged.
  (empire-nexus #242/#243, empire-dojo #47 — deployed + live-verified via a
  real test recording through the live API: posted to `#l0-showcase` with
  caption "Speaking Practice", `practice_mastery` got a `speaking` row,
  calendar `(week,day)` stayed `{accent,vocab,shadow,listening}` only —
  green unaffected.)

## Phase D — Decouple daily-task post (E2) — *interlinked with C/E*
- [x] **D1** Restructure `format_daily_post_chunks`: self-study section
  becomes a calendar nudge (one link, no day-of-week per-exercise content);
  Discord section keeps writing + community (+ speaking only if not on page).
  (R2.1, R2.3)
- [x] **D2** Remove any wording implying a specific day-of-week self-study
  lesson that conflicts with personal calendars. (R2.4) — header no longer
  shows "DAY — {weekday}, Week {N}"; calendar tasks shown by generic name
  only (e.g. "Accent" not "Accent Drill — Long vowels"); explicit line
  added: "Your calendar always shows exactly where YOU are — not today's
  date, YOUR day." Speaking (E1) moved from the Discord section into the
  calendar section, since it's now a practice-page task.
- [x] **D3** Update daily-message tests for the new format. (3 new tests +
  2 updated in `test_tasks.py`; 434 total pass.)
- [ ] **D4** Deploy bot, live-verify the post reads as a nudge + Discord
  tasks and matches the calendar concept. PR merged.

## Phase E — Resolve "4-vs-7 done" confusion + audit (E6) — *after C/D*
- [x] **E1** Messaging: `!progress` / `!today` show the full 7 with a clear
  breakdown of what's left, split into 🌐 calendar (accent/vocab/shadow/
  listening/speaking, 5) vs 💬 Discord-only (writing/community, 2), via a
  shared `features.CALENDAR_TASK_IDS`/`DISCORD_ONLY_TASK_IDS` pair so the
  two commands can never disagree. Calendar = self-study truth. (R6.2, R6.4)
- [x] **E2** Audit script (`scripts/audit_task_counting.py`): checks (1) no
  submission has a task_id outside the canonical 7, (2) every (student,
  date) with all 7 tasks submitted recounts to exactly 7 for that date,
  (3) historical exposure to the tz-boundary bug found below. Run against
  the real DB before closing this phase. (R6.3)
- [x] **E3** Real bug found and fixed (not just messaging): `database.py`
  used a bare `datetime.date.today()` (server/UTC clock) everywhere
  `tasks_completed_today()`/`_recompute_streak()`/`get_voice_minutes()`/
  `record_practice_mastery()` needed "today", while submissions are LOGGED
  under `tasks.today_str()`'s timezone-aware Asia/Dubai date. During the
  window where the two calendar dates disagree (the UTC date has rolled
  over but Dubai's hasn't, or vice versa), a task correctly logged under
  "today" (Dubai) would be invisible to a same-moment read — the exact
  "I did it but it still shows remaining" symptom. Fixed with a single
  `database._today_local()` helper (same pattern as `darb._today_local()`)
  and replaced all 16 call sites. 6 new regression tests pin the fix;
  `test_student_journey.py`'s date-mocking was also fixed (it patched the
  whole `datetime` module in a way that would have silently masked this
  exact bug — now patches `_today_local()` directly). 445 total tests pass.
  PR merged.

## Phase F — AI motivational auto-replies (E4) — *isolated, flag-gated, last*
- [x] **F1** New `motivation.py`: generate short, unique, correction-free
  encouragement (AI + varied fallback pool of 15 per post-type), post-type
  aware, non-repetition hint from a recent-replies ring (per-channel,
  size 12) passed into the LLM prompt. (R4.1, R4.2, R4.5)
- [x] **F2** Hook into `bot.py` `on_message` for `l{n}-text-practice` +
  `l{n}-showcase` (suffix match, so all 4 levels covered); ignore bots
  (existing top-of-function check) and command messages (`!`-prefixed);
  throttle per (student, channel), 60s. (R4.3)
- [x] **F3** Feature flag `hafiz_motivation` (new HAFIZ initiative,
  default off) registered in `flag_registry.py`; supports the standard
  allowlist mechanism for a beta rollout before going to everyone. (R4.4)
- [ ] **F4** Live-verify: distinct replies to a text post and a voice post;
  no repeats across several posts; throttle works; flag off = silent. PR
  merged. *(Deploy with the flag OFF; owner enables for a beta allowlist
  first, then everyone, once satisfied live.)*
  - Tests: 20 new in `test_motivation.py` (uniqueness, post-type
    tailoring, throttle scoping, no-correction guardrail on the fallback
    pool + the AI prompt, flag default-off + allowlist). 465 total pass.

---

## Cross-cutting bookkeeping
- After each phase: update `empire-chronicle/STATUS.md`, link the PR, note
  live-verification evidence.
- SSH keys ephemeral per session; Cloudflare token only in the deploy
  command, never in git.
- Deploy: bot = `git pull && docker compose up -d --build`; page =
  `wrangler pages deploy site`; regenerate via `EEC_REPO_DIR=... generate.py`
  then `verify_pages.py`.
- Tests: `python3.12 -m pytest tests/ -q --ignore-glob='*nour*'`
  (pip install `-r requirements.txt` first if the sandbox was rebuilt).

## Open decisions to confirm during execution
- **C4:** ship Speaking as additive (green stays at 4) — confirmed default;
  flag if you later want "green requires all 5" (needs the date-aware rule).
- **D1:** exact wording/format of the new daily post (draft for owner review
  before deploy).
