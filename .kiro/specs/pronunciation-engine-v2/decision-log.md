# Nutq — Decision Log (the three pivots)

A short, honest record of how the Nutq engine evolved and why, so the history is
never lost.

## Pivot 1 — Whisper word-matching → "felt unreal"
- **What:** Nutq 1 re-wired the existing engine (Groq Whisper transcription + fair
  word comparison) to the practice page; flag-gated; shipped + piloted.
- **Evidence:** Owner (BioRoMa) read a sentence **wrong on purpose** and still got
  praise + no correction. Root cause: Whisper is built to output clean, correct
  text, so it "hears" the intended words — it can't detect *how* you pronounced.
- **Decision:** replace the scoring brain (keep the delivery pipeline).
- Also removed the "beginner grace" that hid the score for the first 3 recordings.

## Pivot 2 — Self-hosted phoneme model (allosaurus) → too noisy
- **What:** Nutq 2 built a self-hosted phoneme scorer (`nutq-scorer`, allosaurus +
  g2p + alignment), calibrated on real Arabic-accented samples, deployed, piloted.
- **Evidence:** On the owner's own recordings, native-like reads scored **41–66**,
  and it flagged sounds the owner said **correctly** (e.g. "is/His/your"). The
  model also scored its own clean TTS only 71–77. Two causes: (a) the tiny model is
  noisy; (b) even a perfect recognizer scores fluent speech ~82 vs the *dictionary*
  pronunciation (natural linking/flapping differs). A precise, fair % isn't
  reliable on this hardware.
- **Decision:** professional accuracy needs a purpose-built pronunciation engine.
  Keep the self-hosted engine as a **fallback**, not the primary.

## Pivot 3 — Azure Pronunciation Assessment (primary) + local fallback → final
- **What:** Use Azure Pronunciation Assessment (accurate per-phoneme, handles
  natural/accented speech) as primary; the free self-hosted engine as fallback.
- **Cost reconciliation:** Azure was earlier ruled out under a "free at ANY scale"
  rule. Once *professional accuracy* became the priority (and the free self-hosted
  route was proven inadequate), the honest truth is **no option is both free-forever
  and professional**. Azure is **$0/month at current scale** and cheaper than a
  capable self-hosted setup until large scale, with zero maintenance.
- **Cost controls (owner-designed):** shadow-only; 1 graded/day/student; ≤2
  try-again/day; weekly checkpoint; **hard usage guard** auto-switches to the free
  local engine at ~90% of the free tier → **never a surprise bill**.
- **Trade-off accepted:** uses a managed API (not fully self-hosted); professional
  quality + $0-now + capped cost was judged the right long-term call. Portable so
  it can be brought in-house later if scale justifies it.
