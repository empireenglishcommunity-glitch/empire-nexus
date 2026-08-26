# B2 (Upper-Intermediate / Vantage) — CEFR Alignment Rationale

> **Owner approval gate.** This document states exactly how the B2 level maps
> to the CEFR, so the alignment is auditable before B2 goes live. B2 content
> loads into the engine but nothing changes for students until they complete
> B1 and pass the B1 exit exam — and until you sign off on B2.

## Truth-in-labelling

B2 content is **CEFR-aligned** (built to the official CEFR B2 descriptors). On
completion, Empire English issues its own certificate: *"Empire English
certifies that [name] has demonstrated proficiency at CEFR Level B2."* We do
**not** claim "CEFR certified" — CEFR has no certifying body.

## What CEFR says B2 is (the target)

> *Can understand the main ideas of complex text on both concrete and abstract
> topics, including technical discussions in their field of specialisation. Can
> interact with a degree of fluency and spontaneity that makes regular
> interaction with native speakers quite possible without strain for either
> party. Can produce clear, detailed text on a wide range of subjects and
> explain a viewpoint on a topical issue giving the advantages and
> disadvantages of various options.*
> — Council of Europe, CEFR global scale, B2. B2 is the higher **independent
> user** band — genuine fluency, argument and abstraction.

## How this B2 course delivers that

### 1. Can-Do objectives (learning outcomes)
`can_do.json` → `B2` holds 20 curated descriptors across all four CEFR modes:
- **Reception** (5): extended speech/lectures + complex argument; TV news &
  films; articles with viewpoints; skim for relevance; literary prose +
  implied meaning.
- **Production** (6): clear detailed descriptions; develop an argument
  systematically; explain a viewpoint with pros/cons; write detailed text
  synthesising sources; essays/reports with reasons & examples; letters
  conveying emotion & significance.
- **Interaction** (5): fluency & spontaneity with native speakers; active part
  in discussion, sustaining views; present & defend arguments, handle
  counter-arguments; convey emotion & comment on others' views; help the work
  along + negotiate a compromise.
- **Mediation** (4): summarise & contrast viewpoints; convey detailed info
  reliably; reformulate/paraphrase to clarify; bridge differences of opinion.

Every week references the specific descriptors it targets (its `can_do` codes).

### 2. Grammar syllabus (B2 structures only)
`grammar_syllabus.json` → `B2`, one point per week, all firmly B2 per the
English Grammar Profile:

