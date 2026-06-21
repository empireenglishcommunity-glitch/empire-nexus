# Quiz System — Technical Audit & Troubleshooting Reference

**Document Type:** Technical Audit, Root Cause Analysis & Permanent Reference  
**Date:** June 19, 2026  
**Status:** VERIFIED & WORKING  
**Scope:** Complete Quiz Flow (Q1–Q7 + Scoring + Plan Delivery)

---

## 1. Executive Summary

The quiz system was rebuilt in n8n to handle the 7-question placement quiz for Empire English Community. The implementation faced **6 distinct technical issues** during development, each requiring diagnosis and resolution. This document captures every problem, its root cause, the investigation process, and the confirmed fix — serving as a permanent reference for future debugging.

**Final Status:** Quiz system is fully operational. All 7 questions flow correctly, scoring works, plan delivery works, and results are saved to Google Sheets.

---

## 2. Final Working Architecture

```
[Switch Node - Quiz Answer Path]
     │
     ▼
[Code in JavaScript1]              ← Parses callback_data (q1_0, q2_3, etc.)
     │                                Extracts: chatId, userId, questionNum, answerValue
     ▼
[Code - Build Sheet Update]        ← Adds: answerField (q1/q2/...), isLastQuestion, nextQuestion
     │
     ▼
[Update Row in Sheet 1]            ← Saves answer to Subscribers tab
     │                                (has "Always Output Data" enabled)
     ▼
[IF - Is Last Question?]           ← Condition: quiz_state (Number) equals 8
     │
     ├── FALSE ──→ [Code - Next Question] ──→ [HTTP Request - Send Question]
     │
     └── TRUE  ──→ [Get Subscriber Answers] ──→ [Code - Score & Level] ──→ [HTTP Request1 - Send Plan] ──→ [Save Quiz Results]
```

---

## 3. Node-by-Node Specification

### 3.1 Code in JavaScript1 (Quiz Answer Parser)

**Purpose:** Parse the raw Telegram callback_query into clean structured data.

**Input:** Raw Telegram trigger data with `_route` field (e.g., `q1_1`, `q3_3`, `q6_confidence`)

**Code:**
```javascript
const input = $input.first().json;
const cbData = input._route;

// Parse question number and answer value
const parts = cbData.split('_');
const questionNum = parseInt(parts[0].replace('q', ''));
const answerValue = parts.slice(1).join('_');

const chatId = input.callback_query?.message?.chat?.id || input.message?.chat?.id;
const userId = input.callback_query?.from?.id || input.message?.from?.id;

return [{
  json: {
    chatId,
    userId,
    questionNum,
    answerValue,
    updateId: input.update_id
  }
}];
```

**Output:**
```json
{
  "chatId": 8924041557,
  "userId": 8924041557,
  "questionNum": 1,
  "answerValue": "1",
  "updateId": 4840008
}
```

---

### 3.2 Code - Build Sheet Update

**Purpose:** Prepare metadata for the Google Sheets update and downstream routing.

**Code:**
```javascript
const item = $input.first().json;
const qNum = item.questionNum;
const answer = item.answerValue;
const chatId = item.chatId;
const userId = item.userId;

const output = {
  chatId,
  userId,
  questionNum: qNum,
  answerValue: answer,
  answerField: `q${qNum}`,
  isLastQuestion: qNum === 7,
  nextQuestion: qNum + 1
};

return [{ json: output }];
```

---

### 3.3 Update Row in Sheet 1 (Google Sheets)

**Operation:** Update Row  
**Sheet:** Subscribers  
**Matching Column:** `telegram_id`  
**Lookup Value:** `{{ $json.userId }}`

**Values:**

| Field | Expression |
|-------|-----------|
| q1 | `{{ $json.questionNum === 1 ? $json.answerValue : '' }}` |
| q2 | `{{ $json.questionNum === 2 ? $json.answerValue : '' }}` |
| q3 | `{{ $json.questionNum === 3 ? $json.answerValue : '' }}` |
| q4 | `{{ $json.questionNum === 4 ? $json.answerValue : '' }}` |
| q5 | `{{ $json.questionNum === 5 ? $json.answerValue : '' }}` |
| q6 | `{{ $json.questionNum === 6 ? $json.answerValue : '' }}` |
| q7 | `{{ $json.questionNum === 7 ? $json.answerValue : '' }}` |
| quiz_state | `{{ $json.nextQuestion }}` |
| last_active_at | `{{ $now.toISO() }}` |

