# Design — Hisn (حِصن): Full Ecosystem Verification

## Testing Architecture: 4-Layer Defense

```
Layer 4: HUMAN JUDGMENT      ← "does this feel right?" (owner walkthrough)
Layer 3: MULTI-STUDENT SIM   ← concurrent load, real timing, real race conditions
Layer 2: INTEGRATION TRACE   ← cross-system flows, end-to-end data consistency
Layer 1: EXHAUSTIVE SCRIPTED ← every command, every flag, every endpoint, every page
```

Each layer catches what the layer below it cannot:
- **Layer 1** catches: crashes, wrong output, broken links, missing
  validation — the "does it even run" tier. Fully automatable, fully
  exhaustive (every single item, no sampling).
- **Layer 2** catches: data inconsistency between systems — the kind of
  bug where each system individually "works" but together they lie to
  each other (e.g., web says done, Discord says not done).
- **Layer 3** catches: timing/concurrency bugs that only appear with
  multiple simultaneous actors — the exact scenario of 16 students
  joining and submitting at once on day 1.
- **Layer 4** catches: things that are technically correct but
  practically bad — confusing wording, bad pacing, a "helpful" AI that
  actually annoys people. No script catches this. Only a human can.

---

## Component 1 — The Ghost Server (Isolated Test Environment)

**Reuses and extends the existing Ghost Testing category concept.**

### Design:
- All Discord-side testing happens using the **Ghost Testing category**
  channels already provisioned by `setup_server.py`, plus 2-3 disposable
  test Discord accounts (or the owner's own alt account) acting as
  "students"
- Database testing uses a **snapshot clone** of the real production
  SQLite file (copied, not touched live) for anything destructive or
  concurrent — R10's load simulation runs against this clone, not the
  live DB
- Non-destructive tests (command responses, flag toggles that don't
  mutate shared state, API GETs) can run directly against production
  since they're naturally safe and this proves the REAL system works,
  not a copy of it
- A clear tagging convention marks test-created data
  (`discord_name LIKE 'GHOST_TEST_%'`) so cleanup is a single verified
  SQL statement, not manual hunting

---

## Component 2 — The Master Test Matrix (Layer 1)

**A single spreadsheet-style checklist, generated FROM the codebase, not
hand-typed from memory** — this is critical: hand-typed lists silently
drop items. Instead:

### Design:
- A generator script scans the actual source for ground truth:
  - `grep '@bot.command' bot.py` → command list (39 found)
  - `flag_registry.REGISTRY` → flag list (38 found)
  - `setup_server.py`'s `CATEGORIES_CONFIG` → channel list (~55 found)
  - `find site/ -name '*.html'` → page list (1,334 found)
  - `grep '@routes.' api_server.py` → endpoint list (11 found)
- This generator produces `test_matrix.md` — one row per item, columns:
  `[item, category, test_status, tester, notes, defect_id]`
- Re-running the generator after this spec is written becomes the
  actual audit tool — if someone adds a 40th command later without
  updating the matrix, the generator diff catches it immediately

### Execution:
- **Commands (39)**: a semi-automated Discord test harness (via
  discord.py-self or a second bot account acting as a human) sends
  each command with 4 input variants (none/valid/invalid/oversized)
  and captures the response for review. Where full automation isn't
  worth building, the owner runs it manually against the checklist —
  either way, EVERY row gets a checkmark, not a sample.
- **Flags (38)**: automated script that iterates the registry, calls
  `!flag enable <name>` / `!flag disable <name>` via the test harness,
  and confirms via `!flag list` that the state actually changed.
- **Channels (~55)**: automated via a script using the bot's own
  Discord API access — checks each channel's `permissions_for()`
  against expected role/category rules, flags any mismatch.
- **Web pages (1,334)**: automated crawler (headless browser via
  Playwright or a simple `curl` + HTML parse sweep) hits every URL,
  checks for: HTTP 200, no missing audio `src`, no broken internal
  `<a href>`, presence of expected exercise markup. Runs in minutes,
  not days — this is exactly the kind of exhaustive-but-mechanical
  check that must never be "sampled" because a script makes 100%
  coverage free.
- **API endpoints (11)**: automated test script (reusing patterns from
  the aiohttp TestClient tests already written during Wuslah
  development) hits every endpoint with the input matrix from R5.

---

## Component 3 — Integration Traces (Layer 2)

**5 specific end-to-end scenarios, each traced with real timestamps
and real data, not just "should work in theory."**

1. **Web → Discord**: complete an exercise on `/dash/`-adjacent practice
   page → confirm `daily_submissions` row appears → confirm Discord
   `!progress` reflects it → confirm dashboard re-fetch shows it →
   confirm NO duplicate if `!done` is also run for the same task
2. **Discord → Telegram → Discord**: trigger a Nour escalation → confirm
   Telegram alert arrives with correct student context → reply in
   Telegram → confirm student receives the DM "from Nour" → confirm
   escalation marked resolved in DB
3. **`!link` → Web**: run `!link` → confirm token generated → paste into
   `/dash/` → confirm dashboard shows THIS student's real data (not
   cached/wrong data) → confirm token `last_used` updates
