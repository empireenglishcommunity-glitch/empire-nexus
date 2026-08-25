# A1 (Beginner) — CEFR Alignment Rationale

> **Owner approval gate.** This document states exactly how the A1 level maps
> to the CEFR, so the alignment is auditable before A1 goes live. Nothing is
> enabled for students until you sign off.

## Truth-in-labelling

A1 content is **CEFR-aligned** (built to the official CEFR A1 descriptors). On
completion, Empire English issues its own certificate: *"Empire English
certifies that [name] has demonstrated proficiency at CEFR Level A1."* We do
**not** claim "CEFR certified" — CEFR has no certifying body.

## What CEFR says A1 is (the target)

> *Can understand and use familiar everyday expressions and very basic phrases
> aimed at the satisfaction of needs of a concrete type. Can introduce
> themselves and others and can ask and answer questions about personal
> details such as where they live, people they know and things they have. Can
> interact in a simple way provided the other person talks slowly and clearly
> and is prepared to help.*
> — Council of Europe, CEFR global scale, A1.

## How this A1 course delivers that

### 1. Can-Do objectives (learning outcomes)
`can_do.json` → `A1` holds 15 curated descriptors across all four CEFR modes:
- **Reception** (4): understand familiar words/phrases, simple instructions,
  numbers/prices/times, very short simple texts.
- **Production** (5): give personal info; describe family/people/home; simple
  phrases; write simple sentences and short notes.
- **Interaction** (4): greet + introduce; ask/answer personal questions; handle
  numbers/quantities/cost/time; give/ask for things + likes/abilities.
- **Mediation** (2): convey a simple fact (name/number/price/time); signal
  understanding / ask for help.

Every week references the specific descriptors it targets (its `can_do` codes).

### 2. Grammar syllabus (A1 structures only)
`grammar_syllabus.json` → `A1`, one point per week, all firmly A1 per the
English Grammar Profile:

| Week | Grammar |
|------|---------|
| 1 | Verb *to be* + subject pronouns |
| 2 | Possessive adjectives + *have got* |
| 3 | Numbers, *there is/are*, time prepositions (at/in/on) |
| 4 | Place prepositions + *this/that/these/those* |
| 5 | Present simple (I/you/we/they) + *don't* |
| 6 | Present simple (he/she/it) *-s* + *some/any* |
| 7 | *How much / how many* + *I'd like* |
| 8 | Adjectives + question words (what/who/where/how) |
| 9 | *can/can't* + *like/love/hate* + *-ing* |
| 10 | Past of *to be* (*was/were*) + review |

No structure above A1 appears (no past simple of regular verbs, no present
continuous, no comparatives — those are A2+).

### 3. Vocabulary band (A1)
~340 active words across the 10 weeks, all high-frequency A1 items selected
against public CEFR-mapped references (Oxford 3000 A1 tags, English Vocabulary
Profile A1). Stored as **our own list** (word, pronunciation, Arabic gloss,
POS, example) — no third-party list is copied. Themes are the classic A1
"concrete needs" domains: self, family, numbers/time, home, routines, food,
shopping, descriptions, abilities/free time, and simple past events.

CEFR guidance puts A1 active vocabulary at roughly 500–750 words *receptive*;
~340 curated **active** production words for a 10-week beginner course is a
sound, achievable A1 core (the assessments test production, not passive
recognition of a huge list).

### 4. Skills coverage (all five, every week)
Each week file provides: **vocabulary**, **listening** (dictation items),
**pronunciation/phonology** (`phoneme_focus`), **speaking** (7 daily missions,
20–60s, rising in demand across the week), and **writing** (7 prompts). This
matches CEFR A1's balanced reception + production + interaction expectations.

### 4b. Reading (added 2026-08-24 — Phase 11B)

**The gap this closes.** Section 4 above lists vocabulary, listening,
pronunciation, speaking and writing — and that list was accurate, which is
exactly the problem: **there was no reading task at all.** CEFR treats reading
as reception alongside listening, so A1 published four reception descriptors but
only ever exercised the listening ones. Measured against `can_do.json`, two A1
descriptors were taught by **no week**:

- `A1.R.1` — *Can recognise familiar words and very basic phrases concerning
  themselves, their family and immediate concrete surroundings.*
- `A1.R.4` — *Can understand very short, simple texts a single phrase at a time.*

**What was added.** One authored passage per A1 week
(`content/a1/reading/weekN_*.json`), delivered as a tracked weekly exercise on
the practice site (`/a1/weekN/dayD/reading`). Each passage carries a bilingual
title, an Arabic gist, a 4-item bilingual glossary, and 4 comprehension
questions.

**Why it is A1, concretely:**

