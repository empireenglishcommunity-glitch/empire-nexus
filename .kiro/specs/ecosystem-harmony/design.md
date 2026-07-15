# Design — Wuslah (وُصلة): Ecosystem Harmony

## Architecture: Hub-and-Spoke Data Flow

```
                    ┌──────────────────┐
                    │   SQLite DB      │
                    │  (20+ tables)    │
                    │  Single source   │
                    │  of truth        │
                    └──────┬───────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
    ┌─────────▼──┐  ┌─────▼─────┐  ┌──▼──────────┐
    │  Discord   │  │  HTTP API │  │  Telegram   │
    │  Bot       │  │  (port    │  │  Ops Bot    │
    │  (write +  │  │   8099)   │  │  (Markaz)   │
    │   read)    │  │  (read +  │  │  (read)     │
    │            │  │   write)  │  │             │
    └────────────┘  └─────┬─────┘  └─────────────┘
                          │
              ┌───────────┼───────────┐
              │                       │
    ┌─────────▼──────────┐  ┌────────▼────────┐
    │  Practice Platform │  │  Student        │
    │  (Cloudflare Pages)│  │  Dashboard      │
    │  - exercises       │  │  (new /dash)    │
    │  - SRS review      │  │  - progress     │
    │  - pronunciation   │  │  - milestones   │
    │  - gamification    │  │  - Nour tips    │
    └────────────────────┘  └─────────────────┘
```

The database is the single source of truth. The API is the **only**
bridge between the web-side (Cloudflare Pages, static JS) and the
server-side (bot + DB). The web never talks to the DB directly —
everything flows through the API. This means:
- Security is enforced in one place (the API layer)
- The web platform stays fully static (free Cloudflare hosting)
- New data exposure = new API endpoint, not new architecture

---

## Component 1 — Expanded API (R1, R7)

### Current state (2 endpoints):
```
GET  /api/progress?token=<token>  → streak, level, tasks_today, srs_words, pronunciation
POST /api/srs-review              → record SRS review result
```

### New endpoints to add:

```
GET  /api/dashboard?token=<token>
  → Full dashboard payload (one call, aggregated):
    {
      streak, level, total_points, leaderboard_rank,
      pronunciation: { scores_14d: [...], average, trend },
      milestones: [ { id, name, completed_at } ],
      assessments: [ { week, overall_score, date } ],
      difficulty_level: 1-5,
      nour_tips: ["tip1", "tip2", "tip3"],
      srs: { due_count, mastered_count, accuracy_pct },
      week_activity: { "Mon": {accent:true, vocab:false, ...}, ... },
      level_progress: { current_xp, needed_for_next, pct },
      voice_portfolio: [ { date, type, score, url } ]  // last 5
    }

GET  /api/leaderboard?token=<token>
  → Top 10 + requester's position:
    { top: [...], your_rank: N, your_points: N }

GET  /api/nour-tips?token=<token>
  → AI-generated study tips (cached, refreshed weekly):
    { tips: ["...", "...", "..."], generated_at: "..." }

POST /api/complete-exercise
  → Record a web-based exercise completion:
    { token, level, week, day, exercise_type }
    → writes to daily_submissions, returns { ok, tasks_today }

GET  /api/notifications?token=<token>
  → Current notification preferences
POST /api/notifications
  → Update notification preferences from the web
```

### Design decisions:
- **One big `/api/dashboard` call** rather than 10 small ones — reduces
  round-trips for the mobile-first reality (high latency, limited
  bandwidth). The dashboard page makes ONE fetch on load.
- **Nour tips are pre-generated and cached** (not computed on every
  API call) — a weekly background task generates personalized tips for
  each active student, stores them in a new `nour_study_tips` table.
  The API just reads the cached result. Zero latency, zero AI cost
  per page load.
- **Exercise completion writes directly to `daily_submissions`** using
  the same format as `!done` — the streak engine, points, celebrations
  all fire exactly as if the student ran the command on Discord.
- **Rate limiting via a simple in-memory counter** per token (same
  pattern as Markaz's Groq failure throttle). No Redis needed.

---

## Component 2 — Student Dashboard Page (R2, R5)

### Location: `/dash/` on the practice platform (empire-dojo)

A new page in the static site that fetches `/api/dashboard` on load
and renders a rich, mobile-first progress view. Key sections:

```
┌─────────────────────────────────────┐
│  🔥 14-day streak    Level L1       │
│  ████████████░░░ 72% to L2          │
├─────────────────────────────────────┤
│  📊 This Week                       │
│  [Mon][Tue][Wed][Thu][Fri][Sat][Sun]│
│   ✅   ✅   ✅   ◻️   ◻️   ◻️   ◻️  │
│  4/7 days active                    │
├─────────────────────────────────────┤
│  🎯 Pronunciation Trend (14d)      │
│  ▁▂▃▄▅▆▇█▇▆▇█▇█  avg: 78%  ↑     │
├─────────────────────────────────────┤
│  🏆 Milestones (3/12 unlocked)     │
│  ✅ First Recording ✅ 7-Day Streak │
│  ✅ First Assessment  🔒 L1 Reached │
├─────────────────────────────────────┤
│  💬 Nour's Study Tips              │
│  • Your 'th' sound is improving    │
│  • Review "would/could" this week  │
│  • Try shadowing at 0.75x speed    │
├─────────────────────────────────────┤
│  📝 SRS Review: 12 cards due       │
│  [Review Now →]                     │
├─────────────────────────────────────┤
│  🏅 Leaderboard: You are #3        │
│  1. Ahmed - 2400 pts               │
│  2. Sara - 2100 pts                │
│  3. YOU - 1800 pts ← 🌟            │
└─────────────────────────────────────┘
```

### Technical:
- Pure HTML + CSS + vanilla JS (no framework — matches rest of site)
- Single `fetch('/api/dashboard?token=...')` on page load
- Skeleton loading states while fetch completes
- Graceful fallback if API is unreachable: "Connect your Discord account"
- Charts rendered with pure CSS (bar heights as percentages) — no
  Chart.js or heavy library needed
- Dark theme (matches existing empire-dojo design)
- Arabic/English bilingual labels (same pattern as other pages)

---

## Component 3 — Adaptive Practice (R3)

The existing practice pages already have the infrastructure
(`ConnectedProgress` class, link tokens, API calls). Adaptive behavior
adds intelligence on top:

### When the student loads a practice page:
1. `ConnectedProgress._fetchProgress()` already runs on load
2. **New:** response now includes `difficulty_level` and `weak_phonemes`
3. JavaScript uses these to:
   - Highlight "recommended" exercises (green border)
   - Show a "focus area" banner: "Nour noticed your 'v/f' distinction
     needs practice — try today's accent drill"
   - Hide exercises above the student's level (unless they toggle
     "show all")
   - Surface SRS-due words as a "quick review" prompt

