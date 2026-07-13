# Requirements — Nabd (نبض): Student Notification System

> **Codename:** Nabd (نبض — "Pulse") — the heartbeat of daily engagement.
> **Purpose:** A smart, personal, multi-layered notification system that
> helps Arabic-speaking students build and maintain a daily English
> learning habit — by nudging at the right time, celebrating wins,
> and recovering students before they disappear.
> **Context:** 16 real students (9 free + 7 paid) about to be invited.
> The bot already delivers daily tasks and tracks streaks/points, but
> has NO proactive outreach to individual students beyond a generic
> missed-day report and the weekly assessment DM. Students who forget
> to open Discord simply fall off silently.

---

## Core Principle

**The right message, at the right time, to the right person.**

Not a notification firehose. Not generic blasts. Every notification
should be:
- **Personal** (references their name, their streak, their specific tasks)
- **Timely** (arrives when they can still ACT, not after the day is over)
- **Actionable** (tells them exactly what to do, not just "be better")
- **Respectful** (never during sleep, opt-out-able, escalating not spamming)
- **Bilingual** (Arabic-first per their language phase from Bawaba B5)

---

## Requirements

### R1 — Morning Kickstart
Every active student receives a personal DM at a configured time
(default: 5 minutes after daily task post) reminding them their tasks
are ready. Acceptance criteria:
- Includes their current streak count and what's at stake ("day 8!")
- Includes their first available task by name (respects gradual intro)
- Includes a direct link to the practice platform day page
- Respects Bawaba B5 language phase (week 1: Arabic only)
- Does NOT fire for students who already completed a task today (don't nag the already-active)

### R2 — Evening Incomplete Reminder
Students with incomplete tasks get a personal DM at 8 PM (configurable).
Acceptance criteria:
- Shows exactly how many tasks remain and which ones
- Suggests the quickest task they can still do
- Only fires if at least 1 task was completed (they showed up but didn't finish — different from total absence)
- Does NOT fire if all tasks are done (no false alerts)

### R3 — Streak-at-Risk Alert
Students with an active streak who have done ZERO tasks today get an
urgent DM at 9 PM. Acceptance criteria:
- Explicitly states their streak length and that it will break at midnight
- Suggests the single easiest 5-minute task they can do
- Only fires if streak >= 3 (a 1-day "streak" isn't worth alarming about)
- Fires only ONCE per day (never double-nags)

### R4 — Real-Time Milestone Celebrations
Instant congratulations when a student hits a meaningful milestone.
Acceptance criteria:
- All 7 tasks complete: public shoutout in #daily-check-in + personal DM
- Streak milestones (7/14/30/60/100): personal DM + public announcement
- First-ever assessment: congratulations DM
- Level advancement: handled by existing cmd_examresult (not duplicated)
- Celebrations feel HUMAN (varied messages, not the same template every time)

### R5 — Weekly Progress Summary
Every student receives a personal progress report (Friday evening).
Acceptance criteria:
- Shows this week vs. last week completion rate (with visual bar)
- Highlights their strongest and weakest task type this week
- Specific encouragement based on performance tier
- If improved: celebration. If declined: supportive + specific suggestion.
- Replaces/enhances the existing monday_progress_report with richer content

### R6 — Absence Recovery Ladder
Students who miss multiple days get escalating outreach. Acceptance criteria:
- Day 2 (missed): gentle bot DM ("مفتقدينك — حتى مهمة واحدة أحسن من لا شيء")
- Day 3: buddy gets a specific prompt to send a voice message
- Day 5: a special "comeback" mini-task DM (one very easy thing to do)
- Day 7+: flagged in !attention (already exists), bot sends a final DM
- Each escalation fires ONCE (not daily at each level)
- Tracks which escalation level was last sent (in DB, survives restarts)

### R7 — Notification Preferences
Students can control their notification experience. Acceptance criteria:
- `!إشعارات` / `!notifications` command shows current settings
- Students can disable specific notification types (morning, evening, social)
- "Quiet hours" respected (no DMs between 11 PM - 5 AM member's timezone)
- Preferences persist in the database (not in-memory)

### R8 — Social Proof (opt-in)
Light social nudges that create community feeling without pressure.
Acceptance criteria:
- When a same-level peer completes all tasks: optional notification
- Framed as community activity, not competition/shame
- Disabled by default (opt-IN, not opt-out) — respects introverts
- Never reveals specific scores or struggles of other members

---

## Constraints

- Same $7/month Hetzner VPS — no external notification services
- All notifications via Discord DM (the bot already has this capability)
- Must not violate Discord rate limits (DMs are limited ~5/second)
- Must respect Bawaba B5 language phases for all message text
- Must work with the existing `@tasks.loop` scheduling infrastructure
- Each notification type gated behind its own feature flag (`nabd_*`)
- Must not disrupt existing scheduled tasks (daily post, assessments, etc.)

---

## Out of Scope (explicitly)

- Telegram bridge (possible future enhancement, not this spec)
- Email notifications (students don't provide email to the bot)
- Push notifications outside Discord (platform limitation)
- AI-generated personalized coaching messages (keep it template-based
  for predictability and speed; AI evaluation stays in writing feedback)
