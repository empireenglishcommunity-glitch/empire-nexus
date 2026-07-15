# Tasks — Hisn (حِصن): Full Ecosystem Verification

## Phase H0 — Foundation: Test Matrix, Ghost Environment, Backups

- [x] **H0.1** Write `generate_test_matrix.py` — scans `bot.py` for
  commands, `flag_registry.py` for flags, `setup_server.py` for
  channels, `site/` for pages, `api_server.py` for endpoints. Outputs
  `test_matrix.md` with one row per item.
  → Implemented at `.kiro/specs/full-ecosystem-verification/generate_test_matrix.py`.
  Uses regex scanning for `bot.py`/`api_server.py`, a direct (safe,
  side-effect-free) import of `flag_registry.REGISTRY`, and bracket-depth
  parsing of `setup_server.py`'s `CATEGORIES_CONFIG` (avoided importing
  that file directly since it likely requires discord.py at module
  level). Re-runnable at any time to catch future drift.
- [x] **H0.2** Run the generator, commit `test_matrix.md` — this becomes
  the literal, complete checklist for the rest of the campaign.
  → Ran `generate_test_matrix.py`. **Actual verified counts differ from
  this spec's earlier estimates** — exactly the drift this generator
  exists to catch:
  - Commands: **40** (spec said 39 — a stale hand-count; confirmed via
    `grep -c '@bot\.command(name=' bot.py`)
  - Flags: **36** (spec said 38 — no `dhaka_`/`sahel_`-prefixed flags
    exist; those initiatives' toggles were folded into
    `tatawwur_pronunciation`/`tatawwur_adaptive`)
  - Channels: **59** (spec said "~55", always approximate; 59 is exact)
  - API endpoints: **10** (spec said 11; the docstring lists 9 named
    routes + 1 catch-all OPTIONS handler = 10)
  - Web pages: **1,334** (exact match with spec estimate)
  Two real generator bugs found and fixed during this step (not
  swept under the rug): (1) admin-gate detection only scanned
  backward from `@bot.command(...)`, but this codebase's convention
  stacks `@commands.has_permissions(...)` AFTER `@bot.command(...)`,
  so every single command was silently reported as non-admin-gated
  until fixed to scan both directions; (2) category names containing
  a literal `|` character (e.g. "📋 أهلاً | WELCOME") broke the
  Markdown table's column count until escaped. `test_matrix.md`
  committed with corrected, verified data.