### Welcome-back banner (2+ days absent):
- API returns `days_since_active` in the progress response
- If ≥ 2: show a motivational banner with a suggested easy-start
  exercise (lowest-effort task type from their history)

---

## Component 4 — Cross-Platform Task Confirmation (R4)

### Flow:
1. Student completes all exercises on a web practice page
2. JavaScript calls `POST /api/complete-exercise` with:
   `{ token, level: "L0", week: 1, day: 3, exercise_type: "accent" }`
3. API writes to `daily_submissions` exactly as `!done accent` would
4. API returns `{ ok: true, tasks_today: 5, streak: 14 }`
5. Web shows a celebration ("✅ Marked as done!")
6. Bot (async, non-blocking): optionally sends a congratulatory DM
   if `nabd_celebrations` flag is enabled

### Important constraint:
- A web completion and a Discord `!done` for the same task on the same
  day MUST NOT double-count (the UNIQUE constraint on
  `daily_submissions(discord_id, date, task_id)` already handles this
  at the DB level — INSERT OR IGNORE)

---

## Component 5 — Nour Study Tips Engine (R5)

### Pre-generation approach:
- A new background task runs weekly (Sunday 8 AM, before the weekly
  report at 9 AM) that generates 3 personalized tips per active student
- Input to AI: last 7 days of pronunciation scores, weak phonemes,
  SRS accuracy, streak pattern, difficulty level, recent Nour
  conversation themes
- Output: 3 short, actionable tips (max 100 chars each)
- Stored in a new `nour_study_tips` table:
  `(discord_id, tip_text, generated_at, week)`
- The `/api/dashboard` endpoint simply reads the latest cached tips
- Zero AI calls per page load — all intelligence is pre-computed

### Fallback (no AI key / generation failed):
- Return generic level-appropriate tips from a static bank
- Never show "no tips available" — always have something useful

---

## Component 6 — Notification Unification (R6)

### Changes:
- Morning kickstart DM (Nabd N1) adds: "📝 You have X SRS cards due
  on the web" if `srs_due_count > 0`
- Weekly summary DM adds web practice stats: "You also practiced X
  times on the web this week"
- `/api/notifications` GET/POST lets the web dashboard show/edit
  notification preferences (same settings as `!notifications`)
- Web dashboard shows a notification badge on the SRS section when
  cards are due

---

## Implementation Priority (Phases)

| Phase | What | Effort | Impact |
|---|---|---|---|
| **W0** | Expanded API (`/api/dashboard`, `/api/leaderboard`) | Medium | High — unlocks everything else |
| **W1** | Student Dashboard page (`/dash/`) | Medium | High — the flagship deliverable |
| **W2** | Cross-platform task confirmation | Medium | High — removes `!done` friction |
| **W3** | Adaptive practice (difficulty-aware, welcome-back) | Low-Med | Medium — makes web feel smart |
| **W4** | Nour study tips engine (weekly pre-generation) | Medium | Medium — personalization shine |
| **W5** | Notification unification + web preferences | Low | Medium — ecosystem coherence |

Each phase is independently deployable and valuable. No phase depends
on a later one (W1 works without W4, W2 works without W3, etc.).

---

## New Database Tables

```sql
-- Nour study tips (pre-generated weekly, served via API)
CREATE TABLE IF NOT EXISTS nour_study_tips (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id      TEXT NOT NULL,
    tip_text        TEXT NOT NULL,
    generated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    week            INTEGER NOT NULL,
    FOREIGN KEY (discord_id) REFERENCES members(discord_id)
);
CREATE INDEX IF NOT EXISTS idx_nour_tips ON nour_study_tips(discord_id, week);
```

No other new tables needed — all other data already exists in
existing tables. The expanded API is purely a read layer over
existing data.

---

## Feature Flags

| Flag | Description | Default |
|---|---|---|
| `wuslah_dashboard_api` | Enable expanded /api/dashboard endpoint | ON |
| `wuslah_exercise_confirm` | Enable web-to-Discord task confirmation | ON |
| `wuslah_nour_tips` | Enable AI-generated weekly study tips | ON |
| `wuslah_adaptive` | Enable adaptive practice recommendations | ON |

---

## Security Model

- **Authentication:** same link-token system (generated via `!link`,
  stored in `link_tokens` table, looked up server-side)
- **Authorization:** a token can ONLY access its own student's data
  (no cross-student data leakage)
- **Token expiry:** tokens auto-expire after 30 days of no API usage
  (a background cleanup task, not a hard DB TTL)
- **Rate limiting:** 60 req/min per token, 429 on excess
- **CORS:** only `practice.empireenglish.online` origin allowed
  (configurable via env var for local dev)
