# n8n Workflow Patterns — Verified Implementation Reference

**Document Type:** Technical Implementation Standard  
**Created:** June 21, 2026  
**Status:** VERIFIED & WORKING  
**Purpose:** This document defines the ONLY verified working patterns for building n8n workflows that interact with Telegram bots. Any future development MUST follow these patterns.

---

## Critical Lesson Learned

**The n8n Switch node's expression engine does NOT reliably evaluate complex JSON paths** like `$json.callback_query.data` — even when the data visibly exists in the JSON output. Multiple hours were spent testing every variation of Switch expressions, all of which failed silently (no error, but no routing either).

**The solution:** Use a **Code node (JavaScript)** to extract routing data into a simple flat field, THEN feed that into the Switch node for routing.

---

## 1. THE STANDARD ARCHITECTURE (Mandatory for All Telegram Bot Workflows)

```
Telegram Trigger → Code Node (Router Logic) → Switch Node (Simple String Match) → Route Handlers
```

**NEVER connect a Telegram Trigger directly to a Switch node with complex expression paths.**

---

## 2. Telegram Trigger Configuration

| Setting | Value |
|---|---|
| Trigger On | `Message` + `Callback Query` (both selected) |
| Credential | Telegram Bot API credential |

**Important:** Only ONE Telegram trigger per bot is allowed (Telegram API limitation). Select BOTH update types in a single trigger.

---

## 3. The Router Code Node (MANDATORY)

This Code node sits between the Trigger and the Switch. Language: **JavaScript**.

```javascript
const input = $input.first().json;
let route = 'unknown';

if (input.message?.text?.includes('/start')) {
  route = 'start';
} else if (input.callback_query?.data) {
  route = input.callback_query.data;
}

return [{ json: { ...input, _route: route } }];
```

**What this does:**
- Reads the incoming trigger data
- Determines if it's a /start message or a button callback
- Extracts the route value into a simple `_route` field
- Passes ALL original data through (spread operator `...input`)

**Why this works when Switch expressions don't:**
- JavaScript's optional chaining (`?.`) works reliably in n8n Code nodes
- The expression engine in Switch nodes has inconsistent behavior with nested paths
- A flat `_route` string is trivial for the Switch to match

---

## 4. Switch Node Configuration

After the Code node, the Switch uses only:

```
{{ $json._route }}
```

For ALL rules. Simple string comparison:

| Rule | Expression | Operation | Value | Output Name |
|---|---|---|---|---|
| 1 | `{{ $json._route }}` | is equal to | `start` | Start |
| 2 | `{{ $json._route }}` | is equal to | `quiz` | Quiz_start |
| 3 | `{{ $json._route }}` | is equal to | `resource` | Resource |
| 4 | `{{ $json._route }}` | is equal to | `how` | How |
| 5 | `{{ $json._route }}` | is equal to | `call` | Call |
| 6 | `{{ $json._route }}` | is equal to | `community` | Community |
| 7 | `{{ $json._route }}` | is equal to | `menu` | Menu |
| 8 | `{{ $json._route }}` | starts with | `q` | Quiz_answer |

---

## 5. Data Access Patterns (VERIFIED WORKING)

After the Code node passes data through, downstream nodes access original trigger data using these VERIFIED paths:

### Chat ID (works for BOTH messages and callbacks):
```
{{ $json.message?.chat?.id ?? $json.callback_query?.message?.chat?.id }}
```

### User's Telegram ID:
```
{{ $json.callback_query?.from?.id ?? $json.message?.from?.id }}
```

### User's First Name:
```
{{ $json.callback_query?.from?.first_name ?? $json.message?.from?.first_name }}
```

### Update ID (for event deduplication):
```
{{ $json.update_id }}
```

### Referencing Trigger Data from Deep in the Chain:

When a node is NOT directly after the Code/Switch (e.g., after a Google Sheets node), use explicit node references:

```
{{ $('Code in JavaScript').first().json.message?.chat?.id ?? $('Code in JavaScript').first().json.callback_query?.message?.chat?.id }}
```

Or reference the trigger directly:
```
{{ $('Telegram Trigger').first().json.callback_query?.from?.id ?? $('Telegram Trigger').first().json.message?.from?.id }}
```

**Rule:** After any Google Sheets node, `$json` contains Sheets data, NOT trigger data. Always use `$('Node Name').first().json` to reach back to earlier nodes.

---

## 6. Google Sheets Chat ID Fix

The error "Bad Request: chat_id is empty" occurs when a Send Message node follows a Google Sheets node. The fix:

**ALWAYS** use explicit node references for Chat ID in Send Message nodes that come after Sheets operations:

```
{{ $('Code in JavaScript').first().json.message?.chat?.id ?? $('Code in JavaScript').first().json.callback_query?.message?.chat?.id }}
```

---

## 7. Inline Keyboard Buttons

