# Empire English — Documentation Index

**Repository purpose.** This repo holds the **planning, strategy, and build specifications** for Empire English Community — a system-driven English-learning program and the Telegram-channel funnel that grows and converts it. These are working documents; **no application code is built or deployed from this repo yet.**

> **New here? Read in this order:** 1 → 2 → 3 → 4 → 5 → 6 (below).

---

## 🗂️ Repository structure

All working documents live under **`growth-program/`**, grouped by layer. Infrastructure documentation lives under **`infrastructure/`**. The root holds this index, status documents, and checkpoints.

```
README.md                         ← you are here (the map)
PROJECT_STATUS_AND_HANDOVER.md    ← full project status & agent handover
CHECKPOINT_2026-06-20.md          ← daily checkpoint (infrastructure day)
growth-program/
  01-foundation/                  ← the product + business
      Empire English Community Learning System.md
      STRATEGIC_EXPANSION_ROADMAP.md
  02-strategy/                    ← funnel strategy + phasing
      CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md
      MASTER_IMPLEMENTATION_ROADMAP.md
  03-phase-0/                     ← the first build phase
      PHASE_0_IMPLEMENTATION_SPEC.md
      PHASE_0_CONTENT_ASSETS.md
      build-kit/                  ← hands-on build assets & CRM templates
infrastructure/                   ← technical implementation references
    N8N_WORKFLOW_PATTERNS.md      ← verified n8n patterns (MANDATORY reference)
    QUIZ_SYSTEM_TECHNICAL_AUDIT.md ← quiz system audit & troubleshooting
    SERVER_REFERENCE.md           ← server & hosting documentation
```

---

## 📚 The documents (read order)

| # | Document | Layer | What it answers |
|---|---|---|---|
| 1 | [Empire English Community Learning System](growth-program/01-foundation/Empire%20English%20Community%20Learning%20System.md) | Product | *What we teach* — curriculum, four levels, daily loop, Discord community, AI content factory, placement, governance |
| 2 | [STRATEGIC_EXPANSION_ROADMAP](growth-program/01-foundation/STRATEGIC_EXPANSION_ROADMAP.md) | Business | *How we sustain it* — pricing ladder, community structures, monetization, free-tool stack, branding |
| 3 | [CHANNEL_GROWTH_CONVERSION_BLUEPRINT](growth-program/02-strategy/CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md) | Funnel strategy | *How we grow & convert* — the channel→bot funnel, content engine, segmentation, reporting, and the **10 locked decisions** |
| 4 | [MASTER_IMPLEMENTATION_ROADMAP](growth-program/02-strategy/MASTER_IMPLEMENTATION_ROADMAP.md) | Program map | *In what order we build* — the full phased picture (P0→P3), gates, and "you are here" |
| 5 | [PHASE_0_IMPLEMENTATION_SPEC](growth-program/03-phase-0/PHASE_0_IMPLEMENTATION_SPEC.md) | Build spec | *Exactly how to build Phase 0* — bot, quiz, CRM schema, automations, acceptance tests |
| 6 | [PHASE_0_CONTENT_ASSETS](growth-program/03-phase-0/PHASE_0_CONTENT_ASSETS.md) | Content | *The words that fill the bot* — bilingual (Arabic-led) copy for every Phase 0 flow |

**Mental model:** Product + Business (1–2) → Funnel strategy (3) → Program map (4) → Phase build spec (5) → Content (6).

---

## 🧭 Single sources of truth (avoid duplication)

To prevent the same thing being defined in multiple places, each cross-cutting topic has **one canonical home**. When in doubt, edit only the canonical doc; everything else should *reference* it.

