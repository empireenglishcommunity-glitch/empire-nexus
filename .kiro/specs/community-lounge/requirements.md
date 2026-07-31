# Requirements — Community Lounge ("Majlis")

> **Codename: Majlis (مجلس)** — the Arabic word for a sitting-room where people
> gather to talk. That is exactly the feeling we want for task #7: a warm place
> you *want* to drop into, where you'll likely find someone — not an empty room
> you're forced to sit in. Directory name (`community-lounge`) stays literal so
> it's discoverable.

## Origin

Empire English is a result-driven English program for ~16 Arabic-speaking
beginners (all Level 0 today). The daily loop has **7 tasks**; task **#7 is
"Community"** and today it requires the student to (a) spend **10+ minutes in a
voice channel** and (b) post a message in **`#general-chat`** — claimed by
typing `!7`.

The 10-minute voice rule was meant as *"be present in case someone's here,"* an
invitation to overlap and actually meet people. In practice, with **no signal
that anyone is around**, students experience it as **"sit alone in an empty room
for 10 minutes."** The owner has received complaints: *"why force us to stay
there alone?"* The intent was never solitary confinement — it was serendipitous
connection.

The owner then raised the **opposite** risk: if we successfully rally people, a
single lounge could become a **crowded, messy free-for-all** — which for a
*language* community is arguably worse (most go silent, one or two dominate).

So the real design goal is a **Goldilocks zone**: never alone, never a mob —
**small, lively pods (~2–5 people)**, with presence made **visible** and
**social**, and credit made **humane**. Make it feel professional and
high-quality.

## Constraints

1. **Zero disruption to the live daily flow.** The 16 students' existing tasks,
   streaks, points, calendar, voice tracking, and `#general-chat` requirement
   must keep working exactly as they do today.
2. **Strict backwards compatibility.** The current way to complete task #7
   (10 min in *any* voice + a `#general-chat` message) MUST remain valid. Every
   new mechanic is **additive** — a *faster* or *friendlier* path — so **no
   student who can complete #7 today can fail it tomorrow.**
3. **Budget & infra:** same bot server, no new paid services, no GPU, no new
   containers. Uses the existing Discord bot (which already has Administrator →
   Manage Channels + Move Members) and the existing Telegram bridge.
4. **No notification fatigue.** For ~16 people, careless pinging is worse than
   silence. Every notification path must be **deduped, rate-limited,
   quiet-hours-aware, opt-in for @-mentions, and self-cleaning.**
5. **Comfort & consent.** Shy learners must never feel exposed. Presence
   broadcasting is low-pressure; being *@-pinged* is **opt-in**.
6. **Bilingual, Arabic-first**, and **bidi-safe** (project text rules).
7. **Owner stays in control:** every surface is flag-gated and owner-tunable;
   the owner can turn any piece off instantly without a redeploy.
8. **Scale (5-year / 10× rule):** the design must work cleanly from 16 to ~160
   students with **no manual channel babysitting** and no mess.
9. **Privacy:** presence is **ephemeral** — we track "who is in a lounge right
   now / minutes today" for the task, not a durable surveillance log.

## Live baseline (verified against the running guild, 2026-07-31)

- Category **`🌍 المجتمع | COMMUNITY`** contains the voice channel
  **`voice-lounge`** and the text channel **`#general-chat`**.
- Level categories each have practice voice rooms (`l0-voice-1/2`,
  `l1-voice-1/2`, `l2-voice-1/2` + `l2-debate`, `l3-voice-1/2` + `l3-debate`).
- **Every voice channel has `user_limit = 0` (unlimited).**
- Task #7 currently credits **any** voice channel → students scatter across
  rooms and never meet.
- Bot has **Administrator** (Manage Channels, Move Members confirmed).

## Glossary

- **Majlis / lounge:** the COMMUNITY-category voice room(s) where task #7 social
  time happens (`voice-lounge` = "Majlis 1"; overflow rooms = "Majlis 2/3…").
- **Together-time:** minutes a student spends in a Majlis lounge **while at least
  one other member is also present.**
- **Beacon:** a short, self-cleaning invite the bot posts to `#community-live`
  when someone is waiting in a mostly-empty Majlis.
- **Community Hour:** a scheduled window when everyone aims to show up together.
- **Pods:** small groups (~2–5). A lounge has a hard capacity cap; overflow
  spawns a new lounge.

---

## Requirements

### R1 — Humane, company-aware credit for task #7 (the complaint fix)
**User story:** As a student, I don't want to be forced to sit alone for 10
minutes; if I show up and genuinely connect with someone, that should count —
and if I'm alone, I should still never be worse off than today.