**Critical Setting:** `Always Output Data` = **ON**

---

### 3.4 IF Node — Is Last Question?

**Condition Type:** Number  
**Value 1:** `{{ $json.quiz_state }}`  
**Operation:** equals  
**Value 2:** `8`

---

### 3.5 Code - Next Question (FALSE path)

**Purpose:** Build the next question message with inline keyboard buttons.

**Key Design:** Reads `chatId` from `row.telegram_id` and `nextQ` from `row.quiz_state` (because the input comes from the Google Sheets node output).

**Code:**
```javascript
const row = $input.first().json;
const chatId = row.telegram_id;
const nextQ = parseInt(row.quiz_state);

const questions = {
  2: {
    text: "تقدر تعرّف عن نفسك بالإنجليزي 30 ثانية؟",
    buttons: [
      [{ text: "لا، ليس بعد", callback_data: "q2_0" }],
      [{ text: "بصعوبة وبجُمل قصيرة", callback_data: "q2_1" }],
      [{ text: "نعم، بشكل مقبول", callback_data: "q2_2" }],
      [{ text: "نعم، بسهولة وثقة", callback_data: "q2_3" }]
    ]
  },
  3: {
    text: "Which sentence is correct?",
    buttons: [
      [{ text: "She go to work every day.", callback_data: "q3_0" }],
      [{ text: "She goes to work every day. ✅", callback_data: "q3_3" }],
      [{ text: "She going to work every day.", callback_data: "q3_1" }],
      [{ text: "She is go to work every day.", callback_data: "q3_0" }]
    ]
  },
  4: {
    text: "ماذا تعني كلمة \"improve\"؟",
    buttons: [
      [{ text: "يتحسّن / to get better ✅", callback_data: "q4_3" }],
      [{ text: "يتوقف / to stop", callback_data: "q4_0" }],
      [{ text: "يسافر / to travel", callback_data: "q4_0" }],
      [{ text: "ينسى / to forget", callback_data: "q4_0" }]
    ]
  },
  5: {
    text: "تقدر تتابع فيديو/بودكاست إنجليزي بسرعة طبيعية؟",
    buttons: [
      [{ text: "لا أفهم تقريبًا شيء", callback_data: "q5_0" }],
      [{ text: "أفهم بعض الكلمات", callback_data: "q5_1" }],
      [{ text: "أفهم معظم الفكرة", callback_data: "q5_2" }],
      [{ text: "أفهم كل شيء تقريبًا", callback_data: "q5_3" }]
    ]
  },
  6: {
    text: "إيش هدفك الأساسي من تعلّم الإنجليزي؟",
    buttons: [
      [{ text: "أتكلم بثقة", callback_data: "q6_confidence" }],
      [{ text: "مقابلة عمل", callback_data: "q6_interview" }],
      [{ text: "السفر", callback_data: "q6_travel" }],
      [{ text: "اختبار", callback_data: "q6_exam" }],
      [{ text: "تحسين اللهجة", callback_data: "q6_accent" }]
    ]
  },
  7: {
    text: "كم وقت تقدر تخصص يوميًا؟",
    buttons: [
      [{ text: "~15 دقيقة", callback_data: "q7_Core" }],
      [{ text: "~30 دقيقة", callback_data: "q7_Core" }],
      [{ text: "60+ دقيقة", callback_data: "q7_Intensive" }]
    ]
  }
};

const q = questions[nextQ];

if (!q) {
  return [{ json: { chatId, text: "خطأ: سؤال غير موجود", replyMarkup: "{}" } }];
}

return [{
  json: {
    chatId,
    text: q.text,
    replyMarkup: JSON.stringify({
      inline_keyboard: q.buttons
    })
  }
}];
```

---

### 3.6 HTTP Request — Send Next Question (FALSE path)

**Method:** POST  
**URL:** `https://api.telegram.org/bot<TOKEN>/sendMessage`  
**Body Content Type:** JSON  
**Specify Body:** Using Fields Below