| Property | Value | Why it is A1 |
|---|---|---|
| Length | 50–67 words | `A1.R.4` is about *very short* texts |
| Presentation | one sentence per line, each individually playable | literally "a single phrase at a time" |
| Grammar | only that week's taught pattern | no structure appears before it is taught |
| Vocabulary | 12–21 of the week's **own** authored words per passage | recycles taught lexis; not generic filler |
| Topics | self, family, home, routine, food, shopping, description, ability, yesterday | exactly `A1.R.1`'s "themselves, their family and immediate concrete surroundings" |
| Support | Arabic gist + glossary, no full translation | comprehension, not decoding |

**Integrity of the questions.** Every correct answer is traceable to a phrase in
its own passage (verified mechanically for all 40 questions). Answer positions
are deterministically shuffled — the first draft had every answer in position 1,
which would have let a student score full marks without reading; a test now
fails if answers cluster in one position.

**Weekly, not daily, and never a gate.** One passage is authored per week, so
reading is a `WEEKLY_EXERCISES` entry: tracked and rewarded, but deliberately
never part of the "is this day green" requirement — adding it there would have
retroactively broken every existing streak.

**Still open for A1 after this:** `A1.M.1`, `A1.M.2` (mediation — no task yet)
and `A1.P.5` (short notes and messages). These are tracked in the coverage
ledger's pinned baseline, so they cannot be quietly forgotten.

### 4c. Mediation (added 2026-08-24 — Phase 11B)

**The gap this closes.** The CEFR Companion Volume (2020) defines **four** modes:
reception, production, interaction and **mediation**. Empire English exercised
three. Mediation — relaying, explaining and summarising *for someone else* — had
no task anywhere, so these two A1 descriptors were taught by no week:

- `A1.M.1` — *Can convey simple, predictable information of immediate relevance
  (a name, a number, a price, a time) to another person.*
- `A1.M.2` — *Can use a single word or a short phrase, with gesture, to signal
  understanding or ask for help.*

**Why this is the right mode for these students.** Our learners are Arabic
speakers who already mediate English in real life — reading a message for a
parent, telling a shopkeeper what a friend wants, passing on a lesson time. The
tasks use exactly those situations, so the practice is authentic rather than
academic. Most competing courses skip mediation entirely.

**Shape of each task** (`content/a1/mediation/weekN_*.json`):

1. **The situation** — who needs help, and why (bilingual).
2. **What you heard/read** — a short English source containing the concrete
   facts. Playable, because at A1 the source is often spoken.
3. **Your job** — relay it. A free-text box; Arabic *or* simple English is
   explicitly allowed, because mediation is measured by whether the information
   arrives, not by grammatical polish.
4. **A good answer** — revealed on request, never before the attempt.
5. **Did you pass on everything?** — the checklist of required facts.
6. **If you do not understand** — the `A1.M.2` signal phrases, each playable,
   with gesture explicitly permitted.

**How it is assessed, and why that is honest.** Mediation is scored by a
**key-points checklist**, not by machine-marking free text. That is genuinely
how CEFR mediation is judged — *did the essential information get across?* — and
it avoids pretending to auto-grade open writing. Tests enforce the integrity of
this: every key point must be **anchored in the source** the student was given
(so the task never asks them to invent information), and the model answer must
**cover every key point** (so it never teaches under-reporting).

**A1 status after this.** A1 now exercises **all four CEFR modes**. The only
remaining A1 descriptor gap is `A1.P.5` (write short notes and messages) — a
production gap, not a missing mode — and it stays pinned in the coverage
ledger's baseline until closed.

### 5. Progression logic
The 10 weeks build a coherent A1 arc: identity → relationships → quantities/time
→ environment → habits → consumption → transactions → description → ability →
simple past + consolidation. Week 10 is an explicit review + a 60-second
capstone speaking task that previews the A1 exit exam.

## Assessment alignment (handled by the Taqdeem engine)
- **Weekly** tests that week's can-do objectives + vocab + grammar.
- **Monthly** tests retention across the A1 weeks.
- **A1 exit exam** (Part A skills + Part B: 60-second self-introduction) tests
  the A1 can-do set as a whole; passing certifies the student at **CEFR A1**
  and promotes them to A2.

## What to review / sign off
- [ ] Themes + week order feel right for your beginners.
- [ ] Vocabulary choices are appropriate (level, Arabic glosses, examples).
- [ ] Grammar sequence is correct and A1-appropriate.
- [ ] Speaking/writing tasks match your students' ability.
- [ ] Certificate wording ("CEFR-aligned", not "certified") is approved.
- [ ] **Reading passages (§4b) read well and feel right for your beginners** —
      10 passages, 50–67 words each, one per week. This is new content, so it is
      the part most worth your eyes before A2–C2 are authored to the same shape.
- [ ] **Mediation situations (§4c) feel true to your students' real life** —
      10 tasks (tell your mother the prices, pass on the lesson time, order for
      a friend, describe a lost child…). Same reason: check the shape here
      before A2–C2 are authored to match.

Once you approve, we run the **Phase 2 silent migration** (L0 → A1, zero loss)
and enable A1 for students.
