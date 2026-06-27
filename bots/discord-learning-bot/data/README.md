# Data Directory — Level Content Templates

This directory contains the structured curriculum content for each level and week.

## File Structure

```
data/
├── README.md           ← you are here
├── l0_week1.json       ← Level 0, Week 1 (Greetings & Self)
├── l0_week2.json       ← Level 0, Week 2 (Numbers, Time, Days)
├── l0_week3.json       ← (to be created: Family & People)
├── l0_week4.json       ← (to be created: Home & Daily Life)
├── l0_week5.json       ← (to be created: Food & Shopping)
├── l0_week6.json       ← (to be created: Places & Directions)
├── l0_week7.json       ← (to be created: Actions & Descriptions)
├── l0_week8.json       ← (to be created: Feelings & Opinions)
└── ...                 ← L1, L2, L3 added as the program grows
```

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

## Adding New Weeks

To add Week 3+:
1. Copy `l0_week1.json` as a template
2. Update: week, theme, phoneme_focus, grammar_pattern
3. Replace vocabulary (56 words themed to the new week)
4. Write 7 speaking missions (one per day type)
5. Write 7 writing prompts (progressive difficulty)

AI will generate the remaining weeks dynamically during the pilot.
These static files are the safety net.
