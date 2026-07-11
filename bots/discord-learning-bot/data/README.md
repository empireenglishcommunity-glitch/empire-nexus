# Data Directory — Level Content Templates

This directory contains the structured curriculum content for each level and week.

## File Structure

```
data/
├── README.md              ← you are here
├── l0_week1.json ... l0_week8.json    ← Level 0, 8 weeks (Greetings & Self → Feelings & Opinions)
├── l0_advancement_exam.json           ← L0 → L1 exit exam
├── l1_week1.json ... l1_week10.json   ← Level 1, 10 weeks (Daily Routines → Social Life)
├── l1_advancement_exam.json           ← L1 → L2 exit exam
├── l2_week1.json ... l2_week12.json   ← Level 2, 12 weeks (Current Events → Future & Technology)
├── l2_advancement_exam.json           ← L2 → L3 exit exam
└── l3_week1.json ... l3_week8.json    ← Level 3, 8 weeks (Idioms → Native-like Fluency, mastery tier — no further advancement exam)
```

## Status (as of 2026-07-11)

**All 4 levels, all 38 weeks, are COMPLETE** with real, hand-written content (vocabulary, speaking missions, writing prompts):

| Level | Weeks | Vocabulary (exact) | Speaking Missions | Writing Prompts |
|-------|:-----:|:----------:|:------------------:|:-----------------:|
| L0 | 8 | 448 words (56/week) | 56 | 56 |
| L1 | 10 | 598 words | 70 | 70 |
| L2 | 12 | 480 words | 84 | 84 |
| L3 | 8 | 317 words/idioms | 56 | 56 |
| **Total** | **38** | **1,843 words** | **266** | **266** |

> **History note:** L1's data files were written in an earlier session and were already real/complete. L2 and L3's `vocabulary` arrays were found **empty (`[]`)** and their `speaking_missions`/`writing_prompts` were **mechanically templated placeholder text** (e.g., `"...about {theme}"` with the theme substituted) despite a prior commit message claiming this content was finished — this was discovered and fully corrected in the 2026-07-11 session (see root `README.md` changelog and the Learning System Blueprint's changelog for details).

Each level's `theme` and `grammar_pattern` fields per week were already correctly assigned in the original file scaffolding and were preserved as-is; only the genuinely missing/templated fields were filled in.

## JSON Structure (per week)

Each file contains:
- `level`: L0/L1/L2/L3
- `week`: week number
- `theme`: vocabulary theme
- `phoneme_focus`: this week's pronunciation target
- `grammar_pattern`: grammar being introduced
- `vocabulary`: array of 56 word objects (8/day)
  - word, pronunciation, arabic, pos
- `speaking_missions`: object keyed by day name
  - type, prompt, target_seconds
- `writing_prompts`: array of 7 prompts (one per day)

## How Content Is Used

1. **Daily task generation** (`src/tasks.py`) reads the appropriate week file
2. If AI generation succeeds, it uses these as context/constraints
3. If AI fails, these serve as the **fallback content** (never an empty day)
4. The vocabulary list feeds the spaced repetition system
5. Speaking missions rotate through the 7-day cycle defined here

## Related Accent & Grammar Content (not in this directory)

The `vocabulary`/`speaking_missions`/`writing_prompts` in this directory are one half of the curriculum. Accent drills and grammar pattern cards live in a **parallel, per-level directory structure** at `../content/{l0,l1,l2,l3}/{accent,grammar}/weekN_*.json`, loaded separately by `src/curriculum.py`. Both halves must exist for a level+week to be fully served — `curriculum.py` will honestly return `None` (never fake/substituted content) for whichever half is missing.

**Important:** content filenames must start with `week<number>_` (e.g. `week10_foo.json`), where `<number>` matches the actual week. `curriculum.py` parses the number directly from the filename — it does NOT rely on alphabetical sort order, specifically because naive alphabetical sorting breaks for any level with 10+ weeks (`"week10"` sorts before `"week2"` as strings). This was a real bug found and fixed on 2026-07-11; do not reintroduce sort-order-based loading.

## Adding New Levels or Extending Existing Ones

To add a new level/week:
1. Copy the nearest existing `lN_weekN.json` as a schema template
2. Update: level, week, theme, phoneme_focus, grammar_pattern
3. Write real vocabulary (aim for ~40-60 words themed to the week — do not leave `vocabulary: []`)
4. Write 7 real speaking missions (one per day type) — avoid generic templated prompts like `"...about {theme}"`
5. Write 7 real writing prompts (progressive difficulty)
6. Add the matching `../content/{level}/accent/weekN_*.json` and `../content/{level}/grammar/weekN_*.json` files
7. Run `curriculum.load_all()` and verify with `get_vocabulary_for_week()`, `get_accent_focus()`, and `get_grammar_pattern()` that the new week resolves correctly before committing

AI (`src/ai_engine.py`) can generate supplementary content dynamically during live sessions, but these static files remain the **required fallback** ensuring no learner ever gets an empty or fake day.