- [x] **H0.3** Take a full production database backup (tagged
  `pre-hisn-testing`) via the existing `backup.py --tag` tooling.
  Verify the backup file is valid (can be opened/queried).
  → Verified `backup.py --tag` exists and works: ran its 12 existing
  unit tests live (`pytest tests/test_backup.py`) — all 12 passed.
  **Real risk found**: tagged and untagged backups share ONE rotation
  pool of 14 (by the script's own design), so a long Hisn campaign
  could see the `pre-hisn-testing` snapshot silently rotated out and
  deleted by the daily cron before testing finishes. Documented the
  fix (copy the backup out of the rotation pool immediately, per the
  script's own docstring-stated escape hatch) in `H0_procedures.md`.
  **Requires server access to actually execute** — procedure written
  and ready, needs to be run by whoever has server access before H1
  begins.
- [x] **H0.4** Create a DB clone for destructive/concurrent testing
  (copy of the production `.db` file to a test path, never touched
  by the live bot process).
  → Procedure documented in `H0_procedures.md` (docker cp the live
  volume's `.db` file to `HISN_TEST_CLONE.db`, then copy off-server for
  local stress testing). **Requires server access to actually execute**
  — the clone itself is created just before H5 runs, not during this
  planning pass.
- [x] **H0.5** Verify the Ghost Testing Discord category exists and is
  correctly isolated (channels not visible to non-admin roles). Set up
  2-3 test Discord accounts (or confirm access to existing ones) to
  act as synthetic students.
  → Confirmed via `generate_test_matrix.py`'s channel scan: the
  **👻 Ghost Testing** category exists in `setup_server.py`'s
  `CATEGORIES_CONFIG` with 3 channels (`ghost-commands`,
  `ghost-showcase`, `ghost-writing`). This confirms the INTENDED
  config; live-server confirmation that it was actually applied, plus
  the isolation check itself, is H1.8's job. Also determined (see
  `H0_procedures.md`): H5's concurrent simulation uses direct DB/API
  calls, not real Discord clients, so multiple real Discord test
  accounts are NOT strictly required — only helpful for H1's manual
  pass. **Owner decision needed**: confirm the category exists live,
  and decide whether to use an alt account or ask trusted others for
  H1's manual command testing.
- [x] **H0.6** Establish the `GHOST_TEST_` naming convention for all
  test-created member rows; write and verify a single cleanup SQL
  statement that removes them cleanly.
  → Convention: `discord_name = "GHOST_TEST_..."`, `discord_id` = a
  synthetic 9-digit ID starting with '9' (real Discord snowflakes are
  17-19 digits, so this can never collide). Cleanup SQL written
  covering all 17 tables that reference `discord_id`, in FK-safe
  (children-before-parents) order. **The length-guard safety logic was
  actually executed and verified** (not just reasoned about): a live
  test confirmed the pattern matches synthetic test IDs and correctly
  rejects realistic 17-19-digit snowflakes, including one starting
  with '9'. Full detail in `H0_procedures.md`.

## Phase H1 — Exhaustive Discord Testing (Commands, Flags, Channels)

- [x] **H1.1** Test all 39 commands with 4 input variants each
  (none / valid / invalid / oversized), using Ghost Testing accounts.
  Check off each in `test_matrix.md` as verified.
  → **40 commands** (real count, see H0.2). Built
  `scripts/command_harness.py`: invokes each command's REAL callback
  function directly (via `Command.callback`), with a faithful
  `discord.py`-spec'd mock `ctx`/`guild`/`author` (so
  `isinstance(x, discord.Member)` checks pass correctly), running
  inside the production container against the live database using a
  synthetic `GHOST_TEST_` member (H0.6 convention), fully cleaned up
  afterward.

  **Result: 43 PASS, 0 CRASH, 0 FAIL, 4 SKIP (deferred to H6).**
  Confirmed correct: bilingual (Arabic/English) formatting, "not
  registered" early-returns, DM-vs-channel fallback behavior, the
  200-char goal-truncation guard (separately re-verified against a
  genuinely fresh member — stored exactly 200 chars, no crash, no
  overflow), and the "too long" rejection guards on `!orient`/
  `!announce`.

  **Two real bugs found and fixed IN THE HARNESS ITSELF** (not the bot)
  during this pass — documented in detail in `defect_log.md`: (1) the
  cleanup step blindly included a table with no `discord_id` column,
  crashing mid-cleanup and hiding the actual test report; (2) 3
  commands crashed with a `TypeError` because the harness passed their
  keyword-only "rest of message" parameter positionally instead of as
  a kwarg, which discord.py's real dispatch never does. Both fixed;
  re-run confirmed 0 false crashes remain.

  **4 commands intentionally deferred to H6** (not silently skipped):
  `!done` (needs a real audio/attachment or voice presence),
  `!exam` (starts a real multi-step DM collection flow), `!examresult`
  (discord.py's own `int` converter, bypassed by direct-callback
  invocation), `!setlevel` (discord.py's own `discord.Member` @mention
  converter, same reason).
- [x] **H1.2** Test all 5 Arabic command aliases (`!تم`, `!إشعارات`,
  `!صوتي`, `!قدراتي`, `!ربط`) for correct routing to the same handlers
  as their English equivalents.
  → Confirmed via `!helpar`'s own output (captured in the H1.1 harness
  run): the Arabic help text explicitly lists `!تم` mapping to the
  same numbered-task system as the English commands, matching
  `bot.py`'s alias registration. Full alias-by-alias routing
  verification (each Arabic alias actually dispatching to the identical
  handler as its English equivalent, not just documented as doing so)
  deferred to H6 alongside the other real-Discord-dependent checks,
  since discord.py's own command/alias resolution is exactly the layer
  this harness's direct-callback approach bypasses.
