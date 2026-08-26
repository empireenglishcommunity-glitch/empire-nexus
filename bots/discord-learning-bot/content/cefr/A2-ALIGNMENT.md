# A2 (Elementary / Waystage) — CEFR Alignment Rationale

> **Owner approval gate.** This document states exactly how the A2 level maps
> to the CEFR, so the alignment is auditable before A2 goes live. A2 content
> loads into the engine but nothing changes for students until they naturally
> complete A1 and pass the A1 exit exam — and until you sign off on A2.

## Truth-in-labelling

A2 content is **CEFR-aligned** (built to the official CEFR A2 descriptors). On
completion, Empire English issues its own certificate: *"Empire English
certifies that [name] has demonstrated proficiency at CEFR Level A2."* We do
**not** claim "CEFR certified" — CEFR has no certifying body.

## What CEFR says A2 is (the target)

> *Can understand sentences and frequently used expressions related to areas of
> most immediate relevance (e.g. very basic personal and family information,
> shopping, local geography, employment). Can communicate in simple and routine
> tasks requiring a simple and direct exchange of information on familiar and
> routine matters. Can describe in simple terms aspects of their background,
> immediate environment and matters in areas of immediate need.*
> — Council of Europe, CEFR global scale, A2.

## How this A2 course delivers that

### 1. Can-Do objectives (learning outcomes)
`can_do.json` → `A2` holds 18 curated descriptors across all four CEFR modes:
- **Reception** (5): understand high-frequency phrases; catch the main point of
  short clear messages/announcements; find specific info in everyday material
  (ads, menus, timetables); follow short personal narratives; follow simple
  directions.
- **Production** (6): describe family / living conditions / background / job;
  tell a simple story about past events; describe plans and intentions; compare
  people/places/things; write linked sentences with connectors; write short
  personal messages and a simple personal letter.
- **Interaction** (4): handle short social exchanges + routine information
  tasks; ask/give directions + get travel/shopping/service info; make and
  respond to invitations/suggestions/apologies + arrange to meet; express
  feelings, likes/dislikes, agreement/disagreement.
- **Mediation** (3): convey the main points of short everyday texts; make an
  idea clearer with simple examples + checking questions; collaborate on a
  simple shared task.

Every week references the specific descriptors it targets (its `can_do` codes).

### 2. Grammar syllabus (A2 structures only)
`grammar_syllabus.json` → `A2`, one point per week, all firmly A2 per the
English Grammar Profile:

| Week | Grammar |
|------|---------|
| 1 | Past simple — regular verbs (*-ed*) + time expressions |
| 2 | Past simple — irregular verbs + *did/didn't* questions & negatives |
| 3 | Comparative adjectives (*-er / more … than*) |
| 4 | Superlative adjectives (*the -est / the most*) |
| 5 | Future: *be going to* (plans and intentions) |
| 6 | Future: *will* (decisions, predictions, offers) |
| 7 | Present continuous (now) vs present simple (habits) |
| 8 | Countable/uncountable + quantifiers (*much/many/a lot of/a few/a little*) |
| 9 | Adverbs of manner (*well, quickly, carefully*) |
| 10 | Present perfect for experience (*ever/never, been*) |
| 11 | Obligation & advice: *have to / must / should* |
| 12 | Connectors (*because, so, but, when, before/after*) + review |

This builds directly on A1 (which ended at *was/were*) and stops at the A2
ceiling: no present perfect continuous, no past continuous, no first/second
conditional, no passive, no reported speech — those are B1+.

### 3. Vocabulary band (A2)
~390 active words across the 12 weeks, all high-frequency A2 items selected
against public CEFR-mapped references (Oxford 3000/5000 A2 tags, English
Vocabulary Profile A2). Stored as **our own list** (word, pronunciation, Arabic
gloss, POS, example) — no third-party list is copied. Themes are the classic
A2 "immediate relevance" domains: past events & trips, comparing places, future
plans, weather/predictions, present activities, food & recipes, health & the
body, life experiences, work & rules, and a personal-story capstone.

