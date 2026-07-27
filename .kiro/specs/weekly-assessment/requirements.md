# Requirements — Weekly Assessment ("Itqan")

> **Codename: Itqan (إتقان)** — Arabic for "mastery / doing something
> properly." The whole point of this feature is to prove, honestly, that a
> student has *mastered* a week's content — not just showed up. Directory
> name (`weekly-assessment`) stays literal so it's discoverable.

## Origin

Empire English is a **result-driven** learning system for ~16 Arabic-speaking
beginners (Level 0 alone runs ~8 weeks). Students do a 7-task daily loop and
practice on the Darb page (practice.empireenglish.online).

The old "weekly assessment" was deleted (session 33) because it scored four of
five skills as 0 or 100 purely on *whether a task was submitted* — attendance
dressed up as a skill grade, then labeled Excellent…Critical. It was
misleading and unprofessional.

The owner wants a **real** weekly assessment that:
- fires **after each week**, on that week's content;
- is **cumulative with a recency focus** (a "spiral": mostly the latest week,
  plus sampled earlier weeks so nothing is forgotten);
- proves **both** that the student was *active on the daily tasks* **and**
  *actually learned the material*;
- is a **professional, visual page inside the practice site** (not a Discord
  quiz), using **Kokoro** for audio and voice recording for speaking;
- has **professional pass/fail** and a real **anti-cheat** posture, because
  "result-driven" is the brand promise;
- **celebrates winners publicly** and **supports strugglers privately** — no
  public shaming.

## Constraints

1. **Zero disruption to the live daily flow.** The 16 students' existing daily
   tasks, streaks, points, calendar, and recording flows must keep working
   exactly as they do today.
2. **Budget:** same server + free/cheap AI (Groq Whisper for speech→text,
   Groq/Gemini for text feedback, Kokoro for TTS already integrated). No new
   paid services, no GPU, no new containers.
3. **Graceful degradation:** if an AI/scoring service is down, the assessment
   must not hard-fail a student — fall back safely and/or flag for the owner.
4. **Beginners, Arabic-first:** instructions bilingual (Arabic primary),
   mobile-first, kind tone. Assume low English and phone usage.
5. **Timezone:** all unlocks/reports honor Asia/Dubai.
6. **Security/privacy:** the assessment page is gated by the student's existing
   Darb session. Recordings are analyzed then discarded; only scores/feedback
   are stored.
7. **Owner stays in control:** manual override for edge cases; a human is the
   final authority on any consequential/borderline call.

## Glossary

- **Content week (W):** a 7-day block of the level's curriculum (each level has
  several). Anchored to the student's own join date (personal calendar).
