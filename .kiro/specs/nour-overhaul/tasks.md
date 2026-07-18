# Nour Overhaul — Implementation Tasks

> **Initiative #14 — Codename: Rawiya (الراوية)**
> 8 phases, executed in order. Each phase is independently deployable.

---

## Phase R0: MSA Foundation (Language Switch)

The single most impactful change — touches every Nour file.

- [ ] R0.1: Rewrite `NOUR_SYSTEM_PROMPT` in `nour_concierge.py` to MSA
  - Replace all Egyptian colloquial instructions with MSA equivalents
  - Keep warmth: "friendly news anchor" tone, not "government letter"
  - Add explicit instruction: "NEVER use Egyptian dialect"
  - Add instruction: "Use accessible modern MSA, not literary/archaic"
- [ ] R0.2: Rewrite all template fallback responses in `nour_concierge.py` to MSA
- [ ] R0.3: Rewrite all proactive message prompts in `nour_proactive.py` to MSA
  - System prompt for generation
  - All template fallbacks (new_student, quiet_student, score_drop, first_milestone)
- [ ] R0.4: Rewrite all DM messages in `nour_onboarding.py` to MSA
  - Wrong channel redirect
  - Command typo help
- [ ] R0.5: Rewrite time-of-day personality strings in `nour_personality.py` to MSA
- [ ] R0.6: Rewrite cultural context strings in `nour_personality.py` to MSA
- [ ] R0.7: Update `data/nour_knowledge.md` to MSA (the entire knowledge base)
- [ ] R0.8: Register `nour_msa` flag in `flag_registry.py` (under "nour" initiative)
- [ ] R0.9: Gate the new system prompt behind `nour_msa` flag (old prompt as fallback)
- [ ] R0.10: Run `scripts/bidi_check.py` on all modified files — 0 issues required
- [ ] R0.11: Deploy + verify via a test DM that Nour responds in MSA

**Deliverable:** Nour speaks MSA. Zero colloquial markers. Bidi-safe.

---

## Phase R1: Knowledge Base Expansion

Nour can only answer what she knows. Expand dramatically.

