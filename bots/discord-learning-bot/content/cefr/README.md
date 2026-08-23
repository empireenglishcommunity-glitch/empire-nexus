# Mi'yar — CEFR content

This directory holds the CEFR-aligned curriculum scaffolding for the six
levels (A1–C2). Built level-by-level during the Mi'yar rollout, behind the
`cefr_curriculum` flag.

## Files

- `can_do.json` — the bilingual CEFR can-do descriptor library (learning
  objectives), keyed by level → mode. Source: Council of Europe Companion
  Volume (2020), which is freely published.
- `grammar_syllabus.json` — per-level ordered grammar points, authored against
  public English Grammar Profile concepts.
- `vocab/<level>.json` — our own CEFR-banded wordlists per level (word, band,
  POS, Arabic gloss, pronunciation, example). Banding decided against public
  CEFR-mapped references (Oxford 3000/5000 CEFR tags, English Vocabulary
  Profile); the stored list is our own to avoid any IP issue.

## Truth-in-labelling

Content here is **CEFR-aligned** (built to the official descriptors). Empire
English issues its own certificates stating the CEFR level demonstrated. We do
NOT claim "CEFR certified" — CEFR has no certifying body.

## Authoring discipline

Every level:
1. is authored against the official CEFR sources,
2. ships a short alignment rationale (which descriptors / grammar / vocab band),
3. passes the **owner approval gate** before going live.
