# Empire Bot v2 — All Code Node Contents

> **Purpose:** Each section below is the complete JavaScript for one Code Node in the workflow.
> Copy-paste into the corresponding node after importing the base JSON.
> 
> **Reference pattern:** All Code Nodes reference `$('Code Router').first().json.*` for user data.
> The Switch node routes to the correct branch. Each branch is:
> Code Node → HTTP Request (sendMessage) → Google Sheets (log event)

---

## 1. START / MENU — Welcome + 5-Button Menu + CRM Upsert

**Node name:** `Build Welcome`
**Connected from:** Switch → Start output AND Switch → Menu output

```javascript
// WELCOME — sends the 5-button main menu + upserts subscriber
const chatId = $('Code Router').first().json.chat_id;
const firstName = $('Code Router').first().json.first_name || '';
const telegramId = $('Code Router').first().json.telegram_id;
const username = $('Code Router').first().json.username || '';

const text = `أهلاً بك في Empire English 🏛\n\nأنا هنا عشان أساعدك تتكلم إنجليزي بثقة — خطوة بخطوة، بنظام واضح، مش مجرد دروس.\n\nاختر من القائمة 👇`;

const keyboard = JSON.stringify({
  inline_keyboard: [
    [{ text: '🎯 حدّد مستواي (دقيقتان)', callback_data: 'quiz' }],
    [{ text: '🎁 هديتي المجانية', callback_data: 'resource' }],
    [{ text: '📚 كيف يعمل Empire + الأسعار', callback_data: 'how' }],
    [{ text: '📅 احجز مكالمة مجانية', callback_data: 'call' }],
    [{ text: '💬 انضم للمجتمع', callback_data: 'community' }]
  ]
});

return [{
  json: {
    chat_id: chatId,
    text: text,
    reply_markup: keyboard,
    telegram_id: telegramId,
    first_name: firstName,
    username: username,
    event_type: 'JOINED_BOT'
  }
}];
```

**After this node:**
1. HTTP Request → `POST https://api.telegram.org/bot{TOKEN}/sendMessage` with `chat_id`, `text`, `reply_markup`
2. Google Sheets → Append/Update row in `Subscribers` tab (upsert on `telegram_id`)
3. Google Sheets → Append row in `Events` tab (`JOINED_BOT`)

---

## 2. QUIZ START — Send Question 1

**Node name:** `Build Quiz Q1`
**Connected from:** Switch → Quiz output

```javascript
// QUIZ START — send first question
const chatId = $('Code Router').first().json.chat_id;

const text = '❓ السؤال 1/7\n\nكيف تصف إنجليزيتك اليوم؟';

const keyboard = JSON.stringify({
  inline_keyboard: [
    [{ text: 'أعرف حروف/كلمات بسيطة فقط', callback_data: 'q1_0' }],
    [{ text: 'أكوّن جُمل بسيطة بصعوبة', callback_data: 'q1_1' }],
    [{ text: 'أتعامل مع محادثات يومية', callback_data: 'q1_2' }],
    [{ text: 'أتحدث بطلاقة عن معظم المواضيع', callback_data: 'q1_3' }]
  ]
});

return [{
  json: {
    chat_id: chatId,
    text: text,
    reply_markup: keyboard
  }
}];
```

---

## 3. QUIZ ANSWER HANDLER — Process answer + send next question OR score

**Node name:** `Quiz Answer Handler`
**Connected from:** Switch → QuizAnswer output