| Parameter | Value |
|-----------|-------|
| chat_id | `{{ $json.chatId }}` |
| text | `{{ $json.text }}` |
| reply_markup | `{{ $json.replyMarkup }}` |

---

### 3.7 Get Subscriber Answers (TRUE path)

**Type:** Google Sheets — Read Rows  
**Sheet:** Subscribers  
**Filter:** `telegram_id` equals `{{ $json.telegram_id }}`

---

### 3.8 Code - Score & Level (TRUE path)

**Purpose:** Calculate quiz score, determine level, generate plan message.

**Code:**
```javascript
const row = $input.first().json;
const chatId = row.telegram_id;
const firstName = row.first_name || '';

const q1 = parseInt(row.q1) || 0;
const q2 = parseInt(row.q2) || 0;
const q3 = parseInt(row.q3) || 0;
const q4 = parseInt(row.q4) || 0;
const q5 = parseInt(row.q5) || 0;
const q6 = row.q6 || 'confidence';
const q7 = row.q7 || 'Core';

const score = q1 + q2 + q3 + q4 + q5;

let level, levelName;
if (score <= 3) {
  level = 'L0';
  levelName = 'المستوى صفر — مبتدئ تمامًا 🌱';
} else if (score <= 7) {
  level = 'L1';
  levelName = 'المستوى الأول — إنجليزية النجاة 💪';
} else if (score <= 11) {
  level = 'L2';
  levelName = 'المستوى الثاني — التواصل 🚀';
} else {
  level = 'L3';
  levelName = 'المستوى الثالث — الطلاقة واللهجة 🏆';
}

const othersAvg = (q1 + q3 + q4 + q5) / 4;
const reviewFlag = Math.abs(q2 - othersAvg) >= 2;

const goalMap = {
  confidence: 'تتكلم بثقة',
  interview: 'مقابلة عمل',
  travel: 'السفر',
  exam: 'اختبار',
  accent: 'تحسين اللهجة'
};
const goal = goalMap[q6] || q6;

const plans = {
  L0: `نتيجتك يا ${firstName}: ${levelName}\nهذا ممتاز — البداية الصحيحة أهم من البداية السريعة. نركّز أول شي على:\n• أصوات الإنجليزية الأساسية\n• أول 500 كلمة الأكثر استخدامًا\n• جُمل تعريف بسيطة عن نفسك\nوبما إن هدفك ${goal}، رح نوجّه التمارين نحوه من البداية.\nالمسار المناسب لك: ${q7}.`,
  L1: `نتيجتك يا ${firstName}: ${levelName}\nعندك أساس — هدفنا الحين تتكلم في المواقف اليومية بدون توتر. نركّز على:\n• محادثات يومية (طلبات، اتجاهات، تعارف)\n• التشديد وإيقاع الجملة الأمريكي\n• توسيع المفردات إلى ~1500 كلمة\nوبما إن هدفك ${goal}، رح نختار المواقف الأقرب له.\nالمسار المناسب لك: ${q7}.`,
  L2: `نتيجتك يا ${firstName}: ${levelName}\nأنت تتواصل — هدفنا الحين السرعة، الطلاقة، وفهم الكلام الطبيعي. نركّز على:\n• مواضيع أعقد (آراء، شرح، حكايات)\n• الربط والاختزال في النطق\n• فهم السرعة الطبيعية + التعابير الشائعة\nوبما إن هدفك ${goal}، رح نكثّف التمارين المرتبطة فيه.\nالمسار المناسب لك: ${q7}.`,
  L3: `نتيجتك يا ${firstName}: ${levelName}\nمستوى متقدم! هدفنا الحين الصقل: طلاقة طبيعية ولهجة أوضح. نركّز على:\n• صقل دقيق للنطق (Flap T، الشوا، الربط)\n• مفردات وتعابير ومصطلحات أصلية\n• التعبير الحر والثقة في أي موضوع\nوبما إن هدفك ${goal}، رح نخصّص التمارين له.\nالمسار المناسب لك: ${q7}.`
};

return [{
  json: {
    chatId: String(chatId),
    userId: String(chatId),
    text: plans[level],
    level,
    score,
    goalTag: q6,
    timeTrack: q7,
    reviewFlag,
    firstName
  }
}];
```