In the Telegram "Send a text message" node:
- Reply Markup: **Inline Keyboard**
- Use **"Add Keyboard Row"** and **"Add Button"** for each button
- Each button needs:
  - **Text:** the visible label
  - **Callback Data:** (under "Additional Fields" → "Add Field") the routing value (e.g., `quiz`, `resource`, `how`, `call`, `community`, `menu`)
- **Append n8n Attribution:** OFF

**NEVER paste raw JSON into the keyboard fields.** Always use the visual builder.

---

## 8. Event Logging Pattern

For Google Sheets "Append row in sheet" (Events tab):

```
event_id:     {{ $('Code in JavaScript').first().json.update_id }}-EVENT_TYPE
telegram_id:  {{ $('Code in JavaScript').first().json.callback_query?.from?.id ?? $('Code in JavaScript').first().json.message?.from?.id }}
event_type:   EVENT_TYPE
timestamp:    {{ $now.toISO() }}
```

---

## 9. What FAILED (Do NOT Use These Approaches)

| Approach | Why It Failed |
|---|---|
| Switch with `$json.data` | Field doesn't exist at top level for callbacks |
| Switch with `$json.callback_query.data` | Expression engine doesn't resolve it despite data existing |
| Switch with `$json.callback_query?.data` | Optional chaining doesn't work in Switch expressions |
| Switch with `$json.callback_query?.data ?? ""` | Same — expression engine limitation |
| Putting Chat ID as `$json.from.id` | Wrong path; resolves to undefined |
| Using `$json` after a Google Sheets node | `$json` becomes the Sheets output, not trigger data |

---

## 10. Workflow Architecture Summary

```
[Telegram Trigger]
    (Message + Callback Query)
         │
         ▼
[Code in JavaScript]
    (Extracts _route, passes all data through)
         │
         ▼
[Switch - mode: Rules]
    (Matches $json._route to simple strings)
         │
    ┌────┼────┬────────┬──────┬──────┬───────────┬──────┬────────────┐
    ▼    ▼    ▼        ▼      ▼      ▼           ▼      ▼            ▼
  Start Quiz Resource  How   Call  Community   Menu  Quiz_answer  (Fallback)
    │    │    │        │      │      │           │      │
    ▼    ▼    ▼        ▼      ▼      ▼           ▼      ▼
  [Route Handler Nodes - Sheets + Telegram Send Message]
```

---

## 11. Testing Protocol

After any workflow change, verify:
1. Send `/start` → bot replies with welcome + 5 buttons
2. Tap each button → bot responds with correct message
3. Check CRM Subscribers tab → row exists
4. Check CRM Events tab → correct events logged
5. Tap ↩️ Menu → menu reappears
6. Send `/start` again → no duplicate CRM row (upsert works)

---

## 12. HTTP Request Pattern for Dynamic Telegram Messages (VERIFIED WORKING)

**When to use:** Any time you need to send a Telegram message with an inline keyboard built dynamically from code (variable buttons, conditional buttons, JSON-constructed keyboards).

**Why:** The n8n Telegram node's built-in keyboard builder works for STATIC buttons (hardcoded via the visual UI). But when buttons come from expressions or Code nodes, the Telegram node fails with "can't parse inline keyboard button" errors. The HTTP Request approach bypasses this entirely.

### Pattern:

```
[Code Node - builds message + keyboard JSON] → [HTTP Request - POST to Telegram API]
```

### HTTP Request Configuration:

| Setting | Value |
|---------|-------|
| Method | POST |
| URL | `https://api.telegram.org/bot<YOUR_TOKEN>/sendMessage` |
| Send Body | ON |
| Body Content Type | JSON |
| Specify Body | **Using Fields Below** |

### Parameters:

| Name | Value |
|------|-------|
| chat_id | `{{ $json.chatId }}` |
| text | `{{ $json.text }}` |
| reply_markup | `{{ $json.replyMarkup }}` |

### Code Node Output Format:

```javascript
return [{
  json: {
    chatId: "123456789",
    text: "Your message text here",
    replyMarkup: JSON.stringify({
      inline_keyboard: [
        [{ text: "Button 1", callback_data: "btn1" }],
        [{ text: "Button 2", callback_data: "btn2" }]
      ]
    })
  }
}];
```

### For static buttons (no dynamic generation needed):

Pass `reply_markup` as a plain text value (not expression mode):
```
{"inline_keyboard":[[{"text":"🔙 Menu","callback_data":"menu"}]]}
```

### CRITICAL RULES:
- **NEVER** use `JSON.stringify()` inside the raw JSON body field — use "Fields Below" instead
- **NEVER** use `JSON.parse()` inside expressions — it causes parsing errors
- If the HTTP Request node comes after a Google Sheets node, use `$('Code Node Name').first().json.chatId` instead of `$json.chatId`

---

## 13. Node Reference Pattern — Accessing Data From Earlier Nodes

**The Problem:** In n8n, `$json` always refers to the output of the IMMEDIATELY PREVIOUS node. When a Google Sheets node sits between your Code node and your Send/HTTP node, `$json` becomes the sheet data — your original variables are gone.

**The Solution:** Use explicit node references with `$('Node Name').first().json.field`

