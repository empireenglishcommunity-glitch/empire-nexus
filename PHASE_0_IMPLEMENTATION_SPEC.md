# Empire English — Phase 0 Implementation Spec (Foundation & Instrumentation)

**Implementation Specification v1.0** · *Confidential* · **Date:** June 2026

> **Status: PLANNING / SPEC ONLY.** This document specifies *exactly how* Phase 0 should be built — bot flows, data schemas, quiz logic, automation wiring, and acceptance tests — so the build can be executed without ambiguity. **Nothing here has been built or deployed.** It is the bridge between the approved strategy and the first line of configuration. Review and approve before any setup begins.

> **Parent documents.** This spec implements **Phase 0** of `CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md` (v1.1, decisions locked in §10). It assumes the product context in `Empire English Community Learning System.md` and the business context in `STRATEGIC_EXPANSION_ROADMAP.md`.

> **Locked decisions this spec is built on (from Blueprint §10):** Telegram channel + Telegram bot feeding Discord · 5-button bot menu · primary goal = free taster/trial (self-serve) + free calls in parallel · main offer = Core Membership + time-boxed Founding Citizen · lead-magnet ladder (quiz → "3 American Sounds" → 7-Day Speaking Starter → Core) · Arabic-led bilingual · high call capacity · explicit consent + Google Sheets CRM · 5–6 posts/week · Cal.com booking.

---

## Table of Contents