| Week | Grammar |
|------|---------|
| 1 | Present perfect simple vs continuous (refined) |
| 2 | Past perfect (simple & continuous) |
| 3 | Narrative tenses together |
| 4 | Future perfect & future continuous |
| 5 | Third conditional |
| 6 | Mixed conditionals |
| 7 | *wish / if only* (regrets & wishes) |
| 8 | Reported speech (questions, commands, requests + reporting verbs) |
| 9 | Passive (all tenses) + causative *have/get something done* |
| 10 | Modals of past deduction (*must/might/could/can't have done*) |
| 11 | Relative clauses: non-defining & reduced |
| 12 | Gerunds & infinitives (advanced patterns + meaning change) |
| 13 | Determiners, articles & quantifiers (advanced) |
| 14 | Linking & discourse: contrast, concession, cause & result |
| 15 | Emphasis: cleft sentences (*It was… that / What… is*) + *so/such … that* |
| 16 | Phrasal verbs, collocations & register + review |

This builds on B1 (first/second conditional, present perfect, basic relative
clauses, reported statements, present/past passive) and stops at the B2 ceiling:
no negative/adverbial **inversion**, no **subjunctive**, no advanced **ellipsis**
or **nominalisation** — those are C1+.

### 3. Vocabulary band (B2)
~600 active words across the 16 weeks, all mid-frequency B2 items selected
against public CEFR-mapped references (Oxford 5000 B2 tags, English Vocabulary
Profile B2). Stored as **our own list** (word, pronunciation, Arabic gloss,
POS, example). Themes move into the abstract/topical B2 domains: achievements,
life stories, the future of work, regret & hindsight, wishes, reporting &
interviews, news & services, deduction, detailed description, verb-pattern
nuance, society & generalisation, argument, emphasis/style, and a fluency
capstone.

CEFR guidance puts B2 vocabulary at roughly 3,250–5,000 words *receptive*; a
~600-word curated **active** production layer for a 16-week upper-intermediate
course, stacked on A1–B1 (~1,200), is a sound B2 core (assessments test
production).

### 4. Skills coverage (all five, every week)
Each week file provides: **vocabulary**, **listening** (dictation items),
**pronunciation/phonology** (`phoneme_focus` — connected speech, contrastive
stress, discourse-marker intonation), **speaking** (7 daily missions, 45–90s,
now requiring argument, narration, abstraction and register control), and
**writing** (7 prompts, including essays, reports and argument). This matches
CEFR B2's fluent independent-user expectations across all four modes.

### 5. Progression logic
The 16 weeks build a coherent B2 arc: **master the tense system**
(perfect/past-perfect/narrative/future-perfect) → **conditionals & wishes**
(third → mixed → wish) → **report & attribute** (reported speech, passive,
past deduction) → **describe & nuance** (non-defining relatives, verb patterns,
determiners) → **argue & style** (discourse linking, emphasis) → **fluency &
register** (phrasal verbs/collocations). Week 16 is an explicit review + a
90-second fluency capstone that previews the B2 exit exam.

## Assessment alignment (handled by the Taqdeem engine)
- **Weekly** tests that week's can-do objectives + vocab + grammar.
- **Monthly** tests retention across the B2 weeks.
- **B2 exit exam** (Part A skills + Part B: an extended spoken/written argument
  weighing options with reasons) tests the B2 can-do set as a whole; passing
  certifies the student at **CEFR B2** and promotes them to C1.

### 4b. Reading, Mediation + two interaction missions (added 2026-08-24 — Phase 11B)

**What was missing.** B2 had **no reading task and no mediation task**, and five
descriptors were taught by *no week*: `B2.R.4`, `B2.M.1`, `B2.M.4`, `B2.I.1`,
`B2.I.5`. **All five now close. B2 is 18/20.**

**Reading — 16 passages** (157–223 words), covering the three text types B2's
descriptors actually distinguish:

| Descriptor | Text type | Weeks |
|---|---|---|
| `B2.R.3` | articles/reports on contemporary problems, writer's viewpoint | 13 weeks |
| `B2.R.5` | literary prose, literal vs **implied** meaning | 2, 3, 10 |
| `B2.R.4` | **quickly judging relevance** of news items and reports | 4, 9, 13, 14 |

**`B2.R.4` needed a different shape.** It is *"can quickly identify the content
and relevance of news items, articles and reports, **deciding whether closer
study is worthwhile**"* — that is **skimming to choose**, and a single continuous
passage cannot teach it. Those four weeks use a **news-digest format**: four
short items (a government report, an opinion column with no sources, a company
press release, an independent study) and questions that ask *which item is worth
studying closely for a stated purpose*. That also teaches source quality, which
is the real-world form of the skill.

**Mediation — 16 tasks**, split by act:

- **`B2.M.1` summarise + contrast viewpoints (6):** each source contains **two
  opposed views**, because the descriptor requires *contrasting* them, not just
  summarising one.
- **`B2.M.4` bridge a disagreement (5):** ask a question to check each position,
  **restate both fairly**, then suggest a way forward — the three moves named.
- `B2.M.2` convey detailed information + significance (3) and `B2.M.3`
  reformulate/paraphrase to move a discussion on (2), both already taught.

**Two interaction missions — the content edits, flagged for review.** `B2.I.1`
and `B2.I.5` are **interaction**, so no passage or mediation task can prove them.
Both weeks' replaced mission was the more duplicative of an adjacent pair:

| | Before | After |
|---|---|---|
| **w14 Thu** (`B2.I.5`) | "Debate a topic with a partner…" — the week already had four *argue-a-point* tasks | **Group negotiation:** invite the quietest member **by name**, restate the position you disagree with, reach a compromise. *"Do not simply win the argument — reach an agreement."* |
| **w16 Thu** (`B2.I.1`) | "Reflect on your B2 journey…" — a monologue that overlapped Friday's capstone talk | **Unprepared conversation:** a partner picks a topic you have not seen; keep it going 90s, ask a follow-up, disagree once, change subject naturally. *"Hesitate if you need to; the aim is spontaneity."* |

`B2.I.1` is specifically about **fluency and spontaneity**, and every previous B2
fluency task was a **prepared monologue** — which is why the Friday capstone was
left untouched and Thursday became the unprepared one.

**Still open for B2:** `B2.R.1` (extended speech and **lectures**) and `B2.R.2`
(**TV news** and films). Both are spoken reception. No passage can close them, so
they remain in `coverage_ledger.GAPS_NEEDING_EXTENDED_LISTENING`.

**Quality gate note.** The shared automated bar caught seven real problems in
this B2 content before it shipped: **five passages were genuinely thin on their
own week's lexis** (weeks 2, 3, 4, 10, 14 — week 10 used only 3 of 33 words;
rewritten so the week's language does the work), one mediation key point had **no
anchor in the source** the student is given, and one model answer **did not
demonstrate** the contrast it demanded. All fixed in the content.

## What to review / sign off

- [ ] **Reading passages (§4b)** — 16 passages, 157–223 words. Especially the
      four **news-digest** weeks (4, 9, 13, 14): they look unusual on purpose,
      because `B2.R.4` is about *choosing what to read*, not reading one text.
- [ ] **Mediation tasks (§4b)** — especially the six "summarise **and contrast**
      two opposed views" tasks, which are the most demanding thing B2 asks.
- [ ] ⚠️ **The two replaced speaking missions (§4b)** — w14 Thursday (group
      negotiation) and w16 Thursday (unprepared conversation). These are the only
      places approved B2 content changed. The Friday capstone talk is untouched.
- [ ] Themes + week order feel right for your upper-intermediate students.
- [ ] Vocabulary choices are appropriate (level, Arabic glosses, examples).
- [ ] Grammar sequence is correct and B2-appropriate (builds on B1, stops below C1).
- [ ] Speaking/writing tasks match your students' ability (argument, abstraction, register).
- [ ] Certificate wording ("CEFR-aligned", not "certified") is approved.

B2 needs **no migration** — students move from B1 to B2 naturally by passing
the B1 exit exam. Once you approve, B2 is ready the moment a student completes B1.