### Syntax:
```
{{ $('Exact Node Name').first().json.fieldName }}
```

### Example Chain:
```
Code - Score & Level → Save Quiz Results (Sheets) → HTTP Request1
```

In HTTP Request1:
- ❌ `{{ $json.chatId }}` → undefined (Sheets output has no chatId)
- ✅ `{{ $('Code - Score & Level').first().json.chatId }}` → correct value

### Rules:
1. The node name inside `$('...')` must match EXACTLY (case-sensitive, spaces matter)
2. This works for any node earlier in the same execution path
3. Use `.first()` to get the first item (standard for single-item flows)
4. You can chain: `$('Node').first().json.nested.field`

### Common Use Cases:
```javascript
// Chat ID from router code after Sheets operations:
{{ $('Code in JavaScript').first().json.callback_query.message.chat.id }}

// User ID from trigger after multiple Sheets operations:
{{ $('Telegram Trigger').first().json.callback_query.from.id }}

// Custom field from a Code node after Sheets:
{{ $('Code - Score & Level').first().json.level }}
```

---

## 14. Google Sheets — "Always Output Data" Rule

**The Problem:** Google Sheets "Update Row" returns NOTHING when:
- No matching row is found, OR
- The update succeeds but the node doesn't pass data forward by default

This causes the entire downstream chain to silently stop — no error, just no execution.

**The Fix:** On EVERY Google Sheets node that has downstream nodes:

1. Open the node
2. Click **Settings** (gear icon, top-right)
3. Toggle **"Always Output Data"** = ON
4. Save

**This ensures:** Even if the Sheets operation returns no data, the node still passes SOMETHING to the next node, allowing the chain to continue.

### When is this mandatory?
- ✅ Update Row with nodes after it → ALWAYS enable
- ✅ Append Row with nodes after it → ALWAYS enable
- ❌ Read Rows (always returns data if rows exist) → not strictly needed but doesn't hurt

---

## 15. IF Node — Type Matching Rules

Google Sheets returns values with specific types:
- Numbers in cells → returned as **Number** type
- Text in cells → returned as **String** type
- Empty cells → returned as **empty string** or **undefined**

**When comparing sheet values in IF nodes:**

| Sheet Cell Contains | IF Condition Type | Example |
|---------------------|-------------------|---------|
| A number (2, 8, 15) | **Number** | quiz_state equals 8 |
| Text ("done", "L1") | **String** | quiz_state equals "done" |
| true/false | **Boolean** | review_flag is true |

**Common Error:** "Wrong type: '2' is a number but was expecting a string"  
**Fix:** Change the IF condition type dropdown from String to Number.

---

## 16. Multi-Step Quiz Pattern (Scalable Loop Architecture)

For building a multi-question quiz that loops through questions:

```
[Switch - quiz_answer] → [Parse Answer Code] → [Save to Sheet] → [IF last?]
                                                                      │
                                                    ├── NO → [Build Next Q] → [HTTP Send]
                                                    └── YES → [Read All Answers] → [Score] → [HTTP Send Result]
```

### Key Design Decisions:
1. **Single path handles ALL questions** — no duplicate nodes per question
2. **Questions stored in a Code node as a JS object** — easy to modify
3. **quiz_state column tracks progress** — increments with each answer
4. **"Last question" detection uses quiz_state = totalQuestions + 1** — because state is set to nextQuestion before the IF check
5. **Score calculation reads ALL answers from sheet in one read** — not passed through the chain

### Answer Format Convention:
- Callback data: `q{number}_{value}` (e.g., `q1_0`, `q3_3`, `q6_confidence`)
- Parsed by splitting on first `_`: question number + answer value
- Q1-Q5: numeric scores (0-3)
- Q6-Q7: text tags (confidence, Core, etc.)

---

## 17. Debugging Methodology (Structured Approach)

When a workflow fails, follow this exact process:

### Step 1: Check Executions
- Does an execution appear? → If NO, trigger is broken
- Is status Success or Error? → If Error, click to see which node failed

### Step 2: Trace the Green Nodes
- Open the failed execution
- Identify the LAST green node and the FIRST non-executed node
- The break is between these two

### Step 3: Check the Break Point
- If last green is Google Sheets → enable "Always Output Data"
- If last green is before IF → check IF condition type (Number vs String)
- If last green is IF → check which branch was taken (TRUE vs FALSE)
- If Telegram/HTTP fails → check data availability (`$json` vs `$('Node')`)

### Step 4: Verify Data Flow
- Click each node → check OUTPUT tab
- Confirm the fields expected by the next node actually exist in the output
- After any Sheets node, expect sheet column data (NOT previous code output)

### NEVER:
- Assume a connection exists without verifying via execution trace
- Try multiple random fixes without first identifying the root cause
- Trust that `$json` has earlier data after a Sheets/HTTP operation

---

*This document supersedes all previous workflow implementation guidance (make-scenarios.md, N8N_MIGRATION_PLAN.md §6-§7). Those documents remain for historical reference only. THIS is the verified working standard.*