1. [Phase 0 Goal, Scope & Exit Criteria](#1-phase-0-goal-scope--exit-criteria)
2. [System Architecture & Data Flow](#2-system-architecture--data-flow)
3. [Tool Setup Checklist (Accounts & Free Tiers)](#3-tool-setup-checklist-accounts--free-tiers)
4. [Telegram Bot Specification](#4-telegram-bot-specification)
5. [The 2-Minute Level Quiz (Logic & Scoring)](#5-the-2-minute-level-quiz-logic--scoring)
6. [Google Sheets CRM Schema](#6-google-sheets-crm-schema)
7. [Consent & Lead Capture](#7-consent--lead-capture)
8. [Cal.com Booking Setup](#8-calcom-booking-setup)
9. [Automation Wiring (Make / n8n)](#9-automation-wiring-make--n8n)
10. [Event Instrumentation (Funnel Tracking)](#10-event-instrumentation-funnel-tracking)
11. [Segmentation & Lead Scoring (Implementation)](#11-segmentation--lead-scoring-implementation)
12. [Build Order (Step-by-Step Sequence)](#12-build-order-step-by-step-sequence)
13. [Acceptance Tests (Definition of Done)](#13-acceptance-tests-definition-of-done)
14. [Free-Tier Limits & Risk Register](#14-free-tier-limits--risk-register)
15. [Explicitly NOT in Phase 0](#15-explicitly-not-in-phase-0)
16. [Content Inventory Needed Before Build](#16-content-inventory-needed-before-build)

---

## 1. Phase 0 Goal, Scope & Exit Criteria

### 1.1 The single goal of Phase 0

> **Build the end-to-end "capture spine" so that a brand-new channel member can be welcomed, take the level quiz, receive a personalized plan + free resource, be stored and tagged in the CRM, and either book a call or enter the taster — fully automated, free, and instrumented.**

Phase 0 is **not** about content volume, growth tactics, or optimization. It is about making the *plumbing* exist and work reliably before any traffic is poured into it. Pouring traffic into a leaky/unbuilt funnel wastes the scarce 57-member audience.

### 1.2 In scope

- One Telegram **bot** with the locked 5-button menu and core conversation flows.
- The **2-minute level quiz** with scoring → provisional level → personalized plan.
- **Lead capture + explicit consent**, stored in a **Google Sheets CRM**.
- Automatic **tagging/segmentation** and a basic **lead score**.
- **Cal.com** booking connected to the "Book a call" button.
- **Welcome automation** triggered when a user starts the bot.
- Delivery of the **quick-win lead magnet** ("3 American Sounds") via the bot.
- **Funnel event logging** for the 6 stages (Blueprint §2.2).

### 1.3 Out of scope (deferred — see §15)

A/B testing, follow-up/reactivation drips, referral system, gamification, the full 45-minute placement diagnostic, paid ads, the weekly auto-report (Phase 1), and the full 7-Day Speaking Starter content build (Phase 0 wires the *delivery mechanism* and stubs the content).

### 1.4 Exit criteria (Phase 0 is "done" when ALL are true)

| # | Exit criterion | Verified by |
|---|---|---|
| E1 | A new user who taps the bot receives a bilingual welcome + can reach all 5 menu items | §13 T1 |
| E2 | A user can complete the quiz and receive a provisional level + personalized plan message | §13 T2 |
| E3 | The user's data (ID, name, level, goal, consent, timestamps) is written to the CRM | §13 T3 |
| E4 | Consent is explicitly captured and stored before any marketing follow-up flag is set | §13 T4 |
| E5 | A user can open Cal.com from the bot and book a slot; the booking is tagged in CRM | §13 T5 |
| E6 | The quick-win resource is delivered on request | §13 T6 |
| E7 | Each of the 6 funnel events is logged with a timestamp | §13 T7 |
| E8 | Lead score + segment auto-update from logged actions | §13 T8 |
| E9 | A daily CRM backup exists | §13 T9 |
| E10 | No automation can enter a spam/double-send loop (idempotency verified) | §13 T10 |

> **Time estimate (planning anchor, solo operator):** ~5–9 focused working days, front-loaded on bot flow + quiz + CRM wiring. Not a commitment.


---

## 2. System Architecture & Data Flow

### 2.1 Components and their single responsibility

| Component | Single responsibility | Tool |
|---|---|---|
| **Telegram Channel** | Broadcast value + proof; route to bot | Telegram |
| **Telegram Bot** | Conversation, menus, quiz, consent, deliver resources, route to booking | Telegram Bot API |
| **Orchestrator** | Logic, branching, read/write to CRM, trigger emails | **Make.com free tier** (primary) or **n8n self-host** (zero-cost alt) |
| **CRM / source of truth** | Store every subscriber + their fields, tags, score | **Google Sheets** |
| **Booking** | Show availability, take bookings, send reminders | **Cal.com** |
| **Email (backup list)** | Owned-list insurance + later drips | **MailerLite or Brevo free tier** (account only in Phase 0) |

> **Why Make.com as primary:** no server to maintain (solo-operator friendly), native Telegram + Google Sheets + webhook modules, generous free tier. **n8n self-host** is the truly-$0 alternative if free-tier task limits become a constraint (see §14). The spec is written tool-neutral; either works.

### 2.2 The data flow (happy path)

```
 User taps channel link / button
        │  (Telegram deep link → bot /start)
        ▼
 [BOT] sends bilingual welcome  ──────────────► [ORCHESTRATOR] upsert row in CRM (status: New)
        │                                              │  log event: JOINED_BOT
        ▼                                              ▼
 [BOT] shows 5-button menu                       [CRM] Subscribers tab
        │
        ├─ "Find my level" ─► quiz Q1..Qn ─► score ─► [ORCH] write level+answers ─► [BOT] send plan
        │                                                   │ log: QUIZ_COMPLETED · score++
        ├─ "Free resource" ─► consent check ─► deliver link/file ─► [ORCH] log: RESOURCE_CLAIMED
        ├─ "How Empire works" ─► info + pricing ─► soft CTA ─► (offer opened) log: OFFER_OPENED
        ├─ "Book a call" ─► Cal.com deep link ─► booking ─► [Cal webhook] ─► [ORCH] tag Hot ─► log: BOOKED
        └─ "Join community" ─► Discord/group invite ─► log: COMMUNITY_CLICK
        ▼
 [ORCH] recompute lead score + segment on every logged event
        ▼
 [CRM] daily scheduled backup (copy tab / export)
```

### 2.3 Identity key

The **Telegram numeric user ID** is the primary key across all systems (stable, unique, never reused). Username/handle is stored as a secondary field (can change). All upserts dedupe on Telegram user ID to guarantee idempotency (E10).

---

## 3. Tool Setup Checklist (Accounts & Free Tiers)

> Create these accounts only; no configuration logic yet. Verify *current* free-tier limits at signup (they change).

| # | Account | Purpose | Free-tier note |
|---|---|---|---|
| 1 | **Telegram bot** via @BotFather | The bot token | Free |
| 2 | **Telegram channel** (exists) + **linked discussion group** | Hub + two-way engagement | Free |
| 3 | **Google account** (dedicated, e.g., ops@) | Owns the Sheets CRM + backups | Free |
| 4 | **Make.com** (or n8n) | Orchestration | Free tier: limited ops/month — monitor |
| 5 | **Cal.com** | Booking | Free tier sufficient for 1 host |
| 6 | **MailerLite or Brevo** | Backup email list (account only in Phase 0) | Free tier |
| 7 | **Canva (free)** | Produce the quick-win PDF + plan template | Free |

> **Security note:** store the bot token and any API keys in the orchestrator's secret/credential store — never in the Sheet, never in the repo, never in chat.

---

## 4. Telegram Bot Specification

### 4.1 Commands

| Command | Action |
|---|---|
| `/start` | Trigger welcome flow + show main menu (also fires on deep-link entry) |
| `/menu` | Re-show the main menu |
| `/help` | Short help + link to community + "talk to a human" note |
| `/language` | Toggle Arabic ⇄ English |

### 4.2 Main menu (locked 5 buttons — inline keyboard)

```
🏛 أهلاً بك في Empire English / Welcome to Empire English
────────────────────────────────────────────
[ 🎯 حدد مستواي (اختبار دقيقتين) / Find my level (2-min quiz) ]
[ 🎁 احصل على هديتك المجانية / Get my free resource ]
[ 📚 كيف يعمل Empire / How Empire works + pricing ]
[ 📅 احجز مكالمة مجانية / Book a free call ]
[ 💬 انضم للمجتمع / Join the community ]
```

### 4.3 Bilingual handling (Arabic-led)

- On first `/start`, default to **Arabic**, with an inline `English 🇬🇧 / عربي 🇸🇦` toggle.
- Store `language` in the CRM; all subsequent bot messages use the stored language.
- All user-facing strings live in a **two-column string table** (key → {ar, en}) so copy is editable without touching logic. (String table itself is content — see §16.)

### 4.4 Conversation flows (state-by-state)

**Flow A — Welcome (`/start`)**
1. Detect language (stored or default Arabic) → offer toggle.
2. Send warm bilingual welcome (1–2 short messages, founder voice).
3. Immediately offer a quick win: "Want to find your English level in 2 minutes?" → buttons `[Start quiz] [Show menu]`.
4. Upsert CRM row (status `New`); log `JOINED_BOT`.

**Flow B — Level quiz** → see §5.

**Flow C — Free resource**
1. If consent not yet given → show consent prompt (§7) → on Yes, set `consent=TRUE`.
2. Deliver the "3 American Sounds" resource (file or link).
3. Log `RESOURCE_CLAIMED`; soft CTA → "Want the full system? Tap *How Empire works*."

**Flow D — How Empire works + pricing**
1. Short bilingual explainer (system-over-instructor, accent-from-day-one).
2. Present the ladder: Free → Core (main) → Citizen → Elite; highlight **Founding Citizen (limited)**.
3. CTAs: `[Start free taster] [Book a free call] [Back to menu]`.
4. Log `OFFER_OPENED`.

**Flow E — Book a call**
1. Brief "what you'll get on the call" + reassurance.
2. Button → Cal.com deep link (§8).
3. On Cal webhook confirmation → tag `Hot lead`, log `BOOKED` (§9, §10).

**Flow F — Join community**
1. Deliver Discord invite + linked discussion-group link.
2. Log `COMMUNITY_CLICK`.

### 4.5 Bot behavior rules

- Always end a flow by returning to a clear next step (never a dead end).
- Keep messages short; prefer buttons over free-text where possible (lower friction, easier to parse).
- Unknown free-text → gentle fallback → show menu.
- Never send more than one unsolicited message; respect Telegram anti-spam norms.


---

## 5. The 2-Minute Level Quiz (Logic & Scoring)

> **Important distinction.** This is a **lightweight 2-minute screener** that returns a *provisional* level for funnel routing and personalization. It is **NOT** the full 45-minute placement diagnostic in the Learning System doc (§3) — that runs later, inside the paid onboarding. The screener's job is conversion + segmentation, not final placement.

### 5.1 Format

- **7 questions**, all tap-to-answer (Telegram quiz/poll-style inline buttons) — no typing.
- Mix: self-assessment + a few objective checks. Target completion < 2 minutes.
- Bilingual; Arabic-led.

### 5.2 Question set (provisional — copy to be finalized in content step)

| # | Question (intent) | Type | Maps to |
|---|---|---|---|
| Q1 | "How would you describe your English today?" (5 options, beginner→advanced) | Self-assessment | Level anchor |
| Q2 | "Can you introduce yourself in English for 30 seconds?" (Not yet / With effort / Easily) | Self-assessment | Speaking |
| Q3 | One objective grammar pick (choose the correct sentence) | Objective | Grammar |
| Q4 | One objective vocabulary pick (choose the meaning) | Objective | Vocabulary |
| Q5 | "Can you follow a fast English video/podcast?" (No / Some / Most / All) | Self-assessment | Listening |
| Q6 | "What is your #1 goal?" (Speak confidently / Job-Interview / Travel / Exam / Accent) | Intent | Segmentation tag |
| Q7 | "How much time can you give daily?" (15 / 30 / 60+ min) | Intent | Track (Core vs Intensive) |

### 5.3 Scoring → provisional level

- Q1–Q5 contribute to a **level score**; Q6–Q7 are **tags** (goal, time/track), not scored.
- Each scored answer yields 0–3 points. Sum (0–15) maps to a provisional level:

| Level-score sum | Provisional level |
|---|---|
| 0–3 | **Level 0 — Absolute Beginner** |
| 4–7 | **Level 1 — Survival English** |
| 8–11 | **Level 2 — Communication** |
| 12–15 | **Level 3 — Fluency / Accent** |

- **Edge rule (mirrors Learning System §3.2 refinement):** if Q2 (speaking) is much higher/lower than the rest, nudge toward the higher level on a trial basis and flag `review=TRUE`.

### 5.4 Output: the personalized plan message

After scoring, the bot sends a short, templated plan:
1. "Your provisional level: **{level name}**."
2. 3 bullet "what to focus on first" (pulled from the level's objectives).
3. Their goal echoed back ("Because your goal is *{goal}*...").
4. Recommended track from Q7 (Core/Intensive).
5. **CTA:** `[Start the free 7-Day Speaking Starter] [Book a free call] [See pricing]`.

> The plan text is **templated per level** (4 templates) with `{goal}`/`{track}` variables — content to be written in the content step (§16), logic specified here.

### 5.5 Data written on quiz completion

`level`, `level_score`, `goal_tag`, `time_track`, `quiz_completed_at`, `review_flag`, and event `QUIZ_COMPLETED` (+ lead-score increment, §11).

---

## 6. Google Sheets CRM Schema

> One spreadsheet, multiple tabs. This is the **single source of truth**; every automation reads/writes here. Keep it boringly simple.

### 6.1 Tab: `Subscribers` (one row per Telegram user)

| Column | Type | Notes |
|---|---|---|
| `telegram_id` | number | **Primary key**; dedupe on this |
| `username` | text | Secondary; can change |
| `first_name` | text | From Telegram |
| `language` | text | `ar` / `en` |
| `status` | text | New · Engaged · Lead · Hot · Customer · Lapsed |
| `level` | text | L0–L3 (provisional) |
| `level_score` | number | 0–15 |
| `goal_tag` | text | confidence / interview / travel / exam / accent |
| `time_track` | text | Core / Intensive |
| `consent` | boolean | TRUE only after explicit opt-in |
| `consent_at` | datetime | Timestamp of opt-in |
| `lead_score` | number | Auto-computed (§11) |
| `segment` | text | Auto-derived (§11) |
| `review_flag` | boolean | Uneven quiz profile |
| `source` | text | e.g., channel_post, referral, direct |
| `first_seen_at` | datetime | First `/start` |
| `last_active_at` | datetime | Updated every event |
| `booked` | boolean | TRUE after Cal.com booking |
| `notes` | text | Manual founder notes |

### 6.2 Tab: `Events` (append-only log; one row per event)

| Column | Type | Notes |
|---|---|---|
| `event_id` | text | UUID or row hash (idempotency) |
| `telegram_id` | number | FK to Subscribers |
| `event_type` | text | JOINED_BOT · QUIZ_COMPLETED · RESOURCE_CLAIMED · OFFER_OPENED · BOOKED · COMMUNITY_CLICK |
| `timestamp` | datetime | When it happened |
| `meta` | text | Optional JSON (e.g., quiz score, goal) |

### 6.3 Tab: `Config` (editable knobs, no code change needed)

Holds lead-score weights, segment thresholds, resource links, Cal.com URL, Discord invite — so tuning never requires touching automations.

### 6.4 Tab: `String_Table` (bilingual copy)

`key | ar | en` — all user-facing bot text. (Content to be filled in §16.)

> **Idempotency:** writes to `Subscribers` are **upserts keyed on `telegram_id`**; writes to `Events` check `event_id` to avoid duplicates on retries (E10).


---

## 7. Consent & Lead Capture

### 7.1 Principle

Capturing a Telegram user in the CRM for *operational* purposes (they interacted with the bot) is fine. **Marketing follow-up (email drips, promotional broadcasts) requires explicit opt-in.** Phase 0 captures consent cleanly so later phases can follow up compliantly.

### 7.2 Consent prompt (shown before first resource delivery or plan)

> "هل تسمح لنا بإرسال خطتك ونصائح مفيدة من وقت لآخر؟ / Can we send you your plan and occasional helpful tips?"  `[نعم / Yes]` `[لا / No]`

- `Yes` → `consent=TRUE`, `consent_at=now`.
- `No` → still deliver the immediate value (resource/plan), but `consent=FALSE`; no future marketing flag set.

### 7.3 What is captured (minimum viable lead record)

Telegram ID, name, language, level + score, goal, time/track, consent + timestamp, source, timestamps. **No sensitive data.** Email is optional and only requested later (when offering the email-delivered taster) — not required in Phase 0.

### 7.4 Opt-out

Any user can send `/stop` (or tap an opt-out) → set `consent=FALSE`, status unchanged. Honor immediately. Document this in `/help`.

---

## 8. Cal.com Booking Setup

### 8.1 Event type

- One event: **"Empire English — Free Level & Roadmap Call"**, 15–20 min.
- Buffer + daily cap configured to protect founder focus (capacity is high per Q7, but cap anyway to avoid all-day fragmentation).
- Timezone-aware; collect name + Telegram username + goal in the booking form.

### 8.2 Connection from the bot

- "Book a call" button → Cal.com booking link with **prefilled** name/username via URL params + a tracking param (e.g., `?src=bot&tid={telegram_id}`) so the booking can be matched back to the CRM row.

### 8.3 Post-booking

- Cal.com **webhook** → orchestrator → match on `telegram_id` (from src param) → set `booked=TRUE`, `status=Hot`, log `BOOKED`, bump lead score.
- Cal.com sends its own confirmation + reminder emails (cuts no-shows) — no custom build needed in Phase 0.

---

## 9. Automation Wiring (Make / n8n)

> Each automation = one scenario/workflow. All read config + write CRM. All idempotent.

### 9.1 Scenario list

| # | Scenario | Trigger | Steps |
|---|---|---|---|
| A1 | **Welcome + upsert** | Telegram `/start` webhook | Detect language → send welcome → upsert Subscriber (status New) → log JOINED_BOT |
| A2 | **Quiz handler** | Quiz answers received | Score → map level → write level/goal/track → send plan → log QUIZ_COMPLETED → recompute score/segment |
| A3 | **Resource delivery** | "Free resource" tap | Consent check → deliver file/link → log RESOURCE_CLAIMED |
| A4 | **Offer view** | "How Empire works" tap | Send explainer + pricing → log OFFER_OPENED |
| A5 | **Booking sync** | Cal.com webhook | Match telegram_id → set booked/Hot → log BOOKED → notify founder |
| A6 | **Community click** | "Join community" tap | Send invites → log COMMUNITY_CLICK |
| A7 | **Score/segment recompute** | After any event (or scheduled) | Recompute lead_score + segment per §11 |
| A8 | **Daily backup** | Schedule (daily) | Copy `Subscribers` + `Events` to a dated backup tab/file |
| A9 | **Hot-lead alert** | Score crosses threshold OR BOOKED | DM/email the founder with the lead summary |

### 9.2 Reliability rules (apply to every scenario)

- **Upsert, don't append** to `Subscribers` (dedupe on `telegram_id`).
- **Dedupe events** by `event_id`.
- **Fail-safe:** on error, log and stop — never retry into a send loop.
- **Rate-awareness:** batch Sheets writes where possible to conserve free-tier ops/quota.
- **Secrets** in the orchestrator credential store only.

---

## 10. Event Instrumentation (Funnel Tracking)

The 6 funnel stages (Blueprint §2.2) map 1:1 to logged events, so the funnel becomes literal numbers:

| Funnel stage | Event logged | Where fired |
|---|---|---|
| Discovery → (join bot) | `JOINED_BOT` | A1 |
| Engagement | `QUIZ_COMPLETED` / `RESOURCE_CLAIMED` | A2 / A3 |
| Lead | `OFFER_OPENED` (+ consent=TRUE) | A4 |
| Appointment | `BOOKED` | A5 |
| Community | `COMMUNITY_CLICK` | A6 |
| Customer | *(manual in Phase 0 — founder sets status=Customer on payment)* | manual |

> Customer conversion is **manual** in Phase 0 (no payment integration yet). The founder flips `status=Customer` when a payment lands. Automated payment tracking is a later phase.

These events are the raw material for the Phase 1 **weekly auto-report** (Blueprint §7) — Phase 0 only ensures they are captured cleanly.


---

## 11. Segmentation & Lead Scoring (Implementation)

> Mirrors Blueprint §6. Implemented as simple formulas/lookups against the `Config` tab so weights are tunable without code.

### 11.1 Lead-score weights (defaults — editable in `Config`)

| Action / state | Points |
|---|---|
| `JOINED_BOT` | +5 |
| `QUIZ_COMPLETED` | +30 |
| `RESOURCE_CLAIMED` | +15 |
| `OFFER_OPENED` | +20 |
| `BOOKED` | +50 |
| `COMMUNITY_CLICK` | +10 |
| Inactive 14 days | −15 (decay) |

### 11.2 Segment derivation (from score + state)

| Segment | Rule |
|---|---|
| **Lurker** | started bot, no quiz/resource/offer |
| **Engager** | quiz OR resource done, no offer opened |
| **Lead** | offer opened AND consent=TRUE |
| **Hot lead** | booked OR score ≥ Hot threshold (default 80) |
| **Customer** | status manually set to Customer |
| **Lapsed** | was active, last_active_at > N days |

- A5/A7 recompute `lead_score` and `segment` after each event.
- When a row crosses into **Hot**, scenario A9 alerts the founder for a personal touch (the highest-value manual action).

### 11.3 Why this is enough for Phase 0

It gives the founder a ranked list of who to talk to *today* (sort `Subscribers` by `lead_score` desc, filter `segment=Hot`). No fancy CRM needed.

---

## 12. Build Order (Step-by-Step Sequence)

> Build in this order so each step is testable before the next depends on it.

| Step | Build | Depends on | Test (from §13) |
|---|---|---|---|
| 1 | Create accounts (§3); store bot token in orchestrator | — | accounts exist |
| 2 | Create the Google Sheet with 4 tabs + `Config` values (§6) | 1 | tabs present |
| 3 | A1 Welcome + upsert + main menu | 2 | T1, T3 |
| 4 | A3 Resource delivery + A7 consent gating | 3, 7 | T4, T6 |
| 5 | Quiz (§5) + A2 handler + plan templates | 3 | T2, T3 |
| 6 | A4 Offer/pricing view | 3 | T7 (OFFER_OPENED) |
| 7 | Cal.com event + bot link + A5 booking sync | 3, 8 | T5 |
| 8 | A6 community click | 3 | T7 (COMMUNITY_CLICK) |
| 9 | A7 score/segment + A9 hot-lead alert | 5–8 | T8 |
| 10 | A8 daily backup | 2 | T9 |
| 11 | End-to-end dry run + idempotency check | all | T1–T10 |

---

## 13. Acceptance Tests (Definition of Done)

> Run each as a real user on a test Telegram account. Phase 0 ships only when all pass.

| ID | Test | Pass condition |
|---|---|---|
| T1 | New user `/start` | Bilingual welcome + 5-button menu appear; CRM row created (status New); JOINED_BOT logged |
| T2 | Complete quiz | Provisional level returned; personalized plan message with correct level template + echoed goal/track |
| T3 | CRM write | Row has telegram_id, level, score, goal, track, language, timestamps |
| T4 | Consent | "No" still delivers value but consent=FALSE; "Yes" sets consent=TRUE + consent_at |
| T5 | Booking | Cal.com opens prefilled; after booking, CRM shows booked=TRUE, status=Hot, BOOKED logged, founder alerted |
| T6 | Resource | "3 American Sounds" delivered; RESOURCE_CLAIMED logged |
| T7 | Events | JOINED_BOT, QUIZ_COMPLETED, RESOURCE_CLAIMED, OFFER_OPENED, BOOKED, COMMUNITY_CLICK all appear with timestamps |
| T8 | Score/segment | Lead score + segment update correctly after a sequence of actions; crossing 80 → Hot + alert |
| T9 | Backup | A dated backup of Subscribers + Events exists after the daily run |
| T10 | Idempotency | Re-sending the same `/start` or retrying a scenario does NOT duplicate rows/events or double-message |

---

## 14. Free-Tier Limits & Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Make.com monthly ops limit hit | Medium | Medium | Batch writes; move heavy scenarios to **n8n self-host** ($0) if exceeded |
| Google Sheets API rate / size limits | Low | Medium | Append-only Events tab; archive old events; batch writes |
| Telegram bot anti-spam / flood limits | Low | Medium | One message per action; no unsolicited bulk sends |
| Cal.com free-tier feature change | Low | Low | Google Calendar fallback (Blueprint §10) |
| Token/secret leakage | Low | High | Secrets only in credential store; never in Sheet/repo/chat |
| Single source of truth corruption | Low | High | Daily backup (A8); upsert discipline |
| Over-automation / brittleness | Medium | Medium | Keep scenarios small + idempotent; weekly 15-min health check |

---

## 15. Explicitly NOT in Phase 0

To protect scope and the solo operator's time, these are **deliberately deferred**:

- Follow-up / reactivation **email drips** (Phase 2) — accounts created, sequences not built.
- **A/B testing** of CTAs/flows (Phase 2).
- **Referral system, gamification, seasons** (Phase 3).
- The **weekly auto-report** dashboard (Phase 1) — events are captured now; reporting built next.
- The **full 45-minute placement diagnostic** (lives in paid onboarding).
- **Payment integration** — customer conversion is manual in Phase 0.
- Full **7-Day Speaking Starter content** — Phase 0 wires delivery + stubs day 1; full content is a content task.
- **Paid ads / second discovery channels** (Phase 3, only after LTV:CAC validated).

---

## 16. Content Inventory Needed Before Build

> The spec defines *logic*; these **content assets** must be written/produced (separately, on approval) to fill it. Listed so nothing is forgotten.

| # | Asset | Used by |
|---|---|---|
| 1 | Bilingual **String Table** (all bot copy, ar+en) | Entire bot |
| 2 | **Welcome message** copy (founder voice) | A1 |
| 3 | **7 quiz questions** + answer options + scoring values | §5 |
| 4 | **4 plan templates** (one per level) with goal/track variables | §5.4 |
| 5 | **"3 American Sounds"** quick-win (PDF + 3 audio clips) | A3 |
| 6 | **"How Empire works + pricing"** explainer copy | A4 |
| 7 | **"What you'll get on the call"** copy | A5 |
| 8 | **Discord + discussion-group invite** copy | A6 |
| 9 | **Consent + opt-out** copy | §7 |
| 10 | **Hot-lead alert** template (for founder) | A9 |

---

## 17. Summary & Next Step

Phase 0 builds the **capture spine**: a bilingual Telegram bot that welcomes, quizzes, personalizes, captures consent, stores everything in a Google Sheets CRM, scores and segments leads, delivers the quick-win, and books calls via Cal.com — all free, idempotent, and instrumented for the 6-stage funnel. Customer conversion and reporting stay manual/deferred by design.

> **Next step:** review and approve this spec. On approval, the build proceeds in the §12 order, validated against the §13 acceptance tests. The **content assets in §16** should be drafted in parallel (separate task) since they fill the logic this spec defines.

---

*End of Phase 0 Implementation Spec v1.0 — planning/spec artifact only. No implementation has been performed.*
