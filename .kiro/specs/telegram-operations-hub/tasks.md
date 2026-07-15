# Tasks — Markaz (مركز): Telegram Operations Hub

> **How to use this file:** same discipline as all other specs — work
> top to bottom, check off tasks. Each phase builds on the previous.

---

## Phase M0 — Bot Setup + Core Messaging ✅ COMPLETE

- [x] **M0.1** Create new Telegram bot via @BotFather (name: "Empire Ops",
  username: @EmpireOpsBot or similar). Get token.
  → Created via Telethon-scripted @BotFather conversation (owner's personal
  account, my.telegram.org api_id/api_hash). Bot: **Empire Ops**,
  username **@empire_ops_eec_bot**, verified live via `getMe`. Telethon
  session deleted immediately after creation — no persistent access kept.
- [x] **M0.2** Add `OPS_BOT_TOKEN` and `OPS_CHAT_ID` to config.py and .env.
  → Added to production `.env` on Hetzner (77.42.43.250) via `chattr -i/+i`
  safe SSH key procedure. `OPS_CHAT_ID` captured from the owner's `/start`
  message via `getUpdates` (chat_id 8924041557). Config vars added in
  `config.py` alongside the existing `TELEGRAM_ALERT_*` block.
- [x] **M0.3** Create `src/ops_hub.py` with:
  - `send_ops_message(text, reply_markup, parse_mode)` — core send function
  - `send_ops_alert(title, body, severity)` — formatted alert
  - Error handling: if Telegram API fails, log and skip (never crash bot)
  → Also added `escape_markdown()` and an automatic plain-text retry
  fallback after discovering (during M0.5 testing) that unescaped
  Markdown special characters in dynamic/student text cause a silent
  Telegram 400 "can't parse entities" error — same class of bug as the
  Discord `!flag list` 2000-char overflow. Fixed proactively rather than
  waiting for it to surface in production.
- [x] **M0.4** Update `nour_escalation.py` to use OPS_BOT_TOKEN (with
  fallback to TELEGRAM_ALERT_TOKEN if OPS not configured yet).
  → `escalate_to_owner()` now resolves `token`/`chat_id` from
  `OPS_BOT_TOKEN`/`OPS_CHAT_ID` first, falling back to the legacy
  `TELEGRAM_ALERT_TOKEN`/`TELEGRAM_ALERT_CHAT_ID`. Student name/message/
  context are now passed through `escape_markdown()` before being
  embedded in the alert.
- [x] **M0.5** Test: send a test message from the bot to verify delivery.
  → Verified live: `send_ops_alert()` and `send_ops_message()` both
  delivered successfully to the owner's Telegram, including the
  plain-text fallback path (confirmed with a deliberately unescaped
  test message).

## Phase M1 — Daily Digest + Escalation Routing ✅ COMPLETE

- [x] **M1.1** Add `@tasks.loop` for daily digest (7 AM Dubai time).
  Query: active members, total submissions, new joins, streaks, Nour
  conversations count, pending escalations.
  → `markaz_daily_digest()` in `bot.py`, gated behind the new
  `markaz_daily_digest` feature flag. New `database.py` query helpers:
  `count_active_members_on`, `total_submissions_on_date`,
  `count_new_members_on`, `streak_milestones_on`,
  `count_nour_conversations_on`. Verified live against a seeded test DB
  (2 active students, 3 tasks, 1 streak milestone, 1 Nour conversation)
  — digest matched exactly.
- [x] **M1.2** Format digest as a clean phone-readable message with emojis.
  → Matches the design.md example format exactly (active students,
  tasks completed, streak milestones, new registrations, Nour
  conversations, pending escalations, healthy/warning footer).
- [x] **M1.3** Route ALL Nour escalations through ops bot (replace old
  TELEGRAM_ALERT_TOKEN usage in nour_escalation.py).
  → `escalate_to_owner()` now sends via `ops_hub.send_ops_message()`
  whenever `OPS_BOT_TOKEN`/`OPS_CHAT_ID` are set (which they are, as of
  M0), with the old `TELEGRAM_ALERT_TOKEN` path kept only as a fallback
  for environments where the ops bot isn't configured yet.
