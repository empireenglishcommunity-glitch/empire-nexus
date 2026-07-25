# Maintenance Mode & "What's New" — Requirements

## Problem
The team ships fixes/enhancements while ~16 students are actively using the
Discord bot + practice page. During each update, students hit half-updated
states, panic that something is "broken," and flood the Discord support channel
+ Telegram groups. There is no way to signal "this is planned maintenance,"
protect their progress, or tell them what changed afterward.

## Goal
A professional, one-command **maintenance mode** across the whole ecosystem
(bot + practice page), plus an automatic **"we're back — here's what's new"**
flow and a self-updating guide. Zero surprise for students, minimal support noise.

## Requirements

### R1 — System status is a single source of truth
- R1.1 One server-side status controls both the practice page and the bot.
- R1.2 States: `live`, `maintenance`. Maintenance has a level: `soft` | `hard`.
- R1.3 Status carries: level, human reason, ETA, started-at, optional custom message.
- R1.4 A public, unauthenticated `GET /api/status` returns the current status
  (network-first on the client, never cached stale).

### R2 — Practice page reacts to status (ship once, toggle live)
- R2.1 On every page load the page checks status; no page redeploy needed to
  start/stop maintenance.
- R2.2 **Soft**: a dismissible banner ("updates in progress, minor glitches
  possible") — page stays usable.
- R2.3 **Hard**: a full-screen, non-dismissible overlay — content is not usable.
- R2.4 Both are bilingual (English + Arabic MSA), show the ETA when set, and
  prominently reassure: **"your streak & progress are 100% safe."**

### R3 — Owner controls it with one command
- R3.1 `maintenance start [soft|hard] [eta] [reason]`, `maintenance end`,
  `maintenance status` — owner-only.
- R3.2 Available via the Markaz **Telegram** ops bot and via **Discord** (owner-only).
- R3.3 Starting/ending broadcasts to students (see R4).

### R4 — Student communication (fan-out)
- R4.1 On start: notify Discord `#announcements`; set the bot's Discord presence
  to a maintenance status; optionally notify configured Telegram groups.
- R4.2 On end: broadcast **"✅ Back online — what's new"** with the changelog
  to the same channels.
- R4.3 Telegram-group targets are optional/config-driven; if group chat IDs are
  not configured, skip gracefully (Discord still fires).

### R5 — Progress & streak protection (the anxiety-killer)
- R5.1 While maintenance is active, a day must **not** break any student's streak.
- R5.2 Messaging everywhere states progress/streaks are protected.

### R6 — Failsafes
- R6.1 **Auto-resume:** maintenance auto-ends after a max window (default 2h) so
  students are never left locked out if `end` is forgotten.
- R6.2 Owner-only for all controls (fail-safe: unknown identity = not owner).
- R6.3 If `/api/status` is unreachable, the page fails **open** (assume live) —
  never trap a student behind a false maintenance screen.

### R7 — Changelog / "What's New" + guide
- R7.1 A single changelog is the source of truth for release notes.
- R7.2 On `end`, the latest entry is broadcast (R4.2).
- R7.3 Returning students see a one-time, dismissible "✨ What's New" note on the
  practice page after an update.
- R7.4 The guide page (`/guide`) shows a "Latest updates / آخر التحديثات"
  section kept current from the changelog.

## Non-goals
- Not a public status page for non-students.
- Not per-student maintenance (it's global).
- No git-history rewrite; no change to how students authenticate.

## Constraints
- Zero disruption to live students during rollout; each phase independently
  shippable, tested, owner-merge-gated, deploy + live-verified.
- Reuse existing infra (settings table, ops `@command`, `/announce` pattern,
  network-first service worker).
