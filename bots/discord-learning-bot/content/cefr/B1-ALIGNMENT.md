# B1 (Intermediate / Threshold) — CEFR Alignment Rationale

> **Owner approval gate.** This document states exactly how the B1 level maps
> to the CEFR, so the alignment is auditable before B1 goes live. B1 content
> loads into the engine but nothing changes for students until they complete
> A2 and pass the A2 exit exam — and until you sign off on B1.

## Truth-in-labelling

B1 content is **CEFR-aligned** (built to the official CEFR B1 descriptors). On
completion, Empire English issues its own certificate: *"Empire English
certifies that [name] has demonstrated proficiency at CEFR Level B1."* We do
**not** claim "CEFR certified" — CEFR has no certifying body.

## What CEFR says B1 is (the target)

> *Can understand the main points of clear standard input on familiar matters
> regularly encountered in work, school, leisure, etc. Can deal with most
> situations likely to arise whilst travelling in an area where the language is
> spoken. Can produce simple connected text on topics which are familiar or of
> personal interest. Can describe experiences and events, dreams, hopes and
> ambitions and briefly give reasons and explanations for opinions and plans.*
> — Council of Europe, CEFR global scale, B1. B1 is the **independent user**
> threshold — the step up from the A2 basic user.

## How this B1 course delivers that

### 1. Can-Do objectives (learning outcomes)
`can_do.json` → `B1` holds 19 curated descriptors across all four CEFR modes:
- **Reception** (5): main points of clear standard speech; main points of
  radio/TV on familiar topics; descriptions of events/feelings in personal
  correspondence; straightforward factual texts; the line of an argument.
- **Production** (6): connect phrases to describe experiences/dreams/ambitions;
  narrate a story / relate a plot; give reasons & explanations for opinions and
  plans; write connected text; write personal letters with some detail; write
  short essays / summarise + give an opinion.
- **Interaction** (5): deal with most travel situations; enter unprepared into
  conversation & exchange opinions; express & respond to feelings; explain a
  problem & compare alternatives; give/seek views, politely (dis)agree.
- **Mediation** (3): relay main points of clear texts; summarise + give an
  opinion on a story/talk/interview; help a discussion along.

Every week references the specific descriptors it targets (its `can_do` codes).

### 2. Grammar syllabus (B1 structures only)
`grammar_syllabus.json` → `B1`, one point per week, all firmly B1 per the
English Grammar Profile:

| Week | Grammar |
|------|---------|
| 1 | Present perfect vs past simple (*for/since, already/yet/just*) |
| 2 | Past continuous + past simple (*when/while*) |
| 3 | Future forms: *will* vs *going to* vs present continuous |
| 4 | First conditional + time clauses (*when/as soon as/unless*) |
| 5 | Second conditional (*if + past, would*) |
| 6 | Modals of deduction & possibility (*must/might/could/can't*) |
| 7 | Present perfect continuous (*how long, for/since*) |
| 8 | *used to / would* (past habits & states) |
| 9 | Comparatives & superlatives — advanced (*as…as, much/far, the…the*) |
| 10 | Relative clauses (*who/which/that/where/whose*) |
| 11 | Reported speech (statements + *say/tell*) |
| 12 | The passive (present & past simple) |
| 13 | Quantifiers & degree (*too/enough, both/neither/either*) |
| 14 | Gerunds & infinitives + linkers (*although/however/so that*) + review |

This builds on A2 (which reached present perfect for experience + connectors)
and stops at the B1 ceiling: no past perfect, no future perfect/continuous, no
third/mixed conditional, no reported questions/commands, no causative or
inversion — those are B2+.

### 3. Vocabulary band (B1)
~460 active words across the 14 weeks, all high-frequency B1 items selected
against public CEFR-mapped references (Oxford 3000/5000 B1 tags, English
Vocabulary Profile B1). Stored as **our own list** (word, pronunciation,
Arabic gloss, POS, example). Themes are the classic B1 "independent user"
domains: recent experiences & news, storytelling, plans, real & hypothetical
possibilities, deduction, skills & hobbies, the past (*used to*), comparing
lifestyles, describing people/things, news & reporting, processes (passive),
money & choices, and a personal-journey capstone.

CEFR guidance puts B1 vocabulary at roughly 2,500–3,250 words *receptive*; a
~460-word curated **active** production layer for a 14-week intermediate
course, stacked on A1 (~340) + A2 (~395), is a sound B1 core (assessments test
production).

### 4. Skills coverage (all five, every week)
Each week file provides: **vocabulary**, **listening** (dictation items),
**pronunciation/phonology** (`phoneme_focus` — connected speech, weak forms,
contractions), **speaking** (7 daily missions, 40–75s, rising in demand and now
requiring reasons/opinions/narration), and **writing** (7 prompts, including
connected text, opinion and reporting). This matches CEFR B1's independent-user
reception + production + interaction + mediation expectations.

### 5. Progression logic
The 14 weeks build a coherent B1 arc: **consolidate & extend the past**
(perfect vs simple → past continuous) → **future & conditionals** (forms →
first → second) → **deduction** → **duration** (perfect continuous) → **past
habits** → **richer comparison** → **relative clauses** → **reporting** →
**passive** → **degree/quantity** → **connected discourse** (gerunds/infinitives
+ linkers). Week 14 is an explicit review + a 10-sentence "My English Journey"
capstone (past + present + future, connected with linkers) that previews the B1
exit exam.

## Assessment alignment (handled by the Taqdeem engine)
- **Weekly** tests that week's can-do objectives + vocab + grammar.
- **Monthly** tests retention across the B1 weeks.
- **B1 exit exam** (Part A skills + Part B: a connected spoken/written narrative
  giving experiences + reasons + opinions) tests the B1 can-do set as a whole;
  passing certifies the student at **CEFR B1** and promotes them to B2.

### 4b. Reading, Mediation + one travel roleplay (added 2026-08-24 — Phase 11B)

**What was missing.** B1 had **no reading task and no mediation task**, and three
descriptors were taught by *no week*: `B1.M.2`, `B1.M.3` and `B1.I.1`. **B1 is now
17/19.**

**Reading — 14 passages** (`content/b1/reading/`), 147–187 words. B1's
reading-side descriptors were *already* claimed by the week files, so these
passages close **no new descriptor** — they exist for two better reasons: B1
students had **no reading task at all**, and `B1.R.3` / `B1.R.4` / `B1.R.5` name
three genuinely *different text types* that should be practised as such:

| Descriptor | Text type | Weeks |
|---|---|---|
| `B1.R.3` | personal letters/emails: events, feelings, wishes | 1, 2, 3, 5, 8, 14 |
| `B1.R.4` | straightforward factual texts on topics of interest | 3, 4, 6, 7, 9, 10, 11, 12, 14 |
| `B1.R.5` | the main **conclusion** in a clearly signalled argument | 4, 9, 13 |

The three `B1.R.5` passages end with an explicit signalled conclusion ("The main
conclusion is clear…", "So what is the conclusion?"), because that descriptor is
specifically about *identifying* it — a passage without one couldn't teach it.

**Mediation — 14 tasks** (`content/b1/mediation/`), split by act so each task
claims only what it performs:

- **`B1.M.1` relay (5):** a friend's news, a change of plan, a grandmother's
  letter, a visitor's description, a manufacturing process.
- **`B1.M.2` summarise + opinion (5):** a short story, a talk, an article, a news
  report, a talk on progress. Each requires a summary **and** an explicit opinion.
- **`B1.M.3` keep a discussion going (4):** water waste, a deduction puzzle, the
  city-or-village debate, a budget meeting. Each requires **inviting a named
  silent classmate**, **restating** someone's point fairly, and **summarising
  where the group has got to** — the three moves the descriptor actually names.

**`B1.I.1` — the one content edit, called out for your review.** *"Can deal with
most situations likely to arise while travelling (transport, accommodation,
dealing with authorities)"* is **interaction**, so neither a passage nor a
mediation task can prove it — it needed a speaking mission, and **no B1 week had
a travel theme.**

Week 3 is *Plans & Arrangements (Future Forms)* — exactly the language a travel
transaction needs — and its Wednesday and Thursday missions **overlapped**:

> Wed: "Arrange to meet a friend: suggest, confirm, and react to a change."
> Thu (before): "Ask a partner about weekend plans and respond with offers."
> Thu (after): "Roleplay a travel problem: you have missed your train and your hotel booking starts tonight. Speak to the ticket office, then to the hotel, using future forms…"

So one mission changed: it closes `B1.I.1`, keeps the week's grammar target, and
removes the duplication. `B1.I.1` was then added to week 3's `can_do`.

**Still open for B1:** `B1.R.1` (main points of clear standard **speech**) and
`B1.R.2` (**radio/TV** programmes). Both are spoken reception — no reading
passage can close them — so they stay recorded in
`coverage_ledger.GAPS_NEEDING_EXTENDED_LISTENING` until real extended-listening
content exists.

**Quality gate note.** The automated bar (shared by every authored level) caught
two real problems in this B1 content before it shipped: one passage was genuinely
thin on its own week's vocabulary (6 of 33 — rewritten, now 18), and five model
answers *performed* the required move without ever **naming** it ("Personally, I
think…" instead of "In my opinion…"), so a student copying the model wouldn't see
that giving an opinion is a required step. Both fixed in the content.

### 4c. Extended listening (added 2026-08-24 — Phase 11D)

**What was missing.** Two descriptors were taught by no week, and both were
spoken:

- `B1.R.1` — main points of **clear standard speech** on familiar matters in
  work, school and leisure
- `B1.R.2` — main points of many **radio or TV** programmes on current affairs,
  *"when delivered relatively slowly and clearly"*

**Both now close. B1 is 19/19.**

Neither was a borderline judgement. `B1.R.2` is explicitly scoped to speech
delivered *slowly and clearly*, which is precisely what a clearly-read bulletin
is — so a bulletin is not a substitute for the descriptor, it is the descriptor.

**14 scripts, 153–193 spoken words** (roughly 60–80 seconds), each recycling its
own week's grammar **in the register where that grammar actually lives**:

| wk | Format | Grammar it carries | Code |
|---|---|---|---|
| 1 | TV news bulletin (3 voices) | present perfect — *"the council **has approved**…"* | `R.2` |
| 2 | colleague's anecdote | past continuous + past simple | `R.1` |
| 3 | team briefing | future forms (arranged vs decided) | `R.1` |
| 4 | exam-day rules | first conditional | `R.1` |
| 5 | radio phone-in (4 voices) | second conditional | `R.2` |
| 6 | TV documentary | modals of deduction | `R.2` |
| 7 | podcast interview (4 voices) | present perfect continuous | `R.1`, `R.2` |
| 8 | radio documentary | used to / would | `R.2` |
| 9 | radio comparison | advanced comparatives | `R.2` |
| 10 | walking-tour audio guide | relative clauses | `R.1` |
| 11 | news review (4 voices) | reported speech | `R.2` |
| 12 | factory tour | the passive | `R.1`, `R.2` |
| 13 | radio advice show (5 voices) | quantifiers & degree | `R.2` |
| 14 | end-of-course talk | gerunds, infinitives, linkers | `R.1` |

**29 speaker turns across the level**, each with its own voice, so a phone-in
genuinely has a host and two callers rather than one voice playing everybody.

**The gist question is answered before the transcript unlocks** — that lock is
what the listening claim rests on. And the gist questions are deliberately about
whole clips, several of them about a *disagreement* or a refusal to answer
plainly: *"What do the two callers agree about?"*, *"Which life does the
programme say is better?"* (answer: **neither**). At B1, noticing that a speaker
has **not** given a simple answer is part of comprehension.

**What is deliberately not claimed.** `B1.R.3` (personal **letters**), `B1.R.4`
(factual **texts**) and `B1.R.5` (argumentative **texts**) are written-channel
descriptors, closed by the reading passages in §4b. No script names them, and
the authoring pass restricts B1 scripts to `{B1.R.1, B1.R.2}`.

## What to review / sign off

> **OWNER SIGN-OFF — APPROVED 2026-08-27.** The owner reviewed the authored B1
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

- [x] Themes + week order feel right for your intermediate students.
- [x] **Extended-listening scripts (§4c)** — 14 recordings, 153–193 words. Worth
      checking two things: that the **news and radio scripts sound like
      broadcast** rather than like a textbook, and that the endings which
      deliberately refuse to resolve (week 11's *"everybody was a little wrong"*,
      week 13's caller answering his own question) feel right rather than
      unfinished to you.
- [x] **Reading passages (§4b) feel right for B1** — 14 passages, 147–187 words,
      three text types.
- [x] **Mediation tasks (§4b)** — especially the four "keep the discussion going"
      tasks, which are the newest kind of thing we ask a student to do.
- [x] ⚠️ **The week-3 Thursday travel roleplay (§4b)** — this replaced an existing
      mission, so it is the one place approved B1 content changed.
- [x] Vocabulary choices are appropriate (level, Arabic glosses, examples).
- [x] Grammar sequence is correct and B1-appropriate (builds on A2, stops below B2).
- [x] Speaking/writing tasks match your students' ability (reasons, opinions, narration).
- [x] Certificate wording ("CEFR-aligned", not "certified") is approved.

B1 needs **no migration** — students move from A2 to B1 naturally by passing
the A2 exit exam. Once you approve, B1 is ready the moment a student completes A2.
