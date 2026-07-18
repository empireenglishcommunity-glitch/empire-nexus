# Nour Overhaul — Design

> **Initiative #14 — Codename: Rawiya (الراوية)**

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    NOUR 2.0 (الراوية)                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  STUDENT    │  │  KNOWLEDGE   │  │   OWNER       │ │
│  │  INTERFACE  │  │  ENGINE      │  │   INTERFACE   │ │
│  │             │  │              │  │               │ │
│  │ • DM handler│  │ • System KB  │  │ • Daily report│ │
│  │ • #ask-nour │  │ • FAQ bank   │  │ • Commands    │ │
│  │ • Journey   │  │ • Tutorials  │  │ • Alerts      │ │
│  │ • Proactive │  │ • Context    │  │ • Execute     │ │
│  └─────────────┘  └──────────────┘  └───────────────┘ │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              PERSONALITY LAYER                    │   │
│  │  • MSA (فصحى) — warm, never robotic             │   │
│  │  • Gender-correct addressing                     │   │
│  │  • Cultural/time awareness                       │   │
│  │  • Memory persistence                            │   │
│  │  • Graduated presence (decreasing over weeks)    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │              AI PROVIDER CHAIN                    │   │
│  │  Groq (70B) → Gemini → Template (never silence)  │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

## Component 1: MSA System Prompt Rewrite

The single most impactful change. Currently Nour's system prompt
instructs "Egyptian Arabic عامية" everywhere. Replace with MSA (فصحى)
while keeping warmth:

**Current tone (Egyptian):**
> "أيوه تمام! ماشي يا باشا، خليني أشوف... أنت عايز تسجل المهمة؟"

**New tone (MSA, warm):**
> "بالتأكيد! دعني أساعدك. هل تريد تسجيل المهمة؟ أنا هنا لأي سؤال."