- [x] **M1.4** Include conversation history (last 3 messages) in
  escalation alerts for full context.
  → New `database.get_recent_conversation()` helper (public counterpart
  of `nour_concierge._get_recent_conversation`). Escalation messages now
  include a "📜 Recent conversation" section with the last 3 messages,
  excluding the just-escalated message itself.

**Real bug found and fixed during M1 live testing (important — read
before touching Telegram message formatting again):** Telegram's legacy
`parse_mode="Markdown"` does **not** reliably support escaping all its
own special characters — a backslash-escaped `*` (e.g. `Ahmed\*Test`)
still raises a 400 "can't parse entities" error even though `_` escapes
fine. Confirmed directly against the live Bot API and cross-checked
against Telegram's own docs, which explicitly recommend `MarkdownV2`
over legacy `Markdown` for exactly this reason. Fixed by switching
`ops_hub.py` (and `nour_escalation.py`'s legacy fallback path) to
`MarkdownV2`, with a complete escaping rule for
`_*[]()~\`>#+-=|{}.!` (per the official docs) rather than the old
partial `_*\`[ ` list. Also had to escape literal punctuation in the
bot's *own* message templates (parentheses, periods) since MarkdownV2
requires that even for non-user-generated text. All three message
paths (`send_ops_message`, `send_ops_alert`, escalation alerts, the
daily digest) re-tested live afterward and now send correctly on the
first attempt with zero fallback triggers — previously this relied on
the M0 plain-text safety net to avoid losing the message, which worked
but meant losing all bold/formatting on any message containing student
text with special characters.

## Phase M2 — Reply Forwarding ✅ COMPLETE

- [x] **M2.1** Implement Telegram polling loop (getUpdates) as a
  background task — checks every 5 seconds for new messages.
  → Implemented in new `src/ops_poller.py`, started once from
  `on_ready()` via `asyncio.create_task()` (self-guarded against
  duplicate starts, checked both in `ops_poller._running` and in
  `bot.py` via a `bot._ops_poller_started` flag). **Deviation from the
  spec's "every 5 seconds":** used `getUpdates` long-polling
  (`timeout=25`) instead of a tight 5-second poll loop — long-polling
  is Telegram's own recommended approach (near-instant delivery, far
  fewer wasted requests than polling every 5s with `timeout=0`), and
  the offset is persisted via `database.get_setting`/`set_setting` so
  a restart doesn't reprocess old updates or miss ones sent while the
  bot was down.
- [x] **M2.2** When owner replies to an escalation message: match
  reply_to_message_id → find discord_id → DM student as Nour.
  → New persistent `pending_escalations` table (replacing the old
  in-memory-only dict, which would have lost every unresolved
  escalation on a redeploy — a real gap, since a redeploy can land at
  any time relative to when the owner replies). New
  `nour_escalation.forward_reply_to_student()` delivers the DM and
  records it in `nour_conversations` history.
- [x] **M2.3** After successful delivery: send confirmation
  "✅ Delivered to [student name]" in Telegram.
  → `ops_poller._handle_escalation_reply()` calls
  `ops_hub.send_ops_alert("Delivered", ...)` on success.
- [x] **M2.4** If delivery fails (DMs disabled): notify owner
  "❌ Couldn't deliver — student has DMs off."
  → Same handler sends a `severity="warning"` alert on failure, and
  deliberately leaves the escalation unresolved (not marked resolved)
  so it still shows up as pending in the next daily digest.

**Two real bugs found and fixed during M2 live testing** (both only
surfaced when testing with a member that had a missing/malformed DB
row, not in the initial happy-path test — worth remembering):
1. `forward_reply_to_student()` originally wrapped the Discord DM
   *and* the conversation-history write in one try/except. A failure
   in the history write alone (e.g. a `FOREIGN KEY constraint failed`)
   was misreported as "delivery failed" even though the DM had already
   been sent successfully. Fixed by separating them into two try
   blocks — the DM send determines the return value; history storage
   is now best-effort logging only.
