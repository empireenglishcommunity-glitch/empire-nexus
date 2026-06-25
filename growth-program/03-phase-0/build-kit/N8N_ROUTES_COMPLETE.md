# Empire English — Phase 0: Complete Route Implementation (n8n)

**Build Document v1.0** · **Date:** June 25, 2026
**Status:** READY TO IMPLEMENT — copy into n8n node-by-node

> **What this is.** The exact n8n node configurations, Code Node JavaScript, and message content needed to complete the 4 remaining bot routes: **resource**, **how**, **call**, **community**. These routes currently exist as stubs in the "Empire Bot — Main" workflow on `bot.empireenglish.online`. This document provides everything needed to make them fully functional.

> **Prerequisites.** The main workflow already has: Telegram Trigger → Code Node (JS Router) → Switch node. The Switch routes `quiz`, `menu`, and `/start` already work. The 4 routes below need their branches completed.

> **Pattern (mandatory — from N8N_WORKFLOW_PATTERNS.md):**
> - Switch routes to a **Code Node** that builds the response
> - Code Node outputs to an **HTTP Request node** (not Telegram node) for inline keyboards
> - After any Google Sheets node, reference data with `$('NodeName').first().json.field`
> - Always set "Always Output Data = ON" for Sheets nodes

---

## Route 1: `resource` — Free Resource Delivery

### Trigger
User taps `🎁 هديتي المجانية` button → callback_data = `resource`

### Flow
```
Switch (resource) → Code: Build Resource Message → HTTP Request: Send Message
                                                  ↓
                                    Google Sheets: Log RESOURCE_CLAIMED event
```

### Code Node: "Build Resource Message"

```javascript
// Route: resource — deliver the "3 American Sounds" quick-win
const chatId = $('Code Router').first().json.chat_id;
const firstName = $('Code Router').first().json.first_name || '';

// Config — update these when assets are ready
const RESOURCE_LINK = 'https://empireenglish.online/3sounds'; // placeholder until PDF uploaded
const BOT_TOKEN = $env.BOT_TOKEN; // set in n8n credentials/environment

const text = `هديتك جاهزة يا ${firstName}! 🎁

**3 أصوات تخليك تنطق أمريكي أكثر** — دليل قصير + 3 مقاطع صوتية تتمرّن معها.

حمّلها من هنا 👇
${RESOURCE_LINK}

جرّب صوت واحد اليوم فقط — النتيجة تفاجئك 🔥`;

const keyboard = {
  inline_keyboard: [
    [
      { text: '📚 كيف يعمل Empire', callback_data: 'how' },
      { text: '📅 احجز مكالمة', callback_data: 'call' }
    ],
    [
      { text: '↩️ القائمة', callback_data: 'menu' }
    ]
  ]
};

return [{
  json: {
    chat_id: chatId,
    text: text,
    parse_mode: 'Markdown',
    reply_markup: JSON.stringify(keyboard),
    _bot_token: BOT_TOKEN,
    _event_type: 'RESOURCE_CLAIMED',
    _telegram_id: chatId,
    _first_name: firstName
  }
}];
```

### HTTP Request Node: "Send Resource Message"

| Field | Value |
|-------|-------|
| Method | POST |
| URL | `https://api.telegram.org/bot{{ $json._bot_token }}/sendMessage` |
| Body Type | JSON |
| Body | `{ "chat_id": {{ $json.chat_id }}, "text": "{{ $json.text }}", "parse_mode": "{{ $json.parse_mode }}", "reply_markup": {{ $json.reply_markup }} }` |

> **Alternative (simpler):** Use "Fields Below" send mode with the fields mapped individually.

### Google Sheets Node: "Log Resource Event"

| Field | Value |
|-------|-------|
| Operation | Append Row |
| Sheet | `Events` |
| Columns | `event_id`: `={{ $now.toISO() }}-resource-{{ $json._telegram_id }}` · `telegram_id`: `={{ $json._telegram_id }}` · `event_type`: `RESOURCE_CLAIMED` · `timestamp`: `={{ $now.toISO() }}` · `meta`: `{}` |

---

## Route 2: `how` — How Empire Works + Pricing

### Trigger
User taps `📚 كيف يعمل Empire + الأسعار` button → callback_data = `how`

### Flow
```
Switch (how) → Code: Build How Message → HTTP Request: Send Message
                                        ↓
                          Google Sheets: Log OFFER_OPENED event
```

### Code Node: "Build How Message"

```javascript
// Route: how — explain the system + value ladder (no public prices day one)
const chatId = $('Code Router').first().json.chat_id;
const BOT_TOKEN = $env.BOT_TOKEN;

const text = `في Empire، ما نبيعك "كورس" — نعطيك **نظام تعلّم كامل** يمشي معك كل يوم 👇

• نطق أمريكي من اليوم الأول
• مهام كلام يومية (مو بس نظري — تتكلم فعلاً)
• مجتمع يدعمك + متابعة لتقدّمك
• مستويات واضحة: ما ترتقي إلا لما تتقن

