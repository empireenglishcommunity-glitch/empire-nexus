# Empire English — Nudge Automations (n8n Workflows)

**Build Document v1.0** · **Date:** June 25, 2026
**Status:** READY TO IMPLEMENT

> **What this is.** Two n8n workflows that run daily and send one-time nudge messages to users who started the bot but didn't complete the next funnel step. These are the two highest-impact re-engagement automations identified in Phase 1 spec §8.

> **Rules:**
> - Each nudge fires **once per user, ever** (flag in Subscribers sheet prevents repeats)
> - Nudges are sent at 18:00 Asia/Dubai (non-intrusive evening time)
> - Both nudges are bilingual (Arabic-led)
> - After sending, the sheet is updated immediately (idempotent)

---

## Prerequisites

Before building these workflows:
1. Add two new columns to the `Subscribers` tab:
   - `nudge_quiz_sent` (leave blank; will be set to `TRUE` when sent)
   - `nudge_call_sent` (leave blank; will be set to `TRUE` when sent)
2. Ensure the `Events` tab is being populated by the main bot workflow
3. The bot token must be available as an n8n credential or environment variable

---

## Workflow 1: "Empire — Quiz Nudge" (3-day reminder)

### Purpose
Users who started the bot (`JOINED_BOT`) but never completed the quiz (`QUIZ_COMPLETED`) after 3 days get a gentle one-time reminder.

### Trigger
- **Schedule node:** Daily at 18:00 Asia/Dubai

### Flow

```
Schedule (18:00 daily)
    ↓
Google Sheets: Get All Subscribers
    ↓
Code Node: Filter Eligible Users
    ↓
Split In Batches (1 at a time, 1s delay)
    ↓
HTTP Request: Send Nudge Message
    ↓
Google Sheets: Update Row (set nudge_quiz_sent = TRUE)
```

### Code Node: "Filter Quiz Nudge Eligible"

```javascript
// Filter: users who joined 3+ days ago, never quizzed, never nudged
const items = $input.all();
const now = Date.now();
const THREE_DAYS = 3 * 24 * 60 * 60 * 1000;

const eligible = [];

for (const item of items) {
  const row = item.json;
  
  // Skip if already nudged
  if (row.nudge_quiz_sent === 'TRUE' || row.nudge_quiz_sent === true) continue;
  
  // Skip if no first_seen_at (shouldn't happen, but safety)
  if (!row.first_seen_at) continue;
  
  // Skip if they already completed the quiz (level is filled)
  if (row.level && row.level.trim() !== '') continue;
  
  // Check if 3+ days since first seen
  const firstSeen = new Date(row.first_seen_at).getTime();
  if (now - firstSeen < THREE_DAYS) continue;
  
  // This user is eligible
  eligible.push({
    json: {
      telegram_id: row.telegram_id,
      first_name: row.first_name || '',
      row_number: item.json._rowNumber || item.json.row_number
    }
  });
}

// Return eligible users (may be empty — that's fine)
return eligible.length > 0 ? eligible : [{ json: { _empty: true } }];
```

### Code Node: "Build Quiz Nudge Message" (after Split In Batches)

```javascript
// Skip empty batches
if ($input.first().json._empty) return [];

const chatId = $input.first().json.telegram_id;
const firstName = $input.first().json.first_name;
const BOT_TOKEN = $env.BOT_TOKEN;

const text = `مرحبًا${firstName ? ' ' + firstName : ''}! 👋

شفت إنك ما جربت اختبار المستوى بعد — دقيقتين بس وتعرف بالضبط وين تبدأ.

جرّبه؟ 🎯`;

const keyboard = {
  inline_keyboard: [
    [{ text: '🎯 ابدأ الاختبار', callback_data: 'quiz' }],
    [{ text: '↩️ القائمة', callback_data: 'menu' }]
  ]
};

return [{
  json: {
    method: 'sendMessage',
    chat_id: chatId,
    text: text,
    reply_markup: JSON.stringify(keyboard),
    _bot_token: BOT_TOKEN,
    _telegram_id: chatId,
    _row_number: $input.first().json.row_number
  }
}];
```

### HTTP Request Node: "Send Quiz Nudge"

| Field | Value |
|-------|-------|
| Method | POST |
| URL | `https://api.telegram.org/bot{{ $json._bot_token }}/sendMessage` |
| Body | JSON: `chat_id`, `text`, `reply_markup` from previous node |
| Continue on Fail | YES (user may have blocked the bot) |

### Google Sheets Node: "Flag Quiz Nudge Sent"

| Field | Value |
|-------|-------|
| Operation | Update Row |
| Sheet | `Subscribers` |
| Match by | `telegram_id` = `{{ $json._telegram_id }}` |
| Update column | `nudge_quiz_sent` = `TRUE` |

---

## Workflow 2: "Empire — Call Nudge" (7-day reminder)

### Purpose
Users who completed the quiz (`QUIZ_COMPLETED`) but never booked a call (`BOOKED`) or opened the offer (`OFFER_OPENED`) after 7 days get a gentle one-time reminder.