Acceptance criteria:
1. THE SYSTEM SHALL keep the existing completion path valid: **10+ minutes in
   any voice channel today AND a `#general-chat` message today → task #7
   complete.** (Backwards-compatible; unchanged.)
2. THE SYSTEM SHALL add a **faster "together" path**: WHEN a student accumulates
   **≥ `together_minutes` (default 5)** of *together-time* in a Majlis lounge
   today AND has posted in `#general-chat`, THE SYSTEM SHALL mark task #7's voice
   half complete — even though it's under 10 minutes — because real interaction
   occurred.
3. THE SYSTEM SHALL treat these as an **OR**: the voice half is satisfied by
   (10 min any voice) **OR** (`together_minutes` of together-time in a Majlis).
   A student is therefore **never worse off** than today.
4. WHEN task #7 is incomplete, THE SYSTEM SHALL show a bilingual checklist that
   reflects whichever path is closer (e.g. "أنت مع ٢ في المجلس — كمّل ٣ دقايق"
   vs. the solo "X/10 دقيقة").
5. `together_minutes` SHALL be an owner-tunable config value.

### R2 — Presence beacon (turn waiting into an invitation)
**User story:** As a student who just entered the lounge alone, I want others to
know I'm here so they can join me, instead of me sitting in silence.

Acceptance criteria:
1. WHEN a member joins a Majlis lounge and the lounge is in the **"lonely/lively"
   band** (occupancy between 1 and `beacon_max_occupancy`, default 4), THE
   SYSTEM SHALL post a short, bilingual, Arabic-first **beacon** to a dedicated
   **`#community-live`** text channel with a **jump link** to the lounge.
2. THE SYSTEM SHALL **not** beacon when the lounge is already "healthy"
   (≥ `beacon_max_occupancy` present) — notifications stop once it's lively.
3. THE SYSTEM SHALL **never** address the beacon to the person who just joined.
4. THE SYSTEM SHALL **debounce**: at most one active beacon per lounge per
   `beacon_cooldown_min` (default 40), so joins/re-joins can't spam.
5. THE SYSTEM SHALL **self-clean**: edit/remove the beacon when the lounge
   empties or the beacon expires, so `#community-live` stays tidy.
6. THE SYSTEM SHALL respect the existing **quiet-hours** window (no beacons
   during quiet hours).

### R3 — Notification discipline (professional, not spammy)
**User story:** As the owner, I want this to feel premium — helpful pings, never
noise.

Acceptance criteria:
1. THE SYSTEM SHALL keep **all** presence chatter in the dedicated
   `#community-live` channel (not `#announcements`, not `#general-chat`).
2. THE SYSTEM SHALL only **@-mention** members who have **opted in** (R5);
   everyone else sees the beacon post without a ping.
3. THE SYSTEM SHALL rate-limit every notification path (per-lounge and global
   caps) and respect quiet hours.
4. THE SYSTEM SHALL reserve **Telegram** broadcasts for **high-signal events
   only** (Community Hour start — R6), never per-join beacons.
5. Every automated message SHALL be bilingual (Arabic-first) and bidi-safe.

### R4 — Tidy small pods (never a mob)
**User story:** As a student, I want the room I join to be a small, comfortable
group where I can actually talk — not a chaotic crowd.

Acceptance criteria:
1. THE SYSTEM SHALL enforce a **hard capacity cap** on each Majlis lounge
   (`lounge_capacity`, default **6**; ideal pod 2–5).
2. WHEN all Majlis lounges are at/near capacity, THE SYSTEM SHALL make an
   **overflow lounge** available so newcomers get a fresh small room rather than
   piling into a full one.
3. THE SYSTEM SHALL support **dynamic overflow rooms**: a **"➕ افتح مجلس / New
   Room"** join-to-create voice channel that, on join, spawns a new capped
   Majlis lounge and moves the member into it.
4. THE SYSTEM SHALL **auto-delete** dynamically created lounges when they become
   empty (with a short grace period), so the channel list never bloats.
5. THE SYSTEM SHALL keep the **level practice rooms** (`l0-voice-*`, etc.)
   untouched and separate from Majlis lounges.
6. The beacon (R2) SHALL point newcomers toward a lounge in the "lively but not
   full" band, load-balancing across lounges.

### R5 — Opt-in pings & "Knock" (comfort + consent)
**User story:** As a shy student, I don't want to be pinged constantly; as an
eager one, I want to summon people when I'm free.

Acceptance criteria:
1. THE SYSTEM SHALL provide an **opt-in role** (e.g. `community-pings`) that a
   student can toggle themselves (button/command). Only opted-in members get
   @-mentioned by beacons.
