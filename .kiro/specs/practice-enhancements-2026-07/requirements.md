# Practice Experience Enhancements — Requirements

**Context:** Post-launch feedback after Darb went live and was human-tested.
Two urgent bugs (catch-up recording day, stale service-worker CSS) and one
member reset (Balqees) were already fixed/handled outside this spec. This
spec covers the remaining **6 enhancement items** from owner + student
feedback, to be executed phase-by-phase, each independently shippable and
live-verified (same discipline as the Darb spec).

Constraints (unchanged from Darb): don't break the ~16 live students, $0 /
no new vendors, server = source of truth, each phase live-verified before
the next.

---

## E1 — Speaking added to the practice page (owner decision: yes)

- **R1.1** The practice page shall include **Speaking** as a 5th exercise
  on each day, following the same pattern as Accent/Shadow: record on the
  page → **Send to Discord** → auto-posts to `#lN-showcase` → auto-marks
  the exercise done for the viewed content-day.
- **R1.2** Speaking pages shall be generated for every level/week/day by
  `generate.py`, consistent with the other exercise pages (gate, watermark,
  Home button, `darb.js`).
- **R1.3** Speaking shall use the recording-required flow (no bare "Done"
  checkbox), identical to Accent/Shadow.
- **R1.4** Speaking completion shall record `practice_mastery` for the
  **viewed** content-day (not today) and run the canonical points/streak
  path — consistent with the catch-up fix already shipped.
- **R1.5** **Grandfather rule:** adding Speaking must NOT retroactively
  un-green days students already completed at 4/4 before this launches.
- **R1.6** The calendar, day menu, exercise nav, and bottom nav shall
  include Speaking wherever the other 4 exercises appear.

## E2 — Decouple the shared daily-task post from personal calendars

- **R2.1** The shared per-level daily-task channel post shall stop implying
  a specific "day N / content" that conflicts with each student's personal,
  join-anchored calendar. It shall act as a **daily nudge** pointing to the
  student's calendar, plus the Discord-only tasks.
- **R2.2** The personal calendar (practice page) remains the single source
  of truth for which self-study day a student is on.
- **R2.3** The daily post shall clearly separate: (a) "open your calendar
  for today's practice" and (b) the Discord-only tasks (writing, community,
  and — until E1 ships everywhere — any task not yet on the page).
- **R2.4** No student shall be shown a specific day-of-week lesson in the
  channel that contradicts their calendar "today."

## E3 — Vocab task UX overhaul

- **R3.1** The three vocab modes shall be clearly labelled by purpose:
  Flashcards, **Translate** (Arabic→English), **Listen & Type** (audio→spelling).
- **R3.2** Answer matching shall be **forgiving**: trim whitespace, ignore
  case and surrounding punctuation, accept US/UK spelling variants, and
  tolerate a single-character typo.
- **R3.3** A 🔊 play/replay control shall be available in both Translate
  and Listen modes (hear the word).
- **R3.4** The end-of-round screen shall not be confusable with a wrong
  answer: rename the restart control (e.g. "🔄 Review again") and add a
  clear "✅ Done / back to day" action.
- **R3.5** No change shall weaken how vocab completion is recorded.

## E4 — AI motivational auto-replies in #text-practice and #showcase

- **R4.1** When a student posts in `#lN-text-practice` (text) or
  `#lN-showcase` (voice/audio), the bot shall reply with a short,
  **unique, non-repetitive** motivational message.
- **R4.2** Replies shall be tailored to the post type (encourage a
  recording differently from a written sentence) and vary every time
  (AI-generated via the existing Groq/Gemini engine, with a varied
  fallback pool if AI is unavailable).
- **R4.3** The bot shall ignore its own/other bots' messages, and shall be
  throttled to avoid spamming during bursts.
- **R4.4** The feature shall be behind an on/off feature flag.
- **R4.5** Replies shall never contain corrections/criticism — encouragement
  and engagement only (feedback belongs in the dedicated feedback channel).

## E5 — Community task requires BOTH voice AND general-chat

- **R5.1** The community task shall require **both**: (a) 10+ minutes in a
  voice lounge today, **and** (b) a message in `#general-chat` today.
- **R5.2** `!done community` shall clearly tell the student which of the two
  sub-tasks is still missing, and shall only mark done when both are met.
- **R5.3** Voice-minute tracking shall be **persistent** (survives a bot
  restart), so students are not unfairly reset mid-progress.
- **R5.4** The daily task description and any onboarding text shall reflect
  the new two-part requirement.

## E6 — Resolve the "finished all tasks but shows remaining" confusion

- **R6.1** Clarify and align the two notions of "done": the practice-page
  calendar (self-study exercises) vs the 7-task Discord daily program.
- **R6.2** After E1, the page covers 5 of 7 tasks (accent, vocab, shadow,
  listening, speaking); only **writing** and **community** remain
  Discord-only. Messaging shall make this explicit so a student who greens
  their calendar understands the 2 remaining Discord tasks.
- **R6.3** An audit shall confirm there is no genuine counting bug: a
  student who verifiably completed all 7 must show 7/7. Any real defect
  found is fixed under this requirement.
- **R6.4** The daily message / progress replies shall show a clear
  breakdown so "remaining" is never mysterious.

---

## Cross-cutting

- **C1** Each phase is independently shippable + live-verified with a ghost
  or test account before the next.
- **C2** No regressions to the ~16 live students; grandfather all existing
  progress.
- **C3** `empire-dojo` has no CI beyond `verify_pages.py`; every deploy is
  manual `wrangler` + live re-check.
- **C4** Keep secrets out of git (`DARB_SESSION_SECRET`, Cloudflare token).
