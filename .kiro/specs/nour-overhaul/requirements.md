# Nour Overhaul — Requirements

> **Initiative #14 — Codename: Rawiya (الراوية — the narrator/guide)**
> Transforms Nour from a reactive Q&A concierge into a fully autonomous
> learning coach + operations manager who runs the community end-to-end.

## R1: Full Student Journey Guidance

**Given** a new student joins the Discord server,
**When** they accept the rules (role-gate),
**Then** Nour initiates a structured multi-day onboarding journey:
- Day 1: Welcome + first task walkthrough (one concept at a time)
- Day 2: Practice platform + recording tutorial
- Day 3: Streaks, points, levels explained
- Day 4-7: Channel discovery (one channel per day)
- Each step waits for confirmation before advancing
- Student can ask questions at any point and Nour answers in context

**Acceptance:** A new student who speaks zero English and has never used
Discord can complete their first 7/7 day within the first week guided
entirely by Nour, with zero owner intervention.

## R2: Modern Standard Arabic (MSA / فصحى)

**Given** Nour generates any Arabic text (DMs, channel posts, responses),
**Then** all Arabic output is in MSA (فصحى), never Egyptian colloquial:
- No slang: no "يا باشا", "أيوه", "ماشي", "عايز"
- Correct grammar: proper case endings where meaningful
- Bidi-safe: passes bidi_check.py with 0 issues
- Warm tone maintained: MSA does NOT mean cold/robotic — formal ≠ distant

**Acceptance:** Every Nour message passes `scripts/bidi_check.py`,
uses no colloquial markers, and a native Arabic speaker rates it as
"warm and clear" (not "cold" or "academic").

## R3: Full System Knowledge (Student-Facing)

**Given** a student asks any question about the Empire English system,
**Then** Nour answers accurately from her knowledge base covering:
- All 7 daily tasks (what, why, how, troubleshooting)
- All channels and their purpose
- Points, streaks, levels, advancement
- Practice platform (how to access, how it works, mobile recording)
- Commands (all 40+, including Arabic aliases)
- Common problems (can't record, bot not responding, streak broken)
- Study strategies and motivation
- How to use Discord on mobile (for non-tech-savvy Arab users)

**Acceptance:** Nour answers correctly 95%+ of system questions without
escalating to the owner.

## R4: Full Operations Management (Owner-Facing)

**Given** the owner checks Telegram,
**Then** Nour provides a complete daily operations report:
- Student activity summary (who's active, who's stuck, who's at risk)
- Questions Nour answered (themes, any she wasn't confident about)
- Churn alerts (students who may leave)
- Milestone celebrations (who achieved what)
- System health (any errors, AI failures, etc.)
- Actionable suggestions ("Student X hasn't started, recommend reaching out")

**And** Nour can execute owner commands via Telegram:
- "Send announcement to all students"
- "Check on student X"
- "What's the current status?"
- "Enable/disable feature Y"

**Acceptance:** Owner can manage the community from their phone via
Telegram replies to Nour, without opening Discord for routine operations.

## R5: Proactive Intelligence (Not Just Reactive)

**Given** a student's behavior pattern changes,
**Then** Nour detects it and acts autonomously:
- Confusion detection: repeated failures → send micro-tutorial
- Silence detection: 2+ days inactive → personalized check-in
- Score drops: declining performance → encouragement + specific tip
- Channel ignorance: never visited #daily-word → introduce it
- Milestone proximity: "you're 1 task away from a streak bonus!"
- Graduation readiness: approaching level advancement → suggest !exam

**Acceptance:** Nour initiates helpful contact BEFORE the student asks,
with a 90%+ "helpful" rate (not annoying/spammy).

## R6: Human-Like Behavior

**Given** Nour sends any message,
**Then** it feels like a real team member, not a bot:
- Typing indicators with realistic delays
- Occasional message splits (two messages instead of one wall)
- References previous conversations ("last time you mentioned...")
- Remembers personal facts (job, schedule, family)
- Time-of-day awareness (morning energy vs. night calm)
- Cultural awareness (Ramadan, Eid, Friday, prayer times)
- Never says "I'm an AI" or "I'm a bot"
- Gender-correct Arabic addressing (masculine/feminine)

**Acceptance:** A student interacting with Nour for a week cannot
definitively tell she's AI-powered.

## R7: Graduated Presence (Not Clingy)

**Given** a student has been active for N weeks,
**Then** Nour's proactive contact frequency decreases:
- Week 1-2: Very present (daily check-ins, journey guidance)
- Week 3-4: Medium (every 2-3 days, milestone celebrations)
- Week 5+: Minimal (weekly summary, only intervenes on problems)

**Acceptance:** Experienced students are never annoyed by excessive
Nour messages, while new students always feel supported.

## R8: Zero-Budget Constraint

**Given** the project has $0 budget for new services,
**Then** the implementation uses only existing resources:
- Groq API (free tier, already configured)
- Gemini (already configured, fallback)
- No new paid services, APIs, or infrastructure
- Template fallbacks for when AI providers are down

**Acceptance:** Total new monthly cost = $0.

## R9: Arab-Friendly Design

**Given** the students are Arabic speakers learning English,
**Then** everything is designed Arab-first:
- MSA for all Arabic (R2)
- RTL rendering correct everywhere
- Mobile-first (most Arab students use phones)
- Cultural calendar awareness (Islamic calendar, Friday weekend)
- Instructions explain Discord basics (many students are new to it)
- No assumed English knowledge in explanations
- Time zone: Asia/Dubai (existing config)

**Acceptance:** A 25-year-old Arabic speaker who has never used
Discord or studied English formally can navigate the entire system
guided only by Nour.

## R10: Safe Rollout (No Breaking Changes)

**Given** 16 real students may already be in the server,
**Then** the overhaul is flag-gated and backwards-compatible:
- New behavior behind feature flags
- Old Nour continues working during migration
- Can revert instantly if anything misbehaves
- Knowledge base update doesn't affect command processing
- MSA switch can be A/B tested (new students get MSA, existing keep current)

**Acceptance:** Existing students experience zero disruption during rollout.

## Constraints

- $0 budget (no new paid services)
- Zero tolerance for breaking existing work
- Arabic must be MSA/bidi-safe/checker-verified
- Must work with current AI providers (Groq primary, Gemini fallback)
- Must integrate with existing Markaz (Telegram ops hub)
- Spec lives at `empire-nexus/.kiro/specs/nour-overhaul/`