- **Week Assessment (Itqan test):** the end-of-week test for week W.
- **Spiral:** the test is ~65% week W + ~35% sampled from weeks 1…W-1 (the
  older items chosen from the student's weak-item / SRS queue).
- **Consistency score:** did the student actually do week W's daily tasks
  (already tracked).
- **Mastery score:** how well the student performed on the Itqan test.
- **Mastered:** passed both Consistency and Mastery for week W.

---

## Requirements

### R1 — Calendar-gated unlock
**User story:** As a student, I want the weekly assessment to appear on my
calendar and open only after I've genuinely gone through the whole week, so the
test is fair and I'm never tested on content I skipped.

Acceptance criteria:
1. THE SYSTEM SHALL show a **Weekly Assessment marker** on the student's Darb
   calendar at the end of each content week (its own calendar stop).
2. WHEN a student has completed **every day of week W at least once** (each of
   the week's days has at least one recorded completion), THE SYSTEM SHALL
   **unlock** week W's assessment.
3. WHILE any day of week W is not yet completed at least once, THE SYSTEM SHALL
   keep week W's assessment **locked**, showing what remains ("finish Day X to
   unlock").
4. THE SYSTEM SHALL anchor weeks to the student's personal (join-anchored)
   calendar, so each student unlocks based on *their* progress, not a fixed date.
5. IF a student completes the week late, THE SYSTEM SHALL still unlock the
   assessment whenever completion is reached (no expiry).

### R2 — The assessment page (practice site)
**User story:** As a student, I want to take the assessment on a clean,
professional page (not a chat), so it feels like a real exam and I can focus.

Acceptance criteria:
1. THE SYSTEM SHALL present the assessment as a **dedicated page** in the Darb
   practice site, gated by the student's existing session.
2. THE SYSTEM SHALL show, before starting: an **Arabic-first explanation** of
   how it works, the approximate length (~10–15 min), that it is **timed**, and
   a **sample question** that does not count.
3. THE SYSTEM SHALL present **one question/section at a time**, with clear
   progress ("Question 3 of 10").
4. THE SYSTEM SHALL play required audio via **Kokoro** and allow **voice
   recording** for spoken items, on mobile and desktop.
5. THE SYSTEM SHALL run a visible **timer** and auto-submit when time expires.
6. THE SYSTEM SHALL be **mobile-first** and fully usable on a phone.

### R3 — What it tests (all five skills)
**User story:** As the owner, I want the assessment to evaluate everything they
practice daily, so a pass reflects real, all-round learning.

Acceptance criteria:
1. THE SYSTEM SHALL include items covering all five practiced skills:
   **listening, vocabulary, pronunciation, speaking, writing.**
2. THE SYSTEM SHALL include at least one **production** item (speaking AND/OR
   writing) where the student must *produce* language using the week's content.
3. THE SYSTEM SHALL generate items from the **existing curriculum data** for the
   covered weeks (vocabulary, phonemes, listening scripts, themes).

### R4 — Spiral (cumulative with recency focus)
**User story:** As a student, I want the test to focus on the newest week but
still check I remember earlier weeks, so I retain everything.

Acceptance criteria:
1. THE SYSTEM SHALL weight each week-W test approximately **65% week W** and
   **35% earlier weeks (1…W-1)**.
2. THE SYSTEM SHALL select the earlier-week items **primarily from the student's
   weak-item / spaced-repetition queue** (what they're most likely to have
   forgotten), not at random.
3. THE SYSTEM SHALL keep total length roughly constant as weeks accumulate
   (a late-level test is not dramatically longer than an early one).

### R5 — Scoring: two dimensions
**User story:** As the owner, I want a pass to mean "they were active AND they
learned it," shown professionally and kindly.

Acceptance criteria:
1. THE SYSTEM SHALL compute a **Consistency score** (did they do week W's daily
   tasks — from existing tracking) and a **Mastery score** (test performance).
2. THE SYSTEM SHALL define **Pass ("Mastered") = both scores at or above their
   thresholds.**
3. THE SYSTEM SHALL display results with **kind, professional band labels**
   (e.g., `🏅 Mastered`, `📈 Almost there`, `🔁 Needs review`) — never
   "Fail/Critical."
4. THE SYSTEM SHALL award a **`⭐ Distinction`** marker for a top-tier Mastery
   score.
5. THE SYSTEM SHALL make the passing thresholds **configurable** (tunable by the
   owner as real data comes in).

### R6 — Pass outcome (public celebration)
**User story:** As a student, I want passing to be recognized publicly, so I
feel proud and others are inspired.

Acceptance criteria:
1. WHEN a student masters week W, THE SYSTEM SHALL award a **"Week W Mastered"**
   badge on their profile/calendar.
2. WHEN a student masters week W, THE SYSTEM SHALL post a **celebration** in a
   Discord **`🏅 Week Champions`** channel (in the level category), naming the
   student and the week (and Distinction if earned).
3. THE SYSTEM SHALL make celebration posts **positive-only**.

### R7 — Not-pass outcome (private support, no lockout)
**User story:** As a struggling student, I want help and another chance in
private, without losing my daily habit, so I stay motivated to improve.

Acceptance criteria:
1. IF a student does not pass week W, THE SYSTEM SHALL **not** lock or pause
   their daily tasks, streak, or calendar.
2. THE SYSTEM SHALL withhold the "Week W Mastered" badge until they pass.
3. THE SYSTEM SHALL send a **private, encouraging** message (DM) telling them
   exactly what to review and inviting a retake.
4. THE SYSTEM SHALL **never** post a non-pass publicly or in any shared channel.

### R8 — Retake policy (anti-brute-force)
**User story:** As the owner, I want retakes to require real review, so students
improve instead of guessing the answers.

Acceptance criteria:
1. THE SYSTEM SHALL allow **retakes** of a not-yet-passed week assessment.
2. THE SYSTEM SHALL require, before a retake: a **cooldown wait** and a prompt to
   **review the missed items** first.
3. THE SYSTEM SHALL **reshuffle / re-draw** items from the pool on each attempt
   so answers can't simply be memorized.
4. THE SYSTEM SHALL record attempts and mark which one achieved the pass.

### R9 — Feedback that teaches
**User story:** As a student, I want to learn from the test itself, so it's
valuable, not just a grade.

Acceptance criteria:
1. AFTER an attempt, THE SYSTEM SHALL show **what was wrong, the correct answer,
   and a one-line explanation**, per item.
2. THE SYSTEM SHALL feed the student's **weak items back into their daily
   practice / SRS queue**, so review happens inside the habit they already have.

### R10 — Owner weekly report
**User story:** As the owner, I want a weekly summary of results, so I can prove
outcomes and know who needs help.

Acceptance criteria:
1. AFTER each week's assessments, THE SYSTEM SHALL give the owner (via Empire
   Ops / an admin surface) a summary: **who passed, who didn't, scores, and the
   most-missed items/skills.**
2. THE SYSTEM SHALL make the report available on demand as well as scheduled.

### R11 — Owner overrides
**User story:** As the owner, I want manual control for edge cases, so I'm the
final authority.

Acceptance criteria:
1. THE SYSTEM SHALL let the owner **mark a week as Mastered** for a student
   manually.
2. THE SYSTEM SHALL let the owner **reset a student's attempt** for a week.

### R12 — Anti-cheat
**User story:** As the owner, I want results to be trustworthy, so "result-driven"
is real.

Acceptance criteria:
1. THE SYSTEM SHALL run the test **timed**, **one item at a time**, with **no
   going back**.
2. THE SYSTEM SHALL draw items from a **pool** so each attempt differs.
3. THE SYSTEM SHALL **disable copy/paste** on input fields and flag/limit
   tab-switching (leaving the page) during a scored attempt.
4. THE SYSTEM SHALL rely on **spoken and written production items** as the
   primary anti-fake signal (a beginner cannot fake live speech).
5. THE SYSTEM SHALL count **one scored attempt at a time**; retakes are clearly
   marked and governed by R8.

### R13 — Fair AI scoring for beginners
**User story:** As a student, I don't want a robot to unfairly fail my real
effort, so scoring must be kind and human-checked when unsure.

Acceptance criteria:
1. THE SYSTEM SHALL score speaking/writing **supportively for beginners** — did
   they genuinely attempt and use the week's target content — not native-level
   grammar perfection.
2. WHEN an AI score is **borderline** (near the pass line), THE SYSTEM SHALL
   **flag it for the owner** rather than auto-deciding.
3. IF the AI scoring service fails, THE SYSTEM SHALL degrade gracefully (accept
   the attempt, defer scoring / flag to owner) and never crash the student's
   experience.

### R14 — Motivation & progression
**User story:** As a student, I want to see my journey and earn lasting
recognition, so I stay driven.

Acceptance criteria:
1. THE SYSTEM SHALL track a **"weeks mastered in a row"** streak.
2. THE SYSTEM SHALL show a **progress map** ("Level 0 — Week 3 of 8 mastered").
3. WHEN a student masters **every week of a level**, THE SYSTEM SHALL issue a
   **shareable level-completion certificate**.
4. THE SYSTEM MAY invite a **top scorer** to record a short teaching clip for the
   champions channel (community/learning bonus).

### R15 — Non-functional
1. THE SYSTEM SHALL not degrade or alter the existing daily-task, streak,
   points, or recording behavior.
2. THE SYSTEM SHALL be bilingual (Arabic primary), mobile-first, and
   Dubai-timezone aware.
3. THE SYSTEM SHALL keep a single week assessment to ~10–15 minutes.
4. THE SYSTEM SHALL be delivered in **owner-merge-gated phases**, each tested and
   live-verified with zero student disruption.


---

## R16 — Mastery-based progression gate (no skipping)
**User story:** As the owner, I want students to move to the next week only
after they **pass** the current week's assessment, so progress reflects real
mastery and nobody skips ahead — our mission is to *push* students to their
goals, not just monitor them.

Acceptance criteria:
1. THE SYSTEM SHALL keep **week 1 always open**, and unlock **week W+1's
   content only after week W's assessment is PASSED (Mastered).**
2. WHILE week W is not passed, THE SYSTEM SHALL keep week W+1 **locked**, with a
   clear Arabic-first message ("pass Week W's test to open Week W+1").
3. THE SYSTEM SHALL preserve the R7/R8 safety valves — **unlimited retakes**
   (with cooldown), **near-miss owner rescue**, and **owner override** — so a
   student is never permanently stuck.
4. THE SYSTEM SHALL **grandfather existing students** on enable: weeks already
   reached under the prior date-based calendar stay open; the gate applies to
   **new** week-openings going forward.
5. THE SYSTEM SHALL make the gate **flag/config-controlled** (toggle
   `itqan_progression_gate`) so it can be turned off instantly.

## R17 — Full status report + due-assessment nudges
**User story:** As the owner, I want to see who has a **due** assessment they
haven't done, and have those students nudged automatically, so I push
completion.

Acceptance criteria:
1. THE SYSTEM SHALL provide an **on-demand full report** (Discord `!itqan-due` +
   Telegram `/itqan-due`) of every student's assessment status: current week,
   days-done, and state (**locked / due / passed / not-yet / flagged**),
   highlighting **DUE = week's days complete but assessment not yet passed.**
2. THE SYSTEM SHALL send a **private Arabic motivational DM** to students with a
   due assessment, **at most once per due week** (no daily nagging).
3. THE SYSTEM SHALL include, in the flagged-attempt owner alert, the **exact
   copy-paste commands for that specific student** (`!` prefix + discord id) and
   make the **`!` vs `/`** distinction clear (`!` = paste-ready, `/` = menu picker).

---

## Amendments (post-pilot, session 33)

These refine earlier requirements from real pilot data (BioRoMa) and are the
current source of truth where they differ:

- **A1 (refines R13.2 flagging):** the system flags an attempt for the owner
  **only when the student did NOT pass** AND a human might fairly change it —
  i.e. an **AI/recording error** or a **near-miss just below** the mastery line.
  A **clear pass is never held for review** (it celebrates immediately). A clear
  not-yet is scored normally (supportive path).
- **A2 (refines R6/R7 + R11 overrides):** an **owner manual pass** (`!itqan-pass`
  / `/itqan-pass`) SHALL notify + celebrate the student **the same as an earned
  pass** — private DM + `🏅 Week Champions` post + level certificate if it
  completes the level. A reset lets them retake.
- **A3 (refines Constraint 6 privacy):** assessment **recordings are RETAINED
  (owner-review only)** for a short window (**default 14 days**) then
  auto-purged (and wiped on reset) — needed so the owner can *listen* during a
  review. Still private; never shown to other students.
- **A4 (refines R3 listening):** the listening item is **dictation** — Kokoro
  says the English word, the student **types the English word they heard** (a
  true listening/spelling check; no fuzzy Arabic-meaning matching).
- **A5 (owner review workbench, extends R10/R11):** `!itqan-review <id>` /
  `/itqan-review` produce a **sectioned coaching brief** (strengths · what went
  wrong · needs attention · what to say to the student, incl. an AI paragraph)
  and **attach the student's audio recordings**.
