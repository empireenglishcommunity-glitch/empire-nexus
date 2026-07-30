# Nutq — Pronunciation Feedback — Requirements (CONSOLIDATED, FINAL)

**Codename:** Nutq (نُطق). This is the single source of truth for the whole Nutq
feature. It supersedes the earlier drafts of this spec (self-hosted-only) and the
`pronunciation-feedback` spec (Whisper-based). See `decision-log.md` for the three
pivots and the evidence behind them.

**Status:** DRAFT — awaiting owner approval. **No code until approved.**

---

## What we are building (in one line)
Accurate, professional, bilingual pronunciation feedback on the practice page,
powered by **Azure Pronunciation Assessment** (primary) with the **free local
self-hosted engine as fallback**, kept **$0/month at current scale** by a strict
cost policy + a hard usage guard.

## Why (verified, not assumed — see decision-log.md)
- **Nutq 1 (Whisper + word match):** Whisper "hears" intended words, so it can't
  detect mispronunciation — reading wrong still scored high ("felt unreal").
- **Nutq 2 (self-hosted allosaurus phonemes):** too noisy on real recordings —
  native-like reads scored 41–66 and it flagged sounds the student said correctly.
  Proven on the owner's own recordings.
- **Conclusion:** professional accuracy needs a purpose-built pronunciation
  engine. Azure's is accurate, handles natural/accented speech, and is **free at
  our scale**. The self-hosted engine (already built) becomes the safety-net.

---

## Requirements (EARS-style)

### R1 — Accurate, professional scoring (primary = Azure)
WHEN a student records the **shadow** exercise, THE SYSTEM SHALL score it with
**Azure Pronunciation Assessment** against that day's exact shadow target text,
returning Accuracy + Fluency + Completeness and **per-word / per-phoneme** detail.

### R2 — Trustworthy behaviour
WHEN a student reads **well** (even with an Arabic accent), THE SYSTEM SHALL
return a **high** score; WHEN they read **wrong / mispronounce**, THE SYSTEM SHALL
return a **lower** score and identify the **correct** failed sound(s). The named
sound MUST be right (the Nutq 2 failure of flagging correctly-said sounds must not
recur).

### R3 — Cost policy: $0/month at current scale, capped as we grow
THE SYSTEM SHALL bound Azure usage so it stays within the free tier for the
current cohort:
- Azure-score **only the shadow task**, **once per student per day** (the graded submission).
- Allow at most **2** Azure "try-again" re-checks per student per day.
- Azure-score **one** reading in the **weekly assessment** (progress checkpoint).
- Accent/other tasks are NOT Azure-scored.

### R4 — Hard usage guard (never a surprise bill)
THE SYSTEM SHALL track Azure audio-seconds used this calendar month; WHEN usage
reaches **~90% of the free monthly allowance (~5 audio hours)**, THE SYSTEM SHALL
stop calling Azure for the rest of the month and use the **fallback engine**.

### R5 — Fallback = the free local engine
WHEN Azure is unavailable/slow/errors OR the usage guard has tripped, THE SYSTEM
SHALL score with the **free self-hosted engine (`nutq-scorer` / allosaurus)** so
the student still gets feedback. Fallback feedback SHALL be honest/coarser (a band
+ encouragement, **without** naming a specific sound, since the local per-phoneme
detail is not reliable).

### R6 — Best-effort; NEVER blocks the core flow
THE SYSTEM SHALL complete the exercise and post to `#showcase` **before** scoring;
IF all scoring paths fail/time out, THE SYSTEM SHALL still complete normally and
show a neutral "saved — couldn't score this time" note (never an error, never a
lost completion). Bounded by a timeout with a "🎧 checking…" indicator.

### R7 — Reuse the Nutq delivery pipeline unchanged
THE SYSTEM SHALL keep the shipped page recorder → `/api/submit-recording` +
`/api/pronunciation-check` → flag gate → on-page panel → try-again → storage, and
return the **same `pronunciation` JSON shape**, so the dojo UI needs **no change**.

### R8 — Reliable, actionable bilingual feedback
WHEN Azure scores a recording, THE SYSTEM SHALL name the specific word(s)/sound(s)
to improve and give **one** short, correct, actionable tip in **English + Egyptian
Arabic**, encouragement-first, NOT Nour-voiced, no grammar/content critique.

### R9 — Score exactly what the page shows
THE SYSTEM SHALL score the shadow recording against the exact passage the page
displayed for that week/day/level (drift already closed via `_drill_primary_text`).

### R10 — Persistence + progress + usage accounting
THE SYSTEM SHALL store each score to `pronunciation_scores` (so `!progress` keeps
working) and record Azure audio-seconds for the usage guard (additive, no breaking
schema change). It SHALL record which engine produced each score.

### R11 — Privacy
Feedback SHALL remain private to the student's own authenticated session; nothing
posted publicly. `#showcase` posting is unchanged.

### R12 — Flag-gated pilot → rollout
THE SYSTEM SHALL gate behind `tatawwur_pronunciation` (currently OFF), pilot on
BioRoMa + Mai, live-verify R1/R2/R8, then enable for all students.

### R13 — Secrets & safety
Azure key + region SHALL come from environment (`.env`), never committed. The
usage guard SHALL make runaway cost impossible. Deploys backed up + verified.

### R14 — Scale
Cost SHALL grow modestly and remain **capped** by the guard; the design SHALL be
portable so the engine can later be brought fully in-house if scale ever justifies
it, with no change to the delivery pipeline.

---

## Non-goals
- Azure-scoring the accent/speaking tasks (shadow only for now).
- Free-form speaking/fluency grading (future).
- Prosody/grammar/topic scoring (Azure can, but out of scope for v1).
- Re-enabling adaptive difficulty.
- Any change to completion/points/streak/mastery or `#showcase`.

## Constraints
- **$0/month at current (17-student) scale**; capped thereafter by R4.
- Bilingual EN + Egyptian Arabic; not Nour-voiced.
- Same safe-deploy discipline: own PR per phase, tests green, owner-merged, backup
  before server change, live-verify, zero disruption to the daily flow.
- No guessing — behaviour verified live on real recordings before rollout.
