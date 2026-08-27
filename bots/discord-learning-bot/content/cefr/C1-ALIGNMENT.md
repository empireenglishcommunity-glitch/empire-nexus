# C1 (Advanced / Effective Operational Proficiency) — CEFR Alignment Rationale

> **Owner approval gate.** This document states exactly how the C1 level maps
> to the CEFR, so the alignment is auditable before C1 goes live. C1 content
> loads into the engine but nothing changes for students until they complete
> B2 and pass the B2 exit exam — and until you sign off on C1.

## Truth-in-labelling

C1 content is **CEFR-aligned** (built to the official CEFR C1 descriptors). On
completion, Empire English issues its own certificate: *"Empire English
certifies that [name] has demonstrated proficiency at CEFR Level C1."* We do
**not** claim "CEFR certified" — CEFR has no certifying body.

## What CEFR says C1 is (the target)

> *Can understand a wide range of demanding, longer texts, and recognise
> implicit meaning. Can express ideas fluently and spontaneously without much
> obvious searching for expressions. Can use language flexibly and effectively
> for social, academic and professional purposes. Can produce clear,
> well-structured, detailed text on complex subjects, showing controlled use of
> organisational patterns, connectors and cohesive devices.*
> — Council of Europe, CEFR global scale, C1. C1 is the lower **proficient
> user** band — effective, flexible, largely effortless command of the language
> for demanding academic and professional use.

## How this C1 course delivers that

### 1. Can-Do objectives (learning outcomes)
`can_do.json` → `C1` holds 20 curated descriptors across all four CEFR modes:
- **Reception** (5): extended, loosely-structured speech with only implied
  relationships; films with heavy slang/idiom; lengthy complex texts in and out
  of one's field; recognising attitude, tone, irony and register; extracting
  ideas from highly specialised sources.
- **Production** (6): clear detailed descriptions/presentations integrating
  sub-themes; well-structured argument expanded with subsidiary points; clear
  well-structured texts on complex subjects; selecting appropriate style/register
  with efficient cohesion; well-organised expansion with supporting detail; and
  controlled, precise formal writing.
- **Interaction** (5): fluent, spontaneous, almost effortless interaction;
  flexible, effective language for social and professional ends; precise
  expression of finer shades of meaning; backtracking and repairing smoothly;
  and skilful turn-taking / holding the floor.
- **Mediation** (4): summarising demanding source texts; relaying detailed
  information and argument reliably; reformulating for different audiences and
  registers; and mediating nuance and implied meaning.

Every week references the specific descriptors it targets (its `can_do` codes);
across the 18 weeks **all 20 C1 descriptors** are covered.

### 2. Grammar syllabus (C1 structures only)
`grammar_syllabus.json` → `C1`, one point per week, all firmly C1 per the
English Grammar Profile:

| Week | Grammar |
|------|---------|
| 1 | Inversion after negative/limiting adverbials |
| 2 | Inversion in conditionals (*Had I / Were I / Should you*) |
| 3 | Advanced cleft sentences & fronting |
| 4 | Participle clauses (present, past, perfect) |
| 5 | Advanced & impersonal passive (*it is thought that…*) |
| 6 | Nominalisation (verbs/adjectives → nouns) for formal register |
| 7 | Advanced modals & semi-modals |
| 8 | Hedging & cautious language |
| 9 | Advanced discourse markers & cohesion |
| 10 | Relative clauses (quantifier + *which/whom*; prepositional) |
| 11 | Ellipsis & substitution |
| 12 | Emphasis & intensification |
| 13 | Future in the past & complex time reference |
| 14 | Advanced conditionals (*provided/as long as/supposing*; inverted) |
| 15 | Idiomatic & figurative language + deep collocation |
| 16 | Register & style shifting |
| 17 | Complex noun phrases & precision |
| 18 | Fluency, coherence & discourse strategies + review |

This builds on B2 (narrative & perfect tenses, third/mixed conditionals,
reported speech, the full passive, non-defining/reduced relatives, cleft
emphasis) and takes each to the C1 ceiling: **inversion**, **nominalisation**,
**ellipsis/substitution**, **hedging**, **impersonal passive**, register control
and discourse strategy. It stops below C2 — no full mastery-level stylistic
manipulation, literary/marked syntax for effect, or near-native idiomatic
subtlety as a systematic focus; those are C2.

### 3. Vocabulary band (C1)
~580 active words across the 18 weeks, all higher-frequency-to-academic C1 items
selected against public CEFR-mapped references (Oxford 5000 C1 tags, English
Vocabulary Profile C1). Stored as **our own list** (word, pronunciation, Arabic
gloss, POS, example). Themes move into abstract, academic and professional C1
domains: formal nominalised trends, fine modal distinctions, hedged/cautious
argument, cohesion and case-building, precise description, efficient
ellipsis/substitution, emphasis, layered time reference, nuanced conditions,
idiom & figurative meaning, register shifting, dense noun phrases, and a fluency
capstone.

