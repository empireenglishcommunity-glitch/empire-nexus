# Empire English Community — Project Status & Handover

> **Last Updated:** June 25, 2026
> **Status:** Phase 0 COMPLETE — Bot fully operational, automations running, MCP infrastructure live Document

**Date:** June 20, 2026  
**Version:** 1.0  
**Role:** Systems Architect Audit + Handover Documentation

---

## 1. Executive Summary

Empire English Community is a **system-driven English learning program** for Arabic speakers, focused on American accent mastery. The technical infrastructure consists of a **Telegram bot** that serves as the public-facing conversion funnel, backed by a **Google Sheets CRM**, **Cal.com booking**, and an orchestration layer for automation.

**Current state:** The project is mid-migration from Make.com (a paid, ops-limited automation platform) to n8n (a self-hosted, unlimited-operations open-source alternative). Phase 0 (the "capture spine") was fully built on Make.com and is functional. The migration to n8n is approximately **40% complete** — the server is live and running n8n, but Google Sheets connectivity is not yet established, and workflows have not been rebuilt.

**Key tension:** The project has two parallel systems right now — a working Make.com setup (offline/not activated) and a partially-configured n8n server. The migration must be completed before going live.

---

## 2. Timeline of Decisions (Chronological)

| # | Decision/Action | Rationale | Status |
|---|---|---|---|
| 1 | Repository established with strategy docs | Foundation for the entire program | ✅ Complete (pre-session) |
| 2 | Phase 0 build on Make.com (live guided assembly) | Get the bot working fast; validate the concept | ✅ Complete |
| 3 | 3 bugs identified and fixed (menu, formulas, duplicates) | QA before going live | ✅ Complete |
| 4 | Phase 1 spec written | Plan for content rhythm & reporting | ✅ Written (PR #16 merged) |
| 5 | Make.com scalability concern raised | Credits burned fast during testing; fear of ops costs at scale | Identified |
| 6 | Architecture review conducted | Evaluated Make.com vs n8n vs custom code | ✅ Complete |
| 7 | **Decision: Migrate to n8n self-host** | $0/mo unlimited ops vs $16-99/mo growing linearly | ✅ Locked |
| 8 | Oracle Cloud signup attempted | Free forever hosting | ❌ Failed (card verification rejected) |
| 9 | **Pivot: Hetzner Cloud selected** | €4.15/mo, stable German company since 2003, no vendor tricks | ✅ Account created |
| 10 | Server provisioned (CX23, Helsinki) | 2 vCPU, 4 GB RAM, $7.09/mo | ✅ Running |
| 11 | Docker + n8n installed | Self-hosted automation platform | ✅ Running at http://77.42.43.250:5678 |
| 12 | Telegram Bot credential connected in n8n | Same bot token as Make.com | ✅ Connected & tested |
| 13 | Google Sheets credential setup attempted (OAuth) | Failed — requires domain name for redirect URI | ❌ Blocked |
| 14 | **Pivot: Service Account approach** | No domain needed, more stable for servers | ⏳ In progress |
| 15 | Google Cloud project created + OAuth consent configured | Prerequisite for Service Account | ✅ Complete |
| 16 | Service Account creation in Google Cloud | Needed to get JSON key file | ⏳ **Current blocker** |

---

## 3. Current Architecture

### 3.1 Target Architecture (what we're building toward)

```
┌─────────────────────────────────────────────────────────────────┐
│                    EMPIRE ENGLISH SYSTEM                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  [Telegram Channel] ──→ [Telegram Bot @EmpireEnglishBot]          │
│        (57 members)           │                                   │
│                               ▼                                   │
│  [n8n on Hetzner: 77.42.43.250:5678]                             │
│     • Webhook receives all bot events                            │
│     • Switch node routes: /start, quiz, resource, how, call, etc │
│     • Code Node: JavaScript quiz scoring (replaces Make chains)  │
│     • Writes to Google Sheets CRM                                │
│     • Sends Telegram responses                                   │
│     • Daily backup, weekly report, nudges                        │
│                               │                                   │
│                               ▼                                   │
│  [Google Sheets: Empire CRM]                                     │
│     • Subscribers tab (lead records)                             │
│     • Events tab (funnel tracking)                               │
│     • Config tab (tunable settings)                              │
│     • String_Table tab (bilingual bot copy)                      │
│                               │                                   │
│                               ▼                                   │
│  [Cal.com] ←── booking webhook ──→ [n8n]                         │
│     • Free strategy calls                                        │
│     • Webhook notifies n8n on booking → CRM update              │
│                                                                   │
│  [Formulas in Sheets]                                            │
│     • lead_score (INDIRECT+ROW, written by Make.com/n8n)        │
│     • segment (same approach)                                    │
│                                                                   │
│  COST: $7.09/mo (Hetzner) + $0 (everything else)                │
│  OPERATIONS: Unlimited                                            │
│  WORKFLOWS: Unlimited                                             │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Current Reality (what exists right now)

| Component | Status | Location |
|---|---|---|
| Telegram Bot (@EmpireEnglishBot) | ✅ Created, token exists | Telegram/BotFather |
| Make.com scenarios (A1–A9) | ✅ Built, tested, bugs fixed — **OFF** | Make.com (eu1) |
| Google Sheets CRM | ✅ Working with data from testing | Google Sheets |
| Cal.com booking | ✅ Configured, webhook connected to Make.com | Cal.com |
| Hetzner server | ✅ Running (77.42.43.250) | Hetzner Helsinki |
| n8n instance | ✅ Running, accessible, owner account created | http://77.42.43.250:5678 |
| n8n → Telegram connection | ✅ Working | n8n credentials |
| n8n → Google Sheets connection | ❌ **NOT CONNECTED** (blocked on Service Account JSON) | n8n credentials |
| n8n workflows | ❌ **NOT BUILT** (waiting for Google connection) | n8n |
| Phase 0 bot live for users | ❌ **NOT ACTIVATED** (waiting for migration complete) | — |

---

## 4. Completed Work

### 4.1 Repository & Documentation (all merged to main)
- ✅ README.md (project index)
- ✅ Empire English Community Learning System.md (product blueprint)
- ✅ STRATEGIC_EXPANSION_ROADMAP.md (business layer)
- ✅ CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md (funnel strategy, 10 locked decisions)
- ✅ MASTER_IMPLEMENTATION_ROADMAP.md (4-phase overview with gates)
- ✅ PHASE_0_IMPLEMENTATION_SPEC.md (full Phase 0 build spec)
- ✅ PHASE_0_CONTENT_ASSETS.md (bilingual Arabic/English bot copy)
- ✅ Build Kit: botfather-setup.md, make-scenarios.md, quiz-logic.md, crm/*.csv
- ✅ PATCH-001-fixes.md (3 bug fixes documented)
- ✅ N8N_MIGRATION_PLAN.md (full migration guide)
- ✅ PHASE_1_IMPLEMENTATION_SPEC.md (content rhythm & reporting spec)

### 4.2 Make.com Build (functional, tested, bugs fixed)
- ✅ Bot responds to all 5 menu buttons + menu navigation
- ✅ 7-question quiz with scoring + level assignment + personalized plan
- ✅ CRM creates rows with proper upsert (no duplicates on /start)
- ✅ lead_score and segment formulas written by Make.com into each row
- ✅ Cal.com booking sync → marks Hot → alerts founder
- ✅ Daily backup (Google Drive copy)
- ✅ Hot-lead alerts to founder's Telegram

### 4.3 Infrastructure (new — n8n)
- ✅ Hetzner Cloud account + server provisioned
- ✅ Docker installed on Ubuntu 26.04
- ✅ n8n running (Docker Compose, auto-restart)
- ✅ n8n owner account created (Mahmoud Ashri)
- ✅ Telegram Bot credential connected and tested in n8n
- ✅ Google Cloud project created ("Empire English n8n")
- ✅ Google OAuth consent screen configured

---

## 5. Work In Progress (Partially Complete)

| Item | What's done | What remains |
|---|---|---|
| Google Sheets credential in n8n | Service Account form found, Google Cloud project created | Create the Service Account, download JSON key, share sheet, paste into n8n |
| n8n workflow migration | — | Build all workflows (welcome, quiz, resource, offer, booking, community, backup, report, nudges) |
| Phase 0 activation (go live) | Bot built, tested, fixed | Complete migration → switch to n8n → activate |

---

## 6. Outstanding Tasks (Prioritized)

### Priority 1 — Complete the Migration (BLOCKING everything else)

| # | Task | Effort | Dependency |
|---|---|---|---|
| 1.1 | Create Google Cloud Service Account + download JSON key | 5 min | Google Cloud Console access |
| 1.2 | Share Empire CRM with the service account email | 1 min | 1.1 |
| 1.3 | Enable Google Sheets API + Google Drive API | 2 min | 1.1 |
| 1.4 | Paste credentials into n8n → test connection | 2 min | 1.1, 1.2, 1.3 |
| 1.5 | Build the main bot workflow in n8n (welcome + all routes) | 2–3 hours | 1.4 |
| 1.6 | Build the quiz flow with Code Node scoring | 1–2 hours | 1.5 |
| 1.7 | Build booking sync webhook workflow | 30 min | 1.4 |
| 1.8 | Build daily backup workflow | 15 min | 1.4 |
| 1.9 | Update Cal.com webhook URL to point to n8n | 5 min | 1.7 |
| 1.10 | End-to-end testing (T1–T10 acceptance tests) | 1 hour | All above |
| 1.11 | Switch bot from test to live (activate) | 5 min | 1.10 passes |

### Priority 2 — Phase 1 Execution (after go-live)

| # | Task | Effort |
|---|---|---|
| 2.1 | Create + link Telegram discussion group | 15 min |
| 2.2 | Update bot community route with real invite | 5 min |
| 2.3 | Write first 2 weeks of content (12 posts + daily rituals) | 2–3 hours |
| 2.4 | Schedule first week's posts | 30 min |
| 2.5 | Build weekly auto-report workflow in n8n | 1–2 hours |
| 2.6 | Build nudge workflow in n8n | 1 hour |
| 2.7 | Produce "3 American Sounds" PDF + audio clips | 1–2 hours |
| 2.8 | Replace resource stub in bot with real delivery | 15 min |
| 2.9 | Collect first transformation stories | Ongoing (weeks 2–6) |
| 2.10 | Run for 6+ weeks, read weekly reports, iterate | 6 weeks |

### Priority 3 — Housekeeping

| # | Task | Effort |
|---|---|---|
| 3.1 | Update MASTER_IMPLEMENTATION_ROADMAP.md §3 "You Are Here" to reflect Phase 0 is BUILT | 10 min |
| 3.2 | Archive/deactivate Make.com scenarios (after 30 days of stable n8n) | 5 min |
| 3.3 | Add HTTPS/domain to n8n (optional, improves security) | 1 hour |
| 3.4 | Set up uptime monitoring (UptimeRobot free tier) | 10 min |

---

## 7. Issues & Risks

### 7.1 Immediate Blockers

| # | Issue | Impact | Resolution |
|---|---|---|---|
| B1 | Google Sheets Service Account not yet created | Cannot build any n8n workflows that touch the CRM | Complete steps 1.1–1.4 (10 minutes of work) |

### 7.2 Technical Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| R1 | n8n server goes down (no monitoring) | Medium | Set up UptimeRobot (free) + Docker `restart: always` (already configured) |
| R2 | No HTTPS on n8n (data in transit is unencrypted) | Low (bot token is the only sensitive data, already stored in n8n's encrypted credential store) | Add Caddy/nginx + Let's Encrypt later (requires a domain name or Cloudflare tunnel) |
| R3 | No automated n8n backup (workflows) | Medium | Export workflows as JSON monthly; store in repo |
| R4 | Single server = single point of failure | Low (for current scale) | Acceptable until 1,000+ users; then consider redundancy |
| R5 | Make.com still has the bot token stored | Low | Remove token from Make.com after 30-day parallel period |

### 7.3 Strategic Risks

| # | Risk | Severity | Mitigation |
|---|---|---|---|
| S1 | Project not yet live — no real user data after weeks of building | High | Complete migration ASAP (1–2 days), go live, start Phase 1 |
| S2 | "Perfect system" trap — over-building infrastructure before validating with users | Medium | Phase 1's job is VALIDATION. Ship fast, measure, iterate |
| S3 | Solo operator burnout | Medium | Everything automated; manual effort = content + calls only |
| S4 | Telegram platform risk (ban, policy change) | Medium | Email backup list (Phase 2); second channel (Phase 3) |

### 7.4 Inconsistencies Found During Audit

| # | Issue | Resolution |
|---|---|---|
| I1 | `make-scenarios.md` documents Make.com workflows that are being deprecated | Keep as reference during migration; add a header note "Legacy — migrating to n8n" |
| I2 | `PHASE_0_IMPLEMENTATION_SPEC.md` references Make.com as the orchestrator | Add a footnote: "Orchestrator migrated to n8n self-host — see N8N_MIGRATION_PLAN.md" |
| I3 | `MASTER_IMPLEMENTATION_ROADMAP.md` §3 still shows "Phase 0 BUILD: not started" | Update to reflect current state (Phase 0 built, migration in progress) |
| I4 | The `04-phase-1/` folder was created but is not referenced in the main README.md | Update README.md to include Phase 1 in the structure |
| I5 | `PATCH-001-fixes.md` describes Make.com fixes that are now embedded in the working Make.com setup but won't exist in n8n | Keep for historical reference; n8n workflows will be built correctly from scratch |

---

## 8. Strategic Review

### 8.1 Is the current direction correct?

**Yes.** The migration from Make.com to n8n self-host is the correct long-term decision:
- $7.09/mo fixed vs. $16-99/mo scaling linearly with users
- Unlimited operations removes the fundamental constraint
- Self-hosted = full ownership, no vendor lock-in
- The migration plan is sound and nearly complete

### 8.2 What should be challenged?

| Question | Assessment |
|---|---|
| Should we have built on n8n from the start? | **No.** Make.com got the concept validated in days. That speed had value. Now we migrate with confidence because we KNOW the system works. |
| Is Hetzner the right long-term host? | **Yes.** 20+ year track record, stable pricing, professional infrastructure. No concerns. |
| Should we add HTTPS/domain now? | **Not urgent.** The bot and Sheets connections work without it. Add it when convenient (improves professionalism but not functionality). |
| Is Google Sheets still the right CRM? | **For now, yes.** At 500+ active users, consider migrating to PostgreSQL (free on the same server). But Sheets works fine for Phase 1–2 scale. Flag for Phase 3 review. |
| Should the Phase 1 spec be revised given the architecture change? | **Minor updates only.** The Phase 1 spec already recommends Telegram native scheduler (independent of Make/n8n) and offers Apps Script as a report option. The weekly report and nudges will just be built in n8n instead of Make.com — same logic, different tool. |

### 8.3 Opportunities for simplification

1. **Quiz optimization:** When rebuilding in n8n, use a single JavaScript Code Node for all scoring logic (replaces the fragile Set Variable → module reference chains that caused bugs in Make.com).
2. **Single workflow architecture:** In n8n, the entire bot can be ONE workflow with a Switch node — simpler than Make.com's separate-scenarios constraint.
3. **Version control for workflows:** n8n workflows export as JSON — these can be stored in the repo, giving you proper version history.

---

## 9. Revised Roadmap

```
IMMEDIATE (This week)
━━━━━━━━━━━━━━━━━━━
□ Complete Google Sheets Service Account connection (10 min)
□ Build n8n main workflow (2-3 hours)  
□ Build n8n quiz + scoring (1-2 hours)
□ Build n8n booking sync (30 min)
□ Build n8n backup (15 min)
□ Test T1-T10 (1 hour)
□ Go LIVE (activate bot for real users)

WEEK 2-3 (Phase 1 start)
━━━━━━━━━━━━━━━━━━━
□ Create discussion group
□ Write + schedule first content batch
□ Build weekly report in n8n
□ Build nudges in n8n
□ Produce "3 American Sounds" asset
□ Decommission Make.com (after 2 weeks stable)

WEEKS 3-8 (Phase 1 execution)
━━━━━━━━━━━━━━━━━━━
□ 5-6 posts/week consistently
□ Weekly report running
□ Collect stories
□ Measure baseline conversion rates
□ Identify winning content category

WEEK 9+ (Gate check → Phase 2)
━━━━━━━━━━━━━━━━━━━
□ ≥4 weeks of KPI data
□ ≥1 proven content category
□ Write Phase 2 spec (A/B tests, drips, referral)
```

---

## 10. Agent Handover Documentation

### 10.1 Project Identity

- **Project:** Empire English Community — Growth Automation System
- **Repository:** `empireenglishcommunity-glitch/EEC-REPO`
- **Owner:** Mahmoud Ashri (macalempire@gmail.com)
- **Mandate:** Long-term systems architecture — every decision must prioritize lifetime scalability, reliability, low maintenance, zero vendor lock-in

### 10.2 Key Accounts & Infrastructure

| System | Access | Notes |
|---|---|---|
| Telegram Bot | @EmpireEnglishBot | Token stored in n8n + Make.com |
| Hetzner Cloud | console.hetzner.cloud | Server: empire-n8n, IP: 77.42.43.250 |
| n8n | http://77.42.43.250:5678 | Owner: Mahmoud Ashri |
| Google Sheets CRM | "Empire CRM" | 4 tabs: Subscribers, Events, Config, String_Table |
| Cal.com | cal.com/empireenglish/level-call | Booking for free calls |
| Make.com | eu1.make.com (scenario 6256394 + 6262016) | Legacy — to be decommissioned |
| Google Cloud | console.cloud.google.com (project: empire-english-n8n) | For Service Account credentials |

### 10.3 The Single Most Important Next Action

**Complete the Google Sheets Service Account connection in n8n.** This is the single blocker preventing all other progress. It requires:
1. Create Service Account in Google Cloud (IAM → Service Accounts)
2. Create a JSON key for it
3. Share Empire CRM sheet with the service account email
4. Enable Google Sheets API + Google Drive API
5. Paste the email + private key into n8n

Once this is done, all workflows can be built and the system goes live.

### 10.4 Design Principles (locked)

1. **Self-hosted, open-source preferred** — avoid platforms with per-operation costs or restrictive limits
2. **Free-first** — paid spend only where it directly buys retention or removes friction
3. **Solo-operator sustainable** — if it needs daily manual effort, automate it or cut it
4. **One source of truth** — Google Sheets CRM (until scale requires PostgreSQL)
5. **Gate discipline** — don't start a phase until the prior gate passes
6. **Honest by default** — real scarcity, attainable outcomes, never "sound 100% native"
7. **Arabic-led bilingual** — MSA, fresh/conversational, pan-Arab

### 10.5 File Map (what lives where)

```
README.md                              ← Project index (read first)
growth-program/
  01-foundation/                       ← Product + business design
    Empire English Community Learning System.md
    STRATEGIC_EXPANSION_ROADMAP.md
  02-strategy/                         ← Funnel + phasing
    CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md
    MASTER_IMPLEMENTATION_ROADMAP.md
  03-phase-0/                          ← Phase 0 (capture spine)
    PHASE_0_IMPLEMENTATION_SPEC.md     ← Build spec
    PHASE_0_CONTENT_ASSETS.md          ← Bilingual bot copy
    build-kit/                         ← Hands-on build assets
      README.md                        ← Build order
      botfather-setup.md               ← Telegram bot setup guide
      make-scenarios.md                ← Make.com runbook (LEGACY)
      quiz-logic.md                    ← Quiz scoring + plan templates
      N8N_MIGRATION_PLAN.md            ← n8n migration guide (CURRENT)
      PATCH-001-fixes.md               ← Bug fixes (Make.com era)
      crm/                             ← Importable CSV templates
        subscribers.csv, events.csv, config.csv, string_table.csv
  04-phase-1/                          ← Phase 1 (content + reporting)
    PHASE_1_IMPLEMENTATION_SPEC.md     ← Build spec
PROJECT_STATUS_AND_HANDOVER.md         ← THIS DOCUMENT
```

---

## 11. Conclusion

The Empire English project has a **strong strategic foundation** (exceptional documentation) and a **proven functional system** (Make.com bot works end-to-end). The migration to self-hosted n8n is the correct strategic decision and is ~40% complete. The **single blocker** is the Google Sheets Service Account setup — approximately 10 minutes of focused work.

Once that connection is made, the workflow rebuild in n8n will take 1–2 focused days (cleaner than the Make.com build thanks to JavaScript Code Nodes and single-workflow architecture). Then the bot goes live for real users and Phase 1 begins.

**The project is in a strong position.** The infrastructure is sound, the strategy is clear, and the remaining work is well-defined. There are no fundamental architectural problems — only completion work.

---

*End of Project Status & Handover Document v1.0*
