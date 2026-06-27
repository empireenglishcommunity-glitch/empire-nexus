> **HISTORICAL DOCUMENT** — This file is kept for reference only. The work described here has been completed and the systems have moved on.

# Build Kit — Make.com Scenario Runbook (A1–A9)

Implements spec §9. Build these scenarios **in order**; test each before moving on. All read/write the `Empire CRM` Google Sheet and read copy from the `String_Table` tab.

> **Conventions used below**
> - **TG** = Telegram Bot module · **GS** = Google Sheets module.
> - **Primary key** = Telegram numeric user ID (`telegram_id`). All Subscriber writes are **upserts** on this key.
> - **String lookup** = GS → *Search Rows* on `String_Table` where `key = <key>`, return the `ar` or `en` column based on the user's stored `language`.
> - Store the **bot token** only in the Make.com Telegram connection (never in the Sheet/repo).

---

## One-time setup in Make.com
1. Create a **Telegram Bot** connection (paste the BotFather token).
2. Create a **Google Sheets** connection (the dedicated Google account).
3. Note the `Empire CRM` spreadsheet ID and the 4 tab names.
4. Create a helper: a reusable **"get string"** pattern (GS Search Rows on `String_Table`) you replicate where copy is needed.

---

## A1 — Welcome + upsert  *(trigger: `/start`)*
**Goal:** greet, create/refresh the CRM row, show the menu, log JOINED_BOT.

| # | Module | Config |
|---|---|---|
| 1 | **TG → Watch Updates** | Webhook for the bot (this is the entry trigger for most scenarios; route by update type/text) |
| 2 | **Router** | Branch: `/start` → this flow |
| 3 | **GS → Search Rows** | `Subscribers` where `telegram_id = {{user.id}}` (to know if new) |
| 4 | **Router/Filter** | If no row → path *New*; else → path *Returning* |
| 5a | **GS → Add a Row** (New) | telegram_id, username, first_name, language=Config.DEFAULT_LANGUAGE, status=`New`, source, first_seen_at=now, last_active_at=now, consent=FALSE |
| 5b | **GS → Update a Row** (Returning) | last_active_at=now |
| 6 | **GS → Add a Row** | `Events`: event_id={{uuid}}, telegram_id, event_type=`JOINED_BOT`, timestamp=now |
| 7 | **TG → Send Message** | text = `welcome_1` (with language buttons `btn_lang_ar`/`btn_lang_en`) |
| 8 | **TG → Send Message** | text = `welcome_2` (interpolate {first_name}); inline buttons: `btn_start_quiz`, `btn_resource`, main menu |

**Idempotency:** step 3+4 ensure no duplicate Subscriber row. Event dedupe handled by unique `event_id`.
**Test → T1.**

---

## A2 — Quiz handler  *(trigger: quiz answers received)*
**Goal:** score, map level, write data, send the plan. Logic in `quiz-logic.md`.

| # | Module | Config |
|---|---|---|
| 1 | Trigger | Quiz callback answers (collect Q1–Q7; store per-user temp via Data Store or pass through) |
| 2 | **Tools → Set variables** | q1..q5 points; goal_tag (Q6); time_track (Q7) |
| 3 | **Tools** | `level_score = q1+q2+q3+q4+q5`; map to level via Config `LEVEL_BAND_*`; compute `review_flag` (edge rule) |
| 4 | **GS → Update a Row** | `Subscribers`: level, level_score, goal_tag, time_track, review_flag, last_active_at=now |
| 5 | **GS → Add a Row** | `Events`: `QUIZ_COMPLETED`, meta = score+goal |
| 6 | **GS → Search Rows** | `String_Table` key = `plan_{level}` → pick ar/en |
| 7 | **TG → Send Message** | the plan text, interpolate {first_name}, {goal} (use `goal_{tag}` string), {track}; append `plan_review_note` if review_flag; plan buttons |

**Test → T2, T3.**

---

## A3 — Resource delivery  *(trigger: "🎁 My free gift" tapped)*
| # | Module | Config |
|---|---|---|
| 1 | Trigger | callback = resource |
| 2 | **GS → Search Rows** | `Subscribers` consent value |
| 3 | **Router** | If consent not TRUE → run **Consent sub-flow** (A-consent) first |
| 4 | **TG → Send Message** | `resource_deliver` (interpolate {first_name}, {RESOURCE_LINK} from Config) |
| 5 | **GS → Add a Row** | `Events`: `RESOURCE_CLAIMED` |

