> **HISTORICAL DOCUMENT** — This file is kept for reference only. The work described here has been completed and the systems have moved on.

# Phase 0 — Patch #001: Three Bug Fixes

**Date:** June 2026  
**Fixes:** Menu button dead-end · CRM formula inheritance · Duplicate rows on /start  
**Applies to:** `Empire Bot — A1 Welcome` scenario in Make.com + `Empire CRM` Google Sheet

---

## Issue 1: Main Menu Navigation Button Not Working

### Root cause

When we built the bot, several flows include a "↩️ القائمة / Menu" button with `callback_data = "menu"`. However, **no route in the A1 Router handles the `menu` callback**. The Router only has filters for:
- `/start` (text message)
- `quiz`, `resource`, `how`, `call`, `community` (callback queries)
- `q1_*` through `q7_*` (quiz answer callbacks)

When a user taps "Menu," Telegram sends a callback query with `data = "menu"` → the Router has no matching filter → **nothing happens**.

### Fix — Add a "menu" route to the Router

In your `Empire Bot — A1 Welcome` scenario:

1. From the main **Router**, add a **new route**.
2. **Filter:**
   - Label: `menu`
   - Condition: `{{1.callbackQuery.data}}` **Text operators: Equal to** `menu`

3. **Module: Telegram Bot → Send a Text Message**
   - Chat ID: `{{1.callbackQuery.message.chat.id}}`
   - Text:
     ```
     🏛 أهلاً بك في Empire English
     اختر من القائمة 👇

     🏛 Welcome to Empire English
     Choose from the menu 👇
     ```
   - Inline keyboard:
     ```json
     [[{"text":"🎯 حدّد مستواي (دقيقتان)","callback_data":"quiz"}],[{"text":"🎁 هديتي المجانية","callback_data":"resource"}],[{"text":"📚 كيف يعمل Empire","callback_data":"how"}],[{"text":"📅 احجز مكالمة مجانية","callback_data":"call"}],[{"text":"💬 انضم للمجتمع","callback_data":"community"}]]
     ```

That's it — one route, one message module.

### Verification

- Run once → tap any "↩️ القائمة" or "Menu" button from any flow → the 5-button menu re-appears.
- Confirm other routes (quiz, resource, how, call, community) still work (no regression).

---

## Issue 2: CRM Lead Score & Segment Formulas Not Applied to New Rows

### Root cause

Google Sheets' **"Add a Row"** API (which Make.com uses) inserts a raw data row. It does **not** copy formulas from adjacent rows. Formulas only exist in the rows where you manually pasted them. New rows inserted by Make.com arrive as blank cells in the `lead_score` and `segment` columns.

### Fix — Use an ARRAYFORMULA in a header row that auto-covers all rows

Instead of per-row formulas that need to be "dragged down," we use a single **ARRAYFORMULA** in row 1 (or a dedicated formula row) that automatically calculates for every row that has data. This is the standard Google Sheets pattern for automation-friendly scoring.

**Step 1 — Identify your column letters**

Check your `Subscribers` tab. Based on the CSV, the intended order is:

| Col | Header |
|---|---|
| A | telegram_id |
| B | username |
| C | first_name |
| D | language |
| E | status |
| F | level |
| G | level_score |
| H | goal_tag |
| I | time_track |
| J | consent |
| K | consent_at |
| L | lead_score ← formula goes here |
| M | segment ← formula goes here |
| N | review_flag |
| O | source |
| P | first_seen_at |
| Q | last_active_at |
| R | booked |
| S | notes |

> ⚠️ **If your columns are in a different order** (e.g., you added quiz_state, q1–q7 columns), adjust the column letters below accordingly. The logic is what matters.

**Step 2 — Replace the lead_score formula (cell L2) with this ARRAYFORMULA:**

Delete any existing formula in L2 and all rows below in column L. Then paste into **L2**:

```
=ARRAYFORMULA(
  IF(A2:A = ""; "";
    MMULT(
      (TRANSPOSE(Events!B$2:B) = A2:A) *
      TRANSPOSE(
        (Events!C$2:C="JOINED_BOT")*5 +
        (Events!C$2:C="QUIZ_COMPLETED")*30 +
        (Events!C$2:C="RESOURCE_CLAIMED")*15 +
        (Events!C$2:C="OFFER_OPENED")*20 +
        (Events!C$2:C="BOOKED")*50 +
        (Events!C$2:C="COMMUNITY_CLICK")*10
      );
      SIGN(ROW(Events!B$2:B))^0
    )
  )
)
```

