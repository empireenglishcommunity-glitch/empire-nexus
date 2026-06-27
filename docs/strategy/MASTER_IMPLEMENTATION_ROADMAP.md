# Empire English — Master Implementation Roadmap (The Whole Picture)

**Program Overview v1.0** · *Confidential* · **Date:** June 2026

> **Why this document exists.** Before building anything, this is the **single bird's-eye view** of the entire channel-growth program — all four phases (0→3), how they connect, what each one delivers, the decision gate between them, and where we are right now. It is a **map, not a build order in itself**: each phase has (or will have) its own detailed spec. Read this to approve the *direction and sequence* before any implementation begins.

> **Status: PLANNING / OVERVIEW ONLY.** Nothing in this program has been built or deployed. Phase 0 is fully specified and its content is drafted; Phases 1–3 are outlined here and will each get a dedicated spec **only when their gate opens.**

---

## Table of Contents

1. [Document Map (What We've Produced So Far)](#1-document-map-what-weve-produced-so-far)
2. [The Whole Picture on One Page](#2-the-whole-picture-on-one-page)
3. [You Are Here](#3-you-are-here)
4. [Guiding Principles (Apply to Every Phase)](#4-guiding-principles-apply-to-every-phase)
5. [Phase 0 — Foundation & Instrumentation](#5-phase-0--foundation--instrumentation)
6. [Phase 1 — Content Rhythm & Reporting](#6-phase-1--content-rhythm--reporting)
7. [Phase 2 — Conversion Optimization](#7-phase-2--conversion-optimization)
8. [Phase 3 — Growth Loops & Scale](#8-phase-3--growth-loops--scale)
9. [Phase Gates (Go/No-Go Decisions)](#9-phase-gates-gono-go-decisions)
10. [Cumulative Tool Stack by Phase](#10-cumulative-tool-stack-by-phase)
11. [KPI Maturity by Phase](#11-kpi-maturity-by-phase)
12. [Program-Level Risk Register](#12-program-level-risk-register)
13. [What Stays Manual the Whole Way](#13-what-stays-manual-the-whole-way)
14. [Decisions Needed From the Founder](#14-decisions-needed-from-the-founder)

---

## 1. Document Map (What We've Produced So Far)

The program is documented across a small set of artifacts. This roadmap sits **on top** of them as the index.

| Document | Layer | Role | Status |
|---|---|---|---|
| `Empire English Community Learning System.md` | Product | The learning OS (curriculum, daily loop, Discord, AI) | Pre-existing |
| `STRATEGIC_EXPANSION_ROADMAP.md` | Business | Pricing ladder, community structures, free-tool stack | Pre-existing (PR #4) |
| `CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md` | Funnel strategy | The channel→bot funnel; 10 locked decisions | **Merged (PR #6)** |
| `PHASE_0_IMPLEMENTATION_SPEC.md` | Build spec | Exact Phase 0 build (bot, quiz, CRM, automations) | **Merged (PR #7)** |
| `PHASE_0_CONTENT_ASSETS.md` | Content | Bilingual copy filling the Phase 0 bot | Open (PR #8) |
| `MASTER_IMPLEMENTATION_ROADMAP.md` | Program overview | **This document** — the whole picture | New |

> **How the layers stack:** Product + Business (what we sell) → Funnel strategy (how we convert) → Phase specs (how we build each step) → Content (the words that fill it) → this Roadmap (the map over all of it).

---

## 2. The Whole Picture on One Page

```
                     ┌─────────────────────────────────────────────────────────────┐
                     │                  EMPIRE ENGLISH GROWTH PROGRAM                │
                     └─────────────────────────────────────────────────────────────┘

 PHASE 0              PHASE 1                PHASE 2                  PHASE 3
 Foundation &         Content Rhythm         Conversion              Growth Loops
 Instrumentation      & Reporting            Optimization            & Scale
 (Weeks 1–2)          (Weeks 3–8)            (Weeks 9–16)            (Month 5+)
 ───────────          ───────────            ───────────             ───────────
 Build the            Feed the spine         Improve the             Compound the
 "capture spine"      with consistent        numbers; recover        wins; scale
                      content + see          lost leads              discovery
                      the numbers
 • Telegram bot       • 5–6 posts/week       • A/B test CTAs         • Reels/Shorts/UGC
 • Level quiz         • Discussion group     • Follow-up drips       • Referral system
 • Sheets CRM         • Story collection     • Reactivation drips    • Gamification/seasons
 • Cal.com booking    • Weekly auto-report    • Lead-scoring alerts  • 2nd discovery channel
 • Consent + events   • Baseline KPIs        • Referral v1           • (maybe) light paid ads
 • Quick-win delivery                        • AI repurposing        • (maybe) first VA hire

   │  GATE 0→1            │  GATE 1→2             │  GATE 2→3                │
   ▼                      ▼                       ▼                          ▼
 End-to-end flow       4+ weeks of KPIs        Lift on ≥2 funnel         Self-sustaining
 works (E1–E10)        + 1 proven content      steps + LTV:CAC           flywheel; founder
                       category that drives    sanity check before       time on sales +
                       bot taps                any paid push             strategy, not ops

 ════════════════════════════════════════════════════════════════════════════════════
 FUNNEL MATURES:  capture → measure → optimize → scale
 EFFORT SHIFTS:   build plumbing → build habit → tune conversion → remove founder from ops
 RISK POSTURE:    don't pour traffic into a leaky funnel → validate before spending
```

> **The core narrative:** Phase 0 makes the pipe exist. Phase 1 proves people flow through it and gives you eyes (reporting). Phase 2 makes more of them convert. Phase 3 makes the whole thing grow itself. Each phase only starts when the previous one has *earned* it (the gates, §9).


---

## 3. You Are Here

| Milestone | State |
|---|---|
| Strategy locked (10 decisions, Telegram confirmed) | ✅ Done (PR #6) |
| Phase 0 build spec | ✅ Done (PR #7) |
| Phase 0 content drafted | ✅ Done (PR #8) |
| Master roadmap | ✅ Done (PR #9) |
| Repo cleanup + index + folder organization | ✅ Done (PR #10, #11) |
| Pre-build decisions (pricing display, Arabic register, orchestrator) | ✅ Locked |
| **Phase 0 BUILD — Bot + Quiz + CRM + Automations** | ✅ **COMPLETE** (June 25, 2026) |
| **Infrastructure — Hetzner + n8n + Cloudflare Tunnel + MCP** | ✅ **COMPLETE** |
| **Asset production (PDF lead magnet)** | ✅ **COMPLETE** (hosted on Google Drive) |
| **Gate 0→1 — All acceptance tests passing** | ✅ **PASSED** |
| **Phase 1 — Content Rhythm & Reporting** | 🟡 **IN PROGRESS** (content written, publishing starting) |
| Phase 1 detailed spec | ✅ Written (`04-phase-1/PHASE_1_IMPLEMENTATION_SPEC.md`) |
| Phases 2–3 detailed specs | ⬜ Written at each gate (not before) |

> **Current state (June 25, 2026):** Phase 0 is COMPLETE and passing all acceptance tests. Phase 1 has begun — content is written, discussion group is live, weekly report is running. The system is operational on n8n self-hosted (migrated from Make.com). Gate 1→2 will be evaluated after ≥4 weeks of measured funnel data.

---

## 4. Guiding Principles (Apply to Every Phase)

These hold from Phase 0 through Phase 3 and come straight from the locked strategy + the audit guardrails:

1. **Free-first.** Every stage uses free/freemium tools; paid spend only after LTV:CAC ≥ 3:1 is demonstrated (Phase 3 at earliest).
2. **Solo-operator-sustainable.** If it needs daily manual effort, automate it or cut it. Consistency over ambition.
3. **Don't pour traffic into a leaky funnel.** Build and validate the capture spine before chasing growth.
4. **One source of truth.** The Google Sheets CRM; every automation reads/writes here.
5. **Measure before optimizing.** No A/B tests or paid pushes until baseline KPIs exist (Phase 1).
6. **Honest by default.** Real scarcity, real proof, attainable outcomes — never "sound 100% native." Protects trust at small scale.
7. **Ethics + ToS.** Explicit consent, no fake engagement, instant opt-out. A ban or broken trust is fatal at 57 members.
8. **Gate discipline.** Don't start a phase until the prior gate passes. Half-built phases stacked on each other are how solo projects die.

---

## 5. Phase 0 — Foundation & Instrumentation

> **Fully specified** in `PHASE_0_IMPLEMENTATION_SPEC.md`; content drafted in `PHASE_0_CONTENT_ASSETS.md`. Summarized here for the whole-picture view.

| Field | Detail |
|---|---|
| **Goal** | Build the end-to-end "capture spine": a new member can be welcomed → quiz → personalized plan + free gift → stored/tagged/scored in CRM → book a call. Automated, free, instrumented. |
| **Builds** | Telegram bot (5-button menu) · 2-min level quiz + scoring · Google Sheets CRM · consent capture · Cal.com booking · welcome automation · quick-win delivery · 6 funnel events logged · lead scoring + segments · daily backup |
| **Deliverables** | Working bot; CRM with 4 tabs; booking link; 9 automation scenarios (A1–A9); event log |
| **Content needed** | The 10 assets in PR #8 (+ produce 3 audio clips & PDF; confirm prices) |
| **Tools** | Telegram Bot API · Make.com (or n8n) · Google Sheets · Cal.com · MailerLite/Brevo (account only) |
| **Effort (anchor)** | ~5–9 focused solo days |
| **Stays manual** | Sales calls, story curation, group replies, flipping `status=Customer` on payment |
| **Exit (Gate 0→1)** | All 10 acceptance tests (E1–E10 / T1–T10) pass: end-to-end flow works + idempotent |

> **Phase 0 explicitly excludes:** drips, A/B tests, referral, gamification, the weekly report, payment integration, full placement diagnostic. Those are later phases.

---

## 6. Phase 1 — Content Rhythm & Reporting

> **Outline only** — gets a dedicated spec when Gate 0→1 passes. The job of Phase 1: prove people actually flow through the spine, and give the founder *eyes* on the funnel.

| Field | Detail |
|---|---|
| **Goal** | Establish a sustainable content cadence that drives traffic into the bot, launch the two-way discussion group, and stand up the weekly auto-report so the funnel becomes visible numbers. |
| **Builds** | Content calendar + batching workflow · scheduled publishing automation · the linked discussion group (live + seeded) · systematic testimonial/story collection · **the weekly auto-report** (KPI digest from the §10/§11 event data) · reminder/nudge automations |
| **Deliverables** | 5–6 posts/week running for ≥6 weeks · discussion group active · first transformation stories collected · a self-assembling weekly digest (Blueprint §7) · baseline funnel conversion rates |
| **Content needed** | The 10 post categories (Blueprint §3.1) seeded; first batch of value/proof/engagement posts; word-of-the-day ritual; story-capture template |
| **New tools** | Scheduling automation (Make/n8n) · Apps Script or n8n for the report · (discussion group already free) |
| **Effort posture** | Batch content weekly in one sitting; reporting auto-runs; founder replies in group manually |
| **Exit (Gate 1→2)** | ≥4 weeks of measured funnel rates + at least one content category proven to reliably drive bot taps |

> **Why reporting lands in Phase 1, not 0:** Phase 0 *captures* events; Phase 1 turns them into a weekly decision tool. You can't optimize (Phase 2) what you can't see, so reporting must exist before optimization starts.

> **Key Phase 1 question to answer with data:** which post category actually moves people from *reading* → *tapping the bot*? That answer shapes all of Phase 2.


---

## 7. Phase 2 — Conversion Optimization

> **Outline only** — dedicated spec when Gate 1→2 passes. The job of Phase 2: make more of the existing flow convert, and stop losing the people who don't convert on first contact.

| Field | Detail |
|---|---|
| **Goal** | Lift conversion at the weakest funnel steps and recover non-converters through automated follow-up — without spending on ads. |
| **Builds** | A/B testing of CTAs + bot flows (the CTA library, Blueprint §5.5) · **follow-up drip** for people who tap the bot but don't book/trial · **reactivation drip** for lapsed members · lead-scoring thresholds + **Hot-lead founder alerts** wired to action · **referral v1** ("bring a friend to your squad") · AI content repurposing (one lesson → Reel + carousel + quiz) |
| **Deliverables** | Documented lift on ≥2 funnel steps · working email/bot drips (consented) · referral producing first member-sourced joins · founder gets a daily ranked "who to talk to" list |
| **Content needed** | CTA variations (1–3 each) · drip sequence copy (bilingual) · reactivation copy · referral offer copy |
| **New tools** | MailerLite/Brevo activated for drips · simple A/B logging in CRM |
| **Effort posture** | Drips run themselves; founder runs *one* experiment per week against the bottleneck (Blueprint §7.5) |
| **Exit (Gate 2→3)** | Lift demonstrated on ≥2 steps **and** an LTV:CAC sanity check passes before any paid acquisition |

> **Phase 2 is where "the money in follow-up" gets captured.** Most non-converters in Phase 0–1 are simply lost; Phase 2 builds the safety net that turns a chunk of them into customers at near-zero cost.

---

## 8. Phase 3 — Growth Loops & Scale

> **Outline only** — dedicated spec when Gate 2→3 passes. The job of Phase 3: make the system grow itself and remove the founder from day-to-day operations.

| Field | Detail |
|---|---|
| **Goal** | Turn a validated, optimized funnel into a compounding growth engine, scaling discovery and formalizing the loops that bring members in. |
| **Builds** | Scaled discovery (Reels/Shorts/UGC clips of transformations) · formalized **referral + loyalty** program · **gamification/seasons** (improvement-based, squad-based) · a **second discovery channel** (so growth isn't single-platform) · *optional* light paid amplification (**only if LTV:CAC ≥ 3:1**) · *optional* first VA hire for content batching/story collection |
| **Deliverables** | Compounding growth via proof + referral loops · report-driven weekly optimization is routine · founder time concentrated on sales + strategy, not manual ops |
| **Content needed** | UGC/clip templates · referral mechanics copy · season/quest narratives · badges & belonging artifacts |
| **New tools** | CapCut/Canva at volume · possibly a scheduling tool for multi-channel · (paid tools only post-validation) |
| **Effort posture** | Ops increasingly delegated/automated; founder is the closer + strategist, not the operator |
| **Exit** | Self-sustaining flywheel; the program runs on loops, not on the founder's daily effort |

> **Phase 3 is the only place paid spend or hiring is even considered**, and only behind the LTV:CAC ≥ 3:1 guardrail. Everything before it is free-first by design.

---

## 9. Phase Gates (Go/No-Go Decisions)

> Gates are the discipline that keeps a solo program from collapsing under half-built layers. **Do not start a phase until its entry gate passes.**

| Gate | Pass condition | If it fails |
|---|---|---|
| **Gate 0→1** | All Phase 0 acceptance tests (E1–E10) pass; a real test user completes the full flow; automations are idempotent | Fix the spine first. Do **not** start producing content cadence on a broken funnel |
| **Gate 1→2** | ≥4 weeks of measured funnel conversion rates exist; ≥1 content category reliably drives bot taps; discussion group is active | Keep iterating content/cadence until there's signal + data. No optimization without a baseline |
| **Gate 2→3** | Demonstrated lift on ≥2 funnel steps; follow-up drips recover non-converters; **LTV:CAC sanity check passes** | Keep optimizing organically. Do **not** scale discovery or spend on ads on weak unit economics |
| **(within Gate 2→3)** | LTV:CAC ≥ 3:1 specifically before *paid* acquisition | Grow only via free loops (referral, UGC) until economics support spend |

> **Gate review cadence:** the weekly digest (from Phase 1 on) is the instrument. Monthly, ask: "has the current gate's condition been met?" Only then write the next phase's spec.

---

## 10. Cumulative Tool Stack by Phase

> Tools accumulate; nothing is thrown away. All free/freemium until Phase 3's optional paid step.

| Tool | P0 | P1 | P2 | P3 | Purpose |
|---|:--:|:--:|:--:|:--:|---|
| Telegram bot + channel | ● | ● | ● | ● | Front door + conversion engine |
| Make.com / n8n | ● | ● | ● | ● | Orchestration/automation |
| Google Sheets CRM | ● | ● | ● | ● | Single source of truth |
| Cal.com | ● | ● | ● | ● | Booking |
| Telegram discussion group | | ● | ● | ● | Two-way engagement |
| Apps Script / n8n reporting | | ● | ● | ● | Weekly auto-report |
| MailerLite / Brevo | (acct) | (acct) | ● | ● | Drips + reactivation |
| CapCut / Canva | (asset) | ● | ● | ● | Clips, carousels, badges |
| Second discovery channel | | | | ● | Anti single-platform risk |
| Paid ads (optional) | | | | ◐ | Only if LTV:CAC ≥ 3:1 |
| VA (optional) | | | | ◐ | Only when volume justifies |

● = active · (acct/asset) = set up but not yet driving · ◐ = optional, gated

---

## 11. KPI Maturity by Phase

The funnel's measurability deepens each phase. North-star throughout: **appointments/trials started per week**.

| Phase | Primary KPIs watched | What "good" looks like |
|---|---|---|
| **P0** | Acceptance tests pass; events logging correctly | The pipe works and is instrumented |
| **P1** | New joins, return/react rate, bot-tap rate, quiz completions, baseline conversion rates | Consistent cadence; a visible, stable funnel baseline |
| **P2** | Step-by-step conversion rates, drip recovery rate, trial→paid, referral joins | Measurable lift on ≥2 steps; recovered non-converters |
| **P3** | LTV:CAC, growth-loop coefficient, retention/churn, % ops automated | Compounding growth; sustainable unit economics |

> Detailed KPI hierarchy and the weekly digest template live in `CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md` §7.


---

## 12. Program-Level Risk Register

> Cross-phase risks (phase-specific risks live in each phase's spec).

| # | Risk | Phase most exposed | Mitigation |
|---|---|---|---|
| R1 | **Building ahead of validation** (skipping gates) | All | Enforce gate discipline (§9); write each phase spec only at its gate |
| R2 | **Solo-operator burnout / inconsistency** | P1 | Batch content; automate ruthlessly; consistency over volume |
| R3 | **Single-platform dependency** (Telegram ban/changes) | All | Owned backup list from P0; second channel in P3; back up CRM daily |
| R4 | **Funnel leak goes unnoticed** | P0–P1 | Event instrumentation (P0) + weekly report (P1) surface leaks early |
| R5 | **Trust erosion** (over-selling, fake proof, CTA fatigue) | All | 80/20 give:ask; honest scarcity; attainable claims |
| R6 | **Free-tier ceilings hit** (Make ops, email sends) | P2–P3 | Monitor limits; n8n self-host fallback; batch operations |
| R7 | **Premature paid spend** on weak economics | P3 | LTV:CAC ≥ 3:1 hard gate before any ads |
| R8 | **Pricing unvalidated** | P1–P2 | Treat prices as anchors; validate in pilot before scaling |
| R9 | **Content stalls** (run out of ideas/assets) | P1 | AI repurposing (P2); story/UGC engine; reusable categories |
| R10 | **Consent/compliance slip** | P0+ | Explicit opt-in, instant opt-out, no unsolicited bulk DMs |

---

## 13. What Stays Manual the Whole Way

Some things should **never** be fully automated, because at this scale they *are* the moat (Blueprint O4):

- **Sales/strategy calls** — the founder closing is the highest-value human action.
- **Personal DMs to Hot leads** — automation flags them; the human touch converts them.
- **Discussion-group presence** — authentic founder replies build trust competitors can't buy.
- **Story/testimonial curation** — judgment, consent, and emotional framing.
- **Pricing/offer decisions** and edge-case support.
- **Flipping `status=Customer`** on payment (until payment integration, a later consideration).

> The automation's job is to free the founder's time *for* these, not replace them.

---

## 14. Decisions Needed From the Founder

Most pre-build decisions are now **locked** (✅). Remaining open items gate the build itself.

| # | Decision | Status |
|---|---|---|
| D1 | Approve roadmap's direction & sequence | ✅ Approved |
| D2 | Approve Phase 0 content (PR #8) | ✅ Merged |
| D3 | Pricing display | ✅ **Locked: no public prices day one — pricing via call/DM.** Price tokens reserved for later |
| D4 | Arabic register/tone | ✅ **Locked: MSA, fresh & conversational** (pan-Arab); light proofread before publish |
| D6 | Orchestrator choice | ✅ **Locked: Make.com** (n8n self-host fallback if limits hit) |
| D5 | **Give the go to BUILD Phase 0** | ⬜ **Open — the one remaining decision** |
| D7 | Pre-write Phase 1 spec now vs wait for Gate 0→1 | ⬜ Open (recommend wait) |
| — | Produce 2 assets (audio ×3 + PDF) + set Config links | ⬜ Pending (can run in parallel with build) |

> **Where we are:** the plan, content, and all design decisions are locked. The **only** thing standing between here and a working Phase 0 is the **build go (D5)** plus producing two assets and creating the accounts/Config values. Phase 1's detailed spec stays parked until Gate 0→1 passes (D7).

---

## 15. Summary

This program turns a 57-member Telegram channel into a self-running growth engine in four gated phases: **build the capture spine (P0) → establish content rhythm + reporting (P1) → optimize conversion + recover lost leads (P2) → scale via growth loops (P3).** Each phase is free-first, solo-sustainable, and starts only when the previous gate is earned. Phase 0 is fully specified and content-drafted; Phases 1–3 are mapped here and will each get a focused spec at their gate.

> **The discipline that makes this work:** don't pour traffic into a leaky funnel, don't optimize what you can't measure, and don't spend money on unvalidated economics. Build the pipe, get eyes on it, tune it, then scale it.

> **Next step:** review this roadmap and tell me which decisions in §14 you want to lock. Nothing gets built until you give the explicit go.

---

*End of Master Implementation Roadmap v1.0 — program-overview artifact only. No implementation has been performed.*