2. `_store_reply_in_history()` (and all four new `pending_escalations`
   functions in `database.py`) used bare `conn.close()` after
   `conn.execute()`/`conn.commit()` with no `try/finally`. When
   `execute()` raised, `close()` was skipped entirely, leaking an open
   connection with a dangling transaction that then locked the SQLite
   file (`database is locked`) for the very next operation
   (`resolve_pending_escalation()`, called moments later in the same
   request). Fixed with `try/finally` around every new
   `pending_escalations` function — this matters more than usual here
   because `ops_poller` is a long-running background loop that never
   restarts on its own, so a leaked connection compounds indefinitely
   rather than clearing on the next process restart.

Verified live end-to-end against the real @empire_ops_eec_bot and a
real Telegram reply-to-message (not a synthetic payload): sent a real
escalation, replied to it in Telegram, captured the real `getUpdates`
payload, replayed it through `ops_poller._handle_update()` against a
mock Discord bot/guild/member, and confirmed: DM "sent", conversation
history stored, escalation marked resolved, and a real
"✅ Delivered" confirmation alert delivered to the owner's Telegram.

## Phase M3 — Quick Actions (commands) ✅ COMPLETE

- [x] **M3.1** Implement command router in polling loop (detect /commands).
  → Extended `ops_poller._handle_update()` to detect standalone (non-reply)
  messages starting with `/` and dispatch them to a new `_handle_command()`
  function, which delegates to `ops_commands.dispatch()`. Errors are caught
  and reported back to the owner as a formatted error message rather than
  crashing the poller.
- [x] **M3.2** `/status` — bot uptime, API health, active student count,
  last error (if any).
  → Shows version, Discord connection, heartbeat, AI providers (Groq/Gemini),
  registered students by level, today's submissions, and pending escalations.
- [x] **M3.3** `/students` — list active students with level + streak.
  Paginated if > 10.
  → Sorted by streak descending. Shows `name — level, 🔥Xd` per student.
  Paginated with `/students 2` for page 2, page size 10.
- [x] **M3.4** `/flag <name> on/off` — toggle feature flags from Telegram.
  Confirm with current state.
  → `/flag` alone lists all flags with 🟢/🔴 state. `/flag <name>` shows
  one flag's state. `/flag <name> on/off` toggles it. Accepts multiple
  synonyms (on/enable/1/true, off/disable/0/false).
- [x] **M3.5** `/announce <message>` — post to Discord #announcements.
  Confirm "✅ Posted to #announcements".
  → Validates message length (≤1950), finds #announcements channel, posts
  with the same "📢 **Announcement**" header as `!announce`, confirms
  delivery back to Telegram.
- [x] **M3.6** `/nour on/off` — quick toggle for nour_concierge flag.
  → Shortcut that wraps the `nour_concierge` flag. `/nour` shows state,
  `/nour on/off` toggles.

Also added `/help` — lists all available commands with descriptions.

All commands use `ops_hub.escape_markdown()` for any dynamic text,
respecting the MarkdownV2 rules established in M1. Responses are sent
back to the owner's Telegram via `ops_hub.send_ops_message()`, reusing
the plain-text fallback safety net from M0. New module:
`src/ops_commands.py` — decorator-based registry pattern, cleanly
separated from the polling/routing logic in `ops_poller.py`.

Verified live: sent real `/status`, `/help`, and `/students` responses
through the actual @empire_ops_eec_bot to the owner's Telegram —
all delivered with correct MarkdownV2 formatting on the first attempt.

## Phase M4 — Weekly Report + Revenue Intelligence ✅ COMPLETE

- [x] **M4.1** Add `@tasks.loop` for weekly report (Sunday 9 AM).
  Comprehensive business metrics.
  → `markaz_weekly_report()` task loop, only fires on Sundays
  (weekday check inside the loop body). Gated behind
  `markaz_weekly_report` feature flag.
