# Requirements — Wuslah (وُصلة): Ecosystem Harmony

> **Codename:** Wuslah (وُصلة — "link/connection") — because the goal
> is to weave the Discord bot, practice platform, and database into one
> seamless, unified student experience where progress flows freely
> between systems and the student never has to manually bridge them.
> **Purpose:** Eliminate the fragmentation between the Discord learning
> bot (rich data, 20+ tables, 8 initiatives of intelligence), the
> practice web platform (currently only sees streak/SRS via 2 API
> endpoints), and the Telegram ops layer (owner sees everything, student
> sees almost nothing). Make every piece of student data accessible
> wherever the student is — Discord, web, or eventually mobile.
> **Context:** The bot now tracks pronunciation scores, voice portfolios,
> SRS vocabulary with SM-2 scheduling, Nour AI conversations + memory,
> ability milestones, conversation sessions, difficulty levels (Dhaka'
> adaptive engine), weekly assessments, notification preferences, and
> more. But the practice platform only consumes streak + SRS words +
> basic pronunciation average via a 2-endpoint API. The student's full
> learning journey is invisible on the web. Meanwhile, the owner gets a
> comprehensive daily/weekly/monthly view via Markaz — the student
> deserves an equivalent "my progress" experience.

---

## Core Principle

**One student, one journey, visible everywhere.**

A student should never have to wonder "how am I doing?" — whether
they're on Discord, the web platform, or getting a morning notification,
their complete progress should be coherent, accessible, and actionable.
The systems should feel like one product, not three separate tools
that happen to share a database.

---

## Requirements

### R1 — Expanded Student API
The bot's HTTP API MUST expose the full richness of student data that
the bot now tracks, not just streak + SRS. Acceptance criteria:
- Pronunciation history (last N scores, trend, average)
- Voice portfolio recordings (list with dates, types, scores)
- Ability milestones achieved (with dates)
- Assessment history (weekly scores over time)
- Current difficulty level (Dhaka' adaptive engine)
- Nour AI insights (last conversation summary, personalized study tips)
- Level-up progress (what's needed to advance)
- Notification preferences (so web can display/edit them)
- Weekly progress breakdown (tasks per day, per type)
- Total points, leaderboard rank

### R2 — Unified Student Dashboard (Web)
The practice platform MUST have a dedicated "/dashboard" page showing
the student's complete learning picture in one view. Acceptance criteria:
- Current streak (days, fire animation at milestones)
- Level + progress-to-next-level (visual progress bar)
- Pronunciation trend chart (last 14 days, line graph)
- Ability milestones (achieved vs. available, badge-style)
- SRS health (due cards, mastered count, accuracy %)
- This week's activity (7-day grid, which tasks done which days)
- Voice portfolio player (listen to your own recordings over time)
- Nour's study tips (AI-generated, personalized, refreshed weekly)
- Leaderboard position (top 5 + "you are #X")

### R3 — Adaptive Practice (Web reacts to bot-side intelligence)
The practice platform SHOULD adapt what it shows/recommends based on
bot-side data. Acceptance criteria:
- Difficulty level (Dhaka') determines which exercises are suggested
- SRS-due words appear as a "review now" prompt on any practice page
- Pronunciation scores < 70% on a phoneme → extra drill suggested
- Absent 2+ days → motivational "welcome back" banner with easy restart
- Level-appropriate content highlighted (hide exercises above/below)

### R4 — Cross-Platform Task Confirmation
Completing practice on the web SHOULD count toward Discord task
completion. Acceptance criteria:
- Finishing a full exercise set on the web auto-marks it in the bot's
  database (no manual !done needed)
- Bot sends a congratulatory DM: "Great job on accent drill! 🎯"
- Daily progress in Discord reflects web-based completions
- Works via the existing link-token auth (no new auth flow needed)

### R5 — Nour on the Web (Study Intelligence Surface)
Students SHOULD see Nour's personalized intelligence on the web
platform. NOT a full chat interface, but a curated "Nour says"
section. Acceptance criteria:
- "Nour's Notes" card on the dashboard with 2-3 AI-generated tips
  specific to this student (refreshed weekly or on-demand)
- Tips based on: pronunciation weak spots, vocabulary gaps, streak
  patterns, difficulty level, recent conversation themes
- "Ask Nour" link that opens Discord DM (not a web chat — keeps Nour
  centralized in one place)

### R6 — Student-Facing Progress Notifications (Web + Discord unified)
The notification system (Nabd) SHOULD be aware of web activity and
vice versa. Acceptance criteria:
- Morning kickstart DM includes "You have X SRS cards due on the web"
- Web platform shows notification badge for due reviews
- Weekly summary DM includes web practice stats alongside Discord stats
- Notification preferences editable from both Discord (!notifications)
  and the web dashboard

### R7 — API Security + Performance
The expanded API MUST remain secure and performant. Acceptance criteria:
- Link tokens expire after 30 days of inactivity (auto-cleanup)
- Rate limiting: 60 requests/minute per token
- Responses cached for 60 seconds (stale-while-revalidate pattern)
- No PII in API responses beyond what the student themselves can see
- All endpoints behind CORS with the practice platform origin only
- Token validation is O(1) (indexed lookup, not table scan)

---

## Constraints

- Same $7/month Hetzner VPS — no additional servers
- Practice platform stays on Cloudflare Pages (free, static + JS)
- API runs in the same Docker container as the bot (port 8099)
- No new authentication flow — extends the existing !link token system
- Must not increase bot startup time by more than 1 second
- Dashboard page must load in under 2 seconds on 3G
- All new API endpoints must be gated behind a feature flag so they
  can be disabled instantly if they cause load issues

---

## Out of Scope (for now)

- Real-time WebSocket connection between web and bot (polling is fine)
- Full Nour chat on the web (stays in Discord for now)
- Payment/subscription features on the dashboard
- Mobile app (the PWA + web dashboard IS the mobile experience)
- Admin dashboard on the web (that's what Markaz/Telegram is for)
- OAuth2/social login (the link-token system is working and simpler)
