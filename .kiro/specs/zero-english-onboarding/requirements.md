# Requirements — Bawaba: Zero-English Onboarding

> **Codename:** Bawaba (بوابة — "Gateway")
> **Purpose:** Make the Discord learning system fully accessible to
> Arabic speakers who have NEVER learned English before — their literal
> first encounter with the language.
> **Context:** 16 real students (9 free + 7 paid) are about to be
> invited. Some are absolute beginners. The current system requires
> typing English commands and reading English channel names — an
> impossible barrier for someone with zero English.

---

## Core Principle

**The bot interface IS the first English lesson.** Rather than requiring
English literacy as a prerequisite to use the system, the system teaches
English literacy by gradually revealing it — starting from 100% Arabic
and transitioning to bilingual as the student progresses.

---

## Requirements

### R1 — Zero-English Registration
A student who cannot read or type a single English word MUST be able to
register themselves and begin the program. Acceptance criteria:
- At least one registration path requires zero English typing
- At least one registration path requires zero typing at all (reaction-based)
- The student understands what happened (confirmation in Arabic)

### R2 — Zero-English Task Completion
A student who cannot type English MUST be able to complete daily tasks
and earn points. Acceptance criteria:
- Number-based commands (`!1` through `!7`) work as direct task aliases
- Arabic command aliases (`!تم`, `!تم 1`) work identically to English ones
- The daily task post's numbering matches the number commands exactly
- Verification still works (no shortcutting the anti-cheat system)

### R3 — Zero-Reading Onboarding
A student who struggles to read (in ANY language) MUST be able to
understand how the system works. Acceptance criteria:
- Audio onboarding messages exist (Arabic voice clips explaining steps)
- A visual journey map image exists (infographic, not text)
- A video walkthrough is linked (YouTube, Arabic narration)
- At least one onboarding path is purely interactive (learning by doing)

### R4 — Gradual English Introduction
The bot MUST transition its own response language from Arabic-first to
bilingual as the student progresses. Acceptance criteria:
- Week 1: bot responses primarily Arabic, commands shown as numbers
- Week 2-3: responses bilingual (Arabic first, English shown as learning)
- Week 4+: full bilingual (current system, English + Arabic together)
- The transition is automatic (based on join date), not manual

### R5 — Human Bridge on Day 1
A brand-new student MUST have a human touchpoint on their first day.
Acceptance criteria:
- The assigned buddy receives a specific prompt to reach out
- The prompt suggests sending a voice message (not text)
- The buddy knows what the new student's first task is

### R6 — Cognitive Load Reduction
A new student MUST NOT be overwhelmed by 30+ channels on day 1.
Acceptance criteria:
- A mechanism exists to show fewer channels initially
- The student has a clear "I'm done with orientation" signal
- Full server access unlocks after orientation

### R7 — Backward Compatibility
All existing commands (`!join`, `!done accent`, etc.) MUST continue
working exactly as before. Acceptance criteria:
- Zero breaking changes to the current command interface
- Students who already know English commands are unaffected
- The Arabic/number aliases are purely ADDITIVE

### R8 — Ships Behind Feature Flags
Every piece of this ships dormant and gets enabled via `!flag`, per the
Aegis convention. Acceptance criteria:
- Each phase can be enabled/disabled independently
- Ghost bot testing verifies each phase before production release
- Kill switch works instantly if anything misbehaves

---

## Constraints

- Same $7/month Hetzner VPS — no new services, no new accounts
- Kokoro TTS (already on the server) for Arabic audio generation
- empire-html2img (already running) for visual infographic generation
- No changes to the underlying curriculum or gamification mechanics
- Must work on mobile Discord (most Arab students use phones)

---

## Out of Scope (explicitly)

- Translating the curriculum CONTENT into Arabic (that's a content
  project, not a UX project — the content is English because the goal
  is to LEARN English)
- RTL layout changes to the practice platform (already handled with
  `lang="ar" dir="rtl"` spans)
- A separate Arabic-only bot (one bot, additive layers)
