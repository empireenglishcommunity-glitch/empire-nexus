# Phase 8 — CEFR Assessment Alignment & Validation Statement

> **Codename: Mi'yar (معيار).** This document is the honest, auditable record of
> *how* Empire English's placement test, level exit exams and certificates
> relate to the CEFR — and, just as importantly, of the limits of that claim.
> It is referenced by the certificate footer and must be read before anyone
> (a future session, the owner, or marketing) describes the assessments
> publicly.

## 1. The one-line claim we are allowed to make

> **"Built to CEFR methodology and aligned to the CEFR by design; pending
> empirical validation. Not an accredited CEFR examination."**

Never "CEFR certified," "official CEFR test," or an implication of external
accreditation. This follows requirement **R0 (truth in labelling)**.

## 2. The method we followed (Council of Europe, 4 stages)

The Council of Europe's *Manual for Relating Language Examinations to the CEFR*
defines four stages for linking an exam to the CEFR. Here is exactly which we
have done and which we have not:

| Stage | What it means | Status here |
|---|---|---|
| **1. Familiarisation** | The team genuinely knows the CEFR descriptors. | ✅ Done — the whole curriculum, week by week, is authored from the CEFR can-do descriptors in `can_do.json`. |
| **2. Specification** | Map exam content to CEFR categories/descriptors. | ✅ Done — every exit-exam item is tagged to a descriptor code (e.g. `B1.P.3`); placement probes the four CEFR skill modes. |
| **3. Standardisation** | Consistent judgement of what a level performance looks like. | ✅ Done by design — rating rubrics, worked descriptor anchors, and the AI rater are all pinned to the level's descriptors; boundary cases route to human review. |
| **4. Empirical validation** | Statistically calibrate item difficulty and cut scores against real candidate data. | ❌ **Not done — and we say so.** See §3. |

## 3. Why stage 4 is not done (and why claiming it would be dishonest)

Empirical validation requires a sample large enough to estimate item
difficulty, discrimination, and defensible cut scores. **Empire English has ~17
students.** That is far too few to calibrate anything statistically — any
"difficulty parameter" or "cut score" derived from it would be noise dressed as
rigour.

Therefore:

- **Item difficulty is expert-assigned**, not data-calibrated.
- **Cut scores are expert-set** (see §5), not empirically derived.
- We deliberately did **not** wire in the separate `empire-oracle` IRT engine
  (see §6), because a 3PL "ability estimate" would imply a precision the data
  cannot support.

Stating this openly is not a weakness — it is the difference between an honest
aligned instrument and an overclaimed one. Overclaiming is the single thing that
could damage the reputation the programme is being built to protect.

## 4. Criterion-referenced, not norm-referenced

CEFR is a **can-do** framework. We assess a student against the **descriptors of
the level** (criterion-referenced) — "can they do these things?" — not by
ranking them against other students (norm-referenced). This is the pedagogically
correct way to apply the CEFR and, conveniently, the only sound way with a tiny
cohort. Every assessment artifact traces to `can_do.json`.

## 5. Cut scores (expert-assigned, documented here so they are not silently changed)

Exit-exam pass criteria — Part A is structured/objective, Part B is an
integrated production task rated against the level's production descriptors:

| Levels | Part A (objective) | Part B (production, /100) |
|---|---|---|
| A1–A2 | ≥ 65% | ≥ 60 |
| B1–B2 | ≥ 65% | ≥ 65 |
| C1–C2 | ≥ 65% | ≥ 70 |

- **Distinction** at any level: Part B ≥ 90.
- **Boundary review band:** if the result is within **±7** of a threshold, or
  the AI rater reports low confidence, the attempt is **not auto-decided** — it
  goes to the owner review queue. This protects against both false passes and
  false fails on the exact cases where automated judgement is least reliable.

The production weight and threshold rise with level (R7.2): higher levels are
judged more on sustained production, less on discrete items.

## 6. What we did NOT integrate, and the trigger to revisit

The `empire-oracle` product has a genuine 3PL IRT adaptive engine. We did **not**
use it for Phase 8 because:

1. it is a **separate deployed app** with its own database and no integration
   bridge to the bot — building that is its own project;
2. its CEFR output is four **coarse, ambiguous bands** (`A2-B1`, `C1-C2`) that
   cannot emit a single level; and
3. IRT implies empirical calibration we cannot honestly provide (see §3).

**Revisit trigger:** once there is a calibrated item bank and enough real
attempts to estimate item parameters, the oracle IRT engine becomes the natural
"full adaptive placement" upgrade. Until then, the self-contained branching
placement (per-skill, conservative) is the honest choice.

## 7. Placement philosophy

Placement outputs a **per-skill CEFR profile** (Vocabulary/Grammar, Listening,
Writing, Speaking), because CEFR is skill-differentiated and collapsing it to a
single number is a recognised misuse. The **overall** placement is deliberately
**conservative** — a student is slotted where they can succeed, not at the
ceiling of their range, because a well-placed student who advances quickly is a
far better outcome than a mis-placed one who stalls and quits.

## 8. Change log

- **2026-08-25** — created with Phase 8. Documents the alignment method, the
  validation boundary, expert-set cut scores, and the deliberate non-use of the
  oracle IRT engine.