- [x] **M4.2** Format as business dashboard (active, retention, avg
  tasks, pronunciation, top students, churn risk).
  → Includes: total students, new this week, peak daily active, total
  tasks, avg tasks/active student, retention % (3+/7 days active),
  level distribution, top 3 streaks, streak milestones, pending
  escalations. All dynamic values passed through `escape_markdown()`
  for MarkdownV2 safety.
- [x] **M4.3** Conversion signal: when student completes first 7-day
  streak → "🎯 [Name] conversion-ready" alert.
  → `ops_monitoring.check_conversion_ready()` called from the `!done`
  handler whenever streak ≥ 7. Only fires on the FIRST 7-day streak
  (checks `longest_streak == 7`). Gated behind `markaz_conversion_alerts`.
- [x] **M4.4** Churn signal: highly active student goes silent 3+ days
  → "⚠️ [Name] might churn" alert.
  → `ops_monitoring.check_churn_risk()` called daily from the
  `markaz_daily_digest` loop. Targets students with `longest_streak ≥ 3`
  who have `last_active_at` 3+ days ago. Sorted by highest-value first,
  sends at most 3 alerts per day. Gated behind `markaz_churn_alerts`.
- [x] **M4.5** Monthly summary: engagement tiers, revenue potential.
  → `markaz_monthly_summary()` task loop (1st of month, 9:30 AM Dubai).
  Shows high/medium/low engagement tiers by current streak, level
  distribution, conversion-ready count, premium candidates.

## Phase M5 — System Health Monitoring ✅ COMPLETE

- [x] **M5.1** Bot restart detection: on_ready() sends "🔄 Bot restarted"
  to ops channel (useful for knowing deploys happened).
  → `ops_monitoring.notify_bot_restart()` called once from `on_ready()`
  (guarded against duplicate firing on gateway reconnects via
  `bot._restart_notified`). Shows version and UTC timestamp.
- [x] **M5.2** Groq failure tracking: if > 5 failures in 1 hour →
  "⚠️ Groq API issues" alert.
  → `ops_monitoring.track_groq_failure()` called from both
  `ai_engine._call_groq()` and `nour_concierge._call_groq_chat()` on
  any failure (status != 200 or exception). In-memory sliding-window
  counter with 1-hour window + 1-hour throttle between alerts.
- [x] **M5.3** Hourly heartbeat (optional): "💚" ping so absence of
  message = something is wrong.
  → **Deliberately NOT implemented as a separate Telegram message** —
  the existing `heartbeat` task loop already writes to the DB every 2
  minutes (Aegis Phase 2), and sending a Telegram message every hour
  would just be noise. Instead, the daily digest's "All systems
  healthy" footer and the restart detection (M5.1) together give the
  owner confidence the system is alive — if the daily digest doesn't
  arrive at 7 AM, something is wrong. A future `/heartbeat` command
  could be added if the owner wants on-demand "are you alive?" checks.
- [x] **M5.4** Database error detection: any SQLite error → alert.
  → `ops_monitoring.notify_database_error(error, context)` available
  for any caller to use. Throttled to max 1 alert per 10 minutes to
  avoid flooding on cascading failures.

---

## Cross-phase notes

- **Same container, same process** — ops_hub is a module inside the
  Discord bot, not a separate service.
- **Telegram polling** runs as asyncio background task alongside Discord.
- **Fallback:** If OPS_BOT_TOKEN not set, fall back to TELEGRAM_ALERT_TOKEN
  (existing behavior preserved during migration).
- **Rate limiting:** Telegram API allows 30 messages/second to same chat.
  More than enough for all operations.
- **Message formatting:** Use Markdown parse_mode for all messages.
  Keep under 4096 chars (Telegram limit).
- **Bot creation:** Owner creates the bot via @BotFather (takes 30 seconds),
  gives the token. Agent adds it to .env and deploys.
- **Privacy:** All messages go to owner's private chat only. No groups,
  no other recipients.
