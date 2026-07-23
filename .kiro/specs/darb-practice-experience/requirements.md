# Darb (درب) — Gated Personal Practice Experience — Requirements

> **Codename:** Darb (درب, "the path/trail one walks").
> **Status:** Draft for owner approval. Nothing here is executed until the
> phased plan in `tasks.md` is approved and worked through in order.
> **Spans two repos:** `empire-nexus` (Discord bot, API, database) and
> `empire-dojo` (the practice platform / Cloudflare Pages site).
> **Author:** Kiro, 2026-07-22.

## Background / Why this exists

The practice platform (`practice.empireenglish.online`) and the Discord
bot are the two halves of a paid learning product, but the seam between
them is currently rough and — critically — **the paid content is not
actually protected.** The owner asked for a single, coherent overhaul.
Real, paying students (15 live at time of writing, all Level 0) are
already using the system, so **every change must be safe and reversible,
and nothing may break the experience for current students mid-flight.**

The overhaul has one guiding principle the owner stated plainly:

> This is paid content and a paid community. It must be genuinely gated —
> anyone opening a link must not get access — and each student should
> walk their own personal daily path from the day they joined, never
> feeling "late."

## Problems being solved (all verified in code, not assumed)

1. **The gate is cosmetic.** Lesson content ships inside every page's
   HTML; the "lock" is a CSS/JS overlay. View-source, dev-tools, or
   disabling JS exposes 100% of paid content with no token.
2. **A lock screen flashes on every page load** (the overlay renders
   before the async token check resolves), and the homepage briefly
   renders then auto-redirects — both look broken/unprofessional.
3. **The practice page shows all four levels** to every student,
   regardless of their actual Discord level role.
4. **"We feel late / we missed days."** The bot advances curriculum by
   calendar time (`week = days_since_join // 7 + 1`), so missing days
   silently pushes students forward; days have names (Sat–Fri) but no
   dates, and there is no per-student calendar.
5. **Access tokens are permanent and reusable**, trivially shareable —
   no protection against a student handing their link to non-payers.
6. **Inconsistent / dead UI:** a "Connect Discord" button that some see
   and some don't, plus a useless "Join Discord" invite button.
7. **Per-task deep links clutter the daily message** (a link on all 7
   tasks plus a general link).

## Constraints (hard requirements on HOW we build)

- **C1 — Do no harm to live students.** Each phase must be independently
  shippable and verifiable; no phase may leave current students worse off
  than before it. Prefer additive, reversible changes.
- **C2 — $0 budget, no new vendors.** Use what already exists: Cloudflare
  Pages (incl. Pages Functions), the existing aiohttp bot API, SQLite,
  the existing Telegram alert path. No paid services, no second server.
- **C3 — No secrets in git.** Any signing key / shared secret lives in
  server `.env` and the Cloudflare Pages environment, never committed.
- **C4 — Preserve bilingual AR/EN** throughout, Arabic-primary for
  student-facing text (matches the rest of the ecosystem).
- **C5 — Server is the single source of truth** for identity, level,
  completion, and mastery — never the browser (localStorage is a cache
  only, never authority).
- **C6 — Manual deploy discipline** for `empire-dojo` (no CI/CD): every
  practice-page change is deployed with `npx wrangler pages deploy site
  --project-name=empire-practice --branch=main` and verified live.

---

## Requirements

### R1 — Consolidated daily task message
**User story:** As a student, I want one clear daily message that tells me
exactly what to do and where, so I'm never confused by clutter.

Acceptance criteria:
1. WHEN the bot posts daily tasks or sends the morning DM, THE SYSTEM
   SHALL include exactly **one** practice-platform link: the intro link
   `practice.empireenglish.online` (no per-task deep links).
2. THE SYSTEM SHALL group the 7 tasks into two clearly-labelled sections:
   **🌐 On the practice platform** (accent, vocabulary, shadowing,
   listening) and **💬 Here on Discord** (speaking, writing, community).
3. THE message SHALL remain bilingual (Arabic-primary) and within
   Discord's 2000-char limit per message.
4. WHEN this change ships, THE SYSTEM SHALL NOT alter task verification,
   streaks, or points behavior.

### R2 — Remove dead UI and eliminate the gate flash
**User story:** As a student, I want the app to feel polished — no
flashing lock screens, no useless buttons.

