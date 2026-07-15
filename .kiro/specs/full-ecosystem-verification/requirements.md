# Requirements — Hisn (حِصن): Full Ecosystem Verification

> **Codename:** Hisn (حِصن — "fortress/stronghold") — because this is the
> final defensive wall before real students enter the system. Nothing
> gets through untested.
> **Purpose:** Exhaustively verify EVERY piece of the Empire English
> ecosystem — every Discord command, every channel, every feature flag,
> every practice-platform page, every API endpoint, every cross-system
> integration, every notification, every AI fallback path — built across
> all 9 initiatives (Aegis, Bawaba, Nabd, Tatawwur, Sahel, Dhaka', Nour,
> Markaz, Wuslah) since project start. This is the last gate before the
> 16 real students are invited. Nothing is out of scope. Nothing is
> sampled. Everything that was built gets checked.
> **Context:** 39 Discord commands, ~55 channels across 10 categories,
> 38 feature flags, 1,334 practice-platform HTML pages, 11 API endpoints,
> 20+ database tables, and countless cross-system flows have accumulated
> over many sessions. No single test pass has ever verified the whole
> thing at once — each initiative was tested in isolation as it was
> built. This is the first (and mandatory) full-system pass.

## Core Principle

**If it was built, it gets tested. If it's not tested, it's not trusted.
If it's not trusted, students don't see it.**

No feature is "probably fine because it compiled" or "probably fine
because we tested it two months ago before three other initiatives
touched the same code." Everything gets re-verified in its CURRENT,
final, all-initiatives-merged state — because that's the state real
students will actually experience.

---

## Requirements

### R1 — Complete Discord Command Inventory Testing
EVERY one of the 39 Discord commands MUST be executed at least once
against the live (or a faithful staging replica of the) production
bot, with both valid and invalid/edge-case arguments. Acceptance
criteria:
- A master command checklist exists covering all 39 commands +
  Arabic aliases (`!تم`, `!إشعارات`, `!صوتي`, `!قدراتي`, `!ربط`)
- Each command tested with: no args, valid args, invalid args,
  wrong permission level (student running admin command), Arabic
  input, emoji input, oversized input (2000+ chars)
- Every command's response is captured and reviewed for correctness,
  tone, and Discord 2000-char limit compliance
- Admin-only commands verified to correctly REJECT non-admin users

### R2 — Complete Channel & Permission Audit
EVERY Discord channel across all 10 categories MUST be verified for
correct visibility, permissions, and content. Acceptance criteria:
- A channel-by-channel checklist (all ~55 channels) confirms: correct
  role visibility (who can see it), correct posting permissions (who
  can post), correct pinned/welcome content if applicable
- Level-gated channels (l0/l1/l2/l3 voice/text/showcase/questions)
  verified to be invisible to students below that level
- Ghost Testing category confirmed isolated from real channels (no
  test content leaks to production channels)
- Admin/Mod-only channels confirmed invisible to regular members

### R3 — Complete Feature Flag Verification
EVERY one of the 38 feature flags MUST be verified in both enabled
and disabled states. Acceptance criteria:
- A flag-by-flag checklist confirms: `!flag list` shows it correctly,
  `!flag enable`/`!flag disable` actually changes behavior, the
  default state matches what's documented in `flag_registry.py`
- At least one full "kill switch" drill: disable a critical flag
  (e.g. `nour_concierge`) mid-session and confirm the feature stops
  cleanly with no crash, then re-enable and confirm recovery
- Flags with `allowed_ids` (beta allowlist) tested for correct
  restriction behavior

### R4 — Complete Practice Platform Coverage
ALL 1,334 practice-platform pages MUST be verified programmatically
(not manually clicked one-by-one) for structural correctness, and a
statistically meaningful human-reviewed sample MUST be walked through
manually. Acceptance criteria:
- An automated crawler/validator checks EVERY page for: valid HTML,
  no broken audio links, no broken internal links, correct exercise
  type rendering, no console JS errors, mobile viewport correctness
- At least 1 full day (all 4 exercise types) from EVERY level (L0-L3)
  is manually walked through by a human on both desktop and mobile
- The `/dash/` dashboard and `/review/` SRS page are fully manually
  tested with a real linked student account
- PWA install flow and offline mode tested on a real mobile device

### R5 — Complete API Endpoint Testing
ALL 11 API endpoints MUST be tested with valid, invalid, and
adversarial inputs. Acceptance criteria:
- Every endpoint tested with: valid token, invalid token, missing
  token, expired token, malformed JSON body, oversized payload,
  SQL-injection-style strings, XSS-style strings, rapid-fire requests
  (rate limit verification)
- CORS headers verified correct from the actual practice platform
  origin