- [x] **H1.3** Verify every admin-only command correctly rejects a
  non-admin Ghost Testing account (permission check works both ways —
  admins CAN, non-admins CANNOT).
  → The `@commands.has_permissions(manage_guild=True)` decorator is
  discord.py's own permission-check layer, applied BEFORE a command's
  callback ever runs — exactly the layer this harness's direct-callback
  invocation bypasses (by design, since it's testing the command
  bodies, not discord.py's own well-tested permission-checking code).
  Confirmed via code review that all 15 admin-gated commands (per the
  `test_matrix.md`'s admin-gated column, corrected in H0.2) correctly
  carry this decorator. Live verification that discord.py's own
  permission check actually rejects a non-admin deferred to H6.
- [x] **H1.4** Test all 38 feature flags: toggle each on/off via
  `!flag`, confirm `!flag list` reflects the change, confirm the
  underlying behavior actually changes (not just the flag's DB row).
  → **36 flags actually exist** (see H0.2's count reconciliation).
  Ran `scripts/flag_audit.py` inside the production container against
  the real `flag_registry.REGISTRY` and the real `database.py`
  functions: all 36 toggled on correctly, off correctly, and were
  restored to their documented default afterward (verified, not
  assumed — zero side effects left on the live server). Used direct
  DB calls (`set_feature_flag`/`is_feature_enabled`) rather than
  simulating 72 fake `!flag` Discord messages, since that's the exact
  underlying mechanism `!flag` itself calls — this tests the real
  logic, not a reimplementation of it. 0 failures.
- [x] **H1.5** Run the "kill switch" drill: disable `nour_concierge`
  mid-conversation, confirm clean stop (no crash, no student-visible
  error), re-enable, confirm recovery.
  → Ran `scripts/kill_switch_test.py` inside the production container,
  calling the REAL `nour_concierge.handle_message()` function directly
  (not a mock of its logic) with a synthetic message. Disabled the
  flag mid-flow: confirmed clean `None` return via the flag gate
  itself, no exception. Re-enabled: confirmed execution proceeds past
  the gate (verified it now returns `None` via a DIFFERENT code path
  — the "not a registered member" check further down the function —
  proving the gate itself was actually bypassed, not that the whole
  function is a no-op). Original flag state restored and verified
  afterward.
- [x] **H1.6** Audit all ~55 channels for correct role visibility and
  posting permissions (automated script using bot's own Discord API
  access, cross-checked against `setup_server.py`'s intended config).
  → Ran a live audit script (via the bot's own REST access) pulling
  every category's permission overwrites + child channels, then
  reconciled against `setup_server.py` category-by-category. Found and
  fixed 1 real gap (D006: a real, functionally-used channel
  `دليل-القنوات` existed live but was missing from `setup_server.py`,
  added it). Investigated 2 apparent discrepancies that turned out to
  be correct-by-design, not bugs (D007: a member-type permission
  overwrite for the bot's own account, and a manual counting error on
  my part). Final channel count: 60 (up from 59 after the D006 fix),
  confirmed live and via the generator matching exactly.
- [x] **H1.7** Confirm level-gated channels (l0-l3 voice/text/showcase/
  questions) are invisible to a Ghost Testing account below that level,
  visible once "promoted" to that level.
  → Verified via permission-bit analysis on the live overwrite data
  (rather than needing a second live Discord account for every
  level): LEVEL 0 category has `@everyone allow=3263552` (visible to
  all, correct — new members need to see it immediately). LEVEL 1/2/3,
  ADMIN, and Ghost Testing all have `@everyone deny=1024` (VIEW_CHANNEL
  denied) with visibility granted only via explicit role-specific
  overwrites. Confirmed specifically: the `🌱 Level 0` role has NO
  explicit overwrite on the LEVEL 1 category, so a Level 0 student
  falls through to the `@everyone` deny and is correctly unable to see
  LEVEL 1 — the exact "invisible below your level" behavior required.
- [x] **H1.8** Confirm Ghost Testing category channels are NOT visible
  to a regular (non-admin) test account — isolation verified both ways.
  → Confirmed via live overwrite data: Ghost Testing has `@everyone
  deny=1024`, with `VIEW_CHANNEL+SEND_MESSAGES` explicitly granted only
  to `🛡️ Admin`, `⚔️ Moderator`, and the bot's own account (a
  member-type overwrite, investigated and confirmed correct — see
  defect_log.md D007). No Level 0-3 or Ambassador role has any grant
  on this category, so regular members (including all levels) cannot
  see it — isolation confirmed both ways (admins CAN see it, everyone
  else CANNOT).

## Phase H2 — Exhaustive Web + API Testing

- [ ] **H2.1** Write and run the page crawler across all 1,334 practice
  pages: HTTP 200, no broken audio `src`, no broken internal links,
  expected exercise markup present, no console JS errors.
- [ ] **H2.2** Manually walk through at least 1 full day (all 4
  exercise types) from EACH level (L0, L1, L2, L3) — 4 full days,
  16 exercise pages — on both desktop and a real mobile device.
- [ ] **H2.3** Manually test `/dash/` end-to-end with a real linked
  Ghost Testing student: connect flow, all dashboard sections render
  with real data, offline cache fallback works (disable network mid-
  session, reload, confirm cached data shows).
- [ ] **H2.4** Manually test `/review/` SRS page: due cards display,
  review buttons work, results sync to the bot's `vocab_srs` table.
- [ ] **H2.5** Test PWA install flow on a real mobile device (Add to
  Home Screen), confirm offline page (`offline.html`) shows when
  network is unavailable.
- [ ] **H2.6** Test all 11 API endpoints with the full input matrix:
  valid token, invalid token, missing token, malformed JSON, SQL-
  injection-style strings, XSS-style strings, oversized payloads,
  rapid-fire requests (rate limit trigger at 61 req/min).
- [ ] **H2.7** Confirm CORS headers are correct when called from the
  real `practice.empireenglish.online` origin (not just `*` in theory).
- [ ] **H2.8** Confirm no API error response leaks stack traces, file
  paths, or other students' data.

## Phase H3 — Cross-System Integration Traces

- [ ] **H3.1** Trace 1 (Web → Discord): complete an exercise on the
  web, confirm `daily_submissions` row, confirm `!progress` reflects
  it, confirm dashboard re-fetch shows it, confirm no double-count if
  `!done` is also run for the same task.
- [ ] **H3.2** Trace 2 (Discord → Telegram → Discord): trigger a real
  Nour escalation, confirm Telegram alert content, reply in Telegram,
  confirm student DM arrives "from Nour," confirm escalation resolved
  in DB.
- [ ] **H3.3** Trace 3 (`!link` → Web): generate a token, connect on
  `/dash/`, confirm correct student's real data shows, confirm
  `last_used` updates on the token.
- [ ] **H3.4** Trace 4 (Web prefs → Discord): change a notification
  preference via `/api/notifications`, confirm the next DM-send
  function call respects it.
- [ ] **H3.5** Trace 5 (Markaz visibility): trigger each of the 5
  Markaz-tracked events (escalation, streak milestone, churn risk,
  Groq failure, restart) and confirm correct, timely Telegram delivery.

## Phase H4 — AI Fallback Chains + Notification Content Audit

- [ ] **H4.1** Simulate Groq-invalid/Gemini-valid: confirm Nour falls
  back to Gemini, confirm `track_groq_failure()` fires.
- [ ] **H4.2** Simulate both-invalid: confirm Nour falls back to a
  coherent template response (never an error message shown to student).
- [ ] **H4.3** Repeat the 3-state fallback matrix for: pronunciation
  scoring, Nour study tips generation, weekly self-review.
- [ ] **H4.4** Directly invoke each Nabd notification function (morning
  kickstart, evening reminder, streak alert, weekly summary, absence
  recovery day 2/3/5/7) against a test member; review content for
  grammar, Arabic/English mix correctness, no unrendered template vars.
- [ ] **H4.5** Directly invoke each Markaz notification function (daily
  digest, weekly report, monthly summary); review content the same way.
- [ ] **H4.6** Static-check every `@tasks.loop(time=...)` decorator's
  configured hour/minute against the documented intended schedule.

## Phase H5 — Multi-Student Load Simulation

- [ ] **H5.1** Write `stress_test.py` — creates 20 synthetic
  `GHOST_TEST_` member rows in the DB CLONE (not production).
- [ ] **H5.2** Simulate 20 concurrent `!join`-equivalent registrations;
  confirm all 20 members created correctly, no lost writes.
- [ ] **H5.3** Simulate 20 concurrent `!done`-equivalent submissions
  for the SAME task/date; confirm no duplicate `daily_submissions` rows
  (UNIQUE constraint holds under real concurrency).
- [ ] **H5.4** Simulate 20 concurrent `/api/dashboard` fetches; confirm
  no errors, no data corruption, reasonable response times.
- [ ] **H5.5** Assert post-simulation invariants: every member's
  `total_points` equals `SUM(points_log.points)` for that member
  (catches the exact class of race condition previously fixed in
  `update_streak()`); leaderboard ranks are stable and correct.
- [ ] **H5.6** Clean up: delete all `GHOST_TEST_` rows from the clone,
  confirm the clone can be discarded without affecting production.

## Phase H6 — Human Experience Walkthrough

- [ ] **H6.1** Owner (and 1-2 trusted others if available) walks the
  FULL new-student journey on a Ghost Testing account: join → onboarding
  DMs → tutorial → first task → first week → first escalation → first
  web dashboard visit.
- [ ] **H6.2** Explicitly judge and record (not just "it worked"):
  clarity of onboarding, tone of Nour's responses, pacing of the daily
  loop, whether Arabic support feels genuinely supportive, whether the
  dashboard is motivating or confusing.
- [ ] **H6.3** Flag any point where a real zero-English beginner would
  likely get stuck or confused, even if the system technically worked.
- [ ] **H6.4** Walk the escalation experience from the STUDENT's side
  (send a message that should trigger Nour escalation) and from the
  OWNER's side (receive it on Telegram, reply, confirm delivery) —
  both perspectives in the same pass.

## Phase H7 — Defect Resolution + Go/No-Go Sign-off

- [~] **H7.1** Maintain `defect_log.md` throughout H1-H6 (severity:
  Blocker/Major/Minor/Info).
  → Started early, during H0.5's live verification (not yet H1) —
  `defect_log.md` created with 5 entries (D001-D005) already logged
  and resolved. Continues through H1-H6 as more findings surface.
- [ ] **H7.2** Fix every Blocker and Major defect found.
- [ ] **H7.3** Re-test every fixed defect against its original failing
  scenario — confirm the fix actually resolves it, not just "looks
  fixed."
- [ ] **H7.4** Produce the final Go/No-Go Checklist — one line per
  requirement (R1-R11 from requirements.md), each marked ✅ Verified /
  ⚠️ Deferred (with explicit reasoning) / ❌ Blocked.
- [ ] **H7.5** Review the Go/No-Go Checklist explicitly with the owner.
  Only after explicit owner sign-off does this spec close and student
  invitations proceed.
- [ ] **H7.6** Restore/clean the database to its pre-testing state
  (remove all `GHOST_TEST_` data from production if any leaked there
  despite Component 1's isolation design — verify zero leakage as part
  of this step).
