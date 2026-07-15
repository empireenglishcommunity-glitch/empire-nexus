# Tasks — Wuslah (وُصلة): Ecosystem Harmony

## Phase W0 — Expanded Student API ✅ COMPLETE

- [x] **W0.1** Add `/api/dashboard` endpoint — aggregates: streak,
  level, total_points, leaderboard_rank, pronunciation (14d scores,
  average, trend), milestones, assessments, difficulty_level,
  srs stats, week_activity (7d grid), level_progress, voice_portfolio
  (last 5). Single response, one DB query batch.
  → Implemented in `api_server.py`. Returns 17 fields covering the
  full student data picture in a single API call. Verified live with
  a seeded test DB: all fields populated correctly.
- [x] **W0.2** Add `/api/leaderboard` endpoint — top 10 by points +
  requester's own rank/points.
  → Returns `top[]`, `your_rank`, `your_points`, `your_name`. Rank
  computed via a single COUNT query with a WHERE clause.
- [x] **W0.3** Add rate limiting middleware (60 req/min per token,
  in-memory counter, 429 on excess).
  → Sliding-window counter per token. Applied to ALL endpoints (both
  new and existing). Request 61 within 60 seconds correctly returns
  HTTP 429. Verified via automated burst test.
- [x] **W0.4** Add token expiry cleanup — background task removes
  tokens with no API usage in 30 days.
  → New `last_used` column on `link_tokens` (with migration for
  existing DBs). `cleanup_expired_tokens()` function removes tokens
  where `last_used < 30 days ago` (or `created_at` if never used).
  Called daily from the `markaz_daily_digest` loop. Verified: correctly
  removes only expired tokens, keeps fresh ones.
- [x] **W0.5** Add `wuslah_dashboard_api` feature flag, gate all new
  endpoints behind it.
  → New flag in registry (initiative: WUSLAH 🔗, default ON). Both
  `/api/dashboard` and `/api/leaderboard` return 503 when flag is OFF.
- [x] **W0.6** Test: verify /api/dashboard returns correct data for a
  real student with history.
  → Full integration test using `aiohttp.test_utils.TestClient`:
  dashboard returns correct streak/level/pronunciation/SRS/difficulty,
  leaderboard returns correct rank, rate limit triggers at 61 requests,
  token expiry removes the right tokens.

## Phase W1 — Student Dashboard Page

- [ ] **W1.1** Create `/dash/index.html` in empire-dojo with skeleton
  loading UI (dark theme, Arabic/English bilingual).
- [ ] **W1.2** Implement dashboard JS — fetch /api/dashboard on load,
  render all sections (streak, level progress bar, week activity grid,
  pronunciation trend chart via CSS bars, milestones, SRS stats,
  leaderboard, Nour tips).
- [ ] **W1.3** Add graceful fallback states — "Connect Discord" if no
  token, "Loading..." skeleton, "Offline" if API unreachable.
- [ ] **W1.4** Add "🔗 Connect" flow (same token-paste pattern as
  /review page) if not already linked.
- [ ] **W1.5** Mobile-first CSS — touch targets ≥48px, no horizontal
  scroll, OLED-friendly dark, fast animations.
- [ ] **W1.6** Link dashboard from the practice platform's main page
  (navigation: "📊 My Dashboard" button/link).
- [ ] **W1.7** Deploy to Cloudflare Pages, verify end-to-end with a
  real linked student.

## Phase W2 — Cross-Platform Task Confirmation

- [ ] **W2.1** Add `POST /api/complete-exercise` endpoint — writes to
  daily_submissions (INSERT OR IGNORE for idempotency), updates streak,
  awards points exactly like `!done` does.
- [ ] **W2.2** Add `wuslah_exercise_confirm` feature flag, gate
  endpoint behind it.
- [ ] **W2.3** Update practice platform exercise pages — after
  completing all steps of an exercise, call the API to mark done.
- [ ] **W2.4** Show web-side confirmation UI: "✅ Marked in Discord!"
  with confetti if all 7 tasks done for the day.
- [ ] **W2.5** (Optional) Bot sends congratulatory DM on web-based
  completion if `nabd_celebrations` is enabled.
- [ ] **W2.6** Verify: completing on web + running `!done` on Discord
  for the same task does NOT double-count points.

## Phase W3 — Adaptive Practice

- [ ] **W3.1** Expand `/api/progress` response to include:
  `difficulty_level`, `weak_phonemes[]`, `days_since_active`,
  `recommended_exercise`.
- [ ] **W3.2** Add welcome-back banner logic in app.js: if
  `days_since_active >= 2`, show a motivational message with a
  suggested easy exercise.
- [ ] **W3.3** Add "focus area" highlight on practice pages: if a
  specific phoneme is weak, highlight that day's accent drill.
- [ ] **W3.4** Add difficulty-appropriate content filtering: show
  exercises matched to the student's Dhaka' difficulty level, dim
  or collapse others.
- [ ] **W3.5** Add SRS-due prompt on non-review pages: "You have X
  cards due → Review now" floating banner if due_count > 5.

## Phase W4 — Nour Study Tips Engine

- [ ] **W4.1** Create `nour_study_tips` table in database.py schema.
- [ ] **W4.2** Implement weekly tip generation task (Sunday 8 AM
  Dubai, before weekly report). Input: pronunciation scores, SRS
  accuracy, streak patterns, difficulty level, Nour conversation
  themes. Output: 3 actionable tips per student (max 100 chars each).
- [ ] **W4.3** Add `/api/nour-tips` endpoint (reads cached tips from
  DB, fallback to generic tips if none generated).
- [ ] **W4.4** Render "Nour's Study Tips" card on the dashboard —
  3 bullet points, refreshed weekly.
- [ ] **W4.5** Add `wuslah_nour_tips` feature flag.
- [ ] **W4.6** Add generic tip bank (level-appropriate fallback tips
  for when AI generation fails or student has no history).

## Phase W5 — Notification Unification

- [ ] **W5.1** Add `/api/notifications` GET endpoint — returns current
  notification preferences for the linked student.
- [ ] **W5.2** Add `/api/notifications` POST endpoint — updates
  preferences (same validation as the Discord `!notifications` command).
- [ ] **W5.3** Update Nabd morning kickstart DM to include SRS due
  count: "📝 You have X cards due on the web."
- [ ] **W5.4** Update Nabd weekly summary to include web practice
  stats alongside Discord stats.
- [ ] **W5.5** Add notification badge on the dashboard SRS section
  when cards are due.
- [ ] **W5.6** Add "Notification Settings" section on the dashboard
  with toggle switches (calls POST /api/notifications).
