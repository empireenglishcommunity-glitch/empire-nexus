# Practice Experience Enhancements — Design

How each item is built, the key decisions, and the trade-offs. Grounded in
the current code (verified during the feedback investigation).

---

## E1 — Speaking on the practice page

**Current state:** `PRACTICE_EXERCISES = ("accent", "vocab", "shadow", "listening")`
(database.py). The calendar's "day done" = all 4 ≥ 1; `day_tier` = min of 4.
The practice page generates accent/shadow/listening/vocab per day. Speaking
is a Discord-only daily task.

**Approach:** add `speaking` as a 5th practice exercise that uses the
Accent/Shadow **recording** pattern (record → `Send to Discord` →
`/api/submit-recording` → posts to `#lN-showcase` + records mastery for the
viewed day).

**Key decision — how "day done / green" works with 5 exercises (grandfather):**
- **Recommended:** make "green" **date-aware**. A content-day is "done" when
  all *required* exercises are complete, where **speaking is required only
  for days practised on/after the Speaking launch date**; days already
  greened at 4/4 before launch stay green (grandfathered). Store the launch
  date in config (`SPEAKING_LAUNCH_DATE`).
- **Simpler alternative (fallback):** keep "green = the 4 core exercises";
  Speaking is a tracked 5th exercise (own tier badge, counts toward
  points/streak and the 7-task program) but not required to green a day.
  Auto-grandfathers with zero date logic.
- **Chosen for the spec:** start with the **simpler alternative** (green =
  4 core; speaking additive) to ship safely and avoid un-greening anything,
  then revisit "require 5" later if desired. This keeps `get_calendar_mastery`
  simple and guarantees R1.5.

**Touch points:** `generate.py` (new `gen_speaking`, nav/bottom-nav/day-menu
include speaking, regenerate all pages), `darb.js` (`DarbRecording` already
generic — just recognise `speaking` in the URL regex; the calendar cell +
day menu list speaking), `database.py` (speaking already a valid daily task;
if speaking joins the calendar's exercise set for display, keep the "done"
set = 4 core per the chosen decision, and track speaking separately for its
badge), `api_server.py` submit-recording already handles any exercise in a
set — extend the accepted set to include `speaking` for recording.

**Migration:** none needed for green days (grandfathered by the chosen rule).
Speaking mastery starts empty and fills as students record.

---

## E2 — Decouple daily-task post from personal calendars

**Current state:** `daily_task_post()` posts one message per level channel,
selecting content by **day-of-week** (`day_index` Sat=0..Fri=6). Phase 0
already reduced it to one calendar link + task titles; the header still
shows "Week N" (from `member_week_number`, which now matches the calendar's
week) and the Discord-only task prompts.