---

### 3.9 HTTP Request1 — Send Plan (TRUE path)

**Method:** POST  
**URL:** `https://api.telegram.org/bot<TOKEN>/sendMessage`  
**Body Content Type:** JSON  
**Specify Body:** Using Fields Below

| Parameter | Value |
|-----------|-------|
| chat_id | `{{ $('Code - Score & Level').first().json.chatId }}` |
| text | `{{ $('Code - Score & Level').first().json.text }}` |
| reply_markup | `{"inline_keyboard":[[{"text":"🔙 القائمة الرئيسية","callback_data":"menu"}]]}` |

**Critical:** Uses `$('Code - Score & Level')` node reference because this node sits after "Save Quiz Results" which overwrites `$json`.

---

### 3.10 Save Quiz Results (Google Sheets)

**Operation:** Update Row  
**Sheet:** Subscribers  
**Matching Column:** `telegram_id`  
**Lookup Value:** `{{ $('Code - Score & Level').first().json.userId }}`

| Field | Value |
|-------|-------|
| level | `{{ $('Code - Score & Level').first().json.level }}` |
| level_score | `{{ $('Code - Score & Level').first().json.score }}` |
| goal_tag | `{{ $('Code - Score & Level').first().json.goalTag }}` |
| time_track | `{{ $('Code - Score & Level').first().json.timeTrack }}` |
| review_flag | `{{ $('Code - Score & Level').first().json.reviewFlag }}` |
| quiz_state | `done` |
| last_active_at | `{{ $now.toISO() }}` |

---

## 4. Problem Registry — Complete Root Cause Analysis

### PROBLEM 1: Quiz Answer Not Reaching Handler

| Field | Detail |
|-------|--------|
| **Symptom** | Pressing Q1 answer button → nothing happens |
| **Initial Assumption** | Data not reaching the trigger |
| **Investigation** | Checked Executions list → execution DID appear with "Success" status |
| **Root Cause** | Execution reached Switch and was routed to Quiz Answer path, but the chain ended at Code in JavaScript1 — no nodes were connected after it |
| **Fix** | Connected the full chain: Code → Build Sheet Update → Google Sheets → IF → Next Question / Score |
| **Lesson** | Always verify node connections by checking execution traces, not visual inspection |

---

### PROBLEM 2: Google Sheets "Update Row" Returns No Output

| Field | Detail |
|-------|--------|
| **Symptom** | Chain stops at "Update Row in Sheet 1" — IF node shows "no input items" |
| **Initial Assumption** | Connection is broken |
| **Investigation** | Clicked on Update Row node → OUTPUT shows "No output data" |
| **Root Cause** | Google Sheets "Update Row" returns nothing when it cannot find a matching row, OR when it updates successfully but the node doesn't pass data forward by default |
| **Fix** | Enable **"Always Output Data"** in the node's Settings (gear icon) |
| **Lesson** | **ALWAYS enable "Always Output Data" on Google Sheets Update/Append nodes** that have downstream nodes depending on them |

---

### PROBLEM 3: IF Node Type Mismatch

| Field | Detail |
|-------|--------|
| **Symptom** | IF node throws "Wrong type: '2' is a number but was expecting a string" |
| **Initial Assumption** | None — error was clear |
| **Root Cause** | The IF condition was set to String comparison, but `quiz_state` from Google Sheets is returned as a Number |
| **Fix** | Change the IF condition type from **String** to **Number** |
| **Lesson** | Google Sheets returns numeric cell values as numbers, not strings. Always use Number comparison type for numeric columns |

---

### PROBLEM 4: Telegram Inline Keyboard Parse Error

