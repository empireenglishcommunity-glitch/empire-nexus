# New CRM Tabs to Create (Phase 1)

Add these tabs to your Empire CRM Google Sheet.

---

## Tab: `KPI_Weekly` (auto-filled by Weekly Report every Monday)

| Column | Type | Auto-filled? | Purpose |
|--------|------|:------------:|---------|
| week_start | Date (YYYY-MM-DD) | YES | Monday date for this row |
| joins | Number | YES | JOINED_BOT events that week |
| quizzes | Number | YES | QUIZ_COMPLETED events |
| resources | Number | YES | RESOURCE_CLAIMED events |
| offers | Number | YES | OFFER_OPENED events |
| booked | Number | YES | BOOKED events |
| community | Number | YES | COMMUNITY_CLICK events |
| rate_join_to_quiz | Number (%) | YES | quizzes / joins * 100 |
| rate_quiz_to_offer | Number (%) | YES | offers / quizzes * 100 |
| rate_offer_to_book | Number (%) | YES | booked / offers * 100 |
| bottleneck | Text | YES | Lowest rate step name |
| notes | Text | NO (manual) | What content ran, observations |

**Note:** This tab is auto-populated every Monday at 8 AM by the "Empire Weekly Report" workflow. You only need to manually fill the `notes` column with what you observed that week (which posts did well, etc.)

---

## Tab: `Stories` (manual — for testimonial collection)

| Column | Type | Purpose |
|--------|------|---------|
| member_name | Text | First name or "anonymous" |
| telegram_id | Number | For consent tracking |
| consent | Boolean | TRUE/FALSE — did they agree to share? |
| quote_ar | Text | Their words in Arabic |
| quote_en | Text | English translation |
| context | Text | Level, timeframe, what they did |
| collected_on | Date | When you gathered it |
| used_on | Date | When posted to channel (if used) |

---

## Setup (2 minutes)

1. Open Empire CRM Sheet
2. Add new tab → name it `KPI_Weekly`
3. Add headers in row 1 (copy from table above)
4. Add new tab → name it `Stories`
5. Add headers in row 1 (copy from table above)
6. Done — the report will auto-fill KPI_Weekly starting next Monday

---

## Tab: `Content_Calendar` (already created ✅)

Reference: `CONTENT_CALENDAR_STRUCTURE.md`