**Approach (Option b — decouple, owner-approved):**
- The shared post becomes a **nudge + Discord-only tasks**: a friendly
  "📅 Your daily practice is ready — open your calendar" with the single
  platform link, plus the **writing** and **community** task prompts
  (and speaking until/if it's fully on the page).
- Remove any wording that asserts a specific day-of-week lesson/content for
  the self-study exercises (those live on each student's personal calendar).
- The self-study exercises (accent/vocab/shadow/listening/speaking) are
  represented as "open your calendar" — the calendar shows the student's
  personal "today."

**Why not personal DMs (Option a):** per-student daily DMs would perfectly
match each calendar but are heavy/spammy and a large change; the nudge +
calendar model achieves alignment with far less risk.

**Touch points:** `tasks.py` `generate_daily_tasks` / `format_daily_post_chunks`
— restructure the message so the self-study section is a calendar nudge (no
per-exercise day-of-week content), Discord section keeps writing/community
(+speaking if not yet on page). Update tests for the new format.

---

## E3 — Vocab UX

**Current state (app.js `InteractiveVocab`):** modes flashcard / quiz
(Arabic shown → type English, **no audio**) / listen (audio → type). Answer
check is exact match (`answer === correct`). End screen shows score + a
"Try Again" restart button. Vocab page (`gen_vocab`) renders mode buttons.

**Approach:**
- **Labels (generate.py):** "📖 بطاقات / Flashcards", "✍️ ترجم / Translate",
  "🎧 اسمع واكتب / Listen & Type" with a one-line hint each.
- **Forgiving match (app.js `checkAnswer`):** normalise (trim, lowercase,
  strip surrounding punctuation), map common US/UK pairs (color/colour,
  -ize/-ise, traveler/traveller, etc.), and accept Levenshtein distance ≤ 1
  as correct-with-note ("almost — it's spelled X"). 
- **Audio (app.js + generate.py):** add a 🔊 replay button to Translate and
  Listen modes.
- **End screen:** rename restart to "🔄 راجع تاني / Review again" and add
  "✅ خلصت / Done" that returns to the day menu.

**Touch points:** `app.js` (`InteractiveVocab._renderQuizCard`,
`checkAnswer`, results screen), `generate.py` vocab template (button labels +
hints). Both static assets — service-worker fix (already shipped) ensures
students get the update.

---

## E4 — AI motivational auto-replies

**Current state:** the bot has an AI engine (`ai_engine.py`, Groq/Gemini) and
an `on_message` handler. Channels `lN-text-practice` and `lN-showcase` exist.

**Approach:**
- In `on_message`, if the channel name matches `l{n}-text-practice` or
  `l{n}-showcase` and the author is a non-bot student, generate a short
  (1–2 sentence) **unique** encouragement via the AI engine, prompted with:
  post type (audio vs text), the student's first name, and an instruction to
  be warm, varied, and free of any correction.
- **Non-repetition:** pass a "make it different from these recent lines"
  hint using the last N replies for that channel (kept in a small in-memory
  ring), plus temperature; fallback to a large randomised phrase pool if AI
  fails.
- **Throttle:** at most one reply per student per channel per short window
  (e.g. 60s) to avoid burst spam; ignore very short/no-content messages.
- **Flag:** `hafiz_motivation` (or similar) feature flag, default off until
  verified.

**Touch points:** new module (e.g. `motivation.py`) + a hook in `bot.py`
`on_message`; reuse `ai_engine`. Cost is minimal (short completions).

---

## E5 — Community task = voice AND general-chat, persistent voice

**Current state (verification.py):** community = general-chat post **OR**
10+ voice min. Voice minutes are tracked **in-memory** (`_voice_sessions`),
lost on restart.

**Approach:**
- Change `verify_community` to require **both** conditions.
- `!done community` returns a checklist: which sub-task is done, which is
  pending, in the student's language.
- **Persist voice minutes:** add a `voice_minutes` table (discord_id, date,
  minutes) updated on voice state changes; `get_voice_minutes_today` reads
  from it. Survives restarts.

**Touch points:** `verification.py` (`verify_community`,
`get_voice_minutes_today`, voice join/leave handlers), `database.py` (new
table + accessors), `bot.py` voice-state listener, `features.py` community
task description.

---

## E6 — "4-vs-7 done" confusion

**Root cause (confirmed):** the practice calendar greens at 4 self-study
exercises; the Discord daily program is 7 tasks (adds speaking, writing,
community). A student who greens their calendar is only 4/7 in Discord →
"I finished but it shows remaining."

**Approach:**
- E1 brings the page to 5 of 7; E2's decoupled post makes the split clear.
- Add explicit messaging: the calendar = your self-study; Discord `!progress`
  / daily post shows the full 7 with a clear breakdown of what's left
  (writing, community).
- **Audit:** script to pick students who did all 7 tasks on a date and
  confirm `tasks_completed_today` returns 7; hunt any genuine mismatch
  (e.g. a task recorded but not counted). Fix if found.

**Touch points:** messaging in `tasks.py`/`features.py`; a one-off audit
script; fix only if the audit surfaces a real bug.

---

## Sequencing rationale
E1 + E2 + E6 are interlinked (they resolve the completion-model confusion)
and should land together or in close sequence. E3 (vocab) and E5 (community)
are independent and low-risk. E4 (AI replies) is isolated and flag-gated.
See tasks.md for the phased order.
