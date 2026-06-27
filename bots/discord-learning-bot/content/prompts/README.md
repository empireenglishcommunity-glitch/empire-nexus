# AI Prompt Library — Empire English Community

## Overview

These are the 25 prompts that power the AI Content Factory (Blueprint §11).
Each prompt is a structured template that generates personalized learning content
when called with learner-specific variables.

## Deployment Status

| # | Prompt | Status | File |
|---|--------|:------:|------|
| 1 | Weekly Vocabulary Cheat Sheet | ✅ | cheat_sheets.json |
| 2 | Grammar Pattern Card Generator | ✅ | cheat_sheets.json |
| 3 | Personal Error Log | ✅ | cheat_sheets.json |
| 4 | Daily Speaking Mission | ✅ | src/ai_engine.py (deployed) |
| 5 | Speaking Evaluation & Feedback | ✅ | evaluation.json |
| 6 | Role-Play Scenario Generator | ✅ | speaking.json |
| 7 | Listening Comprehension Exercise | ✅ | listening.json |
| 8 | Transcription Exercise Generator | ✅ | listening.json |
| 9 | Writing Assessment & Correction | ✅ | src/ai_engine.py (deployed) |
| 10 | Weekly Progress Report | ✅ | evaluation.json |
| 11 | Accent Analysis Report | ✅ | evaluation.json |
| 12 | Leveled Reading Passage | ✅ | materials.json |
| 13 | Conversation Starter Pack | ✅ | materials.json |
| 14 | Shadowing Audio Script | ✅ | materials.json |
| 15 | Assessment Question Bank | ✅ | scaling.json |
| 16 | Personalized Study Plan | ✅ | scaling.json |
| 17 | Onboarding Sequence Messages | ✅ | scaling.json |
| 18 | Phoneme Drill Generator | ✅ | src/ai_engine.py (deployed) |
| 19 | Linked Speech Exercise | ✅ | accent.json |
| 20 | Intonation Pattern Drill | ✅ | accent.json |
| 21 | Song Analysis Worksheet | ✅ | immersion.json |
| 22 | Movie Scene Transcript | ✅ | immersion.json |
| 23 | Debate Topic Generator | ✅ | community.json |
| 24 | Writing Prompt Generator | ✅ | materials.json |
| 25 | Grammar Error Explanation | ✅ | cheat_sheets.json |

## How to Use

Each JSON file contains prompt templates with:
- `system_prompt`: The AI's role and context
- `user_prompt_template`: Template with {VARIABLES} to fill
- `variables`: List of required inputs
- `output_format`: Expected JSON structure from the AI
- `example_output`: A sample for validation

To call a prompt:
1. Load the template from the appropriate JSON file
2. Fill {VARIABLES} with learner data
3. Send to Gemini/Groq via `ai_engine.py`
4. Parse the JSON response
5. Deliver to the learner via Discord/DM

## Integration

These prompts integrate with:
- `src/ai_engine.py` — the Python module that calls LLMs
- `src/tasks.py` — uses prompts for daily task generation
- n8n workflows — can call prompts via HTTP for scheduled delivery
- Discord bot — invokes prompts in response to commands/submissions
