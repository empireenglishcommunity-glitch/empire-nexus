# Tasks — Markaz (مركز): Telegram Operations Hub

> **How to use this file:** same discipline as all other specs — work
> top to bottom, check off tasks. Each phase builds on the previous.

---

## Phase M0 — Bot Setup + Core Messaging

- [ ] **M0.1** Create new Telegram bot via @BotFather (name: "Empire Ops",
  username: @EmpireOpsBot or similar). Get token.
- [ ] **M0.2** Add `OPS_BOT_TOKEN` and `OPS_CHAT_ID` to config.py and .env.
- [ ] **M0.3** Create `src/ops_hub.py` with:
  - `send_ops_message(text, reply_markup, parse_mode)` — core send function
  - `send_ops_alert(title, body, severity)` — formatted alert
  - Error handling: if Telegram API fails, log and skip (never crash bot)
- [ ] **M0.4** Update `nour_escalation.py` to use OPS_BOT_TOKEN (with
  fallback to TELEGRAM_ALERT_TOKEN if OPS not configured yet).
- [ ] **M0.5** Test: send a test message from the bot to verify delivery.

## Phase M1 — Daily Digest + Escalation Routing

- [ ] **M1.1** Add `@tasks.loop` for daily digest (7 AM Dubai time).
  Query: active members, total submissions, new joins, streaks, Nour
  conversations count, pending escalations.
- [ ] **M1.2** Format digest as a clean phone-readable message with emojis.
- [ ] **M1.3** Route ALL Nour escalations through ops bot (replace old
  TELEGRAM_ALERT_TOKEN usage in nour_escalation.py).
- [ ] **M1.4** Include conversation history (last 3 messages) in
  escalation alerts for full context.

## Phase M2 — Reply Forwarding

- [ ] **M2.1** Implement Telegram polling loop (getUpdates) as a
  background task — checks every 5 seconds for new messages.
- [ ] **M2.2** When owner replies to an escalation message: match
  reply_to_message_id → find discord_id → DM student as Nour.
- [ ] **M2.3** After successful delivery: send confirmation
  "✅ Delivered to [student name]" in Telegram.
- [ ] **M2.4** If delivery fails (DMs disabled): notify owner
  "❌ Couldn't deliver — student has DMs off."

## Phase M3 — Quick Actions (commands)

- [ ] **M3.1** Implement command router in polling loop (detect /commands).
- [ ] **M3.2** `/status` — bot uptime, API health, active student count,
  last error (if any).
- [ ] **M3.3** `/students` — list active students with level + streak.
  Paginated if > 10.
- [ ] **M3.4** `/flag <name> on/off` — toggle feature flags from Telegram.
  Confirm with current state.
- [ ] **M3.5** `/announce <message>` — post to Discord #announcements.
  Confirm "✅ Posted to #announcements".
- [ ] **M3.6** `/nour on/off` — quick toggle for nour_concierge flag.

## Phase M4 — Weekly Report + Revenue Intelligence

- [ ] **M4.1** Add `@tasks.loop` for weekly report (Sunday 9 AM).
  Comprehensive business metrics.
- [ ] **M4.2** Format as business dashboard (active, retention, avg
  tasks, pronunciation, top students, churn risk).
- [ ] **M4.3** Conversion signal: when student completes first 7-day
  streak → "🎯 [Name] conversion-ready" alert.
- [ ] **M4.4** Churn signal: highly active student goes silent 3+ days
  → "⚠️ [Name] might churn" alert.
- [ ] **M4.5** Monthly summary: engagement tiers, revenue potential.

## Phase M5 — System Health Monitoring

- [ ] **M5.1** Bot restart detection: on_ready() sends "🔄 Bot restarted"
  to ops channel (useful for knowing deploys happened).
- [ ] **M5.2** Groq failure tracking: if > 5 failures in 1 hour →
  "⚠️ Groq API issues" alert.
- [ ] **M5.3** Hourly heartbeat (optional): "💚" ping so absence of
  message = something is wrong.
- [ ] **M5.4** Database error detection: any SQLite error → alert.

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
