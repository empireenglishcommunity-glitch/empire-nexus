# Design — Markaz (مركز): Telegram Operations Hub

## Architecture Overview

```
Empire English Discord Bot (existing)
         ↓ events
ops_hub.py (new module inside the same container)
  - Listens for: escalations, milestones, errors, scheduled reports
  - Sends to: Owner's Telegram via Ops Bot
  - Receives: Owner's replies via Telegram webhook/polling
         ↓
Telegram Ops Bot (@EmpireOpsBot)
  - Owner's private chat
  - Formatted messages with inline keyboards
  - Reply forwarding to Discord students
```

## Component 1 — Ops Bot Core (`src/ops_hub.py`)

Lightweight async module that:
- Sends formatted messages to owner's Telegram
- Polls for replies (or uses webhook if configured)
- Routes replies back to Discord (via Nour)

### Sending Messages

```python
async def send_ops_message(text: str, reply_markup=None, parse_mode="Markdown"):
    """Send a message to the owner via the Ops Bot."""
    url = f"https://api.telegram.org/bot{config.OPS_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.OPS_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    ...
```

### Reply Handling (polling)

```python
async def poll_for_replies():
    """Long-poll Telegram for owner replies to escalation messages.
    
    Runs as background task. When owner replies to an escalation:
    1. Match the replied-to message_id to a pending escalation
    2. Forward the reply text to the student as Nour DM
    3. Confirm delivery back to owner
    """
```

## Component 2 — Daily Digest (`ops_daily_digest()`)

Scheduled: 7 AM Dubai time via `@tasks.loop`

```python
async def send_daily_digest():
    """Morning digest — single message summarizing yesterday."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    
    active_count = count_members_active_on(yesterday)
    tasks_count = count_all_submissions_on(yesterday)
    new_members = count_new_members_on(yesterday)
    nour_convos = count_nour_conversations_on(yesterday)
    pending_escalations = count_pending_escalations()
    
    msg = format_digest(active_count, tasks_count, ...)
    await send_ops_message(msg)
```

## Component 3 — Escalation Router

Replaces the current `nour_escalation.escalate_to_owner()` to use
the new Ops Bot instead of the generic TELEGRAM_ALERT bot.

```python
async def escalate(discord_id, student_name, message, context):
    """Send escalation via Ops Bot with reply forwarding support."""
    msg = format_escalation(student_name, message, context)
    result = await send_ops_message(msg)
    
    # Store message_id → discord_id mapping for reply routing
    _pending_escalations[result.message_id] = discord_id
```

## Component 4 — Quick Actions (command handler)

```python
COMMANDS = {
    "/status": handle_status,      # System health
    "/students": handle_students,  # Active student list
    "/flag": handle_flag,         # Toggle feature flags
    "/announce": handle_announce, # Post to Discord
    "/nour": handle_nour_toggle,  # Enable/disable Nour
}
```

## Component 5 — Weekly Report

Scheduled: Sunday 9 AM

```python
async def send_weekly_report():
    """Comprehensive business dashboard."""
    # Active students + change
    # Avg tasks/day
    # Retention rate
    # Pronunciation averages
    # Top 3 students
    # Churn risk list
    # Nour stats
```

## Component 6 — Revenue Intelligence

Event-driven (fires on specific triggers):

```python
async def check_conversion_signals(discord_id):
    """After a student completes 7 consecutive days, alert owner."""
    
async def check_churn_signals(discord_id):
    """After highly active student goes silent for 3 days, alert owner."""
```

## Config Additions

```python
# In config.py:
OPS_BOT_TOKEN = os.getenv("OPS_BOT_TOKEN", "")
OPS_CHAT_ID = os.getenv("OPS_CHAT_ID", "")  # Owner's chat ID with ops bot
```

## Message Formatting Examples

### Daily Digest
```
📊 *Daily Digest — July 15*
━━━━━━━━━━━━━━━━━━━━

👥 Active students: *12/16*
✅ Tasks completed: *67*
🔥 Streak milestones: 2 (Ahmed 7d, Sara 14d)
🆕 New registrations: 1
💬 Nour conversations: 8
🚨 Pending escalations: 0

*All systems healthy.* ✅
```

### Escalation
```
🚨 *Student needs help*
━━━━━━━━━━━━━━━━━━━━

👤 *Ahmed* (L0, streak 5, 82% pronunciation)
💬 "عايز ألغي الاشتراك — مش عندي وقت"

📋 Context:
- Active for 2 weeks, was doing well
- Last 3 days: 0 tasks (unusual drop)
- Nour tried: encouraged, offered flexibility

💡 *Reply to this message to respond as Nour.*
```

### Weekly Report
```
📈 *Weekly Report — July 8-14*
━━━━━━━━━━━━━━━━━━━━

👥 Active: 14/16 (↑2 from last week)
📊 Avg tasks/day: 4.2/student
🔄 Retention: 87% (14/16 did ≥1 task)
🎯 Pronunciation avg: 72% (↑5%)
🏆 Top 3: Ahmed (490pts), Sara (420pts), Omar (380pts)

⚠️ *Churn risk:*
- Khaled: 0 tasks for 4 days
- Fatma: declining scores (82%→58%)

💰 *Conversion ready:*
- Mostafa: 7-day streak, highly engaged
```

## Deployment

- Same Docker container (new module, not a new service)
- Runs inside the existing bot process as background tasks
- New env vars: `OPS_BOT_TOKEN`, `OPS_CHAT_ID`
- Create bot via @BotFather: /newbot → "Empire Ops" → @EmpireOpsBot