```javascript
// QUIZ ANSWER HANDLER
// Processes quiz callbacks (q1_0, q2_1, q3_3, etc.)
// Stores answers, sends next question, or scores at end
const chatId = $('Code Router').first().json.chat_id;
const firstName = $('Code Router').first().json.first_name || '';
const telegramId = $('Code Router').first().json.telegram_id;
const callback = $('Code Router').first().json.callback_data;

// Parse: q{number}_{points}
const match = callback.match(/^q(\d+)_(\d+)$/);
if (!match) {
  return [{ json: { chat_id: chatId, text: 'خطأ — أعد المحاولة', reply_markup: '{}', _action: 'send' } }];
}

const qNum = parseInt(match[1]);
const points = parseInt(match[2]);

// Questions data
const questions = [
  null, // index 0 unused
  null, // Q1 already sent
  {
    text: '❓ السؤال 2/7\n\nتقدر تعرّف عن نفسك بالإنجليزي 30 ثانية؟',
    options: [
      { text: 'لا، ليس بعد', data: 'q2_0' },
      { text: 'بصعوبة وبجُمل قصيرة', data: 'q2_1' },
      { text: 'نعم، بشكل مقبول', data: 'q2_2' },
      { text: 'نعم، بسهولة وثقة', data: 'q2_3' }
    ]
  },
  {
    text: '❓ السؤال 3/7\n\nأي جملة صحيحة؟',
    options: [
      { text: 'She go to work every day.', data: 'q3_0' },
      { text: 'She goes to work every day. ✅', data: 'q3_3' },
      { text: 'She going to work every day.', data: 'q3_1' },
      { text: 'She is go to work every day.', data: 'q3_0' }
    ]
  },
  {
    text: '❓ السؤال 4/7\n\nماذا تعني كلمة "improve"؟',
    options: [
      { text: 'يتحسّن / to get better ✅', data: 'q4_3' },
      { text: 'يتوقف / to stop', data: 'q4_0' },
      { text: 'يسافر / to travel', data: 'q4_0' },
      { text: 'ينسى / to forget', data: 'q4_0' }
    ]
  },
  {
    text: '❓ السؤال 5/7\n\nتقدر تتابع فيديو/بودكاست إنجليزي بسرعة طبيعية؟',
    options: [
      { text: 'لا أفهم تقريبًا شيء', data: 'q5_0' },
      { text: 'أفهم بعض الكلمات', data: 'q5_1' },
      { text: 'أفهم معظم الفكرة', data: 'q5_2' },
      { text: 'أفهم كل شيء تقريبًا', data: 'q5_3' }
    ]
  },
  {
    text: '❓ السؤال 6/7\n\nما هو هدفك الأول من تعلّم الإنجليزي؟',
    options: [
      { text: '🗣️ أتكلم بثقة', data: 'q6_confidence' },
      { text: '💼 مقابلة عمل', data: 'q6_interview' },
      { text: '✈️ السفر', data: 'q6_travel' },
      { text: '📝 اختبار (IELTS/TOEFL)', data: 'q6_exam' },
      { text: '🇺🇸 تحسين اللهجة الأمريكية', data: 'q6_accent' }
    ]
  },
  {
    text: '❓ السؤال 7/7\n\nكم وقت تقدر تعطي يوميًا؟',
    options: [
      { text: '⏱️ حوالي 15 دقيقة', data: 'q7_Core' },
      { text: '⏱️ حوالي 30 دقيقة', data: 'q7_Core' },
      { text: '⏱️ 60 دقيقة أو أكثر', data: 'q7_Intensive' }
    ]
  }
];

const nextQ = qNum + 1;

// If there's a next question (Q2-Q7), send it
if (nextQ <= 7 && questions[nextQ]) {
  const q = questions[nextQ];
  const keyboard = JSON.stringify({
    inline_keyboard: q.options.map(opt => [{ text: opt.text, callback_data: opt.data }])
  });
  return [{
    json: {
      chat_id: chatId,
      text: q.text,
      reply_markup: keyboard,
      _action: 'send',
      _quiz_data: callback,
      _telegram_id: telegramId
    }
  }];
}

// Q7 answered — need to score. Pass the answer forward for the scoring node.
// The scoring node will read ALL quiz data from the Sheets subscriber row.
return [{
  json: {
    chat_id: chatId,
    text: '⏳ ممتاز! حسبت نتيجتك… لحظة',
    reply_markup: '{}',
    _action: 'score',
    _quiz_data: callback,
    _telegram_id: telegramId,
    _first_name: firstName
  }
}];
```

> **IMPORTANT NOTE about quiz state:** The quiz state (accumulated answers) must be stored somewhere between questions. Two approaches:
> 
> **Approach A (Recommended — Sheets-based):** After each answer, update the subscriber's row with the latest answer (`q1_answer`, `q2_answer`, etc.). When Q7 is answered, read the row to get all answers and compute the score. This is what the existing workflow did.
> 
> **Approach B (Stateless — encode in callback):** Encode all previous answers in each callback (e.g., `q3_1_prev_0_1` carries Q1=0, Q2=1 history). Gets complex but avoids extra Sheets calls.
> 
> The existing workflow used **Approach A**. I recommend keeping that pattern:
> - After each quiz answer → Google Sheets "Update Row" (set `q{N}_answer = points`)
> - After Q7 → Google Sheets "Get Row" (read all q1-q5 answers) → Code Node scores → send plan