| Field | Detail |
|-------|--------|
| **Symptom** | "Bad request: can't parse inline keyboard button: Text buttons are unallowed in the inline keyboard" |
| **Initial Assumption** | JSON structure is malformed |
| **Investigation** | Tried multiple approaches: raw JSON in Reply Markup field, expression mode with JSON.parse, Additional Fields |
| **Root Cause** | n8n's built-in Telegram node has quirks with how it handles `reply_markup` when passed as a JSON string expression. The node's internal parsing conflicts with the Telegram API format |
| **Fix** | **Replace the Telegram Send Message node with an HTTP Request node** that calls the Telegram API directly |
| **Lesson** | **When n8n's Telegram node fails to handle inline keyboards via expressions, use HTTP Request + direct Telegram API call instead** |

---

### PROBLEM 5: HTTP Request JSON Body Parse Error

| Field | Detail |
|-------|--------|
| **Symptom** | "The value in the 'JSON Body' field is not valid JSON - Unexpected end of JSON input" |
| **Initial Assumption** | Expression syntax is wrong |
| **Root Cause** | Using `JSON.stringify(...)` inside the JSON body expression field doesn't work — n8n tries to parse the expression as static JSON before evaluating JavaScript |
| **Fix** | Use **"Specify Body: Using Fields Below"** instead of raw JSON body. Add individual parameters (chat_id, text, reply_markup) as separate fields |
| **Lesson** | **Never use JSON.stringify() in n8n's JSON body field. Always use "Using Fields Below" with individual parameter fields** |

---

### PROBLEM 6: "Message text is empty" — Data Lost After Google Sheets Node

| Field | Detail |
|-------|--------|
| **Symptom** | HTTP Request sends empty text to Telegram API → "Bad Request: message text is empty" |
| **Initial Assumption** | Expression is wrong |
| **Investigation** | Checked the input to HTTP Request node → `$json.chatId` = undefined, `$json.text` = undefined |
| **Root Cause** | **The HTTP Request node was placed AFTER a Google Sheets node.** After any Google Sheets operation, `$json` contains the sheet's row data (column values), NOT the data from earlier Code nodes. The `chatId` and `text` fields from "Code - Score & Level" were overwritten. |
| **Fix** | Use **explicit node references**: `$('Code - Score & Level').first().json.chatId` instead of `$json.chatId` |
| **Lesson** | **After ANY Google Sheets node, `$json` is GONE. Always use `$('Node Name').first().json.fieldName` to reach data from earlier nodes in the chain** |

---

## 5. Critical Rules (MUST follow for all future n8n development)

### Rule 1: Always Output Data
> Every Google Sheets node that has downstream nodes MUST have "Always Output Data" = ON in Settings.

### Rule 2: Data Disappears After Sheets
> After any Google Sheets node executes, `$json` becomes the sheet output. Use `$('Previous Node Name').first().json.field` to access earlier data.

### Rule 3: Use HTTP Request for Dynamic Keyboards
> When sending Telegram messages with dynamically-built inline keyboards (from expressions/code), use HTTP Request node → POST to `https://api.telegram.org/bot<TOKEN>/sendMessage` instead of the built-in Telegram node.

### Rule 4: Use "Fields Below" Not Raw JSON
> In HTTP Request nodes, always use "Specify Body: Using Fields Below" with individual parameters. Never use raw JSON with JavaScript expressions.

### Rule 5: Number Comparisons for Sheet Data
> Google Sheets returns numbers as numbers. All IF node conditions comparing sheet numeric columns must use Number type, not String type.

### Rule 6: Verify Connections via Execution Trace
> Never trust visual inspection of node connections. Always verify by running a test and checking the Execution view to see which nodes actually turned green.

### Rule 7: Check Row Existence
> "Update Row" returns nothing if no matching row is found. Ensure the target row EXISTS before expecting output from an Update operation.

---

## 6. Google Sheets Column Requirements (Subscribers Tab)

The following columns MUST exist in the Subscribers sheet for the quiz to work:

| Column | Type | Purpose |
|--------|------|---------|
| telegram_id | Number | Primary key / matching column |
| first_name | Text | Used in plan message personalization |
| q1 | Number | Q1 answer score (0-3) |
| q2 | Number | Q2 answer score (0-3) |
| q3 | Number | Q3 answer score (0-3) |
| q4 | Number | Q4 answer score (0-3) |
| q5 | Number | Q5 answer score (0-3) |
| q6 | Text | Goal tag (confidence/interview/travel/exam/accent) |
| q7 | Text | Time track (Core/Intensive) |
| quiz_state | Number/Text | Current question (2-7) or "done" |
| level | Text | Assigned level (L0/L1/L2/L3) |
| level_score | Number | Total score (0-15) |
| goal_tag | Text | Final goal tag |
| time_track | Text | Final time track |
| review_flag | Boolean | Edge rule flag |
| last_active_at | DateTime | ISO timestamp of last activity |

