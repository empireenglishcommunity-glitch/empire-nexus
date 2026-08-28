# Content review — 2026-08-27

> **What this is, and what it is not.** This is a full **technical and editorial
> QA pass** over all authored CEFR comprehension content, done by the assistant.
> It is **not** the owner's sign-off. The two are different things and the
> difference matters: the machine checks and the reading below establish that the
> content is *structurally sound and, in the sample read, correctly keyed*. They
> do **not** establish that a human who knows the students has judged it right for
> them. The sign-off boxes in the `*-ALIGNMENT.md` files stay **unticked**. A box
> ticked by the assistant would erase the only signal that separates "a person
> checked this" from "a machine made it" — which, on a programme that issues
> certificates, is the thing worth protecting.

## Scope

270 content files — reading, mediation and broadcast, 90 of each, across A1–C2.

Two layers of review:

1. **Machine validation of every one of the 270 files** (`scripts/content_qa.py`
   + the new `tests/test_content_quality.py`).
2. **Reading, by hand, of the highest-risk items for answer-key correctness** —
   which no machine can check, because "which option is actually correct" is a
   judgement, not a shape. 23 files read in full, chosen to cover the content
   most likely to be mis-keyed.

## Headline

- **Zero objective defects across all 270 files.** No answer index out of range,
  no duplicate or near-duplicate options, no empty stems/options/fields, no
  invalid can-do codes, no glossary entry missing its Arabic, every reading
  question bilingual, every mediation task's bilingual fields carrying Arabic.
- **Every keyed answer in the 23 files read was correct and unambiguous** —
  including the deliberately hard traps.
- **One systemic smell, not an error: length bias** (below).

## What was read by hand, and the verdict

The set you were most worried about — irony and register, where a generated key
is most plausibly wrong — was read in full:

| Set | Files | Result |
|---|---|---|
| **C2.R.3** — humour, irony, implicit cultural meaning | all 12 | every key correct |
| **C2.R.4** — stance conveyed *only* through style | all 5 | every key correct |
| C2.R.2 — abstract / complex written forms | 2 sampled | correct |
| Cross-level (A2, B1, B2, C1) reading + broadcast | 4 sampled | correct |

Examples that show the keys are genuinely reasoned, not lucky:

- **`week12_the_proof_of_the_pudding`** (C2.R.3): the trap option "the members
  were deliberately concealing a decision" is correctly marked *wrong*, because
  the text says "I do not think anybody was being evasive". A shallow reading
  would pick the trap.
- **`week7_much_as_one_admires_it`** (C2.R.3): "it will prevail on the shelf for
  years" is correctly keyed as meaning the report will be **ignored**, not
  influential — the irony is the whole point.
- **`week16_off_the_record`** (B2.R.2): the on-record and off-record answers are
  correctly distinguished, including "it's a much worse answer, which is exactly
  why you got the other one".

### On cultural register (C2.R.4)

The register scripts lean on British-inflected understatement — a farewell
address that praises while damning, a eulogy, a museum narration. My assessment
is that this is **appropriate and, in one case, well-judged**: the museum piece
turns on a Nineteenth-Dynasty limestone relief taken to London and "the country
it was taken from", which is directly resonant for an Egyptian audience rather
than culturally remote. C2.R.4 explicitly asks for stance "conveyed only through
subtle stylistic choices", and understatement is a central instance of exactly
that skill.

**This remains your editorial call, not mine.** I know the CEFR descriptor; you
know the students. If British irony is the wrong idiom for them, it is five
scripts to re-point, and nothing downstream changes.

## The one systemic finding: length bias

Across the 756 comprehension items, the correct option is the *uniquely longest*
**75.5%** of the time, and it rises sharply with level:

| level | correct-is-longest |
|---|---|
| A1 | 39% |
| A2 | 65% |
| B1 | 66% |
| B2 | 80% |
| C1 | **94%** |
| C2 | 85% |

A test-taker who always picked the longest option would score well above chance
without understanding anything. This is a real assessment-validity smell. It
arises honestly — at higher levels the correct answer is a precise, qualified
paraphrase while the distractors are pithy wrong readings — but it is still a
tell.

**C1 has been fixed (2026-08-27); C2/B2 deliberately left for editorial review.**
C1 was the worst level at 94%, and the terminal-but-one, so it was corrected
first: two items per file had a *distractor* strengthened with a clause that is
demonstrably false against the passage/script, so a wrong option is sometimes the
longest. The keyed answers were never touched. Every one of the 72 edited items
was re-read to confirm the strengthened distractor stays clearly wrong (no
double-correct), and the structural checks and full suite pass. C1 fell from
**94% → 44%** — below the point where "pick the longest" is a usable strategy.

C2 (85%) and B2 (80%) were **not** put through the same mechanical pass, on
purpose. Rewriting ~140 more currently-correct items carries a real,
cumulative risk of introducing a subtle second-defensible-answer into content
that is presently correct — the exact failure this review exists to prevent —
for levels no student will reach for a long time. The far safer and nearly-free
place to strengthen those distractors is **inside the human editorial read**:
whoever reads each C2/B2 item for correctness can lengthen a distractor in the
same pass, with eyes on the item. The `content_qa.py` report keeps the per-level
number visible so it is not forgotten.

The lower levels (A1 39%, A2 65%, B1 66%) are milder and lower-stakes; same
recommendation.

Position bias is **not** a real problem: the global answer-index distribution is
239 / 305 / 193 / 19 across indices 0–3, and index 3 is rare only because most
items have three options. Per-file "3 of 4 on one index" warnings are
small-sample noise.

## What this review added to the repo

- **`tests/test_content_quality.py`** — enforces the objective invariants above
  as a hard build failure, for all 270 files and any future content. Verified to
  actually catch bad indices, duplicate/near-duplicate options, empty fields,
  missing Arabic and invalid codes (not vacuously passing).
- **`scripts/content_qa.py`** — reports the length/position smells without
  failing the build, so authors can watch them.

## What remains yours

1. **The editorial sign-off** in the `*-ALIGNMENT.md` files. Unticked, on
   purpose. This review does not tick them and should not.
2. **The C2.R.4 register judgement** — accept the British-understatement idiom,
   or ask for it to be re-pointed.
3. **Whether to commission the length-bias authoring pass**, or accept the
   current items as good enough given the position rotation.

Nothing here is blocking. The content is sound, correctly keyed in everything
read, and now guarded by a test. The remaining items are judgements that are
yours to make, and the point of leaving them to you is that they stay yours.