### Trigger
- **Schedule node:** Daily at 18:00 Asia/Dubai (same time, separate workflow)

### Flow

Same structure as Workflow 1, different filter logic and message.

### Code Node: "Filter Call Nudge Eligible"

```javascript
// Filter: users who quizzed 7+ days ago, never booked, never nudged for call
const items = $input.all();
const now = Date.now();
const SEVEN_DAYS = 7 * 24 * 60 * 60 * 1000;

const eligible = [];

for (const item of items) {
  const row = item.json;
  
  // Skip if already nudged for call
  if (row.nudge_call_sent === 'TRUE' || row.nudge_call_sent === true) continue;
  
  // Must have completed quiz (level exists)
  if (!row.level || row.level.trim() === '') continue;
  
  // Must NOT have booked
  if (row.booked === 'TRUE' || row.booked === true) continue;
  
  // Check timing: needs a quiz completion timestamp
  // Use last_active_at as proxy if quiz_completed_at not available
  const quizTime = row.quiz_completed_at || row.last_active_at;
  if (!quizTime) continue;
  
  const quizDate = new Date(quizTime).getTime();
  if (now - quizDate < SEVEN_DAYS) continue;
  
  eligible.push({
    json: {
      telegram_id: row.telegram_id,
      first_name: row.first_name || '',
      level: row.level || '',
      row_number: item.json._rowNumber || item.json.row_number
    }
  });
}

return eligible.length > 0 ? eligible : [{ json: { _empty: true } }];
```

### Code Node: "Build Call Nudge Message"

```javascript
if ($input.first().json._empty) return [];

const chatId = $input.first().json.telegram_id;
const firstName = $input.first().json.first_name;
const telegramId = chatId;
const BOT_TOKEN = $env.BOT_TOKEN;
const CALL_URL = 'https://cal.com/macalempire/empire-english?src=nudge&tid=' + telegramId;

const text = `أهلاً${firstName ? ' ' + firstName : ''}! 👋

خطتك جاهزة من اختبار المستوى. لو تبي نرسم لك خارطة طريق شخصية في مكالمة قصيرة (15 دقيقة، بدون ضغط) — احجز وقت يناسبك 👇`;

const keyboard = {
  inline_keyboard: [
    [{ text: '📅 احجز مكالمة مجانية', url: CALL_URL }],
    [{ text: '↩️ القائمة', callback_data: 'menu' }]
  ]
};

return [{
  json: {
    chat_id: chatId,
    text: text,
    reply_markup: JSON.stringify(keyboard),
    _bot_token: BOT_TOKEN,
    _telegram_id: chatId,
    _row_number: $input.first().json.row_number
  }
}];
```

### HTTP Request & Sheets Update

Same pattern as Workflow 1:
- HTTP Request sends the message (Continue on Fail = YES)
- Google Sheets updates `nudge_call_sent = TRUE`

---

## Implementation Checklist

| # | Step | Time | Done |
|---|------|:----:|:----:|
| 1 | Add `nudge_quiz_sent` and `nudge_call_sent` columns to Subscribers | 2 min | ☐ |
| 2 | Create new workflow "Empire — Quiz Nudge" in n8n | — | ☐ |
| 3 | Add Schedule trigger (daily 18:00 Asia/Dubai) | 2 min | ☐ |
| 4 | Add Google Sheets "Get All Rows" (Subscribers tab) | 3 min | ☐ |
| 5 | Add Code Node "Filter Quiz Nudge Eligible" (paste code above) | 5 min | ☐ |
| 6 | Add Split In Batches (batch size 1, delay 1000ms) | 2 min | ☐ |
| 7 | Add Code Node "Build Quiz Nudge Message" | 5 min | ☐ |
| 8 | Add HTTP Request "Send Quiz Nudge" (Continue on Fail = ON) | 5 min | ☐ |
| 9 | Add Google Sheets "Update Row" (flag nudge_quiz_sent) | 5 min | ☐ |
| 10 | Test: manually set a test subscriber's first_seen_at to 4 days ago, run workflow | 5 min | ☐ |
| 11 | Duplicate workflow → rename "Empire — Call Nudge" | 2 min | ☐ |
| 12 | Replace filter + message code nodes with Call versions | 10 min | ☐ |
| 13 | Test: set a test subscriber with level filled + no booking + 8 days ago | 5 min | ☐ |
| 14 | Activate both workflows | 1 min | ☐ |

**Total estimated time: ~1 hour of n8n work.**

---

## Safety Guarantees

| Guarantee | How it's enforced |
|-----------|-------------------|
| Never send twice | `nudge_*_sent = TRUE` flag checked before sending |
| Never spam | Only 1 nudge per category per user, ever |
| Graceful failure | HTTP Request has "Continue on Fail" — blocked users don't crash the workflow |
| Rate limiting | Split In Batches with 1-second delay prevents Telegram rate limits |
| Idempotent | Re-running the workflow won't re-send to already-flagged users |
| Opt-out respected | Add a consent check: `if (row.consent === 'FALSE') continue;` in filter |

---

*End of Nudge Automations Build Document — ready to implement in n8n.*
