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

Once you approve, we run the **Phase 2 silent migration** (L0 → A1, zero loss)
and enable A1 for students.