━━━━━━━━━━━━━━━━━━

عندنا مسار واضح يبدأ من المجاني:

🆓 **Recruit (مجاني):** تذوّق المستوى صفر + المجتمع + كلمة اليوم
⭐ **Core (الأساس):** النظام اليومي الكامل + المجتمع + المتابعة
👑 **Citizen:** كل ما سبق + مدرّب ذكاء اصطناعي + أولوية في التصحيح
🏛️ **Founding Citizen (مقاعد محدودة):** عضوية دائمة + لقب مؤسس

الأسعار نرتّبها لك حسب هدفك في مكالمة قصيرة أو رسالة خاصة — عشان تختار الأنسب لك فعلاً، مو الأغلى.

━━━━━━━━━━━━━━━━━━

أنصحك تبدأ باختبار المستوى أو تحجز مكالمة قصيرة 👇`;

const keyboard = {
  inline_keyboard: [
    [
      { text: '🎯 حدّد مستواي', callback_data: 'quiz' },
      { text: '📅 احجز مكالمة مجانية', callback_data: 'call' }
    ],
    [
      { text: '🎁 هديتي المجانية', callback_data: 'resource' },
      { text: '↩️ القائمة', callback_data: 'menu' }
    ]
  ]
};

return [{
  json: {
    chat_id: chatId,
    text: text,
    parse_mode: 'Markdown',
    reply_markup: JSON.stringify(keyboard),
    _bot_token: BOT_TOKEN,
    _event_type: 'OFFER_OPENED',
    _telegram_id: chatId
  }
}];
```

### HTTP Request Node: "Send How Message"

Same pattern as Route 1 HTTP Request node.

### Google Sheets Node: "Log Offer Event"

| Field | Value |
|-------|-------|
| Operation | Append Row |
| Sheet | `Events` |
| Columns | `event_id`: `={{ $now.toISO() }}-offer-{{ $json._telegram_id }}` · `telegram_id`: `={{ $json._telegram_id }}` · `event_type`: `OFFER_OPENED` · `timestamp`: `={{ $now.toISO() }}` · `meta`: `{}` |

---

## Route 3: `call` — Book a Free Call

### Trigger
User taps `📅 احجز مكالمة مجانية` button → callback_data = `call`

### Flow
```
Switch (call) → Code: Build Call Message → HTTP Request: Send Message
```

> **Note:** The BOOKED event is logged later when the Cal.com webhook fires (a separate workflow — A5 in the spec). This route just shows the "what you'll get" message and the Cal.com link.

### Code Node: "Build Call Message"

```javascript
// Route: call — reassure + Cal.com booking link
const chatId = $('Code Router').first().json.chat_id;
const telegramId = $('Code Router').first().json.telegram_id || chatId;
const BOT_TOKEN = $env.BOT_TOKEN;

// Config — set your Cal.com URL in environment or here
const CALL_URL = 'https://cal.com/macalempire/empire-english?src=bot&tid=' + telegramId;

const text = `مكالمة قصيرة (15–20 دقيقة)، بدون ضغط بيع 🙂

في المكالمة:
• نحدّد مستواك وهدفك بدقة
• نرسم لك خطة واضحة للأسابيع القادمة
• تسأل أي شي وتشوف إذا Empire يناسبك

اختر وقت يناسبك 👇`;

const keyboard = {
  inline_keyboard: [
    [
      { text: '📅 احجز الآن', url: CALL_URL }
    ],
    [
      { text: '↩️ القائمة', callback_data: 'menu' }
    ]
  ]
};

return [{
  json: {
    chat_id: chatId,
    text: text,
    reply_markup: JSON.stringify(keyboard),
    _bot_token: BOT_TOKEN
  }
}];
```

### HTTP Request Node: "Send Call Message"

Same pattern as Route 1. Note: no `parse_mode` needed here (no Markdown in this message).

---

## Route 4: `community` — Join the Community

### Trigger
User taps `💬 انضم للمجتمع` button → callback_data = `community`

### Flow
```
Switch (community) → Code: Build Community Message → HTTP Request: Send Message
                                                    ↓
                                      Google Sheets: Log COMMUNITY_CLICK event
```

### Code Node: "Build Community Message"

```javascript
// Route: community — deliver invite links
const chatId = $('Code Router').first().json.chat_id;
const BOT_TOKEN = $env.BOT_TOKEN;

// Config — update when real links are ready
const DISCORD_INVITE = 'https://discord.gg/YOUR_INVITE_HERE'; // replace with real invite
const GROUP_INVITE = 'https://t.me/YOUR_GROUP_HERE'; // replace with real discussion group link

const text = `أهلاً فيك في عائلة Empire 🏛

• مجتمع Discord (تمارين، صوتيات، فعاليات):
• مجموعة النقاش على تيليجرام (أسئلة + كلمة اليوم):

