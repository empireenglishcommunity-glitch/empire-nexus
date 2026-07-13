# Design — Sahel (سَهل): Practice Platform Evolution

## Architecture: Progressive Enhancement

The platform stays a static site on Cloudflare Pages (free, fast, no
server needed). New interactive features are added via JavaScript that
progressively enhances the static content:

```
Layer 3: Connected (Discord API sync, auth, leaderboard)
Layer 2: Interactive (recorder, quizzes, SRS review, PWA)
Layer 1: Enhanced (animations, gamification, mobile UX)
Layer 0: Current (static HTML, TTS, flashcards) ← keep working
```

Each layer works independently. Layer 0 (current) keeps working even
if JavaScript fails. Layers 1-3 add features on top without breaking
the base.

---

## Component 1 — Pronunciation Recorder (R1)

**Already exists in app.js as `Recorder` class but is never used.**

### Design:
- Wire the existing `Recorder` into accent + shadowing pages
- Add a "🎙️ Record Yourself" button below the model audio
- Show recording timer + waveform (simple CSS animation)
- On stop: show playback button + "Download" link
- A/B comparison: "Listen to Model" next to "Listen to Yours"
- Mobile: uses `getUserMedia` (supported on all modern mobile browsers)

### Implementation:
- Modify `generate.py` to add the recorder UI to accent + shadowing pages
- Add recorder controls CSS to `empire.css`
- Wire `Recorder.start()` / `Recorder.stop()` to the buttons

---

## Component 2 — Interactive Exercises (R2)

### Design per page type:

**Accent drill page (enhanced):**
- Current: listen + read minimal pairs + "say this"
- Add: "Record & Compare" button (record → play side by side with model)

**Vocab page (enhanced):**
- Current: flashcard flip
- Add: "Type the Word" quiz mode (hear Arabic → type English)
- Add: "Listen & Type" mode (hear English pronunciation → type spelling)
- Toggle between flashcard mode and quiz mode

**Listening page (already has MCQ):**
- Current: MCQ with auto-check ✅
- Add: "Dictation mode" — hear a sentence, type what you heard
- Score shown after completion

**Shadowing page (enhanced):**
- Current: listen to passage + read transcript
- Add: "Shadow & Record" — plays model, records you simultaneously
- Playback overlay: hear model in one ear, yours in the other

---

## Component 3 — Connected Progress (R3)

**Requires a lightweight API on the bot server.**

### Design:
- New endpoint: `GET /api/progress/:discord_id` on the bot's container
  (a simple Flask/FastAPI micro-app, or even a raw HTTP handler)
- Returns: level, week, streak, points, tasks_completed_today, srs_stats
- Practice platform calls this on page load (if authenticated)
- Authentication: Discord OAuth2 redirect → store token in localStorage
- Fallback: if not authenticated, platform works normally (just no sync)

### Alternative (simpler, no auth needed):
- A "Connect to Discord" button that asks for their Discord username
- Bot generates a one-time link token: `!link` → bot DMs a URL like
  `practice.empireenglish.online?token=abc123`
- Platform stores the token locally, uses it to fetch progress
- No OAuth2 needed, no server changes beyond one bot command

---

## Component 4 — Mobile-First UX Overhaul (R4)

### Design:
- Touch targets: minimum 48px × 48px (Google's mobile guideline)
- Swipe navigation: swipe left/right between exercises on the same day
- Bottom navigation bar (fixed): accent | shadow | listen | vocab
- Full-width cards on mobile (no side padding waste)
- Audio controls: large play/pause, visible progress bar
- Dark mode (already dark — just ensure OLED-friendly pure black option)

### Implementation:
- CSS media queries + touch event handlers
- Update `empire.css` with mobile breakpoints
- Add swipe library (lightweight: ~2KB vanilla JS)

---

## Component 5 — Daily Pattern Card (R5)

### Design:
- On each day's `index.html`, add a "Today's Pattern" card
- Shows: the phrase, when to use it, example, Arabic meaning
- "Listen" button (TTS speaks the pattern)
- "Record yourself saying it" button (Recorder)
- Pulls from `content/patterns/l0_patterns.json` (already created!)

### Implementation:
- Modify `generate.py` to read patterns and include one per day
- Round-robin through the pattern categories across the week

---

## Component 6 — SRS Review Page (R6)

### Design:
- A standalone `/review` page (new, not per-day)
- Shows 10-20 words due for review (pulled from the bot's API)
- Flashcard interface: word → flip → Arabic meaning
- "I knew it" (quality 4-5) / "I forgot" (quality 1-2) buttons
- Results sent back to the bot's SRS (via the same API from R3)
- Works offline: cache the last-fetched word list in localStorage,
  queue review results, sync when online

### Fallback (if no API connection):
- Shows a general review of this week's vocabulary (from the static
  JSON files already on the site)
- No SRS scheduling, just random sampling from recent weeks

---

## Component 7 — Gamification Display (R7)

### Design:
- A persistent header/banner on every page showing:
  - 🔥 Current streak (from Discord sync or localStorage)
  - ✅ Tasks done today: 2/4
  - 🏆 Total points
- Completing all 4 exercises on a day page triggers a confetti animation
- Weekly progress: a simple 7-day bar chart on the index page

### Implementation:
- `Progress` class already exists in app.js (localStorage-based)
- Enhance it with streak counter and visual celebration
- Confetti: lightweight vanilla JS animation (~1KB)

---

## Component 8 — PWA (R8)

### Design:
- `manifest.json` in site root (app name, icons, theme color)
- Service worker: cache-first for static assets (HTML, CSS, JS, audio)
- "Add to Home Screen" prompt on first visit (mobile)
- Offline indicator: "You're offline — some features limited"

### Implementation:
- `site/manifest.json` with Empire branding
- `site/sw.js` service worker (cache static assets on install)
- Register SW in app.js
- iOS: `<meta name="apple-mobile-web-app-capable" content="yes">`

---

## Implementation Priority

| Phase | Component | Effort | Impact |
|---|---|---|---|
| S0 | Pronunciation Recorder (wire existing code) | Low | High — THE missing piece |
| S1 | Mobile-First UX fixes | Low-Medium | High — 90% of users are mobile |
| S2 | Interactive Exercises (quiz modes) | Medium | High — active > passive |
| S3 | Daily Pattern Card | Low | Medium — Tatawwur on web |
| S4 | PWA (manifest + service worker) | Low | Medium — feels like an app |
| S5 | Gamification Display (streak/points) | Low-Medium | Medium — motivation |
| S6 | Connected Progress (bot API) | Medium-High | High — removes friction |
| S7 | SRS Review Page | Medium | Medium — Tatawwur T2 on web |

---

## Open Design Questions

1. **Connected progress (R3):** OAuth2 vs. bot-generated link token?
   Recommendation: link token (simpler, no OAuth2 complexity, one
   `!link` command generates a personal URL).

2. **Recorder storage:** where do recordings go? Options:
   a) Stay in browser only (download to upload to Discord manually)
   b) Upload to server (needs backend — breaks static-site model)
   Recommendation: (a) for now, with a clear "Upload to Discord" workflow.

3. **PWA offline scope:** cache ALL 1,331 pages or just the current
   week? Recommendation: cache current level + current week (small),
   prefetch next week in background.