- [ ] R1.1: Create `data/nour_knowledge/` directory structure
- [ ] R1.2: Write `system_overview.md` (what Empire English is, philosophy, who it's for)
- [ ] R1.3: Write `daily_tasks.md` (all 7 tasks — what, why, how, troubleshooting, mobile guide)
- [ ] R1.4: Write `channels.md` (every student channel, purpose, what to do there)
- [ ] R1.5: Write `commands.md` (all 40+ commands with Arabic aliases, examples)
- [ ] R1.6: Write `practice_platform.md` (full web guide, !link, mobile install, offline)
- [ ] R1.7: Write `troubleshooting.md` (top 20 problems + step-by-step solutions)
- [ ] R1.8: Write `mobile_guide.md` (Discord for beginners on iPhone/Android, MSA)
- [ ] R1.9: Write `study_strategies.md` (motivation, habit building, when to practice)
- [ ] R1.10: Write `faq.md` (top 50 questions, pre-answered in MSA)
- [ ] R1.11: Write `owner_ops.md` (admin knowledge — only loaded in owner context)
- [ ] R1.12: Update `nour_concierge.py` to load from the new multi-file KB
  - Smart loading: only include relevant section(s) per query (token-efficient)
  - Category detection from student's question
- [ ] R1.13: All KB files in MSA, bidi_check passes

**Deliverable:** Nour answers 95%+ of system questions correctly.

---

## Phase R2: Structured Onboarding Journey

The guided experience for new students.

- [ ] R2.1: Create `nour_journey.py` module
- [ ] R2.2: Create `student_journey` DB table (discord_id, current_step, step_data, timestamps)
- [ ] R2.3: Write journey step messages (all MSA, bidi-safe):
  - `welcome` — greeting + ask about their goal
  - `task_intro` — explain 7 tasks simply, encourage trying task 1
  - `first_task` — celebrate + explain practice platform
  - `platform_intro` — web platform walkthrough
  - `streaks_explained` — points, streaks, levels
  - `channels_tour` — introduce channels one by one (3 messages over 3 days)
  - `independent` — "you're ready, I'm always here"
- [ ] R2.4: Implement state machine (advance on triggers, timeout nudges)
- [ ] R2.5: Integrate with `on_member_join` — start journey after role-gate accept
- [ ] R2.6: Handle interruptions (student asks question mid-journey → answer, then resume)
- [ ] R2.7: Register `nour_journey` flag
- [ ] R2.8: Add journey status to Nour's context (so she knows where each student is)
- [ ] R2.9: Deploy + test with a fresh test member

**Deliverable:** New students get a guided 7-day onboarding entirely from Nour.

---

## Phase R3: Enhanced Proactive Intelligence

Expand the 4-condition system to 9+ conditions.

- [ ] R3.1: Add "channel ignorance" trigger (never visited X after N days)
- [ ] R3.2: Add "approaching streak bonus" trigger (streak == 6 or 13 or 29)
- [ ] R3.3: Add "exam readiness" trigger (week >= 8, never used !exam)
- [ ] R3.4: Add "repeated failures" trigger (3+ wrong quiz answers → micro-tutorial)
- [ ] R3.5: Add "return after absence" trigger (was inactive 3+ days, active today)
- [ ] R3.6: Rewrite all proactive prompt templates in MSA
- [ ] R3.7: Register `nour_enhanced_proactive` flag
- [ ] R3.8: Enable `nour_proactive` flag globally (currently OFF)
- [ ] R3.9: Deploy + monitor for 24h (check rate limiting works correctly)

**Deliverable:** Nour proactively reaches out for 9 scenarios, all MSA, rate-limited.

---

## Phase R4: Micro-Tutorials

Pre-written, MSA, step-by-step guides for common confusion points.

- [ ] R4.1: Create `nour_tutorials.py` module
- [ ] R4.2: Write tutorial content (MSA, bidi-safe):
  - `recording_mobile` — how to record voice on Discord mobile
  - `wrong_channel` — why commands need #bot-commands
  - `done_without_proof` — explanation of verification system
  - `streak_broken` — how to restart, encouragement
  - `find_tasks` — guide to daily task channel
  - `practice_platform_access` — !link + token explanation
  - `quiz_struggling` — study tip after 3+ wrong answers
  - `first_day_complete_guide` — full walkthrough of day 1
- [ ] R4.3: Implement trigger detection in `nour_concierge.py` (context-aware tutorial dispatch)
- [ ] R4.4: Register `nour_tutorials` flag
- [ ] R4.5: Integrate with quiz failure tracking in `verification.py`
- [ ] R4.6: Deploy + test each tutorial trigger

**Deliverable:** Confused students get instant, clear micro-tutorials (not generic AI responses).

---

## Phase R5: Owner Operations Interface

Nour as your right-hand via Telegram.

- [ ] R5.1: Enhanced daily Nour report (replace basic digest student section):
  - Trending students (improving)
  - At-risk students (declining/silent)
  - Questions handled (count + themes)
  - Suggestions (AI-generated from data)
  - System health
- [ ] R5.2: Implement owner command parser in `ops_poller.py`:
  - Detect `/command` format in owner messages
  - Route to new `nour_ops_commands.py` handler
- [ ] R5.3: Implement commands:
  - `/check [name]` — full student status report
  - `/announce [msg]` — post announcement in Discord
  - `/nudge [name]` — send personalized Nour check-in
  - `/flag [name] [reason]` — mark for attention
  - `/status` — system health
  - `/students` — roster with activity summary
- [ ] R5.4: Register `nour_owner_commands` flag
- [ ] R5.5: Deploy + test each command via real Telegram

**Deliverable:** Owner manages the community from Telegram. Zero need to open Discord for routine ops.

---

## Phase R6: Graduated Presence

Nour steps back as students mature.

- [ ] R6.1: Implement `_get_presence_level(discord_id)` function:
  - Week 1-2 → "high" (daily)
  - Week 3-4 → "medium" (every 2-3 days)
  - Week 5-8 → "low" (weekly)
  - Week 9+ → "minimal" (monthly + problems only)
- [ ] R6.2: Integrate presence level into proactive check decisions
- [ ] R6.3: Integrate presence level into journey (skip steps for advanced members)
- [ ] R6.4: Register `nour_graduated` flag
- [ ] R6.5: Deploy + verify experienced students aren't over-contacted

**Deliverable:** New students feel supported, experienced students aren't annoyed.

---

## Phase R7: Confusion Detection Enhancement

Real-time intelligence beyond the current wrong-channel/typo detection.

- [ ] R7.1: Detect "stuck" patterns (same command 3+ times in 5 min)
- [ ] R7.2: Detect "lost" patterns (visited 3+ wrong channels before finding right one)
- [ ] R7.3: Detect language confusion (student writing in Arabic in English-only channel)
- [ ] R7.4: Detect first-time struggles (day 1 student, no task completed after 4h)
- [ ] R7.5: Wire each detection to the appropriate micro-tutorial (R4)
- [ ] R7.6: Deploy + monitor false-positive rate

**Deliverable:** Nour catches confusion in real-time and helps before the student gives up.

---

## Phase R8: Final Integration + Testing

- [ ] R8.1: Full journey test (fresh member → 7-day simulation)
- [ ] R8.2: Bidi check all new/modified files
- [ ] R8.3: Load test (simulate 16 concurrent students asking questions)
- [ ] R8.4: Owner command test (all 6 commands via real Telegram)
- [ ] R8.5: MSA quality review (sample 20 Nour responses, verify zero colloquial)
- [ ] R8.6: Update `STATUS.md` and `SESSION_CONTINUITY.md`
- [ ] R8.7: Enable all flags globally
- [ ] R8.8: Close initiative #14

**Deliverable:** Rawiya initiative fully closed. Nour runs the community autonomously.

---

## Phase Execution Order

Phases are designed to be executed sequentially (each builds on previous):

```
R0 (MSA) → R1 (Knowledge) → R2 (Journey) → R3 (Proactive) →
R4 (Tutorials) → R5 (Owner Ops) → R6 (Graduated) → R7 (Detection) → R8 (Integration)
```

However, R0 + R1 can be done together (both are content, no code dependencies).
R3 + R4 can be done together (proactive triggers + tutorial content).
R5 is independent of R3/R4/R6/R7 (owner-facing, different interface).

Suggested grouping for efficiency:
- **Batch 1:** R0 + R1 (language + knowledge — the foundation)
- **Batch 2:** R2 (journey — the biggest new feature)
- **Batch 3:** R3 + R4 (proactive + tutorials — complementary)
- **Batch 4:** R5 (owner ops — independent)
- **Batch 5:** R6 + R7 + R8 (graduation + detection + final integration)