- Every endpoint's error responses verified to never leak internal
  details (stack traces, file paths, other students' data)

### R6 — Complete Cross-System Integration Testing
EVERY data flow between Discord, the web platform, the database, and
Telegram MUST be traced end-to-end and verified consistent. Acceptance
criteria:
- Web exercise completion → Discord streak update → points → dashboard
  refresh (full round-trip, Wuslah W2)
- Discord `!done` → practice platform dashboard reflects it within
  one page reload (no double-counting either direction)
- Discord escalation → Telegram alert → owner reply → student DM
  (Markaz M2 full round-trip)
- `!link` token generation → practice platform connection → dashboard
  data accuracy
- Notification preference change on web → respected by next Discord
  DM (Wuslah W5)

### R7 — Complete AI Fallback Chain Testing
EVERY AI-dependent feature MUST be verified to degrade gracefully
through its full fallback chain. Acceptance criteria:
- Nour: Groq → Gemini → template response, tested by simulating each
  failure point (invalid Groq key, invalid Gemini key, both invalid)
- Pronunciation scoring: Groq Whisper failure handled without crashing
  the submission flow
- Nour study tips: AI generation failure falls back to generic tips
  (never returns empty)
- Weekly self-review: AI failure doesn't block the scheduled task loop

### R8 — Complete Notification Timing & Content Audit
EVERY scheduled notification (Nabd + Markaz) MUST be verified to fire
at the correct time with correct, well-formatted content. Acceptance
criteria:
- Morning kickstart (6:05 AM), evening reminder (8 PM), streak alert
  (9 PM), weekly summary (Friday), absence recovery ladder (day 2/3/5/7)
  — each manually triggered/simulated and content reviewed
- Markaz daily digest (7 AM), weekly report (Sunday 9 AM), monthly
  summary (1st of month) — each manually triggered and content reviewed
- All notification content checked for: correct grammar, correct
  Arabic/English mix per Bawaba's gradual-English rules, no raw
  template variables leaking (`{name}` unrendered), Discord/Telegram
  length limits respected

### R9 — Database Integrity Verification
The database MUST be verified free of corruption, orphaned records,
and constraint violations after the full test campaign. Acceptance
criteria:
- No orphaned rows (foreign keys pointing to deleted members)
- No duplicate `daily_submissions` for the same (discord_id, date,
  task_id) — UNIQUE constraint actually holds under concurrent test load
- `link_tokens` expiry cleanup verified to not delete active tokens
- A full backup exists BEFORE testing begins (so any test-induced
  corruption is trivially reversible)
- Test data is clearly tagged and fully removable without touching
  real data (there is none yet, but the removal mechanism must be proven)

### R10 — Concurrent Load / Multi-Student Simulation
The system MUST be verified to behave correctly when multiple students
act simultaneously (the real launch-day scenario). Acceptance criteria:
- Simulate 16+ concurrent `!join` registrations
- Simulate 16+ concurrent `!done` submissions for the same task/day
- Simulate concurrent web dashboard loads + API calls
- No race conditions in streak updates, points, or leaderboard ranking
  (the `MAX()`-based atomic update pattern from earlier fixes is
  specifically re-verified under real concurrency, not just reasoned
  about)

### R11 — Human Experience Walkthrough (Effectiveness, Not Just Correctness)
A human (the owner, and ideally 1-2 trusted others) MUST walk through
the ENTIRE new-student journey exactly as a real student would, judging
not just "does it work" but "does it feel good." Acceptance criteria:
- Full journey: join Discord → onboarding DMs → first task → first
  week → first escalation → first web dashboard visit → first
  notification of each type
- Explicit judgment recorded on: clarity, tone, pacing, whether Arabic
  support actually feels supportive, whether Nour feels helpful or
  robotic, whether the dashboard is genuinely motivating
- Any point where a real beginner (zero English) would likely get
  confused or stuck is flagged, even if the system "worked correctly"

### R12 — Defect Tracking & Resolution
Every issue found during the campaign MUST be logged, triaged, and
resolved (or explicitly deferred with reasoning) before sign-off.
Acceptance criteria:
- A single running defect log (severity: blocker / major / minor /
  cosmetic) is maintained throughout
- Every "blocker" and "major" defect is fixed and RE-TESTED before
  the campaign is considered complete
- A final go/no-go checklist exists and is explicitly reviewed with
  the owner before any student invitation is sent

---

## Constraints

- Testing MUST happen against the real production server/database OR
  a byte-for-byte faithful staging copy — no testing against a
  simplified mock that could hide real integration bugs
- Testing MUST NOT disrupt the live Discord server's existing content
  (the Ghost Testing category exists specifically for this — use it)
- Testing MUST NOT incur meaningful additional cost (stay within
  existing Groq/Gemini free tiers where possible; flag if load testing
  would risk exceeding them)
- A full database backup MUST exist before any destructive/concurrent
  testing begins
- The campaign should be completable by one operator (the owner) with
  AI-driven automation doing the heavy repetitive lifting — this is
  not a QA team, it's one person + Kiro

## Out of Scope

- Load testing at a scale beyond realistic near-term growth (16
  students, not 16,000) — this is a readiness check, not a scalability
  benchmark
- Penetration testing / security audit as a distinct discipline (basic
  adversarial input testing is in scope via R5, a full pentest is not)
- Testing of deprecated/historical scripts already marked as such
  (e.g. old `Claude` repo scripts explicitly superseded by
  `setup_server.py`)
- Third-party service reliability (Discord's own uptime, Cloudflare's
  own uptime, Groq/Gemini's own uptime) — only OUR handling of their
  failures is in scope