| Topic | Canonical source |
|---|---|
| **Phasing / roadmap (P0–P3, gates)** | `02-strategy/MASTER_IMPLEMENTATION_ROADMAP.md` |
| **Pricing ladder & prices** | `01-foundation/STRATEGIC_EXPANSION_ROADMAP.md` §7 *(live prices set at build time in the CRM `Config` tab)* |
| **Free-tool stack** | `01-foundation/STRATEGIC_EXPANSION_ROADMAP.md` §8 |
| **Locked funnel decisions** | `02-strategy/CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md` §10 |
| **Phase 0 build details** | `03-phase-0/PHASE_0_IMPLEMENTATION_SPEC.md` |
| **Phase 0 copy/strings** | `03-phase-0/PHASE_0_CONTENT_ASSETS.md` |
| **KPIs & weekly report** | `02-strategy/CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md` §7 |
| **n8n workflow implementation patterns** | `infrastructure/N8N_WORKFLOW_PATTERNS.md` |
| **Quiz system architecture & troubleshooting** | `infrastructure/QUIZ_SYSTEM_TECHNICAL_AUDIT.md` |
| **Server & hosting infrastructure** | `infrastructure/SERVER_REFERENCE.md` |

> **Rule of thumb:** strategy lives in the Blueprint, phasing lives in the Master Roadmap, build detail lives in the Phase specs, and copy lives in the Content pack. Don't restate one in another — link instead.

---

## ✅ Status — where the program stands

| Milestone | Status |
|---|---|
| Strategy & 10 funnel decisions locked | ✅ Complete |
| Phase 0 build spec | ✅ Complete |
| Phase 0 bilingual content | ✅ Drafted |
| Full phased roadmap (P0→P3) | ✅ Mapped |
| Docs organized into `growth-program/` | ✅ Complete |
| Pre-build decisions (pricing display, Arabic register, orchestrator) | ✅ Locked |
| **Infrastructure (Hetzner + n8n + Cloudflare Tunnel)** | ✅ Complete & running |
| **Phase 0 BUILD — Bot Core (start, menu, buttons)** | ✅ Working |
| **Phase 0 BUILD — Quiz System (Q1–Q7 + scoring + plan)** | ✅ Working |
| **Phase 0 BUILD — CRM Integration (Google Sheets)** | ✅ Working |
| Phase 0 BUILD — remaining routes (resource, how, call, community) | 🟡 Partially built |
| Phase 0 BUILD — booking sync, backup, hot-lead alerts | ⬜ Not started |
| Asset production (3 audio clips + PDF) + Config links | ⬜ Pending |
| Phase 1–3 detailed specs | ⬜ Written at each gate (not before) |

---

## ⚙️ Locked decisions (quick reference)

Telegram channel + bot → Discord product · 5-button bot menu · primary goal = free taster/trial (self-serve) **+** founder-led calls in parallel · main offer = **Core** + time-boxed **Founding Citizen** · lead-magnet ladder (quiz → "3 American Sounds" → 7-Day Speaking Starter → Core) · **Arabic-led bilingual** · high call capacity · explicit consent + **Google Sheets** CRM · **5–6 posts/week** · **Cal.com** booking.

**Pre-build finalizations (locked):** **no public prices day one** — pricing via call/DM · Arabic register = **MSA, fresh & conversational** · orchestrator = **n8n self-hosted** (migrated from Make.com) · hosting = **Hetzner Cloud CX23** ($7.09/mo) · domain = **empireenglish.online** (Cloudflare Tunnel).

*(Full detail: `02-strategy/CHANNEL_GROWTH_CONVERSION_BLUEPRINT.md` §10.)*

---

## 🚧 Conventions

- All documents are **planning artifacts** until a Phase is explicitly approved for build.
- Prices, costs, conversion rates, and timelines are **anchors to validate**, never promises.
- Tone guardrail: honest, attainable claims — never "sound 100% native."
- Free-first; paid spend only after LTV:CAC ≥ 3:1 (Phase 3 at earliest).
- **Folder convention:** working docs live in `growth-program/`; each new phase gets its own numbered subfolder. Keep the repo root limited to this README and the program folder.

---

*Index maintained as part of repo organization. Update this file whenever a document is added, moved, renamed, or its canonical role changes.*