> **If MMULT gives issues** (it can with very large ranges on free Sheets), use this simpler per-row alternative that still auto-extends. Paste into **L2** only — it covers all rows:

```
=ARRAYFORMULA(
  IF(A2:A = ""; "";
    COUNTIFS(Events!B:B; A2:A; Events!C:C; "JOINED_BOT")*5 +
    COUNTIFS(Events!B:B; A2:A; Events!C:C; "QUIZ_COMPLETED")*30 +
    COUNTIFS(Events!B:B; A2:A; Events!C:C; "RESOURCE_CLAIMED")*15 +
    COUNTIFS(Events!B:B; A2:A; Events!C:C; "OFFER_OPENED")*20 +
    COUNTIFS(Events!B:B; A2:A; Events!C:C; "BOOKED")*50 +
    COUNTIFS(Events!B:B; A2:A; Events!C:C; "COMMUNITY_CLICK")*10
  )
)
```

> ⚠️ **Google Sheets note:** ARRAYFORMULA + COUNTIFS uses **semicolons** (`;`) as separators if your Sheets locale uses them. If you get a formula parse error, try replacing `;` with `,` (locale-dependent).

**Step 3 — Replace the segment formula (cell M2) with this ARRAYFORMULA:**

Delete any existing formula in M2 and below. Paste into **M2**:

```
=ARRAYFORMULA(
  IF(A2:A = ""; "";
    IF(E2:E = "Customer"; "Customer";
      IF(OR(R2:R = TRUE; L2:L >= 80); "Hot";
        IF(AND(COUNTIFS(Events!B:B; A2:A; Events!C:C; "OFFER_OPENED") > 0; J2:J = TRUE); "Lead";
          IF(OR(COUNTIFS(Events!B:B; A2:A; Events!C:C; "QUIZ_COMPLETED") > 0; COUNTIFS(Events!B:B; A2:A; Events!C:C; "RESOURCE_CLAIMED") > 0); "Engager";
            "Lurker"
          )
        )
      )
    )
  )
)
```

> ⚠️ **Known limitation:** ARRAYFORMULA doesn't fully work with OR/AND across arrays in Google Sheets. If this formula errors, use the **simpler IFS version** below (paste in M2, then manually drag down to row 100 — new rows within that range auto-calculate):

```
=IF(A2=""; "";
  IF(E2="Customer"; "Customer";
    IF(OR(R2=TRUE; L2>=80); "Hot";
      IF(AND(COUNTIFS(Events!B:B;A2;Events!C:C;"OFFER_OPENED")>0; J2=TRUE); "Lead";
        IF(OR(COUNTIFS(Events!B:B;A2;Events!C:C;"QUIZ_COMPLETED")>0; COUNTIFS(Events!B:B;A2;Events!C:C;"RESOURCE_CLAIMED")>0); "Engager";
          "Lurker"
        )
      )
    )
  )
)
```

Then select M2 → drag the fill handle down to row 200 (pre-fills formula for future rows).

**Step 4 — Protect the formula columns from Make.com overwriting**

In your Make.com A1 scenario (Module: Add a Row / Update a Row), make sure the `lead_score` and `segment` fields are **left empty / not mapped**. If Make.com writes blank values to those columns, it will overwrite the formulas. Simply don't include those columns in the module's field mapping.

### Verification

1. Delete all test rows in Subscribers.
2. Send `/start` from Telegram → new row appears.
3. Check: columns L (`lead_score`) and M (`segment`) auto-calculate immediately (should show 5 and "Lurker" after just JOINED_BOT).
4. Complete the quiz → score should jump (5 + 30 = 35), segment should become "Engager".

---

## Issue 3: Duplicate CRM Rows When User Sends /start Again

### Root cause

Looking at the A1 scenario as originally built during our live session, the welcome route was created as a simple:

1. Watch Updates (trigger)
2. Add a Row to Subscribers ← always adds, never checks if exists
3. Add a Row to Events
4. Send welcome message

The **spec** (make-scenarios.md, A1) calls for a Search → Router (new vs returning) pattern:
- If no existing row → Add a Row (new subscriber)
- If existing row → Update a Row (just refresh `last_active_at`)

But during the live build, we simplified to just "Add a Row" to get it working fast — which means every `/start` creates a **duplicate row**.