CEFR guidance puts C1 vocabulary at roughly 5,000–8,000 words *receptive*; a
~580-word curated **active** production layer for an 18-week advanced course,
stacked on A1–B2 (~1,800), is a sound C1 core (assessments test production).

### 4. Skills coverage (all five, every week)
Each week file provides: **vocabulary**, **listening** (dictation items),
**pronunciation/phonology** (`phoneme_focus` — connected speech, weak forms,
emphatic and register-marked intonation), **speaking** (7 daily missions,
45–100s, requiring argument, abstraction, register control and sustained
discourse), and **writing** (7 prompts, including academic, analytical and
register-shifting tasks). This matches CEFR C1's fluent, flexible
proficient-user expectations across all four modes.

### 5. Progression logic
The 18 weeks build a coherent C1 arc: **marked syntax for emphasis & formality**
(inversion → inverted conditionals → cleft/fronting → participle clauses →
impersonal passive → nominalisation) → **precision & nuance** (advanced modals,
hedging, cohesion, advanced relatives) → **efficiency & force** (ellipsis,
emphasis) → **complex reference & conditions** (future-in-past, advanced
conditionals) → **idiom, register & density** (figurative language, style
shifting, complex noun phrases) → **fluency & discourse** (coherence, self-repair,
holding the floor). Week 18 is an explicit review + a 100-second fluency capstone
that previews the C1 exit exam.

## Assessment alignment (handled by the Taqdeem engine)
- **Weekly** tests that week's can-do objectives + vocab + grammar.
- **Monthly** tests retention across the C1 weeks.
- **C1 exit exam** (Part A skills + Part B: an extended, well-structured spoken
  and written response on a complex subject, controlling register and cohesion)
  tests the C1 can-do set as a whole; passing certifies the student at **CEFR C1**
  and promotes them to C2.

### 4b. ⚠️ Eight C1 descriptors are published but NOT PROVABLE (found 2026-08-24)

**This section corrects what "C1 teaches all 20 descriptors" has been taken to
mean.** It is true that a week *targets* each of them. It is not true that a
student can *prove* eight of them.

A1–B2 each have three exercises that C1 does not: **reading**, **mediation** and
**extended listening**. Those three are the only routes to eight C1 descriptors,
so a C1 student has no way to produce the evidence:

| Descriptor | Only provable by | Which C1 does not have |
|---|---|---|
| `C1.M.1` summarise long texts, relay detail reliably | mediation | ❌ |
| `C1.M.2` explain complex ideas, adapt for the audience | mediation | ❌ |
| `C1.M.3` mediate discussion, resolve misunderstandings | mediation | ❌ |
| `C1.M.4` synthesise arguments from several sources | mediation | ❌ |
| `C1.R.1` extended speech, relationships only implied | extended listening | ❌ |
| `C1.R.2` follow films with considerable slang | extended listening | ❌ |
| `C1.R.3` lengthy, complex texts in detail | reading | ❌ |
| `C1.R.4` a writer's attitude, tone, irony, register | reading | ❌ |

**The practical consequence.** A C1 student who completed **every exercise on
every day of all 18 weeks** would still finish with those eight unevidenced on
their certificate, and the Level Completion Contract could **never** return
"complete" for C1. Nobody has hit this because every student is currently on A1.

**Two of these were worse than missing — they were mis-attributed.** Until this
was found, `C1.R.1` (*"extended speech… relationships only implied"*) and
`C1.R.2` (*"follow **films** employing a considerable degree of slang"*) were
being evidenced by the **listening dictation** — five typed words a week. Five
words cannot demonstrate following an unstructured argument or a film. The rule
is now enforced in code for all six levels, which is what made these visible.

**What closes it:** authoring **reading, mediation and extended listening for
C1** — 18 weeks each. No code is needed; the exercises, pages, tracking and
ledger all already exist and work, and the moment content lands they turn on.
A test states this as a rule: once a level has all three, nothing it publishes
can be unprovable.

**Until then, the ledger prints this every run** under *"PUBLISHED BUT NOT
PROVABLE"*, with the reason and the consequence. C1 should not be described to
students as fully CEFR-covered while that block is non-empty.

## What to review / sign off
- [ ] ⚠️ **The eight unprovable C1 descriptors (§4b)** — you should know that C1
      cannot currently be completed under the contract, and why. Nothing is
      broken for present students (all are on A1); this is the level's readiness
      for when someone arrives.
- [ ] Whether C1 content (reading / mediation / extended listening) should be
      authored **now**, or deferred until a student is close to C1. Deferring is
      defensible — the ledger reports the gap honestly either way.
- [ ] Themes + week order feel right for your advanced students.
- [ ] Vocabulary choices are appropriate (level, Arabic glosses, examples).
- [ ] Grammar sequence is correct and C1-appropriate (builds on B2, stops below C2).
- [ ] Speaking/writing tasks match your students' ability (argument, abstraction, register, discourse).
- [ ] Certificate wording ("CEFR-aligned", not "certified") is approved.

C1 needs **no migration** — students move from B2 to C1 naturally by passing
the B2 exit exam. Once you approve, C1 is ready the moment a student completes B2.