---

## 4. RESOURCE — Deliver Lead Magnet

**Node name:** `Build Resource Message`
**Connected from:** Switch → Resource output

```javascript
const chatId = $('Code Router').first().json.chat_id;
const firstName = $('Code Router').first().json.first_name || '';
const telegramId = $('Code Router').first().json.telegram_id;

// UPDATE when PDF is uploaded:
const RESOURCE_LINK = 'https://empireenglish.online/3sounds';

const text = `هديتك جاهزة يا ${firstName}! 🎁\n\n3 أصوات تخليك تنطق أمريكي أكثر — دليل قصير + 3 مقاطع صوتية تتمرّن معها.\n\nحمّلها من هنا 👇\n${RESOURCE_LINK}\n\nجرّب صوت واحد اليوم فقط — النتيجة تفاجئك 🔥`;

const keyboard = JSON.stringify({
  inline_keyboard: [
    [
      { text: '📚 كيف يعمل Empire', callback_data: 'how' },
      { text: '📅 احجز مكالمة', callback_data: 'call' }
    ],
    [{ text: '↩️ القائمة', callback_data: 'menu' }]
  ]
});

return [{ json: { chat_id: chatId, text, reply_markup: keyboard, telegram_id: telegramId, event_type: 'RESOURCE_CLAIMED' } }];
```

---

## 5. HOW — System Explainer + Value Ladder

**Node name:** `Build How Message`
**Connected from:** Switch → How output

```javascript
const chatId = $('Code Router').first().json.chat_id;
const telegramId = $('Code Router').first().json.telegram_id;

const text = `في Empire، ما نبيعك "كورس" — نعطيك نظام تعلّم كامل يمشي معك كل يوم 👇\n\n• نطق أمريكي من اليوم الأول\n• مهام كلام يومية (مو بس نظري — تتكلم فعلاً)\n• مجتمع يدعمك + متابعة لتقدّمك\n• مستويات واضحة: ما ترتقي إلا لما تتقن\n\n━━━━━━━━━━━━━━━━━━\n\nعندنا مسار واضح يبدأ من المجاني:\n\n🆓 Recruit (مجاني): تذوّق المستوى صفر + المجتمع + كلمة اليوم\n⭐ Core (الأساس): النظام اليومي الكامل + المجتمع + المتابعة\n👑 Citizen: كل ما سبق + مدرّب ذكاء اصطناعي + أولوية في التصحيح\n🏛️ Founding Citizen (مقاعد محدودة): عضوية دائمة + لقب مؤسس\n\nالأسعار نرتّبها لك حسب هدفك في مكالمة قصيرة أو رسالة خاصة — عشان تختار الأنسب لك فعلاً، مو الأغلى.\n\n━━━━━━━━━━━━━━━━━━\n\nأنصحك تبدأ باختبار المستوى أو تحجز مكالمة قصيرة 👇`;

const keyboard = JSON.stringify({
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
});

return [{ json: { chat_id: chatId, text, reply_markup: keyboard, telegram_id: telegramId, event_type: 'OFFER_OPENED' } }];
```

---

## 6. CALL — Booking with Reassurance

**Node name:** `Build Call Message`
**Connected from:** Switch → Call output

```javascript
const chatId = $('Code Router').first().json.chat_id;
const telegramId = $('Code Router').first().json.telegram_id;

// UPDATE if your Cal.com slug is different:
const CALL_URL = 'https://cal.com/macalempire/empire-english?src=bot&tid=' + telegramId;

const text = `مكالمة قصيرة (15–20 دقيقة)، بدون ضغط بيع 🙂\n\nفي المكالمة:\n• نحدّد مستواك وهدفك بدقة\n• نرسم لك خطة واضحة للأسابيع القادمة\n• تسأل أي شي وتشوف إذا Empire يناسبك\n\nاختر وقت يناسبك 👇`;

const keyboard = JSON.stringify({
  inline_keyboard: [
    [{ text: '📅 احجز الآن', url: CALL_URL }],
    [{ text: '↩️ القائمة', callback_data: 'menu' }]
  ]
});

return [{ json: { chat_id: chatId, text, reply_markup: keyboard, telegram_id: telegramId } }];
```

