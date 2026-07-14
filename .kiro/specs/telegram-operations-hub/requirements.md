# Requirements — Markaz (مركز): Telegram Operations Hub

> **Codename: Markaz (مركز).** Arabic for "command center" — a dedicated
> Telegram bot that serves as the owner's single pane of glass for the
> entire Empire English business. Manage everything from your phone.

## Origin

The owner runs a paid English learning community with 7 complete
initiatives, 39+ commands, 26 feature flags, and 16+ students incoming.
They're one person doing many things simultaneously. They CANNOT sit in
Discord watching. They need a way to:

1. Know what's happening without looking
2. Respond to student issues from their phone
3. See business health at a glance
4. Get alerted only when something needs attention
5. Take actions (flag changes, announcements) without SSH/Discord

Currently: Nour escalations go to a generic bot. System health has no
central visibility. Daily metrics require logging into Discord.
Revenue/retention signals are invisible.

## Constraints

1. **Budget:** Free Telegram Bot API. Zero cost.
2. **Separate bot:** Must be its own bot (@EmpireOpsBot or similar),
   NOT sharing a token with any existing bot. Dedicated and clean.
3. **One chat:** All messages go to one Telegram chat (the owner's
   direct chat with the ops bot). NOT a group. Private and clean.
4. **Reply forwarding:** When owner replies to an escalation message,
   the response gets forwarded to the student as Nour. Seamless.
5. **Non-blocking:** The ops bot is a SENDER (pushes notifications)
   and a RECEIVER (handles replies). It does NOT affect the Discord
   bot's performance. Runs as a lightweight async component.
6. **Phone-first:** All messages must be readable on a phone screen.
   Short, well-formatted, with inline keyboard buttons when actionable.

## Requirements

### Requirement 1 — Dedicated bot identity

**User story:** As the owner, I want a dedicated @EmpireOpsBot that's
ONLY for Empire English operations, so my Telegram isn't cluttered and
I know every message from this bot is business-critical.

**Acceptance criteria:**
1. New Telegram bot created via @BotFather (name: "Empire Ops" or similar)
2. Bot token stored in `.env` as `OPS_BOT_TOKEN`
3. Completely separate from TELEGRAM_ALERT_TOKEN (the old watchdog bot)
4. All Nour escalations, system alerts, and reports go through THIS bot

### Requirement 2 — Daily Digest (every morning)

**User story:** As the owner waking up, I want to see a single message
summarizing yesterday's activity so I know the system is working without
checking Discord.

**Acceptance criteria:**
1. Every day at 7 AM Dubai time, send a digest message:
   - Students active yesterday (count)
   - Total tasks completed yesterday
   - New registrations (if any)
   - Streak milestones hit
   - Nour conversations handled (count)
   - Escalations awaiting response (count, if any)
2. Message formatted with emojis, concise, phone-readable.

### Requirement 3 — Nour Escalations (real-time)

**User story:** As the owner, when a student asks something Nour can't
handle, I want to see it instantly on Telegram with context and be able
to reply directly.

**Acceptance criteria:**
1. When Nour escalates: ops bot sends message with student name, level,
   streak, their question, and conversation history (last 3 messages).
2. Owner replies to that Telegram message → response forwarded to the
   student as a DM from Nour.
3. If no reply within 2 hours → ops bot sends a reminder.
4. After owner replies → ops bot confirms "✅ Delivered to [student]".

### Requirement 4 — System Health Alerts

**User story:** As the owner, if the Discord bot crashes, the API goes
down, or error rates spike, I want to know immediately without checking
server logs.

**Acceptance criteria:**
1. Bot crash/restart → alert within 60 seconds
2. API endpoint unreachable → alert
3. Groq API failures > 5 in 1 hour → alert
4. Database errors → alert
5. Each alert includes: what happened, when, severity (🟡/🔴)

### Requirement 5 — Quick Actions (inline buttons)

**User story:** As the owner on my phone, I want to perform common
actions directly from Telegram without SSH or Discord.

**Acceptance criteria:**
1. `/status` — system health summary (bot uptime, API status, student count)
2. `/students` — list active students with levels and streaks
3. `/flag <name> on/off` — toggle feature flags from Telegram
4. `/announce <message>` — post announcement to Discord #announcements
5. `/nour on/off` — quick enable/disable of Nour concierge
6. All commands respond within 5 seconds.

### Requirement 6 — Weekly Business Report

**User story:** As the owner, every Sunday I want a comprehensive
business report so I can make decisions about the product.

**Acceptance criteria:**
1. Every Sunday 9 AM: detailed weekly report:
   - Total active students (and change from last week)
   - Average tasks/day per student
   - Retention rate (% who completed at least 1 task this week)
   - Pronunciation score averages (improving/declining?)
   - Top 3 students (most points this week)
   - Churn risk (students inactive 3+ days)
   - Nour stats (conversations, escalations, resolution rate)
2. Message formatted as a clean business dashboard.

### Requirement 7 — Revenue Intelligence (future-ready)

**User story:** As the owner, I want to know when a free student should
be converted to paid (engagement signals).

**Acceptance criteria:**
1. When a student completes 7 consecutive days (first week streak) →
   alert: "🎯 [Name] completed their first week. Good time to convert."
2. When a student's engagement drops after being highly active →
   alert: "⚠️ [Name] might churn. Was doing 7/7, now 0 for 3 days."
3. Monthly summary: how many students at each engagement tier.