---

## 7. Scoring Logic Reference

| Score Range | Level | Level Name |
|-------------|-------|-----------|
| 0–3 | L0 | مبتدئ تمامًا (Absolute Beginner) |
| 4–7 | L1 | إنجليزية النجاة (Survival English) |
| 8–11 | L2 | التواصل (Communication) |
| 12–15 | L3 | الطلاقة واللهجة (Fluency & Accent) |

**Edge Rule:** If `|Q2 - average(Q1,Q3,Q4,Q5)| >= 2` → set `review_flag = true`

---

## 8. Testing Checklist

| # | Test | Expected Result | Status |
|---|------|-----------------|--------|
| 1 | Tap quiz button → Q1 appears | Q1 with 4 answer buttons | ✅ |
| 2 | Answer Q1 → Q2 appears | Q2 with 4 answer buttons | ✅ |
| 3 | Answer Q2 → Q3 appears | Q3 with 4 answer buttons | ✅ |
| 4 | Answer Q3 → Q4 appears | Q4 with 4 answer buttons | ✅ |
| 5 | Answer Q4 → Q5 appears | Q5 with 4 answer buttons | ✅ |
| 6 | Answer Q5 → Q6 appears | Q6 with 5 goal buttons | ✅ |
| 7 | Answer Q6 → Q7 appears | Q7 with 3 time buttons | ✅ |
| 8 | Answer Q7 → Plan message appears | Personalized plan + menu button | ✅ |
| 9 | Menu button works | Returns to main menu | ✅ |
| 10 | Sheet updated with q1-q7 values | All answer columns populated | ✅ |
| 11 | Sheet updated with level/score | level, level_score, goal_tag, time_track set | ✅ |
| 12 | quiz_state = "done" after completion | Prevents re-triggering | ✅ |

---

## 9. Debugging Decision Tree

When the quiz flow breaks, follow this diagnostic tree:

```
1. Does an Execution appear when button is pressed?
   ├── NO → Telegram Trigger is not receiving callbacks
   │         Check: Is workflow Active? Is trigger set to "Callback Query"?
   │
   └── YES → Continue to step 2

2. Which nodes are green in the execution trace?
   ├── Only Trigger + Code → Switch is not routing correctly
   │         Check: Does _route match the Switch rule? (starts with "q")
   │
   ├── Up to Google Sheets → Sheets node blocks the chain
   │         Check: Is "Always Output Data" ON? Does the row exist?
   │
   ├── Up to IF node → IF condition fails
   │         Check: Is comparison type set to Number? Is value correct?
   │
   └── Up to HTTP Request → Telegram API rejects the request
            Check: Are fields using $('Node Name') references? Is text non-empty?

3. Execution shows "Success" but no bot response?
   └── The chain ends before reaching a Send/HTTP node
       Check: Verify every node in the chain has an outgoing connection
```

---

## 10. Known Limitations & Future Considerations

1. **Quiz retake:** Currently no mechanism to reset quiz_state for retakes. To allow retakes, add a "retake_quiz" callback handler that resets q1-q7 and quiz_state to 1.

2. **Q6/Q7 non-numeric answers:** Q6 stores text values (confidence, interview, etc.) and Q7 stores text (Core, Intensive). The scoring code handles this by only summing Q1-Q5.

3. **Empty answer edge case:** If callback_data somehow arrives without a valid format, the code defaults to 0 for numeric parsing. No crash, but potentially wrong data.

4. **HTTP Request token exposure:** The bot token is visible in the HTTP Request URL. This is acceptable for self-hosted n8n but should be noted for security awareness.

5. **Plan message buttons:** Currently only "Back to Menu" button. The 3 action buttons (trial, call, how it works) were removed but can be re-added when those handlers are built.

---

*End of Quiz System Technical Audit — v1.0*