Key principles:
- MSA ≠ cold. Think "friendly news anchor" not "government letter"
- Short sentences (2-5 max, same as current)
- Emojis still used (they're universal)
- Name addressing preserved ("أهلاً [Name]!")
- Avoid archaic/literary MSA — use modern, accessible MSA

Affected files: `nour_concierge.py` (NOUR_SYSTEM_PROMPT), `nour_proactive.py`
(all prompt templates + fallbacks), `nour_onboarding.py` (all DM messages),
`nour_personality.py` (time personality strings), `data/nour_knowledge.md`.

## Component 2: Structured Onboarding Journey

New module: `nour_journey.py`

A state machine that tracks each student's onboarding progress:

```
JOIN → WELCOME → TASK_INTRO → FIRST_TASK → PLATFORM_INTRO →
STREAKS_EXPLAINED → CHANNELS_TOUR → INDEPENDENT
```

Each state:
- Has a Nour DM message (MSA, with visual examples)
- Waits for a trigger before advancing (e.g., student completes first task)
- Has a timeout (if no progress in 24h → gentle nudge)
- Can be interrupted by student questions (Nour answers, then resumes journey)

Storage: New `student_journey` table:
```sql
CREATE TABLE IF NOT EXISTS student_journey (
    discord_id    TEXT PRIMARY KEY,
    current_step  TEXT NOT NULL DEFAULT 'welcome',
    step_data     TEXT DEFAULT '{}',  -- JSON for step-specific state
    started_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_step_at  TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at  TEXT DEFAULT NULL
);
```

Journey steps detail:

| Step | Trigger to advance | Nour sends |
|------|-------------------|------------|
| welcome | Automatic (on role-gate accept) | Welcome + "I'm Nour, your guide" + ask about their goal |
| task_intro | Student responds OR 30min timeout | Explains 7 tasks simply, asks them to try task 1 |
| first_task | Student completes ANY task (!done) | Celebrates! Explains the rest + practice platform |
| platform_intro | Student visits practice page (token validated) OR 24h | Shows how to use the web platform |
| streaks_explained | 3 days of activity OR day 4 | Explains streaks/points/levels |
| channels_tour | Day 5+ | Introduces 1 channel per message over 3 days |
| independent | Day 8 or all steps done | "You're ready! I'm always here if you need me" |

## Component 3: Expanded Knowledge Base

Restructure `data/nour_knowledge.md` into a richer, categorized format:
`data/nour_knowledge/`:
- `system_overview.md` — what Empire English is, philosophy
- `daily_tasks.md` — all 7 tasks in detail (what, why, how, troubleshooting)
- `channels.md` — every channel, what it's for, how to use it
- `commands.md` — all 40+ commands with Arabic aliases
- `practice_platform.md` — full guide to the web platform
- `troubleshooting.md` — common problems + solutions (expanded)
- `mobile_guide.md` — how to use Discord on iPhone/Android (for beginners)
- `study_strategies.md` — motivation, habit building, what to do when stuck
- `faq.md` — top 50 questions students ask
- `owner_ops.md` — admin knowledge (only used in owner-facing context)

The system prompt instructs Nour which file(s) to reference based on
the student's question category. Token-efficient: only the relevant
section is included in each AI call, not the entire KB.

## Component 4: Owner Operations Interface (Telegram)

Extends existing Markaz integration. Nour already sends daily digests
and escalation alerts. New capabilities:

### Daily Nour Report (enhanced, replaces current digest's student section):
```
📋 Nour Daily Report — July 17

👥 Active: 12/16 students
📈 Trending up: Ahmad (streak 14), Fatima (first 7/7!)
⚠️ Needs attention: Omar (3 days silent), Sara (score dropping)
❓ Questions today: 8 handled, 0 escalated
💡 Suggestion: Omar mentioned exams last week — might explain silence

🔧 System: 0 errors, Groq 100% uptime
```

### Owner Commands (via Telegram reply):
- `/check [name]` — get full student status
- `/announce [message]` — Nour posts announcement in Discord
- `/nudge [name]` — Nour sends personalized check-in to student
- `/flag [name] [reason]` — mark student for attention
- `/status` — system health overview
- `/students` — quick roster with activity status

These are processed by `ops_poller.py` (already polls Telegram for
owner messages). New: detect `/command` format, route to Nour's ops
handler instead of treating as a reply-to-escalation.

## Component 5: Proactive Intelligence Engine (Enhanced)

Current `nour_proactive.py` checks 4 conditions every 2h. Expand to:

| Trigger | Detection | Action |
|---------|-----------|--------|
| New + not started (24h) | `total_submissions == 0 AND hours_since_join > 20` | Journey nudge (already in journey) |
| Gone quiet (2 days) | `days_inactive >= 2` | Personalized check-in with memory context |
| Score dropping | `recent_avg < older_avg by 20%+` | Encouragement + specific tip |
| First milestone | `tasks_today == 7 AND first_time` | Celebration |
| Channel ignorance | `never visited #daily-word after 5 days` | Introduce the channel |
| Approaching streak bonus | `streak == 6 AND tasks_today >= 1` | "One more day for the bonus!" |
| Exam readiness | `week >= 8 AND !exam never used` | Suggest advancement |
| Repeated failures | `3+ wrong quiz answers in a row` | Micro-tutorial DM |
| Return after absence | `was_inactive_3d AND active_today` | Welcome back message |

Rate limiting preserved: max 1 proactive DM per student per 6h,
max 5 per cycle.

## Component 6: Graduated Presence

New field on `student_journey` or computed from `member_week_number()`:

| Student Age | Nour's Behavior |
|-------------|-----------------|
| Week 1-2 | Daily presence: journey steps, check-ins, celebrations |
| Week 3-4 | Every 2-3 days: milestones, gentle nudges if needed |
| Week 5-8 | Weekly: summary only, intervenes on problems |
| Week 9+ | Minimal: monthly letter, only on issues or achievements |

Implementation: `_get_presence_level(discord_id)` returns `"high"`,
`"medium"`, `"low"`, `"minimal"` — proactive checks skip students
whose presence level doesn't match the trigger's urgency.

## Component 7: Confusion Detection + Micro-Tutorials

New: `nour_tutorials.py`

Pre-written MSA micro-tutorials (not AI-generated — too important to
risk grammar errors):

| Situation | Tutorial |
|-----------|----------|
| Can't record voice (mobile) | Step-by-step with Discord mobile UI description |
| Command in wrong channel | Redirect + explain why it matters |
| !done without proof | Explain verification system |
| Streak broken | Explain how to restart, encourage |
| Can't find tasks | Guide to #l0-daily-tasks |
| Practice platform not loading | Check token, explain !link |
| Quiz wrong 3+ times | Explain the actual answer + study tip |

These are stored as MSA markdown templates, not AI-generated per call.
Triggered by detection logic in the enhanced proactive engine.

## What This Does NOT Do

- Does NOT add a second Discord bot (Nour is still the same bot)
- Does NOT require any new paid services ($0 budget)
- Does NOT change how commands work (only changes Nour's AI responses)
- Does NOT touch the practice platform (empire-dojo)
- Does NOT require Discord server restructuring
- Does NOT replace Markaz — extends it (Nour reports THROUGH Markaz)

## Flag Strategy

| Flag | What it gates | Default |
|------|---------------|---------|
| `nour_msa` | MSA system prompt (vs current عامية) | ON for new, OFF for existing initially |
| `nour_journey` | Structured onboarding journey | ON |
| `nour_enhanced_proactive` | Expanded proactive triggers | ON |
| `nour_owner_commands` | Telegram command processing | ON |
| `nour_tutorials` | Micro-tutorial DMs | ON |
| `nour_graduated` | Graduated presence logic | ON |

Existing flags (`nour_concierge`, `nour_proactive`, `nour_escalation`)
remain as kill-switches above all of these.