---

## 7. COMMUNITY — Invite Links

**Node name:** `Build Community Message`
**Connected from:** Switch → Community output

```javascript
const chatId = $('Code Router').first().json.chat_id;
const telegramId = $('Code Router').first().json.telegram_id;

// UPDATE with real links:
const DISCORD_INVITE = 'https://discord.gg/YOUR_INVITE_HERE';
const GROUP_INVITE = 'https://t.me/YOUR_GROUP_HERE';

const text = `أهلاً فيك في عائلة Empire 🏛\n\n• مجتمع Discord (تمارين، صوتيات، فعاليات)\n• مجموعة النقاش على تيليجرام (أسئلة + كلمة اليوم)\n\nادخل، عرّف عن نفسك، وابدأ معنا 💪`;

const keyboard = JSON.stringify({
  inline_keyboard: [
    [
      { text: '🎮 Discord', url: DISCORD_INVITE },
      { text: '💬 مجموعة تيليجرام', url: GROUP_INVITE }
    ],
    [{ text: '↩️ القائمة', callback_data: 'menu' }]
  ]
});

return [{ json: { chat_id: chatId, text, reply_markup: keyboard, telegram_id: telegramId, event_type: 'COMMUNITY_CLICK' } }];
```

---

## 8. HTTP Request Template (same for ALL routes)

Every Code Node above connects to an HTTP Request node with this config:

| Field | Value |
|-------|-------|
| Method | POST |
| URL | `https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage` |
| Body Type | JSON |
| Body | See below |

**JSON Body (expression mode):**
```
{
  "chat_id": {{ $json.chat_id }},
  "text": {{ JSON.stringify($json.text) }},
  "reply_markup": {{ $json.reply_markup }}
}
```

> Replace `<YOUR_TOKEN>` with your actual bot token. Or use n8n expression: `{{ $env.BOT_TOKEN }}` if you set it as an environment variable.

---

## 9. Google Sheets Event Logging Template (for routes that log events)

After the HTTP Request, connect a Google Sheets node (Append Row) for: Start, Resource, How, Community.
(Call does NOT log here — it's logged when Cal.com webhook fires.)

| Field | Value |
|-------|-------|
| Operation | Append |
| Spreadsheet | Your Empire CRM sheet |
| Sheet | `Events` |
| Columns | |
| - `telegram_id` | `{{ $json.telegram_id }}` |
| - `event_type` | `{{ $json.event_type }}` |
| - `timestamp` | `{{ $now.toISO() }}` |
| - `meta` | `{}` |

---

## 10. Subscriber Upsert (for Start route only)

The Start/Menu route also needs a Google Sheets node to upsert the subscriber:

| Field | Value |
|-------|-------|
| Operation | Append or Update |
| Spreadsheet | Your Empire CRM sheet |
| Sheet | `Subscribers` |
| Match column | `telegram_id` |
| Columns | |
| - `telegram_id` | `{{ $json.telegram_id }}` |
| - `first_name` | `{{ $json.first_name }}` |
| - `username` | `{{ $json.username }}` |
| - `status` | `New` |
| - `first_seen_at` | `{{ $now.toISO() }}` |
| - `last_active_at` | `{{ $now.toISO() }}` |

---

## Summary: Node Chain Per Route

| Route | Chain |
|-------|-------|
| **Start/Menu** | Code (Welcome) → HTTP Request → Sheets (Upsert Subscriber) → Sheets (Log JOINED_BOT) |
| **Quiz** | Code (Q1) → HTTP Request |
| **QuizAnswer** | Code (Handler) → HTTP Request → Sheets (Update answer) → [IF last Q → Score + Plan] |
| **Resource** | Code (Resource) → HTTP Request → Sheets (Log RESOURCE_CLAIMED) |
| **How** | Code (How) → HTTP Request → Sheets (Log OFFER_OPENED) |
| **Call** | Code (Call) → HTTP Request |
| **Community** | Code (Community) → HTTP Request → Sheets (Log COMMUNITY_CLICK) |
