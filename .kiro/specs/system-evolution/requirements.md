# Requirements — Tatawwur (تطور): System Evolution

> **Codename:** Tatawwur (تطور — "Evolution")
> **Purpose:** Transform the Discord learning system from a daily-task
> tracker into a provably transformative English fluency engine — one
> that creates undeniable success stories of Arabic speakers (especially
> Egyptians) going from zero to native-like fluency. Different from any
> course or diploma. Proves results, doesn't just claim them.
> **Vision:** A student joins with zero English. Months later, they have
> RECORDINGS proving their accent changed, SCORES showing pronunciation
> improvement, ABILITIES they can demonstrate, VOCABULARY they recall
> under pressure, and CONVERSATIONS they've had with real people. No
> course in Egypt delivers this. This system does.

---

## Core Principle

**Prove it, don't claim it.**

Every enhancement exists to create EVIDENCE of transformation that the
student (and the world) can see, hear, and verify. Not certificates.
Not grades. Actual, audible, demonstrable change.

---

## Requirements

### R1 — Voice Progress Portfolio ("Hear Your Growth")
Students MUST be able to hear their own transformation over time.
Acceptance criteria:
- The system stores benchmark recordings at regular intervals (day 1,
  week 4, week 8, level change)
- A command shows the student their own recordings chronologically
- The difference between early and later recordings is AUDIBLE to them
- This portfolio is exportable (shareable as a "proof of progress")
- Recordings are stored persistently (survive container rebuilds)

### R2 — AI Pronunciation Scoring + Feedback
Every speaking submission MUST receive specific, actionable feedback on
pronunciation — not just a ✅. Acceptance criteria:
- Each recording gets a phoneme-level score (overall + per-sound)
- Specific sounds that need work are identified ("your /r/ sounds like /l/")
- Progress is tracked per-sound over time (trend visible)
- Comparison to a native model is available (the founder's recordings)
- Uses free/self-hosted AI where possible (budget: $7/mo total)

### R3 — Ability Milestones ("I Can Now...")
Students MUST feel progress as ABILITIES, not just numbers.
Acceptance criteria:
- Each level has concrete "I can now..." statements (not just point thresholds)
- Milestones are tested via real challenges (not self-reported)
- Completion of ability milestones is celebrated and recorded
- Examples: "I can introduce myself in 60 seconds", "I can describe
  my day without pausing", "I can tell a joke that a native understands"

### R4 — Spaced Repetition Engine (Long-Term Recall)
Vocabulary MUST be retained long-term, not just encountered once.
Acceptance criteria:
- Every word taught enters a spaced repetition queue
- Students are tested on OLD words (not just today's) at increasing intervals
- The system tracks which words each student knows vs. struggles with
- Weak words appear more frequently; mastered words fade out
- A student can see their "vocabulary strength" (known / learning / weak)

### R5 — Structured Conversation Sessions
Students MUST practice real-time speaking with other humans regularly.
Acceptance criteria:
- Weekly structured conversation sessions (paired or small group)
- Conversation prompts matched to student level
- The bot facilitates pairing (matches levels or buddy pairs)
- Session attendance is tracked and counts toward community tasks
- Guidelines provided in Arabic (how to do it, what to say if stuck)

### R6 — Conversational Patterns Library
Students MUST learn how natives ACTUALLY talk (not textbook English).
Acceptance criteria:
- Daily/weekly conversational patterns (phrases, not words): "How's it
  going?", "I was wondering if...", "That makes sense", "No worries"
- Patterns grouped by function: greetings, opinions, clarifying, etc.
- Each pattern has: the phrase, when to use it, an example, the Arabic
  equivalent in meaning (not literal translation)
- Integrated into daily tasks (not a separate system)

### R7 — Student Showcase / Success Stories
The system MUST generate visible proof of results for marketing.
Acceptance criteria:
- A #success-stories channel where milestones auto-post
- Students can opt-in to make their voice progress portfolio public
- Before/after recordings (with permission) become marketing assets
- The system generates periodic "community stats" posts (X members
  improved by Y% this month)

### R8 — Adaptive Difficulty
The system MUST adjust to each student's actual pace. Acceptance criteria:
- Fast learners get harder content sooner (not stuck waiting for week 8)
- Struggling students get extra review (not pushed forward unprepared)
- Adaptation is based on actual performance data (completion rate,
  quiz accuracy, assessment scores) — not self-reported
- The student is informed when their pace adjusts ("you're progressing
  fast — unlocking advanced content early!")

---

## Constraints

- Same $7/month Hetzner VPS — no new paid services
- Groq free tier for AI scoring (already available, 1000 req/day)
- Recordings stored in Docker volumes (persistent, survives rebuilds)
- Must work within Discord's file upload limits (25 MB for free servers)
- Ships behind feature flags (tatawwur_* prefix) per Aegis convention
- The founder's OWN accent recordings serve as the "native model"
  (this is the unique selling point — not a generic American voice)

---

## Out of Scope (for now)

- Mobile app (stay on Discord for now)
- Paid AI services (ElevenLabs, OpenAI Whisper API — stay on free tiers)
- Live teacher/tutor marketplace (founder + bot + community is the model)
- Certification / official diplomas (the RECORDINGS ARE the proof)
