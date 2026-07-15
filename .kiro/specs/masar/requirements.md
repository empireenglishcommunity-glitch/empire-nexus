# Requirements — Masar (مسار): Personal Growth Narrative

> **Codename:** Masar (مسار — "path/journey") — because the goal is to
> turn the ecosystem's existing, already-collected data about each
> student into a coherent, honest, personal STORY about their own path
> through it, told in Nour's voice — not four disconnected widgets.
> **Purpose:** Fix D012 (the dashboard's level badge and XP progress bar
> measure two unrelated things, confusing students about their own
> progress) and D020 (the "AI-generated weekly study tips" feature was
> designed in the Wuslah spec but its core generation task, W4.2, was
> never built — every real student has always silently received only
> generic fallback tips) by treating them as the SAME underlying gap,
> not two separate bugs: the ecosystem has rich per-student data
> (Nour's own extracted memories, 12 ability milestones, pronunciation
> trends, SRS mastery, adaptive difficulty) that is collected but
> barely communicated back to the student in a way that feels personal
> or true.
> **Context:** Found during Hisn (the pre-launch full-ecosystem
> verification campaign) — D012 and D020 were both logged as deferred
> defects, then the owner asked to brainstorm something bigger and more
> durable rather than patch them individually. No launch-timeline
> pressure was set for this work ("time is not an issue, the most
> important is to build something professional that lasts and is
> strong") — Masar is scoped and phased accordingly, and is explicitly
> allowed to complete on its own schedule, separate from Hisn's own
> Go/No-Go gate.

---

## Core Principle

**Tell each student a true, specific story about their own path — in
Nour's voice, using data the system already has.**

Every existing display of "progress" (level badge, points bar,
milestone grid, study tips) should either be replaced or clearly
justified against this principle. If a number or badge doesn't map to
something a student can understand and act on, it should be fixed or
removed — not left ambiguous. Nothing here invents new data collection;
everything is built from data this ecosystem already gathers
(`nour_memories`, `ability_milestones`, `pronunciation_scores`,
`vocab_srs`, `difficulty_level`, `nour_conversations`).

---

## Requirements

### R1 — Resolve the Level/Progress Ambiguity (fixes D012)
The dashboard MUST NOT present two differently-computed "progress"
signals (assessment-based level badge vs. a points-threshold bar) as
if they were the same thing. Acceptance criteria:
- The level badge (assessment-based, a real skill certification)
  remains unchanged in meaning and computation — it must not be
  weakened or hidden.
- The existing XP/points bar is either (a) relabeled and re-scoped so
  its own displayed name accurately describes what it measures, with
  no implication that it tracks level-up, or (b) removed and replaced
  by R2's Momentum Score, whichever the design phase determines serves
  students better. Ambiguous, half-true labeling is not an acceptable
  end state.
- Whatever replaces or clarifies the bar must be understandable by a
  true beginner (L0, possibly limited English) without explanation —
  bilingual Arabic/English labeling, consistent with the rest of the
  ecosystem's UI convention.

### R2 — Momentum Score (a single, honestly-computed "how am I doing lately" signal)
Students SHOULD see one clearly-labeled, honestly-computed indicator
of recent consistency and engagement, distinct from level. Acceptance
criteria:
- Computed from real recent behavior (streak, task completion rate,
  pronunciation trend direction) over a defined recent window (e.g.
  7 days) — not a lifetime points total.
- Clearly labeled as being about recent consistency/momentum, not
  about level progression or points — no ambiguity with R1's fix.
- Visible on both the Discord `!progress` command output and the web
  dashboard (`/dash/`) — the two surfaces must not diverge in what
  they claim about the same student at the same moment.

### R3 — Nour's Weekly Growth Letter (fixes D020, replaces the never-built AI tips engine)
Once weekly, each active student MUST receive a short, personal
message from Nour that demonstrably uses real, specific data about
that student — not a generic template. Acceptance criteria:
- Content is built from at least 2 of: `nour_memories` (things Nour
  has actually learned about this student from conversation),
  `pronunciation_scores` trend, `vocab_srs` mastery/due state,
  `ability_milestones` recently unlocked, `difficulty_level` changes,
  recent `nour_conversations` themes.
- Written in Nour's existing established voice/personality (the same
  warm, Egyptian-Arabic-inflected, mentor-like tone already defined in
  `nour_personality.py`/`nour_concierge.py`) — this is a NEW surface
  for an EXISTING personality, not a new voice.
- Delivered as a Discord DM AND surfaced on the web dashboard (same
  content, two places) — replacing the current dashboard's generic
  "Nour's Study Tips" 3-bullet display, not living alongside it.