2. THE SYSTEM SHALL provide a **"👋 Knock"** action (button in `#community-live`
   and/or a `!knock` command) that lets a member proactively signal "I'm in the
   Majlis, who's free?" — pinging the opt-in role, subject to the same
   dedup/quiet-hours/rate limits.
3. Opting in/out SHALL be self-service and reversible at any time.

### R6 — Community Hour (scheduled overlap)
**User story:** As a student, I want a predictable time when everyone shows up,
so meeting people isn't left to luck.

Acceptance criteria:
1. THE SYSTEM SHALL support an owner-configurable **Community Hour** schedule
   (days + start time + timezone). **Owner-confirmed default: 21:00–22:00 Egypt
   time (`Africa/Cairo`), i.e. `community_hour_start = "21:00"`,
   `community_hour_minutes = 60`.** NOTE: the students are Egyptian, so
   Community Hour is scheduled in **`Africa/Cairo`** — deliberately independent
   of the daily-task schedule, which runs on `Asia/Dubai`. The scheduler MUST
   use the configured Community Hour timezone, not the daily-task timezone.
2. AT the window start, THE SYSTEM SHALL post a rally in `#community-live` **and**
   broadcast **once** to the student Telegram group(s) (the single high-signal
   Telegram path), bilingual, with a topic prompt and a lounge jump link.
3. DURING the window, the "together" path (R1) SHALL make task #7 trivially easy
   (everyone is present at once).
4. Community Hour SHALL be independently flag-gated and fully skippable.

### R7 — Topic-of-the-day (light structure so a pod ≠ chaos)
**User story:** As a student in a small group, I want a conversation starter so
we're not staring at each other.

Acceptance criteria:
1. THE SYSTEM SHALL maintain a rotating, level-appropriate **conversation prompt**
   and surface it in `#community-live` (and/or the lounge's text area) daily
   and at Community Hour start.
2. Prompts SHALL be curated content (bilingual), owner-editable, and never
   block completion of task #7.

### R8 — Reward togetherness (gamify meeting, not waiting)
**User story:** As a student, I want a little recognition when I actually
connect with someone, so the *connection* is the reward — not the clock.

Acceptance criteria:
1. WHEN a student completes task #7 via the **together path** with ≥1 other
   member present, THE SYSTEM MAY grant a small bonus/acknowledgement (e.g. a
   "🤝 مجلس" note, optional bonus points) — flag-gated and config-tunable.
2. THE SYSTEM SHALL NOT penalize the solo path; togetherness is a *bonus*, not a
   requirement.
3. Any bonus SHALL be modest and abuse-resistant (once/day, real distinct
   members present).

### R9 — Owner controls, config & flags
**User story:** As the owner, I want to see what's happening and tune every knob
without a deploy.

Acceptance criteria:
1. THE SYSTEM SHALL expose an owner command (Discord admin channel + Telegram)
   to **view live Majlis state** (who's in which lounge, active beacons) and the
   current config.
2. THE SYSTEM SHALL store all tunables (`together_minutes`, `lounge_capacity`,
   `beacon_max_occupancy`, `beacon_cooldown_min`, Community Hour schedule, etc.)
   in `settings` with sane defaults and getters/setters (audit-logged).
3. Each capability SHALL be behind its **own feature flag** (default OFF):
   `community_together_credit`, `community_lounge_beacon`,
   `community_dynamic_rooms`, `community_pings_optin`, `community_power_hour`,
   `community_together_reward`.
4. Slash commands work in the admin channel; the `!` prefix does not there —
   owner controls SHALL be exposed as `/` and/or via Telegram (per the known
   admin-channel behavior).

### R10 — Zero disruption & graceful degradation
Acceptance criteria:
1. WITH all flags OFF, behavior SHALL be **identical to today**.
2. IF Discord denies a channel op (create/move/limit) or an API call fails, THE
   SYSTEM SHALL degrade gracefully (fall back to the existing static lounge and
   the 10-min path) and never crash the bot or block task completion.
3. Voice/presence tracking SHALL survive a bot restart (reuse the existing
   persisted-voice-minutes mechanism).

### R11 — Scale (16 → 160)
Acceptance criteria:
1. Dynamic rooms + caps + capacity-aware beacon SHALL scale without manual
   admin: more people → more small pods, automatically created and reaped.
2. Notification volume SHALL stay bounded (caps are per-lounge and global), so
   growth doesn't mean noise.

### R12 — Privacy
Acceptance criteria:
1. Presence data SHALL be **ephemeral/aggregate** (current occupancy, minutes
   today) — no durable "who talked to whom" surveillance log.
2. No presence data SHALL be exposed outside the guild or to other students
   beyond the transient beacon ("X is in the Majlis now").