**Consent sub-flow (shared):** send `consent_prompt` → on `btn_yes`: Update Subscribers consent=TRUE, consent_at=now → continue. On `btn_no`: send `consent_no`, consent=FALSE → continue (still deliver value).
**Test → T4, T6.**

---

## A4 — Offer / how-it-works  *(trigger: "📚 How Empire works" tapped)*
| # | Module | Config |
|---|---|---|
| 1 | Trigger | callback = how |
| 2 | **TG → Send Message** ×3 | `how_1`, `how_2`, `how_3` (no public prices — pricing via call/DM) |
| 3 | **GS → Add a Row** | `Events`: `OFFER_OPENED` |
| 4 | buttons | Start 7-Day Starter · Book a call · Back |

**Test → T7 (OFFER_OPENED).**

---

## A5 — Booking sync  *(trigger: Cal.com webhook)*
| # | Module | Config |
|---|---|---|
| 1 | **Webhooks → Custom webhook** | Set this URL as the Cal.com booking webhook |
| 2 | **Tools** | Parse `tid` (telegram_id) from the booking's `src/tid` param/metadata |
| 3 | **GS → Update a Row** | `Subscribers` where telegram_id=tid → booked=TRUE, status=`Hot`, last_active_at=now |
| 4 | **GS → Add a Row** | `Events`: `BOOKED`, meta=booking time |
| 5 | **Trigger A9** | (or inline) send founder Hot-lead alert |

**Test → T5.**

---

## A6 — Community click  *(trigger: "💬 Join the community" tapped)*
| # | Module | Config |
|---|---|---|
| 1 | Trigger | callback = community |
| 2 | **TG → Send Message** | `community_invite` ({DISCORD_INVITE}, {GROUP_INVITE} from Config) |
| 3 | **GS → Add a Row** | `Events`: `COMMUNITY_CLICK` |

**Test → T7 (COMMUNITY_CLICK).**

---

## A7 — Score / segment recompute  *(trigger: after any event, or scheduled every 15 min)*
| # | Module | Config |
|---|---|---|
| 1 | Trigger | After-event call, or **Schedule** every 15 min over recently-active rows |
| 2 | **GS → Search Rows** | `Events` for the telegram_id |
| 3 | **Tools** | Sum weighted points (Config `SCORE_*`); apply `SCORE_DECAY_INACTIVE_14D` if last_active > 14d |
| 4 | **Tools** | Derive `segment` (Lurker/Engager/Lead/Hot/Customer/Lapsed) per `quiz-logic.md` §4 |
| 5 | **GS → Update a Row** | `Subscribers`: lead_score, segment |
| 6 | **Router** | If crossed `HOT_LEAD_THRESHOLD` and not already alerted → trigger A9 |

**Test → T8.**

---

## A8 — Daily backup  *(trigger: Schedule, daily)*
| # | Module | Config |
|---|---|---|
| 1 | **Schedule** | Once daily (e.g., 03:00) |
| 2 | **GS → Copy** or **Drive → Copy File** | Duplicate `Subscribers` + `Events` into a dated backup tab/file (e.g., `backup_YYYYMMDD`) |

**Test → T9.**

---

## A9 — Hot-lead alert  *(trigger: score crosses threshold OR BOOKED)*
| # | Module | Config |
|---|---|---|
| 1 | Trigger | from A5 or A7 |
| 2 | **GS → Search Rows** | pull the lead's row |
| 3 | **TG → Send Message** | to `FOUNDER_ALERT_CHAT_ID` (Config), using the template below |

**Founder alert template (internal, English):**
```
🔥 HOT LEAD — Empire English
Name: {first_name} (@{username})
Telegram ID: {telegram_id}
Level: {level_name}   Goal: {goal}   Track: {track}
Lead score: {lead_score}   Segment: {segment}
Trigger: {trigger}   Booked: {booked}   When: {booking_time}
Consent: {consent}
→ Next: {if booked: "prep for call" else: "send a personal DM within 24h"}
```
**Test → T8 (alert fires), T5 (booking path).**

---

## Reliability rules (apply to every scenario)
- **Upsert** Subscribers (dedupe on telegram_id); **dedupe** Events by event_id.
- On error → **log and stop**; never retry into a send loop (set error handler to "commit"/ignore, not blind rollback-retry).
- Batch GS writes where possible (conserve free-tier ops).
- Keep each scenario small + single-purpose.
- Monitor the Make.com monthly ops counter; if near the ceiling, migrate the heaviest scenario (A7) to **n8n self-host** (spec §14).