Acceptance criteria:
1. THE SYSTEM SHALL remove the "Join Discord" invite button from the
   practice pages and homepage.
2. WHEN a returning, authorized student loads any page, THE SYSTEM SHALL
   NOT display any lock/gate screen even momentarily (no visible flash).
3. THE SYSTEM SHALL present a single, consistent "connect" experience
   (no more "some see Connect Discord, some don't" and no duplicate
   connect UIs).
4. THE homepage SHALL NOT render-then-auto-redirect in a way that
   produces a visible flash.

### R3 — True gating (content is never delivered without a valid session)
**User story:** As the owner, I want paid content genuinely protected, so
that opening a link without authorization yields nothing.

Acceptance criteria:
1. WHEN any practice-platform URL is requested without a valid signed
   session, THE SYSTEM SHALL serve only a gate/claim page and SHALL NOT
   deliver any lesson content (HTML, audio, or data).
2. THE gating SHALL be enforced at the edge (before content is served),
   not by hiding already-delivered content in the browser.
3. Disabling JavaScript, viewing source, or inspecting network traffic
   SHALL NOT reveal lesson content to an unauthorized visitor.
4. THE gate decision SHALL not require a per-request round-trip to the
   bot for authenticity (signature verified at the edge), while still
   supporting revocation (R6.4).

### R4 — Level scoping (each student sees only their own level)
**User story:** As a student, I want to see only my level's content, so
I'm never confused or able to wander into content I haven't earned.

Acceptance criteria:
1. THE SYSTEM SHALL determine a student's level from their Discord level
   role (source of truth in the bot database), carried in their session.
2. THE practice homepage SHALL show only the student's own level (no
   level switcher).
3. WHEN a session for level Lx requests a page under a different level's
   path, THE SYSTEM SHALL deny it at the edge (no content served).
4. WHEN a student advances level in Discord, THE SYSTEM SHALL reflect the
   new level on their next session refresh.

### R5 — One-time claim code + durable multi-device session
**User story:** As a student, I want to unlock the platform once and stay
in, on my phone and laptop, without friction.

Acceptance criteria:
1. WHEN a student runs `!link`, THE SYSTEM SHALL issue a **single-use**
   claim code, delivered by DM, that expires if unused within a short
   window.
2. WHEN a student runs `!link` again, THE SYSTEM SHALL invalidate any
   previous unused claim code for that student (no stockpiling codes).
3. WHEN a valid claim code is entered on the gate page, THE SYSTEM SHALL
   consume it (never reusable) and issue a durable, signed device session
   bound to that student and device.
4. A device session SHALL persist across normal browsing and survive a
   reasonable period of inactivity; if a device ever loses it, running
   `!link` again SHALL restore access self-service (no admin required for
   normal use).
5. THE SYSTEM SHALL allow at most **2 active device sessions** per
   student; a 3rd claim SHALL revoke the oldest session and alert the
   owner (R6).

### R6 — Anti-abuse / anti-sharing
**User story:** As the owner, I want to detect and stop students sharing
their paid access.

Acceptance criteria:
1. THE SYSTEM SHALL log the IP and device/user-agent for each session
   creation and use.
2. WHEN a student's access is used from more than the allowed devices, or
   from anomalous locations, THE SYSTEM SHALL send the owner a Telegram
   alert with the details.
3. THE content pages SHALL display a faint, per-student visible watermark
   (their name/ID) as a sharing deterrent.
4. THE owner SHALL be able to revoke a student's session(s) so that the
   next gate check fails (instant lockout on investigation).
5. Claim-code generation SHALL be rate-limited to prevent bulk generation.

### R7 — Personal, join-anchored calendar
**User story:** As a student, I want a calendar that starts the day I
joined, so I always know exactly what to do today and never feel behind.

Acceptance criteria:
1. THE calendar SHALL anchor **Day 1 = the student's join date**; content
   (week, day) for calendar-day D SHALL be week=`(D-1)//7+1`,
   day=`(D-1)%7+1`, scoped to the student's level.
2. Each day cell SHALL show its **real date** (no bare weekday names).
3. **Today** SHALL be highlighted (yellow) with a dot on the upper-right.
4. **Completed** days SHALL be green and remain green permanently
   (server-backed, consistent across devices).
