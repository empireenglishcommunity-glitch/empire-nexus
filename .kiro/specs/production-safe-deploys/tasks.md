# Tasks — Aegis: Production-Safe Deploys

> **How to use this file:** work top to bottom, phase by phase. Check off
> a task (`- [x]`) in the SAME commit/PR that completes it, so this file
> is always an accurate live progress record for any future session —
> never mark something done here until it's actually merged and verified,
> per this project's own established discipline (see `SESSION_CONTINUITY.md`).
>
> **If you are a fresh session/agent picking this up:** read
> `requirements.md` and `design.md` in this same directory first. Then
> resume at the first unchecked task below. Do not skip Phase 0.

---

## Phase 0 — Recover stranded work (do this FIRST, before any new code)

> **✅ PHASE 0 COMPLETE as of 2026-07-13.** All 3 tasks done and
> verified live. Backups are now genuinely automated (daily 3:10 AM
> cron on the server, not just a runnable-by-hand script). Safe to move
> on to Phase 1 (feature flags + kill switch) next.

- [x] **0.1** Recover the 2 stranded commits (`7f685f1`, `5829134`) from
  branch `test/ai-engine-and-features-coverage` that were never merged
  into `main` (see requirements.md's "real finding" section for full
  detail). Cherry-pick or rebase both onto current `main` in a fresh
  branch. Resolve any conflicts against PR #44/#10's later changes.
  Re-run the full test suite + `ruff check` + `py_compile` before
  opening the PR. Open and merge the PR. **Do not silently skip this
  because it "already exists somewhere" — it does not exist in `main`,
  which is what actually runs.**
  — Done 2026-07-13: [empire-nexus PR #46](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/46).
  Both commits cherry-picked onto current `main` (post PR #44/#45).
  One real merge conflict in `features.py` (this cleanup's bare-except
  fix vs. PR #44's buddy-load cap on the same lines) resolved by
  keeping PR #44's cap + applying the except-narrowing on top. Verified
  against current `main`, not just re-applied blindly: 281/281 tests
  (learning-bot), 49/49 (challenge-bot, confirmed unaffected), ruff
  clean, py_compile clean, and `backup.py` run for real against a
  freshly created populated SQLite file (not just via pytest).
- [x] **0.2** Deploy the recovered `scripts/backup.py` to the server
  (`/opt/empire-english-bot`) and take one real backup by hand to
  confirm it works end-to-end against the real production database file
  (not just in CI against a temp DB). **Blocked on PR #46 being merged
  first** — do not attempt this against an unmerged branch.
  — Done 2026-07-13: pulled `main` (`b63bdec`) on `/opt/empire-english-bot-new`,
  rebuilt the container (new `bot-backups` named volume from the recovered
  `docker-compose.yml` change), confirmed clean startup (curriculum
  loaded, bot online, zero errors). Ran `docker exec empire-english-bot
  python3 scripts/backup.py` against the REAL production database —
  confirmed the resulting backup file is a valid, queryable SQLite file
  (8 tables, correct real member count) genuinely persisted in the named
  Docker volume (`/var/lib/docker/volumes/empire-english-bot_bot-backups/_data`,
  confirmed via `docker volume inspect` — not the container's ephemeral
  layer, so it survives a full rebuild). **Also discovered and fixed a
  real gap while doing this**: the server's crontab already had daily
  3 AM backup jobs for n8n, the challenge-bot sibling, and the EMOS DB —
  but NOT for discord-learning-bot, exactly the "Known follow-up NOT
  addressed" flagged in the original stranded commit's own message.
  Added `10 3 * * * cd /opt/empire-english-bot && docker exec
  empire-english-bot python3 scripts/backup.py >> /var/log/learning-bot-backup.log 2>&1`
  (staggered 10 min after the other jobs), then verified the exact cron
  command works by running it manually and confirming the log file
  and a second rotated backup both appeared correctly (2/14 kept).
  Backups are now genuinely automated daily, not just "runnable by
  hand" — closing this gap for real, not just on paper.
- [x] **0.3** Update this spec's own `requirements.md`/`design.md` if
  anything about the recovered code differs from what was assumed when
  those documents were written (e.g. if `backup.py`'s actual interface
  doesn't match the `--tag` extension assumed in design.md — adjust the
  design, don't force the code to match a doc written without seeing it
  merged). Reviewed after PR #46: `backup.py`'s actual interface
  (`backup(backup_dir: str = None)`, positional CLI arg for custom dir)
  is a plain function+CLI, not yet accepting a `--tag` label — Phase
  2.1 (extend with `--tag`) is still accurate as originally designed,
  no design changes needed.

## Phase 1 — Feature flags + kill switch (bot)

> **✅ PHASE 1 COMPLETE as of 2026-07-13.** The centerpiece of the whole
> Aegis design (decoupling deploy from release) is now real, tested,
> and proven end-to-end with a genuine feature (`!systemstatus`), not
> just unit tests. Test suite: 281 → 289. Safe to move on to Phase 2
> (deploy tooling) next, which will build directly on this.

- [x] **1.1** Add `feature_flags` table + migration to `database.py`
  (idempotent `ALTER`/`CREATE IF NOT EXISTS`, matching this file's
  existing migration pattern in `_migrate()`).
  — Done: added to `_SCHEMA` as a plain `CREATE TABLE IF NOT EXISTS`
  (no `_migrate()` ALTER needed since it's a brand-new table, not a new
  column on an existing one — consistent with how `settings`/other
  whole-new-tables were added previously).
- [x] **1.2** Add `is_feature_enabled()`, `set_feature_flag()`,
  `list_feature_flags()` to `database.py`, with real unit tests
  (including: flag doesn't exist yet → treated as disabled; enabled with
  empty allowlist → everyone; enabled with a populated allowlist →
  restricted; disabling an enabled flag with an active allowlist clears
  it correctly).
  — Done: 8 new tests in `test_database.py`, all passing, covering
  exactly those cases plus upsert-not-duplicate and `updated_by`
  tracking.
- [x] **1.3** Add `!flag` admin command to `bot.py` (`list` / `enable` /
  `disable` / `beta @user...` subcommands), reusing the existing
  `manage_guild` permission-check pattern. Message-length-safe (apply
  the same defensive pattern already used for `!orient`/`!announce` if
  `!flag list` could ever exceed 2000 chars — unlikely at this scale,
  but check, don't assume).
  — Done: string-subcommand style (`action` param), matching this
  codebase's existing convention of no `@bot.group()` usage anywhere
  else. `!flag list` capped to the first 20 flags with a "...and N
  more" tail, same pattern as `!attention`'s buddy-load section.
- [x] **1.4** Write and merge one real, low-stakes feature behind a flag
  end-to-end (a good candidate: the "publicly viewable status artifact"
  from Component 8, `!systemstatus` — see Phase 5) to prove the whole
  mechanism works with a real example, not just tests.
  — Done: `!systemstatus` implemented, gated behind the `systemstatus`
  flag (defaults OFF). Verified live via direct simulation: calling it
  before the flag is enabled produces a genuine no-op (0 messages
  sent); after `!flag enable systemstatus`, it correctly reports real
  facts (database reachable, Discord connected, "38 weeks loaded"
  matching what was verified live on the server in Phase 0). Command
  count confirmed via direct bot-object introspection: 26 registered
  (`!flag` + `!systemstatus`), up from 24. Deliberately NOT added to
  `!help` yet (see the command's own docstring) — advertising a
  command that's silently a no-op until an admin flips its flag would
  recreate exactly the "documented but doesn't work" problem the
  missing `!assess` command was. Add the `!help` entry in the same
  session that actually enables it for everyone.
- [x] **1.5** Document the flag-usage convention (the `if
  database.is_feature_enabled(...)` wrapping pattern) in
  `.kiro/steering/project-rules.md` so future sessions use it
  consistently rather than reinventing a different pattern per feature.
  — Done: new "Feature flags" subsection under Discord Bots code
  conventions, including the no-`!help`-entry-until-released rule
  above and an explicit "don't invent a second flagging pattern" note.
  Also updated the server infrastructure table's Backup row to reflect
  Phase 0's real cron addition (was stale, said 14-day rotation with no
  mention of discord-learning-bot at all).

## Phase 2 — Deploy tooling (bot)

> **✅ PHASE 2 COMPLETE as of 2026-07-13.** The full backup → build →
> tag → swap → health-check → rollback cycle is now real, scripted,
> and proven end-to-end against the actual live server (not just
> mocked tests) — including catching one real, if low-stakes,
> bootstrapping quirk in task 2.5's own live run. This same run also
> brought Phase 1's `!flag`/`!systemstatus` and this phase's own
> heartbeat loop into production for the first time. Safe to move on
> to Phase 3 (CI student-journey simulation) next.

- [x] **2.1** Extend recovered `backup.py` with a `--tag <label>`
  argument (additive, don't break its existing default cron-friendly
  usage).
  — Done: added via `argparse`, sanitizes the label to filesystem-safe
  characters before use, and shares ONE rotation pool with untagged
  backups (deliberate — a pre-deploy snapshot isn't meant to live
  forever, just long enough to make a same-day rollback possible).
  Verified with real subprocess CLI calls (not just importing the
  function directly), including the untagged default path still
  working unchanged. 4 new tests added to `test_backup.py`.
- [x] **2.2** Write `scripts/health_check.py` per design.md's Component
  3 (curriculum-loaded check, command-count check, DB reachability,
  gateway-connected check). Exit code 0/non-zero. Callable standalone
  for manual use, not just from the deploy script.
  — Done: 4 checks — DB reachable, curriculum 38/38 weeks
  (`EXPECTED_WEEKS`), ≥`MIN_EXPECTED_COMMANDS` (24, comment flags to
  bump deliberately as real commands are added — currently 26
  registered after Phase 1) commands registered, and heartbeat
  freshness (≤5 min, via the new `heartbeat` loop below). Real bug
  found and fixed while building this: `check_heartbeat()` crashed
  with an unhandled `sqlite3.OperationalError` on a partially
  initialized DB (no `settings` table yet) — wrapped in try/except so
  a fresh/mid-migration DB reports "unhealthy", not a stack trace.
  9 tests in `tests/test_health_check.py`.
  — Also added to `src/bot.py`: a `heartbeat` `@tasks.loop(minutes=2)`
  writing `last_heartbeat` into the `settings` table, wired into
  `on_ready()` — this is what makes `check_heartbeat()` possible at
  all, bridging an external process to the bot's internal
  gateway-connected state without any new infrastructure. Confirmed
  live (not just by reading discord.py's docs) that `Loop.start()`
  fires an initial iteration immediately, not after the first
  2-minute interval.
- [x] **2.3** Write `scripts/deploy.sh` (or `.py`) wrapping: pre-deploy
  tagged backup → build → tag image with git SHA → swap container →
  health check → fail loudly with rollback instructions if unhealthy.
  — Done as `scripts/deploy.py` (Python, per design.md's stated
  preference for Python over bash where either works). Deliberately
  does NOT auto-rollback on health-check failure — only prints
  rollback instructions and exits 1, so an operator looks at *why*
  it's unhealthy before blindly reverting. 5 tests in
  `tests/test_deploy.py` (mocked `subprocess.run` — real Docker
  behavior was verified manually first, see 2.6's note on the real bug
  this caught).
- [x] **2.4** Write `scripts/rollback.sh` (or `.py`): re-tag the previous
  image as `latest`, restart, and document (in the script's own
  docstring/comments, not a separate doc that can drift) the manual DB-
  restore step for when the database itself also needs reverting.
  — Done as `scripts/rollback.py`. Re-tags the previous git-SHA-tagged
  image as `:latest` and restarts, then runs `health_check.py`. The
  DB-restore step is intentionally NOT automated — documented as
  manual steps directly in the module docstring, since blindly
  restoring a DB backup during an automated rollback risks losing
  real student data written between the backup and the rollback.
  6 tests in `tests/test_rollback.py`.
- [x] **2.5** Test the FULL deploy → verify → rollback cycle for real on
  the live server at least once, deliberately, before relying on it
  under pressure. (Good opportunity: use it to deploy Phase 1's
  `!flag` command itself.)
  — Done for real against `77.42.43.250` via temporary SSH access
  (granted and later revoked, same pattern as Phase 0). The server was
  6 commits behind (still at PR #46's merge, missing #47/#48/#49) —
  `git pull` fast-forwarded cleanly to `eb26bd6`, so this deploy was
  also the first time Phase 1's `!flag`/`!systemstatus` and Phase 2's
  heartbeat loop actually reached the live container, not just `main`.
  Ran `python3 scripts/deploy.py` for real: backup → build → tag
  (`empire-english-bot:eb26bd6`) → swap → health check, all 4 checks
  passed against the real bot (26 commands, 38/38 weeks, real Discord
  gateway connection — confirmed "Bot online: Empire English
  Bot#5980 | 1 server(s)" in the container logs — and a genuinely
  fresh heartbeat, 0.0 min old). Then ran `python3 scripts/rollback.py
  eb26bd6` for real: re-tag → `docker compose up -d` → health check,
  confirmed healthy again (heartbeat 1.2 min old on the second check).
  Also ran `scripts/rollback.py --list` and a direct `docker exec ...
  health_check.py` spot-check independently of `deploy.py`/
  `rollback.py`'s own internal calls, to confirm the script is safe to
  run standalone as designed.
  — **Real bootstrapping quirk found** (one-time only, not a recurring
  bug): `deploy.py`'s Step 1 runs the pre-deploy backup via `docker
  exec <container> ... backup.py --tag ...` against the
  *currently-running* container, which on this very first Phase-2
  deploy still had the pre-Phase-2 `backup.py` that has no `--tag`
  support at all. `argparse` silently treated the literal string
  `--tag` as the positional `backup_dir` argument, writing the backup
  into a bogus `/app/--tag/` directory inside the *old* container's
  own (non-persistent) filesystem instead of the real
  `bot-backups` volume — that single redundant snapshot was lost when
  the old container was destroyed on swap. Confirmed no real data was
  actually at risk: the two most recent routine 3:10 AM cron backups
  in the real `bot-backups` volume were untouched, and this can only
  ever happen on the one deploy that introduces `--tag` itself — every
  deploy from now on runs against a container that already understands
  it. Documenting here rather than silently patching, since the fix
  (if wanted) is really "run one untagged backup before ever running
  the first `--tag`-using deploy", not a code change to `deploy.py`.
  — Confirmed unaffected: the crontab's Phase 0 backup job is still
  present and correctly pointed at the same container/path after the
  swap; `!flag`/`!systemstatus` and the heartbeat loop are now live in
  production for the first time.
- [x] **2.6** Add image retention (keep last 5 tagged images, prune
  untagged dangling layers) — either in `deploy.sh` itself or as a
  separate scheduled cleanup, whichever is simpler to keep correct.
  — Done inside `deploy.py`'s success path only (`KEEP_TAGGED_IMAGES =
  5`), per design.md's "whichever is simpler to keep correct" —
  pruning after every successful deploy is simpler than a separate
  scheduled job with its own failure modes. **Real bug found via live
  Docker/Podman testing in this sandbox** (not caught by code review
  alone): both `deploy.py`'s `prune_old_tagged_images()` and
  `rollback.py`'s `list_tagged_images()` filtered on `"\tlatest" not
  in line` against `docker images --format {{.Tag}}\t{{.CreatedAt}}`
  output — but `.Tag` is the FIRST field, not the second, so the
  `:latest` tag itself never actually matched that substring and
  slipped through the "keep latest" filter, meaning `:latest` could be
  pruned as if it were just another old tagged image. Fixed both by
  explicitly splitting `tag, created_at = line.split("\t", 1)` and
  checking `tag != "latest"`. A regression test for this exact bug is
  in `tests/test_deploy.py`.

**Test suite after Phase 2 (2.1-2.4, 2.6):** 313 passing (up from 289
at Phase 1 close), `ruff check` clean, `py_compile` clean on all
changed/new files.

## Phase 3 — CI: student-journey simulation (bot)

> **✅ PHASE 3 COMPLETE as of 2026-07-13.** The "student journey"
> simulation test is merged ([empire-nexus PR #51](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/51)),
> runs in the existing CI workflow with zero changes, and has been
> proven to catch real regressions via a synthetic-bug test. Test suite:
> 313 → 318. Safe to move on to Phase 4 (empire-dojo CI) next.

- [x] **3.1** Write `tests/test_student_journey.py` per design.md's
  Component 4 — one scripted end-to-end scenario (join → 8 days of
  tasks crossing a streak-bonus threshold → `!assess` → full exam flow
  to a level change), asserting final invariants (points, streaks,
  submission counts) match hand-computed expected values.
  — Done 2026-07-13: [empire-nexus PR #51](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/51).
  5 tests covering the full journey (join → 8 days × 7 tasks →
  7-day streak bonus → !assess → exam → level change L0→L1).
  Hand-computed invariants: total_points=3090, longest_streak=8,
  56 submissions across 8 days, 72 points_log entries.
  Notable finding documented in the test: STREAK_BONUS_POINTS[7]=200
  currently fires once per task submission on the day streak hits 7
  (7 × 200 = 1400 total, not 200 once per day) — asserted as-is for
  regression detection, flagged to user as a possible latent over-award.
- [x] **3.2** Confirm it runs in the existing
  `.github/workflows/learning-bot-test.yml` CI workflow with no changes
  needed to that workflow file (it should just pick up the new test file
  automatically) — verify this is actually true, don't assume.
  — Done: the workflow runs `python -m pytest tests/ -v --tb=short`
  which auto-discovers any `test_*.py` file. No workflow changes made.
  pytest-asyncio (required by the 2 async tests) is already in
  requirements-dev.txt. The strict asyncio mode is handled by explicit
  `@pytest.mark.asyncio` markers on both async test functions.
- [x] **3.3** Intentionally introduce one synthetic bug (e.g. break the
  streak-bonus threshold check) in a throwaway local branch and confirm
  this test actually catches it and fails CI, before trusting it as a
  real guardrail. Revert the synthetic bug afterward, obviously.
  — Done: zeroed the streak bonus payout in process_submission
  (`bonus = 0` instead of `config.STREAK_BONUS_POINTS[current_streak]`).
  Result: test_full_student_journey immediately failed ("Expected
  total_points=3090, got 1690") and test_streak_bonus_fires_exactly_at_
  threshold also failed ("Day 6→7 delta: expected 1605, got 205").
  Both pinpoint exactly what broke. Reverted cleanly afterward.

## Phase 4 — empire-dojo CI + preview-URL discipline

- [ ] **4.1** Write `.github/workflows/dojo-verify.yml`: on every PR,
  run `scripts/generate.py` fresh, sweep every generated page with
  Python's `html.parser`, fail on parse errors or unescaped
  injection-shaped substrings — formalizing the exact manual method used
  during the 2026-07-13 XSS fix (PR #10) into a permanent check.
- [ ] **4.2** Write `scripts/diff_against_live.py`: fetch a representative
  sample of pages from both the live domain and a given preview URL,
  print a unified diff. Use it once for real against the current live
  site + a throwaway test branch's preview URL, confirm the output is
  actually useful before considering this done.
- [ ] **4.3** Add a steering note to `empire-dojo/.kiro/steering/project-rules.md`:
  never merge a PR without clicking through its Cloudflare preview URL.
  Codify what should be habit into something a future session actually
  reads.

## Phase 5 — Presence signaling, dev-log, and the public status command

- [ ] **5.1** Add `!maintenance on|off` admin command that changes the
  bot's Discord presence, and decide how `deploy.sh` triggers it (a
  direct DB flag the running bot polls, or a small helper script that
  talks to the bot process some other way) once Phase 2's deploy script
  exists for real — don't over-design this before that.
- [ ] **5.2** Decide `#dev-log` channel placement (new category vs. fold
  into existing `ADMIN` category — flagged as an open question in
  design.md; ask the user, don't just pick one silently) and add it to
  `scripts/setup_server.py`.
- [ ] **5.3** Wire `deploy.sh` to post a one-line summary (git SHA +
  commit message's first line + timestamp) to `#dev-log` on every
  deploy.
- [ ] **5.4** Build `!systemstatus` (public, read-only, distinct from
  the existing admin-only `!status`) sourced from Phase 2's health-check
  writing its last-good timestamp into the `settings` table — this is
  also the natural first real feature to ship behind Phase 1's flag
  mechanism (see task 1.4).

## Phase 6 — Ghost bot (optional, revisit after Phase 1-5 are solid)

> Do not start this phase until the open design question in design.md
> ("worth building before real students exist, or wait for a small real
> beta squad?") has been explicitly answered by the user — this is
> flagged as a deliberate decision point, not a default "yes, build it."

- [ ] **6.1** Get user's decision on timing (before/after real students
  join) before doing anything else in this phase.
- [ ] **6.2** If proceeding: register a second Discord bot application
  (free), invite into the real production guild restricted to a new
  hidden admin-only channel category.
- [ ] **6.3** Stand up a second, minimal container (separate `.env`,
  separate SQLite file, can reuse most of the existing bot's source with
  a different token/DB path) — reuse code, don't fork/duplicate it.
- [ ] **6.4** Document exactly how to use it for pre-release testing in
  this same `tasks.md` file (append a "how to use the ghost bot" section
  once built, so future sessions don't have to rediscover the workflow).

## Phase 7 — Marketing/professionalism reinforcement (ongoing, not a one-time task)

- [ ] **7.1** After the FIRST feature is safely flag-released to 100% of
  students post-invite, post one bilingual `!announce` about it as a
  concrete proof-of-pattern, not just a design idea. Confirm it lands
  well (check for reactions/replies), and record the result here as a
  lightweight retrospective note.

---

## Cross-session bookkeeping (do this whenever ANY phase above changes state)

- [ ] Keep `empire-chronicle`'s `STATUS.md` "Open items" section pointing
  at this spec's current phase until Phase 5 is complete (Phase 6/7 are
  lower-urgency and can be tracked more loosely once the core safety net
  exists).
- [ ] When the 16 real students are actually invited, add a dated note
  right here in this file (not just in `SESSION_CONTINUITY.md`) marking
  which phases were complete *at the moment of invite* — this is the
  single most important checkpoint this whole spec exists to protect.
