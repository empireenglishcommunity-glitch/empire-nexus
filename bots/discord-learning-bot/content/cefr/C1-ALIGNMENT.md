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

### 4b. ✅ CLOSED — the eight unprovable C1 descriptors are now provable

**Status: closed 2026-08-27.** All three missing exercises have been authored for
C1, and the coverage ledger reports **C1: 20 descriptors — OK** with nothing under
*"PUBLISHED BUT NOT PROVABLE"*. This section is kept as the record of what was
wrong, because the mis-attribution it describes is the kind of error that returns
quietly if nobody remembers it.

**What the finding was.** A week *targeted* all 20 descriptors, but a student
could *prove* only 12. A1–B2 each had three exercises C1 lacked — **reading**,
**mediation** and **extended listening** — and those were the only routes to
eight C1 descriptors:

| Descriptor | Only provable by | Now |
|---|---|---|
| `C1.M.1` summarise long texts, relay detail reliably | mediation | ✅ 18 weeks |
| `C1.M.2` explain complex ideas, adapt for the audience | mediation | ✅ 18 weeks |
| `C1.M.3` mediate discussion, resolve misunderstandings | mediation | ✅ 18 weeks |
| `C1.M.4` synthesise arguments from several sources | mediation | ✅ 18 weeks |
| `C1.R.1` extended speech, relationships only implied | extended listening | ✅ 9 scripts |
| `C1.R.2` follow films with considerable slang | extended listening | ✅ 6 scripts |
| `C1.R.3` lengthy, complex texts in detail | reading | ✅ 18 weeks |
| `C1.R.4` a writer's attitude, tone, irony, register | reading | ✅ 18 weeks |

**Two of these were worse than missing — they were mis-attributed.** Until this
was found, `C1.R.1` (*"extended speech… relationships only implied"*) and
`C1.R.2` (*"follow **films** employing a considerable degree of slang"*) were
being evidenced by the **listening dictation** — five typed words a week. Five
words cannot demonstrate following an unstructured argument or a film. That is
now blocked in code for all six levels by an explicit rule about descriptor grain
size (`EXTENDED_SPOKEN_MARKERS`), which is what made these visible in the first
place.

**How the content answers the descriptors, not just the exercise slot.** The nine
`C1.R.1` scripts are deliberately **unsignposted** — no discourse markers doing
structural work, causal links left implicit, the speaker digressing and
correcting themselves — because that is the opposite of the B2 lectures, which
signpost every move on purpose for `B2.R.1`. Using the B2 shape here would have
filled the slot without testing the skill.

**One reservation, recorded rather than hidden.** `C1.R.2` names **films**. Our
audio is Kokoro TTS: one clean voice per turn, no overlapping speech, no
regional accents, no emotional prosody. The scripts are written thick with idiom
and the questions target what an idiom is *doing*, so the slang half is genuinely
delivered — but a student who understands every scene has still never had to read
tone off a real actor's voice. See the same reservation on `B2.R.2`, which the
ledger prints in full every run.

**Delivery speed is now verified, not assumed.** `C1.R.1` is about following
*native* extended speech, so pace matters. C1 audio was measured at **189 wpm**
against a 195 target (`empire-dojo/scripts/verify_audio_pace.py`). Before that
check existed, several C1 clips were rendering at **120 wpm** — slower than the
A1 target — because delivery speed was inherited from whichever TTS voice a
script happened to name.

## What to review / sign off

> **OWNER SIGN-OFF — APPROVED 2026-08-27.** The owner reviewed the authored C1
> content and approved all of it.
>
> Recorded exactly as given: **a single blanket approval of every item at this
> level**, not an item-by-item annotation, against the content as it stood at
> commit `d0db3b0`. Material later edits are *not* covered by it — if the content
> changes, the approval should be re-confirmed rather than assumed to carry over.
>
> This records the **owner's** judgement that the content is right for these
> students. It is separate from, and additional to, the machine checks (test
> suite, coverage ledger, delivery-pace verification) and the assistant's QA pass
> recorded in [`CONTENT-REVIEW-2026-08-27.md`](./CONTENT-REVIEW-2026-08-27.md). Those
> establish that the content is structurally sound and correctly keyed; only this
> sign-off speaks to whether it is *right for the students*.


- [x] ✅ **§4b is now closed** — read it anyway. It records that `C1.R.1` and
      `C1.R.2` were once credited to the five-word dictation, which is the error
      most likely to creep back in.
- [x] **18 C1 reading texts** — `C1.R.3` (detail in lengthy complex texts) and
      `C1.R.4` (attitude, tone, irony, register).
- [x] **18 C1 mediation tasks** — `C1.M.1`–`C1.M.4`.
- [x] **18 C1 extended-listening scripts** — 9 unsignposted monologues
      (`C1.R.1`), 6 idiom-heavy scenes (`C1.R.2`), 3 specialised sources
      (`C1.R.5`). Check the unsignposted nine especially: they are *meant* to
      feel unstructured, and the line between "authentically rambling" and
      "badly written" is a judgement call I should not be making alone.
- [x] **The `C1.R.2` film reservation** — accept that synthesised audio delivers
      the slang but not an actor's tone, or tell me to report it as untaught
      until real recordings exist.
      → **DECIDED 2026-08-27: the reservation is accepted as recorded.** It is
      printed by the coverage ledger next to the word "OK" on every run, and is
      closed only by authentic recorded audio — no code or rewriting.
- [x] Themes + week order feel right for your advanced students.
- [x] Vocabulary choices are appropriate (level, Arabic glosses, examples).
- [x] Grammar sequence is correct and C1-appropriate (builds on B2, stops below C2).
- [x] Speaking/writing tasks match your students' ability (argument, abstraction, register, discourse).
- [x] Certificate wording ("CEFR-aligned", not "certified") is approved.

C1 needs **no migration** — students move from B2 to C1 naturally by passing
the B2 exit exam. Once you approve, C1 is ready the moment a student completes B2.
