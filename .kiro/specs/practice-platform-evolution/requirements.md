# Requirements — Sahel (سَهل): Practice Platform Evolution

> **Codename:** Sahel (سَهل — "Easy/Smooth") — because the platform
> should make practice feel effortless, not like homework.
> **Purpose:** Transform the static practice platform from a passive
> content viewer into an interactive, connected, mobile-first practice
> engine that students actually WANT to open every day.
> **Context:** The platform currently has 1,331 HTML pages with audio +
> flashcards, but zero interactivity beyond listening and flipping cards.
> The Recorder class exists in app.js but isn't wired into any page.
> Progress is localStorage only (lost when browser clears). No connection
> to the Discord bot's data. No recording, no feedback, no exercises.

---

## Core Principle

**Practice should feel like a game, not a textbook.**

Every enhancement exists to make the daily 10-minute practice session
so engaging that students open the platform BEFORE the bot even reminds
them — because it feels good to use, gives instant feedback, and shows
them getting better in real time.

---

## Requirements

### R1 — Interactive Pronunciation Recorder
Students MUST be able to record themselves on the practice page and
hear the playback immediately. Acceptance criteria:
- Accent drill page has a "Record Yourself" button
- Recording plays back alongside the model audio (compare)
- Recording can be downloaded (for uploading to Discord #showcase)
- Works on mobile (Android Chrome, iOS Safari)
- Visual waveform/timer during recording

### R2 — Interactive Exercises (not just passive listening)
Each exercise page MUST have at least one ACTIVE exercise, not just
"listen and read." Acceptance criteria:
- Accent: record + compare to model (side by side)
- Vocab: type-the-word quiz (not just flip cards) + listen-and-type
- Listening: real MCQ with auto-checking (already exists partially)
- Shadowing: record your shadow attempt + playback overlay
- Writing: text input with word count + basic grammar hints

### R3 — Connected Progress (sync with Discord bot)
Practice platform progress SHOULD sync with the Discord bot so
students don't have to do the same work twice. Acceptance criteria:
- An API endpoint on the bot reports the member's progress
- The practice platform shows their Discord streak/points/level
- Completing a practice page auto-confirms the task (or at minimum,
  shows them the !done command to run)
- Authentication: Discord OAuth2 (lightweight, uses existing token)

### R4 — Mobile-First Experience
The platform MUST work beautifully on mobile phones (90%+ of Arab
students use phones as primary device). Acceptance criteria:
- Touch-optimized: large buttons, swipe navigation
- No horizontal scroll on any screen size
- Audio controls work without tiny buttons
- Recording works on mobile browsers
- Page loads under 2 seconds on 3G

### R5 — Daily Pattern Practice (Tatawwur T1 on web)
The daily conversational pattern from Tatawwur MUST be displayed and
practicable on the web platform. Acceptance criteria:
- "Today's Pattern" card on the day page
- Listen to native pronunciation of the pattern
- Record yourself saying it
- See when/how to use it (with Arabic explanation)

### R6 — Spaced Repetition Review Page (Tatawwur T2 on web)
Students MUST be able to review their SRS words on the web (not just
via the Discord quiz). Acceptance criteria:
- A "/review" page showing due words
- Flashcard + audio + "I know it" / "I forgot" buttons
- Syncs with the bot's vocab_srs table
- Works offline (PWA-like: cached words, sync when online)

### R7 — Gamification & Streak Display
Students MUST see their progress/streak/points ON the practice page
(not just in Discord). Acceptance criteria:
- Header shows: current streak, today's tasks done, total points
- Completing all exercises for a day shows a celebration animation
- Weekly progress chart (simple bar graph)

### R8 — Performance & PWA
The platform MUST feel app-like on mobile. Acceptance criteria:
- Installable as PWA (Add to Home Screen)
- Service worker caches pages for offline access
- Manifest.json with Empire branding
- Loads instantly after first visit (no network wait)

---

## Constraints

- Same $7/month Hetzner VPS — static site on Cloudflare Pages (free)
- No backend server for the practice platform itself (stays static)
- Syncing with Discord bot (R3, R6) requires a lightweight API — this
  can be a single endpoint on the existing bot's Docker container
- PWA + Service Worker = zero additional cost
- Must not break existing page structure (extensionless URLs, same
  directory layout)
- Must work without JavaScript for basic content viewing (progressive
  enhancement — recordings and sync need JS, but reading doesn't)

---

## Out of Scope (for now)

- Video content (too heavy for the VPS bandwidth)
- Live tutoring on the platform (stays in Discord voice)
- Payment/subscription features (deferred until revenue justifies)
- AI-generated personalized exercises per student (keep it curated)