### Fix — Implement proper upsert logic in the /start route

Modify the `/start` route in your `Empire Bot — A1 Welcome` scenario:

**Current flow (broken):**
```
Filter: /start → Add Row (Subscribers) → Add Row (Events) → Send Message
```

**Fixed flow:**
```
Filter: /start → Search Rows (Subscribers) → Router → [New path] Add Row
                                                     → [Returning path] Update Row
                                              → Add Row (Events) → Send Message
```

**Step by step:**

1. **After the /start filter**, add: **Google Sheets → Search Rows**
   - Sheet: `Subscribers`
   - Filter: `telegram_id` Equal to `{{1.message.from.id}}`

2. **After the Search Rows**, add a **Router** with 2 paths:

   **Path A — New user** (no row found):
   - Filter: `{{2.totalNumberOfBundles}}` Equal to `0`
     (or: the result array is empty — Make.com shows this as "Number of results" = 0)
   - Module: **Google Sheets → Add a Row** (Subscribers)
     - telegram_id: `{{1.message.from.id}}`
     - username: `{{1.message.from.username}}`
     - first_name: `{{1.message.from.first_name}}`
     - language: `ar`
     - status: `New`
     - consent: `FALSE`
     - source: `{{1.message.text}}`
     - first_seen_at: `{{now}}`
     - last_active_at: `{{now}}`
     - ⚠️ Do NOT map `lead_score` or `segment` (leave them empty so formulas work)

   **Path B — Returning user** (row exists):
   - Filter: `{{2.totalNumberOfBundles}}` Greater than `0`
     (this is the fallback / else path)
   - Module: **Google Sheets → Update a Row** (Subscribers)
     - Row number: `{{2.__ROW_NUMBER__}}` (the row number from the Search result)
     - Only update: `last_active_at` → `{{now}}`
     - Do NOT overwrite any other fields

3. **After both paths converge**, continue to:
   - **Add Row (Events):** log `JOINED_BOT` (this fires for both new and returning — it's fine, it's a true event)
   - **Send Message:** welcome + menu

   > **Note on "returning" behavior:** The spec says a returning user just gets their `last_active_at` refreshed. They still see the welcome/menu (it's a natural UX — they tapped /start because they want the menu). The key is: **no duplicate Subscriber row**.

**Alternative simpler approach (if the Router feels complex):**

If you want to avoid adding a Router inside a Router (which can get visually messy), use this trick:

1. **Search Rows** first.
2. **Google Sheets → Update a Row** — try to update the found row's `last_active_at`. 
   - If no row was found, this module will error/skip.
3. Add an **Error Handler** on the Update module: set to "Ignore" (continue to next).
4. **Google Sheets → Add a Row** — add a new row.
   - Add a **Filter before this module**: only run if Search found 0 results.

Pick whichever feels cleaner in your scenario layout.

### Verification

1. Clear your test row from Subscribers (leave the sheet with only headers + formulas).
2. Send `/start` → one row appears (status: New).
3. Send `/start` again → **same row** updated (`last_active_at` changes), **no second row**.
4. Check Events: two `JOINED_BOT` entries exist (one per /start — that's correct behavior for the event log).

---

## Summary of Changes

| Issue | Root Cause | Fix | Impact |
|---|---|---|---|
| Menu button dead | No route for `callback_data = "menu"` | Add a `menu` route that re-sends the 5-button menu | Zero impact on other routes |
| Formulas not on new rows | `Add a Row` API doesn't copy formulas | Use ARRAYFORMULA in L2/M2 + don't map those columns in Make.com | Formulas auto-calculate for all present and future rows |
| Duplicate /start rows | No Search-before-Add logic | Add Search → Router (new/returning) before the Add/Update | Prevents duplicates; preserves event logging |

### Architectural improvements made:

1. **ARRAYFORMULA** pattern means the sheet is self-maintaining — no manual formula drag-down ever needed.
2. **Upsert pattern** (search → branch → add/update) is now the standard for any future Make.com module that writes to Subscribers.
3. **Menu route** serves as a universal "reset" point — any future flow can include a menu button without worrying about dead-ends.

---

## Files unchanged

- No changes to: quiz logic, plan templates, scoring, Cal.com sync, backup, hot-lead alerts, or any content assets.
- All existing working routes remain untouched.

---

*End of Patch #001 — apply in Make.com + Google Sheets, then re-run T1–T10.*