5. **Future** days SHALL be locked, labelled "opens {date}", and not
   openable before their date (enforces the daily habit).
6. **Missed** days (past, not completed) SHALL show as catch-up (amber),
   remain fully openable, and turn green when completed later
   ("Catch-Up, Never Locked Out").
7. THE "today" determination SHALL use a single server-side timezone
   (Asia/Dubai) so the calendar and the bot never disagree.
8. WHEN a student reaches the end of their level's weeks, THE calendar
   SHALL show a level-complete state with an advancement prompt (exam is
   handled in Discord).
9. Because each student's calendar is anchored to their own join date, no
   student is ever "behind" the curriculum or another student — the UI
   SHALL reinforce this (never show "late").

### R8 — Content-day-aware completion (server source of truth)
**User story:** As the owner, I want completion tracked per content-day on
the server, so the calendar and the bot always agree and work on any
device.

Acceptance criteria:
1. THE SYSTEM SHALL record completion keyed by (student, level, week, day,
   exercise) on the server — not by calendar date alone, and not in the
   browser.
2. WHEN a student completes an exercise on the practice page (including a
   caught-up past day), THE SYSTEM SHALL record it against that explicit
   (week, day, exercise) AND record activity for streak/points so the bot
   "follows their progress."
3. WHEN a completion occurs via Discord (`!done`) or record→showcase, THE
   SYSTEM SHALL write to the same shared server truth so the calendar
   reflects it.
4. A calendar day SHALL count as "done/green" when all four of its
   practice-platform exercises have been completed at least once.

### R9 — Mastery tiers (spaced-repetition gamification)
**User story:** As a student, I want revisiting a day to visibly deepen my
mastery, so I'm motivated to practice the same material until I nail it.

Acceptance criteria:
1. THE SYSTEM SHALL track a mastery **count** and **last-completed date**
   per (student, level, week, day, exercise).
2. THE SYSTEM SHALL increment an exercise's mastery tier **at most once
   per calendar day** (spaced repetition; same-day repeats do not advance
   the tier and SHALL show a "come back tomorrow" message).
3. THE tiers SHALL be 5: 🥉 Bronze (1) → 🥈 Silver (2) → 🥇 Gold (3) →
   💠 Platinum (4) → 💎 Diamond (5+), each with a distinct color.
4. THE tier decision SHALL be made server-side (the browser only displays
   what the server returns), so it cannot be reset or faked by clearing
   the browser.
5. A **day's** tier SHALL be the **minimum tier across its four
   exercises** (so a "Gold day" means all four exercises reached Gold).
6. THE calendar and exercise pages SHALL display the current tier/color.

### R10 — Record → #showcase with auto-complete
**User story:** As a student, I want to record on the practice page and
send it to Discord in one tap, without re-recording in Discord.

Acceptance criteria:
1. THE practice pages SHALL retain the existing record + playback +
   download capability.
2. THE SYSTEM SHALL provide a "Send to Discord" action that uploads the
   student's recording to their level's showcase channel on their behalf.
3. WHEN a recording is sent, THE SYSTEM SHALL auto-mark that task
   complete (no need to type `!done`).
4. WHEN a student who already completed a task via this flow later types
   `!done <task>` in Discord, THE SYSTEM SHALL respond with the normal
   "already done today" reply and SHALL NOT double-count.
5. IF reliable in-browser recording upload proves infeasible on the
   students' real devices, THIS requirement MAY be deferred without
   blocking the rest (it is isolated in its own phase).

### R11 — Bot progress reliability + end-to-end verification
**User story:** As the owner, I want to be 100% sure the bot follows every
student's progress correctly.

Acceptance criteria:
1. THE full chain SHALL be verified end-to-end on the live bot: do task →
   completion recorded → calendar turns green → mastery tier updates →
   streak/points update → `!done`/duplicate handled correctly.
2. Verification SHALL use a synthetic/ghost account, leave zero residue on
   real student data, and be documented.
3. Any defect found SHALL be fixed and re-verified before the phase is
   considered complete.

### R12 — Cross-session durability
**User story:** As the owner, I want this plan to survive session/account
changes so progress is never lost.

Acceptance criteria:
1. THIS spec (requirements/design/tasks) SHALL live in the repo and be
   kept current as phases complete.
2. `empire-chronicle/STATUS.md` SHALL point to this spec while it is the
   active initiative.