ادخل، عرّف عن نفسك، وابدأ معنا 💪`;

const keyboard = {
  inline_keyboard: [
    [
      { text: '🎮 Discord', url: DISCORD_INVITE },
      { text: '💬 مجموعة تيليجرام', url: GROUP_INVITE }
    ],
    [
      { text: '↩️ القائمة', callback_data: 'menu' }
    ]
  ]
};

return [{
  json: {
    chat_id: chatId,
    text: text,
    reply_markup: JSON.stringify(keyboard),
    _bot_token: BOT_TOKEN,
    _event_type: 'COMMUNITY_CLICK',
    _telegram_id: chatId
  }
}];
```

### HTTP Request Node: "Send Community Message"

Same pattern as Route 1.

### Google Sheets Node: "Log Community Event"

| Field | Value |
|-------|-------|
| Operation | Append Row |
| Sheet | `Events` |
| Columns | `event_id`: `={{ $now.toISO() }}-community-{{ $json._telegram_id }}` · `telegram_id`: `={{ $json._telegram_id }}` · `event_type`: `COMMUNITY_CLICK` · `timestamp`: `={{ $now.toISO() }}` · `meta`: `{}` |

---

## Implementation Checklist

| # | Step | Time | Done |
|---|------|:----:|:----:|
| 1 | Open `bot.empireenglish.online` → "Empire Bot — Main" workflow | — | ☐ |
| 2 | In the Switch node, verify routes `resource`, `how`, `call`, `community` exist | 5 min | ☐ |
| 3 | Add Code Node for Route 1 (resource) → connect from Switch output | 10 min | ☐ |
| 4 | Add HTTP Request node after Route 1 Code Node | 5 min | ☐ |
| 5 | Add Google Sheets "Append Row" for RESOURCE_CLAIMED | 5 min | ☐ |
| 6 | Test Route 1: tap 🎁 in bot → message delivered + event logged | 5 min | ☐ |
| 7 | Repeat steps 3-6 for Route 2 (how) | 20 min | ☐ |
| 8 | Repeat steps 3-6 for Route 3 (call) — no Sheets log needed | 15 min | ☐ |
| 9 | Repeat steps 3-6 for Route 4 (community) | 20 min | ☐ |
| 10 | End-to-end test: new user → /start → tap each of 5 buttons → all respond | 10 min | ☐ |
| 11 | Verify Events tab has new rows for resource/offer/community | 5 min | ☐ |
| 12 | Update Config tab with real CALL_URL, DISCORD_INVITE, GROUP_INVITE | 5 min | ☐ |

**Total estimated time: ~2 hours of focused n8n work.**

---

## Config Values to Set (in Google Sheets `Config` tab)

| Key | Value | Status |
|-----|-------|:------:|
| `BOT_TOKEN` | (already set in n8n credentials) | ✅ |
| `CALL_URL` | `https://cal.com/macalempire/empire-english` | Set when Cal.com ready |
| `DISCORD_INVITE` | Discord invite link for the community | Set when server created |
| `GROUP_INVITE` | Telegram discussion group link | Set when group created |
| `RESOURCE_LINK` | URL to "3 American Sounds" PDF | Set when PDF uploaded |

---

## Code Router Update (if needed)

The existing Code Router should already extract `callback_data` into a flat `_route` field. Verify it handles these 4 values. If not, the router should include:

```javascript
// Inside the Code Router node — ensure these routes are extracted
const update = $input.first().json;
let route = '';
let chat_id = '';
let first_name = '';
let telegram_id = '';

if (update.callback_query) {
  route = update.callback_query.data || '';
  chat_id = update.callback_query.message.chat.id;
  first_name = update.callback_query.from.first_name || '';
  telegram_id = update.callback_query.from.id;
} else if (update.message) {
  const text = (update.message.text || '').trim();
  if (text === '/start') route = 'start';
  else if (text === '/menu') route = 'menu';
  else route = 'unknown';
  chat_id = update.message.chat.id;
  first_name = update.message.from.first_name || '';
  telegram_id = update.message.from.id;
}

return [{
  json: {
    _route: route,
    chat_id: chat_id,
    first_name: first_name,
    telegram_id: telegram_id
  }
}];
```

The Switch node then matches `$json._route` against: `start`, `menu`, `quiz`, `resource`, `how`, `call`, `community`.

---

## Acceptance Tests (from Phase 0 Spec §13)

| Test | Pass Condition |
|------|---------------|
| T1 | New user taps bot → welcome + can reach ALL 5 menu items |
| T6 | User taps 🎁 → resource delivered (link/file) |
| T7-resource | Events tab has RESOURCE_CLAIMED row |
| T7-offer | Events tab has OFFER_OPENED row |
| T7-community | Events tab has COMMUNITY_CLICK row |
| No dead ends | Every route ends with buttons (menu/next action) — never a blank response |

---

*End of Route Implementation Document — ready to build in n8n.*
