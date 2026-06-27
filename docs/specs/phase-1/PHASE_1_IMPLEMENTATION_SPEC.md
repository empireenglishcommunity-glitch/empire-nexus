# Empire English — Phase 1 Implementation Spec (Content Rhythm & Reporting)

**Implementation Specification v1.0** · *Confidential* · **Date:** June 2026

> **Status: SPEC ONLY.** This document specifies *exactly how* Phase 1 should be built — content calendar, publishing automation, the discussion group launch, the weekly auto-report, and the KPI baseline — so it can be executed without ambiguity. Review and approve before implementation begins.

> **Parent documents.** This spec implements **Phase 1** of `MASTER_IMPLEMENTATION_ROADMAP.md` (§6). It assumes Phase 0 is built and passing acceptance tests (Gate 0→1 open). It draws on `CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md` §3 (content engine), §5 (engagement), and §7 (weekly reporting).

> **Gate 0→1 confirmed:** The capture spine (bot, quiz, CRM, booking, events, scoring) is working end-to-end. Phase 1 now feeds traffic into that spine and gives the founder eyes on the funnel.

---

## Table of Contents

1. [Phase 1 Goal, Scope & Exit Criteria](#1-phase-1-goal-scope--exit-criteria)
2. [Content Calendar & Batching System](#2-content-calendar--batching-system)
3. [Publishing Automation](#3-publishing-automation)
4. [Discussion Group Launch](#4-discussion-group-launch)
5. [Story & Testimonial Collection](#5-story--testimonial-collection)
6. [Weekly Auto-Report (KPI Digest)](#6-weekly-auto-report-kpi-digest)
7. [Baseline KPIs & Measurement](#7-baseline-kpis--measurement)
8. [Reminder & Nudge Automations](#8-reminder--nudge-automations)
9. [Build Order (Step-by-Step)](#9-build-order-step-by-step)
10. [Acceptance Tests (Definition of Done)](#10-acceptance-tests-definition-of-done)
11. [Explicitly NOT in Phase 1](#11-explicitly-not-in-phase-1)
12. [Content Inventory Needed](#12-content-inventory-needed)

---

## 1. Phase 1 Goal, Scope & Exit Criteria

### 1.1 The single goal of Phase 1

> **Establish a sustainable content cadence that drives traffic into the bot, launch two-way engagement via the discussion group, and stand up the weekly auto-report so the funnel becomes visible, measurable numbers — proving that people flow through the spine.**

Phase 1 is **not** about optimizing conversion rates, A/B testing, or growth hacking. It is about building the **habit** (consistent publishing) and building the **eyes** (weekly report) that make Phase 2 optimization possible.

### 1.2 In scope

- A **content calendar** with the 10 post categories, mapped to a weekly rhythm
- A **batching workflow** (create a week's content in one sitting)
- **Scheduled publishing** via Make.com or Telegram's native scheduler
- The **linked discussion group** — launched, seeded, and active
- A **story/testimonial collection** system (template + process)
- The **weekly auto-report** that pulls from the CRM Events tab
- **Baseline funnel conversion rates** measured for ≥4 weeks
- Light **reminder/nudge automations** (streak, inactive re-engage)

### 1.3 Out of scope (deferred — see §11)

A/B testing, follow-up/reactivation drips, referral system, gamification, paid ads, AI content repurposing at scale, second discovery channel. Those are Phase 2–3.

### 1.4 Exit criteria (Phase 1 is "done" when ALL are true)

| # | Exit criterion | Verified by |
|---|---|---|
| P1-E1 | 5–6 posts/week published consistently for ≥6 weeks | Publishing log |
| P1-E2 | Discussion group is live, linked to channel, with ≥3 posts/week from members | Group activity |
| P1-E3 | Weekly auto-report runs and delivers to founder every Monday | Report history |
| P1-E4 | Baseline conversion rates exist for all 5 funnel steps (≥4 weeks of data) | KPI dashboard |
| P1-E5 | ≥1 content category proven to reliably drive bot taps (measurable correlation) | Report data |
| P1-E6 | ≥3 transformation stories collected (with consent) | Story library |
| P1-E7 | Bot scenario is ON and processing real users without errors for ≥2 weeks | Make.com logs |

> **Time estimate (planning anchor):** ~6–8 weeks of consistent execution. Phase 1 is less "build" and more "run + measure." The build work (report automation, scheduling) is ~2–3 days. The rest is consistent content production.

---

## 2. Content Calendar & Batching System

### 2.1 The 10 post categories (from Blueprint §3.1)

| # | Category | Funnel job | Frequency target |
|---|---|---|---|
| C1 | Value / micro-lesson | Trust | 2×/week |
| C2 | Transformation / success story | Trust → Engagement | 1×/week |
| C3 | Behind-the-scenes / founder | Trust | 1×/2 weeks |
| C4 | Social proof / momentum | Trust | 1×/2 weeks |
| C5 | Engagement bait (poll/question) | Engagement | 1×/week |
| C6 | Offer / promotion | Appointment | 1×/2 weeks (max) |
| C7 | Education-about-problem | Trust → Engagement | 1×/week |
| C8 | Objection-handler | Lead → Appointment | 1×/2 weeks |
| C9 | Community ritual (word of the day) | Engagement/retention | Daily (lightweight) |
| C10 | Event / live | Engagement → Lead | 1×/month |

### 2.2 Weekly template (6 posts + daily ritual)

| Day | Post category | CTA type |
|---|---|---|
| **Saturday** | C1 — Value/micro-lesson | Soft (resource CTA → bot) |
| **Sunday** | C5 — Engagement poll/question | Soft (poll/reply) |
| **Monday** | C7 — Problem education | Medium (quiz CTA → bot) |
| **Tuesday** | C1 — Value/micro-lesson | Soft (resource CTA → bot) |
| **Wednesday** | C2/C4 — Story or social proof | Soft (reaction CTA) |
| **Thursday** | C8/C3 — Objection or behind-scenes | Medium (call/quiz CTA → bot) |
| **Daily** | C9 — Word/phrase of the day (lightweight) | Reply CTA |

> **Give:ask ratio maintained:** 5 value/engagement posts : 1 offer-adjacent post ≈ 83% give / 17% ask. C6 (offer) rotates in every other week, replacing one C8/C3 slot.

### 2.3 Batching workflow (solo-operator sustainable)

**One weekly session (~2–3 hours) produces the entire next week:**

1. **Pick topics** (15 min): choose from a topic bank (§12) based on this week's category slots.
2. **Write posts** (60–90 min): draft 6 posts + 7 daily rituals (word of the day).
3. **Create visuals** (30 min): simple Canva graphics if needed (optional — text posts work fine for Telegram).
4. **Schedule** (15 min): queue all posts in the publishing tool (§3).
5. **Prep discussion seeds** (15 min): write 2–3 questions/prompts to drop in the group during the week.

### 2.4 Topic bank (starter — grows over time)

**C1 (Value/micro-lesson) — first 12 topics:**
1. 3 ways Americans reduce "going to" → "gonna"
2. The flap T: why "water" sounds like "wah-der"
3. 5 phrases to start any conversation confidently
4. The schwa — the laziest (and most common) English sound
5. Word stress: why "present" (noun) ≠ "present" (verb)
6. Linking: why "an apple" sounds like "anapple"
7. 3 greetings beyond "hi" and "hello"
8. The dark L: why "feel" sounds different at the end
9. How to say "I don't know" like an American (5 natural ways)
10. Intonation: questions go UP, statements go DOWN
11. 5 filler words Americans use (and you should too)
12. The difference between "th" sounds (think vs. this)

**C5 (Engagement polls) — first 6:**
1. "What's your biggest fear when speaking English?" (4 options)
2. "How long have you been learning English?" (4 ranges)
3. "Which skill do you want to improve most?" (speaking/listening/vocabulary/accent)
4. "Do you practice English every day?" (yes/trying/not yet)
5. "What time do you study?" (morning/afternoon/evening/random)
6. "Would you join a free live pronunciation clinic?" (yes/maybe/no)

**C7 (Problem education) — first 6:**
1. "Why grammar-first study keeps you silent for years"
2. "The #1 reason you understand English but can't speak it"
3. "Why watching movies with subtitles doesn't improve your accent"
4. "The myth of 'I'm too old to learn English'"
5. "Why apps like Duolingo don't teach you to speak"
6. "You don't need 10,000 words — you need 500 used well"

---

## 3. Publishing Automation

### 3.1 Tool choice: Telegram Native Scheduled Messages

Telegram supports **scheduled messages** natively (no extra tool needed):
- Long-press "Send" → "Schedule Message" → pick date/time
- Works in channels directly
- Zero Make.com operations consumed

**For Phase 1, this is the recommended approach** — simple, free, no extra setup.

### 3.2 Alternative: Make.com scheduled publishing

If you prefer automation (pre-schedule a week's posts from a spreadsheet):

**New scenario: `Empire Content — Auto-Publish`**

| # | Module | Config |
|---|---|---|
| 1 | Schedule | Daily at posting time (e.g., 10:00 AM) |
| 2 | Google Sheets → Search Rows | `Content_Calendar` tab where `publish_date = today` AND `published = FALSE` |
| 3 | Telegram Bot → Send Message | Chat ID = channel ID; Text = post content from the sheet |
| 4 | Google Sheets → Update Row | Set `published = TRUE` |

**New CRM tab: `Content_Calendar`**

| Column | Purpose |
|---|---|
| `post_id` | Unique ID |
| `publish_date` | When to post (YYYY-MM-DD) |
| `category` | C1–C10 |
| `text_ar` | Arabic post content |
| `text_en` | English version (if bilingual post) |
| `cta_type` | soft / medium / hard |
| `cta_callback` | quiz / resource / call / how / community |
| `published` | TRUE/FALSE |
| `engagement_notes` | Manual: reactions, poll votes, bot taps observed |

> **Recommendation for Phase 1:** start with Telegram's native scheduler (simpler). Move to the Make.com auto-publish only if batching from a spreadsheet saves meaningful time (evaluate after 2 weeks).

---

## 4. Discussion Group Launch

### 4.1 Setup

1. Create a **Telegram group** (not channel — groups allow two-way chat)
2. **Link it to your channel:** Channel Settings → Discussion → select the group
3. This makes channel posts auto-forward to the group with a "Comment" button
4. Set group rules (pinned message):
   - Be respectful
   - Arabic + English welcome
   - No spam/self-promotion
   - Questions encouraged
5. Add the group invite link to your `Config` tab (`GROUP_INVITE`) and update the bot's community route (currently stubbed)

### 4.2 Seeding strategy (first 2 weeks)

The group needs activity to not feel dead. **Founder seeds it:**

| Action | Frequency | Example |
|---|---|---|
| Ask a question | 3×/week | "What English word do you use most at work?" |
| Share a tip + ask for replies | 2×/week | "Try saying 'water' with a flap T. Record yourself! How did it feel?" |
| Reply to every comment personally | Always | Build the norm that comments get answered |
| Drop the word-of-the-day | Daily | "Today's word: *improve* — use it in a sentence below 👇" |

### 4.3 Engagement rules

- **React to every member message** (even just a 👍) — signals that participation is seen
- **Highlight good contributions** by forwarding them to the channel with credit (with consent)
- **Ask, don't tell:** end posts with questions, not statements
- **Weekly group-only bonus:** something exclusive (a tip, a pronunciation clip) to make the group feel special

### 4.4 Success metric

Discussion group is "active" when: ≥3 posts/week from members (not founder) by week 4.

---

## 5. Story & Testimonial Collection

### 5.1 Why now

You need social proof content (C2/C4 categories) to sustain the content calendar. At 57 members, stories won't come organically — you need to **ask systematically**.

### 5.2 Collection process

**Template DM (send to engaged members — Engagers/Hot leads):**

> مرحبًا {name}! 👋
> كيف حالك مع الإنجليزي هالأيام؟
> لو عندك أي تقدّم — حتى لو بسيط — أحب أسمع عنه. ممكن أستخدمه (بإذنك) كتشجيع لبقية المجتمع.
> حتى جملة وحدة تكفي! مثلاً: "قبل كنت أخاف أتكلم، الحين أقدر أعرّف عن نفسي."

**EN version:**
> Hey {name}! 👋
> How's your English going these days?
> If you've had any progress — even small — I'd love to hear about it. I might share it (with your permission) to encourage the community.
> Even one sentence is enough! Like: "Before I was scared to talk, now I can introduce myself."

### 5.3 Story format (for channel posts)

Use the success-story framework (Blueprint §3.7):
1. Starting point (relatable pain)
2. The turn (what changed)
3. The proof (specific, measurable)
4. The emotion (identity shift)
5. Soft CTA

### 5.4 Storage

Add a `Stories` tab to the CRM (or a separate doc):

| Column | Content |
|---|---|
| `member_name` | First name or anonymous |
| `telegram_id` | For consent tracking |
| `consent` | TRUE/FALSE |
| `quote_ar` | Their words (Arabic) |
| `quote_en` | Translation |
| `context` | Level, timeframe, what they did |
| `used_on` | Date posted to channel |

Target: collect **≥3 stories** during Phase 1 (enough to rotate one per week).

---

## 6. Weekly Auto-Report (KPI Digest)

### 6.1 What it produces

Every Monday, the founder receives a message (bot DM to themselves) with:

```
🏛 EMPIRE — WEEKLY FUNNEL DIGEST
Week: {start_date} → {end_date}

📊 FUNNEL NUMBERS
━━━━━━━━━━━━━━━━━━
Reach:        +{new_joins} new bot starts
Engagement:   {quiz_count} quizzes · {resource_count} resources claimed
Leads:        {offer_opened} offers viewed · {consented} consented
Appointments: {booked} booked ★
Community:    {community_clicks} community taps
━━━━━━━━━━━━━━━━━━

📈 CONVERSION RATES
Start→Quiz:    {rate_1}%
Quiz→Offer:    {rate_2}%
Offer→Booked:  {rate_3}%

🎯 BOTTLENECK: {lowest_step} ({lowest_rate}%)
💡 Suggested focus: {suggestion}

⚙️ Total subscribers: {total}
Hot leads: {hot_count}
Automation health: OK
```

### 6.2 How it's built — Make.com scenario

**New scenario: `Empire — Weekly Report`**

| # | Module | Config |
|---|---|---|
| 1 | **Schedule** | Every Monday at 08:00 |
| 2 | **Google Sheets → Search Rows** | `Events` tab where `timestamp` is within last 7 days |
| 3 | **Tools → Set multiple variables** | Count each event type: JOINED_BOT, QUIZ_COMPLETED, RESOURCE_CLAIMED, OFFER_OPENED, BOOKED, COMMUNITY_CLICK |
| 4 | **Tools → Set multiple variables** | Calculate conversion rates: quiz/joins, offer/quiz, booked/offer |
| 5 | **Tools → Set variable** | Determine bottleneck (lowest rate) + suggestion |
| 6 | **Google Sheets → Search Rows** | `Subscribers` — count total rows, count segment=Hot |
| 7 | **Telegram Bot → Send Message** | To FOUNDER_ALERT_CHAT_ID, using the digest template above |

### 6.3 Alternative: Google Apps Script (zero Make.com ops)

If Make.com ops are tight, the report can run as a **time-triggered Apps Script** on the Google Sheet itself:

```javascript
function weeklyReport() {
  var events = SpreadsheetApp.getActive().getSheetByName('Events');
  var subs = SpreadsheetApp.getActive().getSheetByName('Subscribers');
  // Count events from last 7 days
  // Calculate rates
  // Format message
  // Send via Telegram Bot API (UrlFetchApp)
}
```

Set a trigger: every Monday at 08:00. **This is recommended** if your Make.com free tier is getting tight — it uses zero Make ops.

### 6.4 Data source: the Events tab

Your Phase 0 Events tab already captures everything needed:
- `JOINED_BOT` → Reach
- `QUIZ_COMPLETED` → Engagement
- `RESOURCE_CLAIMED` → Engagement
- `OFFER_OPENED` → Lead interest
- `BOOKED` → Appointment (north star)
- `COMMUNITY_CLICK` → Community

No new instrumentation needed — Phase 0 already logs it all. Phase 1 just **reads and reports**.

---

## 7. Baseline KPIs & Measurement

### 7.1 The KPI dashboard (simple — one Sheets tab)

Add a new tab to your CRM: **`KPI_Weekly`**

| Column | Content |
|---|---|
| `week_start` | Monday date |
| `joins` | Count of JOINED_BOT that week |
| `quizzes` | Count of QUIZ_COMPLETED |
| `resources` | Count of RESOURCE_CLAIMED |
| `offers` | Count of OFFER_OPENED |
| `booked` | Count of BOOKED |
| `community` | Count of COMMUNITY_CLICK |
| `rate_join_to_quiz` | quizzes / joins % |
| `rate_quiz_to_offer` | offers / quizzes % |
| `rate_offer_to_book` | booked / offers % |
| `bottleneck` | Lowest rate step |
| `notes` | What content ran, what was tried |

The auto-report (§6) fills this weekly. Over 4+ weeks, you'll see patterns.

### 7.2 What "baseline" means

After 4 weeks, you'll know:
- What % of people who start the bot take the quiz
- What % who take the quiz view the offer
- What % who view the offer book a call
- Which content category (C1–C10) correlates with bot-tap spikes

**This is the data that unlocks Phase 2** — without it, optimization is guessing.

### 7.3 How to track which posts drive bot taps

Simple method: in your `Content_Calendar` tab, log the date + category of each post. Cross-reference with the `Events` tab: did bot starts spike on days with C1 posts? C5 posts? C7 posts?

The weekly report notes field captures this qualitatively; the dashboard captures it quantitatively. After 4–6 weeks, one category will clearly win.

---

## 8. Reminder & Nudge Automations

### 8.1 Scope (minimal — don't over-automate in Phase 1)

Only two automations — both simple, both high-impact:

**Nudge 1 — "You started but didn't quiz" (3-day reminder)**

| Field | Detail |
|---|---|
| Trigger | Subscriber has `JOINED_BOT` but no `QUIZ_COMPLETED` after 3 days |
| Action | Bot sends a gentle reminder |
| Message (AR) | "مرحبًا! 👋 شفت إنك ما جربت اختبار المستوى بعد — دقيقتين بس وتعرف بالضبط وين تبدأ. جرّبه؟ 🎯" |
| Message (EN) | "Hey! 👋 Noticed you haven't tried the level quiz yet — just 2 minutes and you'll know exactly where to start. Give it a try? 🎯" |
| Button | `[🎯 Start quiz]` callback_data=quiz |
| Limit | Send once only per user (never repeat) |

**Nudge 2 — "Quizzed but didn't book" (7-day reminder)**

| Field | Detail |
|---|---|
| Trigger | Subscriber has `QUIZ_COMPLETED` but no `BOOKED` and no `OFFER_OPENED` after 7 days |
| Action | Bot sends a soft value-add reminder |
| Message (AR) | "أهلاً! 👋 خطتك جاهزة من اختبار المستوى. لو تبي نرسم لك خارطة طريق شخصية في مكالمة قصيرة (15 دقيقة، بدون ضغط) — احجز وقت يناسبك 👇" |
| Message (EN) | "Hey! 👋 Your plan is ready from the level quiz. If you'd like a personal roadmap in a short call (15 min, no pressure) — pick a time that works 👇" |
| Button | `[📅 Book a call]` callback_data=call |
| Limit | Send once only per user |

### 8.2 Implementation

**New scenario: `Empire — Nudges`**

| # | Module | Config |
|---|---|---|
| 1 | Schedule | Daily at 18:00 |
| 2 | Google Sheets → Search Rows | Subscribers where: has JOINED_BOT event >3 days ago AND no QUIZ_COMPLETED event AND `nudge_quiz_sent` ≠ TRUE |
| 3 | Telegram Bot → Send Message | The nudge 1 message + quiz button |
| 4 | Google Sheets → Update Row | Set `nudge_quiz_sent = TRUE` |
| 5 | (repeat pattern for nudge 2) | 7-day check, no BOOKED, send call nudge, flag `nudge_call_sent = TRUE` |

**Add 2 columns to Subscribers:** `nudge_quiz_sent`, `nudge_call_sent` (boolean flags to prevent repeat sends).

---

## 9. Build Order (Step-by-Step)

| Step | Build | Depends on | Days |
|---|---|---|---|
| 1 | Turn on Phase 0 bot (A1 scenario → ON) | Phase 0 complete | 0 |
| 2 | Create + link the discussion group | Step 1 | Day 1 |
| 3 | Update bot "community" route (replace stub with real invite) | Step 2 | Day 1 |
| 4 | Write first 2 weeks of content (12 posts + daily rituals) | Topic bank (§2.4) | Day 1–2 |
| 5 | Schedule first week's posts (native Telegram scheduler) | Step 4 | Day 2 |
| 6 | Build the weekly auto-report scenario | CRM Events data | Day 2–3 |
| 7 | Add `KPI_Weekly` tab to CRM | Step 6 | Day 3 |
| 8 | Build nudge scenario | Step 1 active, users flowing | Day 3 |
| 9 | Seed discussion group (first 2 weeks of founder activity) | Step 2 | Week 1–2 |
| 10 | Collect first stories (DM engaged users) | Real users in CRM | Week 2–3 |
| 11 | Run for ≥4 more weeks, adjusting content based on report | All above | Weeks 3–8 |
| 12 | Evaluate gate P1-E1 through P1-E7 | Week 6+ | Gate check |

---

## 10. Acceptance Tests (Definition of Done)

| ID | Test | Pass condition |
|---|---|---|
| P1-T1 | Content publishing | 6 posts published this week in the channel, covering ≥3 categories |
| P1-T2 | Discussion group | Group linked, ≥1 member (non-founder) posted this week |
| P1-T3 | Weekly report | Auto-report delivered to founder on Monday with real numbers |
| P1-T4 | KPI tab | `KPI_Weekly` tab has this week's row auto-filled |
| P1-T5 | Bot live | A1 scenario ON; a real new user completed the full flow (quiz + plan) without errors |
| P1-T6 | Nudge | A test user who joined 3+ days ago without quiz received the nudge (once only) |
| P1-T7 | Story collected | At least 1 transformation story obtained (with consent) |

> Run P1-T1 through P1-T7 after week 2. The **exit gate** (P1-E1–E7) is evaluated after ≥6 weeks of consistent execution.

---

## 11. Explicitly NOT in Phase 1

- **A/B testing** of CTAs or bot flows (Phase 2)
- **Follow-up / reactivation email drips** (Phase 2)
- **Referral system** (Phase 2–3)
- **Gamification / seasons** (Phase 3)
- **Paid ads or second discovery channel** (Phase 3)
- **AI content repurposing at scale** (Phase 2)
- **Payment integration** (still manual in Phase 1)
- **Full "3 American Sounds" audio production** (runs in parallel, not gating Phase 1)

---

## 12. Content Inventory Needed

| # | Asset | Used by | Status |
|---|---|---|---|
| 1 | First 12 value/micro-lesson posts (bilingual) | C1 slots (6 weeks) | To write |
| 2 | First 6 engagement polls | C5 slots | To write |
| 3 | First 6 problem-education posts | C7 slots | To write |
| 4 | 3–4 objection-handler posts | C8 slots | To write |
| 5 | 2 behind-the-scenes / founder posts | C3 slots | To write |
| 6 | 42 words/phrases of the day (6 weeks) | C9 daily ritual | To compile |
| 7 | Discussion group pinned rules | Group setup | To write |
| 8 | Story collection DM template | §5 | ✅ Written above |
| 9 | Nudge messages (2) | §8 | ✅ Written above |
| 10 | Weekly report template | §6 | ✅ Specified above |

> **The content is the work of Phase 1.** Unlike Phase 0 (which was a build sprint), Phase 1 is a 6-week execution rhythm. The build is small (report + nudge + group); the discipline is the deliverable.

---

## 13. Summary & Next Step

Phase 1 turns the working capture spine into a **living funnel with traffic, measurement, and iteration**. It publishes 5–6 value-first posts/week that drive bot engagement, launches a two-way discussion group for community feel, and auto-generates a weekly digest that shows exactly where the funnel leaks. After ≥4 weeks of measured data, the founder knows which content works, what the conversion rates are, and where to focus Phase 2's optimization.

> **Next step:** review and approve this spec. On approval:
> 1. Turn on the Phase 0 bot (A1 scenario → ON)
> 2. Create the discussion group + update the bot's community route
> 3. Write the first 2 weeks of content
> 4. Build the weekly report + nudge scenarios
> 5. Start the 6-week clock

---

*End of Phase 1 Implementation Spec v1.0 — planning/spec artifact. No implementation has been performed.*
