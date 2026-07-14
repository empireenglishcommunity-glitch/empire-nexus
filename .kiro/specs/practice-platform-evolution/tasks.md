# Tasks — Sahel (سَهل): Practice Platform Evolution

> **How to use this file:** same discipline as all other specs — work
> top to bottom, check off tasks. Changes go to empire-dojo repo.

---

## Phase S0 — Pronunciation Recorder (wire existing code)

- [x] **S0.1** Wire the existing `Recorder` class in app.js into the
  accent drill page template in `generate.py`. Add a "🎙️ Record
  Yourself" section below the "Say This" card.
- [x] **S0.2** Add recording UI: record button, timer display, stop
  button, playback button, download link.
- [x] **S0.3** Add A/B comparison UI: "Listen to Model" | "Listen to
  Yours" — two buttons side by side after recording.
- [x] **S0.4** Wire the recorder into the shadowing page too (record
  your shadow attempt).
- [x] **S0.5** Add CSS for recorder controls (waveform animation,
  recording indicator, mobile-friendly button sizes).
- [x] **S0.6** Test on mobile (Android Chrome + iOS Safari).
- [x] **S0.7** Regenerate all pages and deploy.

## Phase S1 — Mobile-First UX Fixes

- [x] **S1.1** Audit all page types on a real phone screen (360px wide).
  Fix any overflow, tiny buttons, or unreadable text.
- [x] **S1.2** Add swipe navigation between exercise pages on the same
  day (accent ← → shadowing ← → listening ← → vocab).
- [x] **S1.3** Bottom fixed navigation bar on mobile: 4 exercise icons.
- [x] **S1.4** Increase all button sizes to 48px+ touch targets.
- [x] **S1.5** Optimize audio controls for mobile (larger, more visible).

## Phase S2 — Interactive Exercises

- [x] **S2.1** Vocab page: add "Quiz Mode" toggle (hear Arabic → type
  English word). Show score after all words attempted.
- [x] **S2.2** Vocab page: add "Listen & Type" mode (hear English
  pronunciation → type the word).
- [x] **S2.3** Listening page: add "Dictation" mode (hear sentence →
  type what you heard → compare to transcript).
- [x] **S2.4** Accent page: wired recorder (done in S0) + scoring
  comparison display.
- [x] **S2.5** Shadowing page: "Shadow & Record" mode — plays model
  audio while recording you simultaneously.

## Phase S3 — Daily Pattern Card

- [x] **S3.1** Update `generate.py` to read from
  `content/patterns/l0_patterns.json` and include one pattern per day
  (round-robin through categories across the 7-day week).
- [x] **S3.2** Add "Today's Pattern" card to each day's `index.html`:
  phrase + when to use + Arabic meaning + "Listen" + "Record yourself".
- [x] **S3.3** Regenerate all pages.

## Phase S4 — PWA (Progressive Web App)

- [x] **S4.1** Create `site/manifest.json` (app name: "Empire English",
  theme: gold/black, icons from existing logo).
- [x] **S4.2** Create `site/sw.js` service worker: cache-first strategy
  for static assets (HTML, CSS, JS, audio). Cache only current level/week.
- [x] **S4.3** Register service worker in app.js.
- [x] **S4.4** Add iOS meta tags for "Add to Home Screen".
- [x] **S4.5** Add offline fallback page ("You're offline — here's
  what's cached").
- [x] **S4.6** Deploy and test PWA install on Android + iOS.

## Phase S5 — Gamification Display

- [x] **S5.1** Add a persistent top bar showing: streak 🔥, tasks done
  today ✅, progress bar for the day.
- [x] **S5.2** Completing all 4 exercises on a day triggers a confetti
  animation + "🎉 أحسنت!" message.
- [x] **S5.3** Weekly progress view on the main index page (7-day bar
  chart showing completion per day).
- [x] **S5.4** Store and display streak locally (increment on daily
  completion, reset on missed day).

## Phase S6 — Connected Progress (bot API)

- [x] **S6.1** Add `!link` command to the Discord bot: generates a
  personal URL token (e.g. `?token=abc123`) and DMs it to the user.
- [x] **S6.2** Add a minimal API endpoint to the bot container:
  `GET /api/progress?token=<token>` → returns JSON (level, streak,
  points, tasks_today, srs_due).
- [x] **S6.3** Practice platform: on page load, check localStorage for
  token. If present, fetch progress from API and display in header.
- [x] **S6.4** "Connect to Discord" button on the platform (shows
  instructions: type !link in Discord, paste your personal URL here).

## Phase S7 — SRS Review Page

- [x] **S7.1** Create `/review/index.html` — standalone page for
  vocabulary review.
- [x] **S7.2** If connected (token exists): fetch due words from bot
  API, show as flashcards with "I knew it" / "I forgot" buttons, send
  results back to API.
- [x] **S7.3** If not connected: show a random sample from this week's
  vocabulary (from static JSON files). No SRS scheduling, just practice.
- [x] **S7.4** Queue review results in localStorage if offline, sync
  when connection returns.

---

## Cross-phase notes

- **All changes go to the `empire-dojo` repo** (not empire-nexus).
- **Regeneration required** after S0, S2, S3, S5 — run `generate.py`.
- **S6 requires a bot-side change** (the `!link` command + API endpoint
  in empire-nexus's discord-learning-bot).
- **Cloudflare Pages preview URLs** — use for every PR (per Aegis Phase 4's
  preview-URL discipline).
- **dojo-verify.yml** CI workflow will automatically run on PRs touching
  scripts/ or site/.