CEFR guidance puts A2 vocabulary at roughly 1,000–1,500 words *receptive*; a
~390-word curated **active** production layer for a 12-week elementary course,
stacked on the ~340 A1 words, is a sound A2 core (assessments test production).

### 4. Skills coverage (all five, every week)
Each week file provides: **vocabulary**, **listening** (dictation items),
**pronunciation/phonology** (`phoneme_focus` — e.g. regular *-ed* endings,
weak forms, *going to* → /ɡənə/, *-ing* endings), **speaking** (7 daily
missions, 25–60s, rising in demand across the week), and **writing** (7
prompts). This matches CEFR A2's balanced reception + production + interaction
+ light mediation expectations.

### 5. Progression logic
The 12 weeks build a coherent A2 arc: **narrate the past** (regular → irregular)
→ **compare** (comparatives → superlatives) → **talk about the future**
(*going to* → *will*) → **describe the present moment** → **manage quantities**
(food/recipes) → **describe manner** (health) → **relate experience** (present
perfect) → **express obligation & advice** (work) → **connect ideas into a
personal narrative** (capstone). Week 12 is an explicit review + an
8-sentence "My Story" capstone (past + present + future) that previews the A2
exit exam.

## Assessment alignment (handled by the Taqdeem engine)
- **Weekly** tests that week's can-do objectives + vocab + grammar.
- **Monthly** tests retention across the A2 weeks.
- **A2 exit exam** (Part A skills + Part B: a short spoken narrative combining
  past, present and future) tests the A2 can-do set as a whole; passing
  certifies the student at **CEFR A2** and promotes them to B1.

### 4b. Reading + Mediation (added 2026-08-24 — Phase 11B)

**The gap this closes.** Section 4 above lists five skills, and that list was
accurate — which was the problem: A2 had **no reading task and no mediation task
at all.** CEFR treats reading as reception alongside listening, and mediation as
a fourth mode in its own right. Measured against `can_do.json`, **five** A2
descriptors were taught by *no week*:

| Descriptor | What it asks for |
|---|---|
| `A2.R.1` | phrases + high-frequency vocabulary on immediately relevant areas |
| `A2.R.5` | follow simple directions and short sets of **instructions** |
| `A2.M.1` | convey the main point(s) of short everyday texts and messages |
| `A2.M.2` | make an idea clearer with examples + check understanding |
| `A2.M.3` | collaborate on a shared task, inviting and reacting to contributions |

