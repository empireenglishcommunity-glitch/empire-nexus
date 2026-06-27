# Placement & Entry System (Blueprint §3)

## Overview

The placement system assigns learners to the correct level (L0-L3) through a
structured 45-minute diagnostic assessment. Correct placement is critical:
too low = boredom → churn. Too high = frustration → churn.

## Assessment Modules

| Module | Duration | What It Tests | Format |
|--------|:--------:|---------------|--------|
| 1. Speaking | 10 min | Production ability, fluency, pronunciation | Read aloud + spontaneous + shadowing |
| 2. Listening | 10 min | Comprehension at 3 speeds | 15 MCQ (80/130/160 WPM) |
| 3. Vocabulary | 10 min | Word recognition across frequency bands | 40 MCQ |
| 4. Grammar | 10 min | Structural awareness | 25 MCQ |

## Scoring Algorithm

1. Score each module 0-100
2. Map each to a level (L0/L1/L2/L3) using thresholds
3. Majority-rules: most common level = assigned level
4. Tiebreaker: Speaking score wins
5. 20+ point gap between dimensions = flag for human review

## Files

| File | Contents |
|------|----------|
| `scoring_algorithm.json` | Level thresholds, scoring logic, assignment rules |
| `module1_speaking.json` | Speaking prompts for all levels |
| `module2_listening.json` | Listening clips + questions (3 speeds) |
| `module3_vocabulary.json` | 40 vocabulary questions across frequency bands |
| `module4_grammar.json` | 25 grammar questions across structures |
| `onboarding_flow.json` | Complete 48-hour onboarding sequence (§3.3) |

## Pilot Simplification

For the 10-member pilot, a simplified placement is acceptable:
- Existing 7-question Telegram quiz (quick screener)
- + 60-second voice recording (founder evaluates speaking)
- + 5 written sentences (founder evaluates writing)
- = Founder assigns level based on judgment

The FULL diagnostic below is for Phase 2+ (automated, scalable placement).
Building it now so it's ready when needed.