- MUST use the same AI-provider fallback discipline already
  established elsewhere in this codebase (a real generation attempt,
  fallback provider, and a graceful non-AI fallback that is still
  personal-feeling, e.g. built from milestones/streak data via
  template rather than raw AI, never a generic "no tips" or silence).
- MUST NOT re-introduce the exact W4.2 gap (a docstring/flag claiming
  AI generation happens when it doesn't) — the actual generation task
  must be built and demonstrably running, verified live before this
  requirement is considered met, not just code-reviewed.

### R4 — Milestone Moments (personalized unlock messages)
When a student unlocks one of the 12 existing `ability_milestones`,
Nour SHOULD send an in-the-moment personalized message about it, not
a generic "🏆 Unlocked!" notification. Acceptance criteria:
- Triggered from the existing `complete_milestone()` call site — no
  new milestone logic, only a new notification hook.
- Message content should reference real, specific context about that
  student where available (e.g. how long they've been working toward
  it, related memory/conversation Nour has), falling back to a warm
  but still milestone-specific template if no extra context exists.
- Respects existing notification preferences (`celebrations` flag in
  `notification_preferences`) and quiet hours — this is a new message
  TYPE, not a new notification CHANNEL/exemption.

### R5 — Adaptive Difficulty Transparency
When the existing Dhaka' adaptive engine (`adaptive_engine.py`)
changes a student's `difficulty_level`, the student SHOULD be told,
honestly and briefly, in Nour's voice. Acceptance criteria:
- Triggered from the existing difficulty-adjustment call site — no
  changes to the adaptive logic itself, only a notification hook.
- Message is honest about direction (harder or easier) and frames it
  positively regardless of direction (harder = "you're ready for
  more," easier = "let's build confidence first," never framed as a
  penalty).
- Does not fire on every single micro-adjustment if the engine
  adjusts frequently — batched/throttled so students aren't spammed
  (exact threshold is a design-phase decision, not a requirements
  constraint).

### R6 — Data Honesty Audit (process requirement, not a feature)
Before Masar is considered complete, every existing student-facing
progress/achievement/personalization display in the ecosystem (web
dashboard cards, `!progress`, `!streak`, `!level`, milestone grid,
leaderboard) MUST be reviewed against the Core Principle above and
either confirmed honest-and-clear or fixed. Acceptance criteria:
- A written checklist of every such display, with a pass/fail judgment
  and rationale, produced during the design phase.
- Any display found to be misleading (showing a number without a
  clear, truthful meaning) is either fixed within Masar's scope or
  explicitly logged as a new deferred defect with owner sign-off to
  defer it — not silently left as-is.

---

## Constraints

- No new infrastructure: same Hetzner VPS, same SQLite DB, same
  Cloudflare Pages static site, same AI providers (Groq/Gemini)
  already configured.
- No new authentication: uses the existing link-token system.
- Must not regress any already-verified-working behavior from Hisn's
  H0-H5 phases (e.g. must not reintroduce a feature-flag-bypass gap
  like D010, must not break the dashboard's already-confirmed-correct
  data aggregation).
- All new scheduled tasks must follow the D022 lesson from Hisn:
  checked against every existing `@tasks.loop` time to avoid new
  same-instant DM collisions.
- All new AI call sites must follow this codebase's established
  fallback discipline (confirmed working in Hisn H4.1-H4.3): real
  attempt → fallback provider → graceful non-silent fallback.
- Every new or changed student-facing message must be bilingual
  (Arabic primary / English secondary or vice versa, matching
  existing convention per surface) — no English-only additions in a
  system built for Arabic-speaking beginners.
- Masar's own completion is independent of Hisn's Go/No-Go timeline —
  per explicit owner instruction, this should be built right, not
  rushed to fit before student invitations.

---

## Out of Scope (for now)

- Redesigning the 12 existing milestones themselves (their names,
  count, unlock conditions) — Masar changes how unlocks are
  communicated, not what they are.
- A full "Growth Profile" page/redesign of the entire dashboard layout
  — discussed as a bigger, later-phase idea; not required for Masar's
  own completion. May be proposed as a future initiative if Masar's
  early phases prove valuable.
- Any change to the underlying adaptive difficulty ALGORITHM — only
  adding a transparency notification on top of existing decisions.
- Real-time (non-scheduled) personalization — Masar's Growth Letter
  and Milestone Moments are triggered by existing scheduled
  tasks/event hooks, not a new real-time pipeline.
- Payment/monetization framing of any of this (e.g. "premium insights")
  — out of scope entirely, no such framing anywhere in this spec.