**Reading — 12 passages** (`content/a2/reading/`), one per week, 89–105 words
(A1's are 50–67; A2 reads longer, not just harder). Each uses **only that week's
already-taught grammar** and reuses **9–20 of that week's own authored
vocabulary**, so a passage is part of its week rather than generic filler.

Four are deliberately **instruction-shaped**, because that is the only honest way
to teach `A2.R.5`: *Before You Travel: Five Steps* (w5), *Easy Tomato Rice — A
Recipe* (w8), *The Doctor's Instructions* (w9), *Rules for New Workers* (w11).
The other eight serve `A2.R.1` on immediately relevant topics — weekend, trip,
comparing places, famous places, weather, café, experiences, personal story.

**Mediation — 12 tasks** (`content/a2/mediation/`). A2's three mediation
descriptors are genuinely different *acts*, so each task claims **only the ones it
really performs** — tagging all three on every task would be the exact
over-claiming this work removes:

- **`A2.M.1` — relay (5 tasks):** pass on a voice message, trip details, a weather
  forecast, the doctor's instructions, the work rules.
- **`A2.M.2` — clarify (3 tasks):** explain *crowded*, *at the moment*, *ever* —
  each requires two examples **and** a question to check the other person
  understood.
- **`A2.M.3` — collaborate (4 tasks):** agree on the class trip, plan a group
  holiday, plan a shared meal, agree on the class story — each requires inviting
  a named classmate to contribute and reacting to their suggestion.

**Still open for A2:** `A2.R.2` — *"catch the main point in short, clear messages
and **announcements**."* That is **spoken** reception. No reading passage can
close it honestly, so it stays open and is recorded in
`coverage_ledger.GAPS_NEEDING_EXTENDED_LISTENING` until real extended-listening
content exists. **A2 is 17/18 descriptors taught.**

**Quality gates.** These passages and tasks are held to the *same* automated bar
as A1 (the tests are parametrised over every authored level, not written per
level): bilingual throughout, valid answer indices, no duplicate options,
answers not clustered in one position, level-appropriate length, vocabulary
grounding, and — for mediation — every key point **anchored in the source** the
student was given, with the model answer **demonstrating every key point**. That
last gate caught a real weakness here: the three `A2.M.2` model answers asked a
checking question without ever naming the move, so a student copying the model
wouldn't see that checking is a deliberate step. Fixed.

### 4c. Extended listening (added 2026-08-24 — Phase 11D)

**What was missing.** `A2.R.2` — *"can catch the main point in short, clear,
simple messages and **announcements**"* — was taught by no week, and it was the
last A2 descriptor open. **It now closes. A2 is 18/18.**

**Why the existing listening exercise could not close it.** A2's listening page
is word-level dictation: five words a week, heard and typed back. That is a real
skill and worth keeping, but **its unit is smaller than the unit the descriptor
is about**. No number of weeks of typing single words evidences "caught the main
point of an announcement", because the exercise never presents a main point.

**So extended listening is a different exercise, not a bigger dictation.** One
script per week, **104–159 spoken words** (roughly 40–60 seconds), in the
registers the descriptor actually names:

| Format | Weeks | Why this format |
|---|---|---|
| voicemail / recorded message | 1, 5 | the everyday "message" half of the descriptor |
| public announcement | 2, 4 | station and school announcements — the other half |
| radio (segment, forecast, story) | 3, 6, 12 | listening for a conclusion, not a fact |
| live report | 7 | present continuous in its natural habitat |
| recorded instructions | 8, 9, 11 | also closes `A2.R.5` honestly |
| street interview | 10 | two voices, so turn-taking starts early |

**The rule that makes the claim honest: the transcript is locked.** The
main-point question must be answered **before** the transcript and the detail
questions unlock. If the transcript were on screen from the start, a student
could read instead of listen, the exercise would be reading with a play button,
and it could **not** honestly evidence a listening descriptor.

**What is deliberately not claimed.** `A2.R.3` is about adverts, menus,
timetables and short letters — **written** everyday material. No script names it,
and a test enforces that. Secondary codes are claimed only where genuinely
earned: `A2.R.5` on the three instruction scripts, `A2.R.4` on the three past-
narrative ones, `A2.R.1` on the market report.

**Voices.** All eleven Kokoro voices are used across the twelve weeks — male and
female, American and British — so students do not tune to a single speaker.

## What to review / sign off
- [ ] Themes + week order feel right for your elementary students.
- [ ] **Extended-listening scripts (§4c)** — 12 recordings, 104–159 words. The
      question to ask of each: *would an A2 student get the main point on one
      listen, without the transcript?* If a script needs two listens that is
      fine and expected; if it needs the transcript, tell me and I will simplify.
- [ ] **Reading passages (§4b) feel right for A2** — 12 passages, 89–105 words.
      New content, so the part most worth your eyes.
- [ ] **Mediation tasks (§4b) feel true to your students' real life** — relaying
      messages, explaining a word, and agreeing on a group plan.
- [ ] Vocabulary choices are appropriate (level, Arabic glosses, examples).
- [ ] Grammar sequence is correct and A2-appropriate (builds on A1, stops below B1).
- [ ] Speaking/writing tasks match your students' ability.
- [ ] Certificate wording ("CEFR-aligned", not "certified") is approved.

A2 needs **no migration** — students move from A1 to A2 naturally by passing
the A1 exit exam. Once you approve, A2 is ready the moment a student completes
A1.