4. **Web notification prefs → Discord**: change a preference via
   `/api/notifications` → confirm next scheduled DM respects it (or
   simulate the DM-send function directly with the updated prefs to
   avoid waiting for the real schedule)
5. **Markaz visibility**: trigger any of the 5 Markaz-tracked events
   (new escalation, streak milestone, churn risk, Groq failure,
   restart) → confirm the owner's Telegram receives correct, timely,
   correctly-formatted (MarkdownV2-safe) notice

---

## Component 4 — Multi-Student Load Simulation (Layer 3)

### Design:
- A Python script (`stress_test.py`, temporary, deleted after use —
  or kept in a `tests/` dir behind a "manual run only" marker) that:
  - Creates N synthetic member rows (N=20, more than the real 16, for
    headroom) directly in the DB clone
  - Fires concurrent `asyncio` tasks simulating: simultaneous `!join`,
    simultaneous `!done` for the same task/date, simultaneous
    `/api/dashboard` fetches, simultaneous SRS reviews
  - Asserts afterward: no duplicate `daily_submissions` rows, streak/
    points values are internally consistent (a member's `total_points`
    equals the SUM of their `points_log` — this specific invariant
    check catches the exact class of race condition fixed earlier in
    `update_streak()`), leaderboard ranks are stable and correct
- Run against the DB CLONE, not production — this is explicitly a
  destructive/concurrent test per Component 1's rules

---

## Component 5 — AI Fallback Chain Verification (R7)

### Design:
- A dedicated test script temporarily overrides `config.GROQ_API_KEY`
  and `config.GEMINI_API_KEY` (via environment override in a test run,
  never editing the real `.env`) to simulate each failure point:
  1. Groq valid, Gemini valid → confirm Groq used (primary)
  2. Groq invalid, Gemini valid → confirm Gemini used, confirm
     `track_groq_failure()` fires (Markaz M5.2 hook)
  3. Both invalid → confirm template/generic fallback used, confirm
     the user-facing response is still coherent (not an error message
     leaking to the student)
- Same 3-state matrix applied to: Nour concierge responses, pronunciation
  scoring (Groq Whisper), Nour study tips generation, weekly self-review

---

## Component 6 — Notification Timing & Content Audit (R8)

### Design:
- Rather than waiting for real clock times (6:05 AM, 9 PM, Sunday, 1st
  of month — impractical to wait for all of these), each notification
  function is called DIRECTLY (bypassing the `@tasks.loop` scheduler)
  against a test member, with output captured and manually reviewed
  against a content checklist: grammar, Arabic/English mix correctness,
  no unrendered template variables, length limits
- Timing correctness (the scheduler itself) is verified separately and
  more simply: confirm each `@tasks.loop(time=...)` decorator's
  configured hour/minute matches the documented schedule — a static
  check, not a live wait-and-see

---

## Component 7 — Defect Log & Go/No-Go Gate

### Design:
- A single `defect_log.md` in the spec folder, format:
  `| ID | Severity | Component | Description | Status | Fix PR |`
- Severities: **Blocker** (breaks core flow, must fix before launch),
  **Major** (works but wrong/confusing, must fix before launch),
  **Minor** (cosmetic/edge-case, can defer with owner's explicit OK),
  **Info** (observation, no action needed)
- Final phase produces a **Go/No-Go Checklist** — one line per
  requirement (R1-R11), each marked ✅ Verified / ⚠️ Deferred (with
  reason) / ❌ Blocked — reviewed explicitly with the owner before ANY
  invitation is sent. This is the literal final gate.

---

## Implementation Priority (Phases)

| Phase | What | Effort | Why this order |
|---|---|---|---|
| **H0** | Test matrix generator + Ghost environment setup + DB backup/clone | Low | Nothing else can start safely without this |
| **H1** | Exhaustive scripted testing — commands, flags, channels (Layer 1, Discord) | High | Highest item count, most automatable |
| **H2** | Exhaustive scripted testing — web pages, API endpoints (Layer 1, Web) | Medium | Fully automatable, fast once built |
| **H3** | Integration traces (Layer 2) | Medium | Depends on H1+H2 passing individually first |
| **H4** | AI fallback chain + notification content audit | Low-Medium | Independent, can run parallel to H3 |
| **H5** | Multi-student load simulation (Layer 3) | Medium | Needs the DB clone from H0, runs last among automated work |
| **H6** | Human experience walkthrough (Layer 4) | Medium (owner's time) | Must come after H1-H5 so the system is already stable when judged |
| **H7** | Defect resolution + re-test + Go/No-Go sign-off | Variable | Final gate, depends on everything above |

Each phase produces evidence (logs, screenshots, defect entries) that
feeds the final Go/No-Go checklist in H7. No phase is "done" until its
row in the test matrix is 100% checked — partial completion is
explicitly not acceptable per R1-R6's "every single item" requirement.
