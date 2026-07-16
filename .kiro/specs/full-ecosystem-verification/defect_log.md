# Hisn Defect Log

Running log of every issue found during the Hisn verification campaign.
Severity: **Blocker** (breaks core flow) / **Major** (works but wrong/
confusing) / **Minor** (cosmetic/edge-case) / **Info** (observation only).

---

## D001 — LEVEL 2 category had corrupted emoji (Major)

**Found during:** H0.5 (live Ghost Testing verification, discovered
incidentally while listing categories)
**Severity:** Major — the category was fully functional (correct
channels, correct permissions), but displayed `→` instead of `🚀`,
which would look broken/unprofessional to real students on day 1.
**Root cause:** Unknown — likely a partial/interrupted `setup_server.py`
run or a manual Discord UI edit that mangled the multi-byte emoji
during encoding. Confirmed via raw UTF-8 hex byte inspection (not
terminal rendering) that the live data itself contained `e28692`
(→ U+2192 RIGHTWARDS ARROW) instead of the intended `f09f9a80` (🚀
U+1F680 ROCKET).
**Fix:** Renamed the category via Discord API `PATCH` to the correct
name `🚀 المستوى 2 | LEVEL 2`. Channels and permissions were untouched
(rename only affects the category's `name` field).
**Verified:** Re-queried the category post-fix; API returned the
corrected name, and its 7 channels (`l2-daily-tasks`, `l2-voice-1`,
etc.) were confirmed still attached and unaffected.
**Status:** ✅ Resolved (2026-07-15)

---

## D002 — Duplicate empty LEVEL 2 category (Major)

**Found during:** H0.5, same investigation as D001
**Severity:** Major — a second category also named "LEVEL 2" (with the
CORRECT emoji, ironically) existed simultaneously, completely empty
(0 channels). Confusing for admins, and a sign the server's category
structure had drifted from `setup_server.py`'s intended one-category-
per-level design.
**Root cause:** Likely created by an earlier, separate run of
`setup_server.py` (or a manual re-creation attempt) that didn't detect
the existing category correctly, so it created a new one instead of
reusing/fixing the old one.
**Fix:** Confirmed the duplicate had zero child channels (checked
twice, immediately before deletion, to guard against a race with any
other process). Deleted the category via Discord API `DELETE`.
**Verified:** Post-fix category list shows exactly one "LEVEL 2"
category, with the correct emoji and all 7 real channels attached.
**Status:** ✅ Resolved (2026-07-15)

---

## D003 — ACCOUNTABILITY and RESOURCES categories had corrupted emoji (Major)

**Found during:** H0.5, same investigation as D001/D002
**Severity:** Major — same class of bug as D001: functional but
displaying `▪` (U+25AA BLACK SMALL SQUARE) instead of the intended
`📊` (ACCOUNTABILITY) and `📚` (RESOURCES).
**Root cause:** Same likely cause as D001 (encoding corruption during
setup or manual edit) — both categories showed the identical `▪`
character, suggesting a shared root cause rather than two independent
typos.
**Fix:** Renamed both categories via Discord API `PATCH` to
`📊 المتابعة | ACCOUNTABILITY` and `📚 المصادر | RESOURCES`. Channels
and permissions untouched.
**Verified:** Re-queried both post-fix; API returned corrected names,
channel counts unchanged (3 and 4 respectively).
**Status:** ✅ Resolved (2026-07-15)

---

## D004 — Leftover default "Text Channels" / "Voice Channels" categories (Minor)

**Found during:** H0.5, same investigation
**Severity:** Minor — cosmetic clutter, not referenced anywhere in
`setup_server.py`'s intended design, contained only Discord's
auto-created defaults (`general` text channel, `General` voice
channel) with no real content or purpose.
**Root cause:** Discord automatically creates these on server
creation; they were simply never cleaned up.
**Fix:** Deleted both child channels first (`general`, `General`),
then both now-empty parent categories, via Discord API `DELETE`.
**Verified:** Post-fix category list no longer contains either
default category; total category count matches `setup_server.py`'s
12 intended categories exactly (WELCOME, SYSTEM, LEVEL 0-3, COMMUNITY,
ACCOUNTABILITY, RESOURCES, FEEDBACK, ADMIN, Ghost Testing).
**Status:** ✅ Resolved (2026-07-15)

---

## D005 — Database already contains 4 real member rows (Info)

**Found during:** H0.3 (backup verification)
**Severity:** Info — not a bug, just a planning assumption to correct.
H0's original assumption was an empty database (0 real students,
since none have been invited yet). The backup verification query
showed 4 existing rows: `BioRoMa`, `Mai Mohamed`, `M.A.C.A.L EMPIRE`,
`Empire Ghost` — likely early testers/the owner's own accounts from
prior sessions' ghost-bot work, not real invited students.
**Impact on Hisn campaign:** None — verified these 4 real (17-19 digit)
Discord snowflake IDs do NOT match the `GHOST_TEST_` synthetic-ID
cleanup pattern (9-digit IDs starting with '9'), so H0.6's cleanup SQL
remains safe and will never touch these rows.
**Action:** None required for Hisn. Noted here for awareness only.
**Status:** ℹ️ No action needed



---

## D006 — WELCOME category's `دليل-القنوات` channel missing from setup_server.py (Minor)

**Found during:** H1.6 (channel audit) — live query returned 6 channels
in WELCOME, but `setup_server.py`'s config only defines 5.
**Severity:** Minor — the channel itself works fine and is actively
used (confirmed real content: a full Arabic channel-guide message
posted by the bot, and `features.py`'s `ARABIC_ALLOWED_CHANNELS`
explicitly references it by name). The gap is purely in
`setup_server.py` not being a complete, accurate source of truth —
re-running the script against a fresh server would silently omit this
channel even though the rest of the codebase depends on it existing.
**Root cause:** The channel was likely added manually (or via a
one-off script, per the `fix_all_permissions.py` precedent already
noted elsewhere in `setup_server.py`'s comments) directly against the
live server, and `setup_server.py` was never updated to match.
**Fix:** Added the channel definition to `setup_server.py`'s WELCOME
category, matching its live topic exactly (`🗺️ خريطة كاملة لكل قنوات
السيرفر بالعربي`).
**Verified:** Re-ran `generate_test_matrix.py` post-fix — channel count
increased from 59 to 60, matching the live server's actual channel
count exactly.
**Status:** ✅ Resolved (2026-07-15)

---

## D007 — Two "unmapped role" overwrites investigated, found to be correct (Info, no action)

**Found during:** H1.6, while cross-referencing category permission
overwrites against the guild's role list.
**Severity:** Info only — both turned out to be correct, not bugs.
1. Ghost Testing category's overwrite for ID `1519795406656110857`
   didn't match any role in the guild's role list. Investigated via
   the raw overwrite's `type` field (`type: 1` = member, not `type: 0`
   = role) and a direct member lookup — resolved to the bot's OWN user
   account (`Empire English Bot`), which needs a direct member-level
   grant to post/respond in Ghost Testing regardless of role. Correct
   by design.
2. Manual eyeball count of "61 live channels" vs. the generator's "60"
   was a counting error on my part (mis-reading a role-overwrite log
   line as if it were a channel line), not an actual discrepancy —
   both numbers were 60 once re-checked carefully.
**Action:** None required. Logged for completeness, since a full
verification pass should record what was checked and cleared, not
just what was broken.
**Status:** ℹ️ No action needed



---

## H1.1-H1.3 — Command harness results (2026-07-15)

Ran `scripts/command_harness.py` inside the production container against
all 40 registered commands, invoking each real command callback
directly. Full raw output preserved in this entry for the record.

**Result: 38 PASS, 6 "CRASH", 4 SKIP (deferred to H6), 0 real bot defects.**

All 6 "CRASH" results were investigated individually and confirmed to
be **limitations of the test harness's mocking, not real bugs in the
bot**:

1. **`!join` (valid-args variant), `!orient` (valid-args), `!announce`
   (valid-args)** — `TypeError: cmd_X() takes 1 positional argument but
   2 were given`. Root cause: these 3 commands use a keyword-only
   parameter (`async def cmd_join(ctx, *, goal: str = "")` — note the
   `*`), which discord.py's real dispatch always binds as a keyword
   argument. My harness's `cmd.callback(ctx, *args)` call passed it
   positionally instead, which the real Discord dispatch path never
   does. **Harness bug, not a bot bug** — confirmed by reading the
   actual function signatures.
2. **`!join` (oversized-input variant)** — same root cause as #1 (my
   harness's call pattern, not the oversized-input handling itself,
   which is real, working code per the comments already in `bot.py`
   about message-length stress testing).
3. **`!maintenance` (valid-args)** — `AttributeError: 'NoneType' object
   has no attribute 'change_presence'`. Root cause: this command calls
   `bot.change_presence(...)` on the real, live `bot` singleton, which
   requires an actual active gateway connection. My harness doesn't
   (and structurally can't, without a real Discord connection) provide
   that. **Genuine harness limitation** — this specific sub-path (the
   presence-change side effect) needs H6's live walkthrough to verify;
   the flag-toggle and DB-write parts of the same command (exercised by
   the earlier no-args run, which passed) are already confirmed working.
4. **`!attention`** — `AttributeError: 'coroutine' object has no
   attribute 'members'`. Root cause: `!attention`'s report builder
   iterates `role.members` (via a buddy-load-balancing helper in
   `features.py`) to find eligible buddy candidates. My harness's mock
   guild never populated a `roles` list, so accessing it on the
   auto-speccing mock produced an unexpected coroutine-like stand-in
   instead of a real list. **Harness mocking gap, not a bot bug** —
   the command's actual logic (already reviewed by reading
   `features.py`) is sound; it just needs a more complete mock guild
   (with real role/member data) to exercise this specific branch, which
   is better done live in H6 than with an increasingly elaborate mock.

**Fixed during this run**: found and fixed a real bug in the harness
ITSELF (not the bot) — the synthetic-member cleanup step blindly
included `conversation_sessions` in its `DELETE FROM {table} WHERE
discord_id=?` loop, but that table has no `discord_id` column at all
(participants are stored as a comma-separated `participant_ids` TEXT
field). This crashed the harness mid-cleanup on the first run, hiding
the actual test report behind an unrelated failure. Fixed by (a)
removing that table from the loop, and (b) reordering the script so
the report always prints BEFORE cleanup runs, so a future cleanup bug
can never again hide real test results.

**38 commands confirmed genuinely working** via real invocation of their
actual callback functions against the live database, including
correctly formatted bilingual (Arabic/English) output, correct
"not registered" early-return messages, and correct DM-vs-channel
fallback behavior (`!members`, `!status`, `!attention` all correctly
attempt DM-first).

**4 commands (`!done`, `!exam`, `!examresult`, `!setlevel`) intentionally
deferred to H6** (real audio/attachment/voice verification, real
multi-step DM collection flow, and discord.py's own argument
converters respectively — none of these can be faithfully simulated
without either a real Discord client or an excessively elaborate mock
that would itself need its own verification).

**Status:** ✅ H1.1-H1.3 complete — 0 real defects found in the 38
directly-testable commands; 4 commands' remaining sub-paths flagged for
H6's live human walkthrough, consistent with the harness's own
documented, upfront limitations (not a late excuse).



---

## D008 — Live practice platform is stale; multiple merged features never deployed (BLOCKER)

**Found during:** H2.1 (page crawler), while investigating why `/dash/`
(the Wuslah W1 student dashboard) returned the site's own homepage
content instead of the dashboard.
**Severity:** BLOCKER — this is not a code bug, it's a deployment gap,
but its impact is severe: the entire Wuslah initiative's user-facing
web deliverable (the student dashboard) does not exist for real
students visiting the live site today, despite being fully built,
tested, and merged.

**Root cause, confirmed step by step:**
1. `curl https://practice.empireenglish.online/dash/` returns the site
   HOMEPAGE, not the dashboard page.
2. Investigated whether this was a false positive from Cloudflare
   Pages' 404-fallback behavior (confirmed separately that this site
   has no custom `404.html`, so Cloudflare serves the homepage with
   HTTP 200 for ANY nonexistent path — a real, if minor, finding on
   its own, see the page_crawler.py fix for D009-adjacent handling).
3. Ruled out "the page never existed": confirmed via
   `github_pull_repository` (pulling the REAL, authoritative `main`
   branch from GitHub, not trusting a possibly-stale local sandbox
   checkout) that `site/dash/index.html` genuinely exists on
   `origin/main` at commit `0f79829` ("Merge pull request #21 ...
   wuslah/w1-student-dashboard").
4. Confirmed the homepage's own new "📊 My Dashboard" link (added in
   the same PR #21) is ALSO missing from the live site's homepage —
   proving this isn't specific to one page, but that the live
   deployment predates PR #21 (and likely other recent merges) entirely.
5. Root cause: `empire-dojo` has **no CI/CD auto-deploy pipeline**.
   `.github/workflows/dojo-verify.yml` only runs page-verification
   checks on PRs — it does not deploy anything. Deployment is a fully
   manual step (`npx wrangler pages deploy site --project-name=empire-practice`,
   per this repo's own steering doc), and this step was evidently never
   run after PR #21 (and possibly other recent PRs) merged.

**This is the same root-cause CLASS of bug as the earlier Markaz
"merged PR ≠ deployed PR" finding** (session context: the Hetzner bot
server needed manual `git pull` + `docker compose up --build` after
every merge) — except here for Cloudflare Pages, where the deploy
step is `wrangler pages deploy`, not a git pull. **Both halves of this
ecosystem (bot server AND practice platform) require a manual deploy
step after merge, and both have now been caught silently drifting
out of sync with `main` at least once.**

**Fix (not yet executed — needs owner action or Cloudflare
credentials):**
```bash
cd empire-dojo
git checkout main && git pull   # ensure the true, current main is checked out
npx wrangler pages deploy site --project-name=empire-practice
```
This requires a valid `CLOUDFLARE_API_TOKEN` (and account ID
`8c2ca895bd4e579be07d2fa6c9fdba7e`, per this repo's steering doc). No
such token was available/verifiable in this session — per the
steering doc's OWN explicit warning ("always verify via
`/user/tokens/verify` first, never assume a token is still active"),
a stale token referenced in past session notes should not be assumed
valid without checking. **Owner action needed**: either provide a
verified-valid `CLOUDFLARE_API_TOKEN`, or run the deploy command
directly.

**DEPLOYED AND RESOLVED (session 16, confirmed fresh in session 17)**:
the deploy was run (`wrangler pages deploy site --project-name=empire-practice`
with a verified Cloudflare token), and the process-fix
([empire-dojo PR #22](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/22))
was merged, documenting the mandatory post-merge deploy step so this
can't silently recur. **This resolution was not re-confirmed with a
fresh live check before session 16 ran out of credits** — re-verified
independently in session 17 (2026-07-15) rather than trusting the
unclosed status:
- `curl https://practice.empireenglish.online/dash/` → HTTP 200, body
  confirmed DIFFERENT from the homepage body (contains real
  dashboard-specific markup, not the Cloudflare 404-fallback) — the
  real dashboard is live.
- Homepage confirmed to contain the "My Dashboard" link.
- Ran the FULL `page_crawler.py` exhaustively across all 1,334 pages
  (no sampling): **1,334/1,334 pass, 0 issues.** Confirms no other
  merged-but-undeployed content remains missing anywhere on the site.

**Status:** ✅ **RESOLVED** — deploy confirmed live, full 1,334-page
crawl confirms zero remaining scope, process-fix (PR #22) merged to
prevent recurrence.

---

## D009 — page_crawler.py's own false-positive bugs found and fixed (Info, harness self-correction)

**Found during:** H2.1, while validating the crawler itself before
trusting its output (same discipline as H1's command harness).
**Severity:** Info — both are harness bugs, not site bugs, but
recording them per the campaign's own transparency standard (harness
bugs get logged too, not just swept away quietly, per the precedent
set with H1's command_harness.py fixes).
1. **Off-by-one path resolution**: the script's `SITE_DIR` calculation
   had one `.parent` too few, causing it to look for `empire-dojo` one
   directory level higher than its actual location. Found immediately
   on first run (`ERROR: empire-dojo site dir not found`), fixed by
   counting the actual directory depth precisely rather than guessing.
2. **False "broken-render marker" on every page**: the site's own
   legitimate JavaScript template literals (`` `${totalDone}/${totalPossible}` ``
   inside `<script>` tags) were being flagged as broken/unrendered
   template syntax, since the check searched the raw HTML including
   script contents. Fixed by stripping `<script>...</script>` blocks
   before running the marker check — confirmed via direct testing that
   the homepage (which legitimately contains this exact pattern) now
   passes cleanly, while a genuinely broken page would still be caught
   (marker checks outside `<script>` blocks are unaffected).
3. **Discovered and specifically handled Cloudflare Pages' 404-fallback
   behavior** (serves the homepage with HTTP 200 for ANY nonexistent
   path, since this site has no custom `404.html`) — this ISN'T a bug
   in the crawler being fixed here, but a real platform behavior that
   had to be actively worked around (via homepage-body comparison) for
   the crawler to be trustworthy at all. Documented in the script's own
   docstring/comments in detail. This same behavior is what surfaced
   D008 above — without this fix, D008 would have been invisible (a
   naive "HTTP 200 = page exists" check would have silently passed the
   missing `/dash/` page).
**Status:** ✅ Resolved (harness fixed and re-verified before the full
1,334-page run).


---

## D010 — `/api/nour-tips` + `/api/progress-v2` may not respect their documented feature flags (Major, UNVERIFIED — needs live confirmation)

**Found during:** H2.6 prep (code reading `api_server.py` while
designing the adversarial API test script, before SSH access was
available to test live).
**Severity:** Major IF confirmed — this would be a real kill-switch
gap: an admin disabling `wuslah_nour_tips` or `wuslah_adaptive` via
`!flag` would believe the corresponding endpoint is now inert, but it
would keep serving normally. This is exactly the class of thing Hisn
exists to catch before real students are affected.
**Evidence gathered so far (code-only, NOT yet live-verified):**
- `ecosystem-harmony/design.md`'s feature flag table explicitly lists
  `wuslah_nour_tips` → "Enable AI-generated weekly study tips" and
  `wuslah_adaptive` → "Enable adaptive practice recommendations."
- `flag_registry.py`'s `REGISTRY` entries carry the same descriptions:
  `("wuslah_nour_tips", "Enable AI-generated weekly study tips (W4)", "wuslah", True)`,
  `("wuslah_adaptive", "Enable adaptive practice recommendations on the web (W3)", "wuslah", True)`.
- Reading `api_server.py`'s actual route handlers:
  - `get_dashboard()` → calls `database.is_feature_enabled("wuslah_dashboard_api")` ✅
  - `get_leaderboard()` → calls the same flag check ✅
  - `post_complete_exercise()` → calls `database.is_feature_enabled("wuslah_exercise_confirm")` ✅
  - `get_nour_tips()` → **no `is_feature_enabled()` call anywhere in
    the function body.** Only checks token validity + rate limit.
  - `get_progress_v2()` → **same — no `is_feature_enabled()` call.**
**LIVE-VERIFIED (2026-07-15, session 17)**: with SSH access restored,
toggled both flags off directly via `database.set_feature_flag()` in
the live production container (confirmed via `is_feature_enabled()`
returning `False` for both immediately after), then hit both live
public endpoints (`https://bot.empireenglish.online/api/nour-tips` and
`/api/progress-v2`) with a real `GHOST_TEST_` member's token:
- `/api/nour-tips` → **HTTP 200**, full generic-tips payload returned.
  **Gap CONFIRMED — flag had zero effect.**
- `/api/progress-v2` → **HTTP 200**, full adaptive fields
  (`difficulty_level`, `weak_phonemes`, `recommended_exercise`,
  `srs_due_count`) returned. **Gap CONFIRMED — flag had zero effect.**
- Control check: `/api/dashboard` (gated on `wuslah_dashboard_api`,
  left ON throughout) returned normally, confirming the flag mechanism
  itself works correctly elsewhere and this is specific to these two
  endpoints, not a systemic flag-check failure.
Both flags were restored to their original `True` value immediately
after the check and re-verified via `is_feature_enabled()` — zero
lasting change to production config from the test itself.

**Fix applied and verified**: added the missing 2-line
`is_feature_enabled()` gate to both `get_progress_v2()` and
`get_nour_tips()` in `api_server.py`, matching the exact pattern
already used in `get_dashboard()`/`post_complete_exercise()`. Shipped
via [empire-nexus PR #120](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/120).

**Deployed and post-deploy re-verified (2026-07-15, same session)**:
after PR #120 merged, deployed to production (`git pull` + `docker
compose up -d --build` on `77.42.43.250` — server was confirmed stale
at the old commit `022c6f9` beforehand, fast-forwarded to `15f487f`
after). Container confirmed healthy (Discord gateway connected,
curriculum loaded, API server listening on 8099). Ran the full
verification cycle again with a fresh `GHOST_TEST_` token:
1. Baseline (flags ON, post-deploy code): both endpoints → HTTP 200. ✅
2. Flags toggled OFF: `/api/nour-tips` → **HTTP 503**
   `{"error": "study tips API not enabled"}`; `/api/progress-v2` →
   **HTTP 503** `{"error": "adaptive progress API not enabled"}`.
   **Fix confirmed working exactly as intended.** Control
   (`/api/dashboard`, different flag) unaffected, still 200.
3. Flags restored to `True`, re-confirmed both endpoints back to
   HTTP 200 for real students.
Ghost members cleaned up afterward, 0 residual rows confirmed.
**Status:** ✅ **RESOLVED** — confirmed broken live, fixed, deployed,
and re-verified live post-deploy. No further action needed.



---

## D011 — Cloudflare WAF blocks default Python User-Agent on `bot.empireenglish.online` (Info, test-tooling gap, not an app defect)

**Found during:** H2.6 execution (first real run of
`api_adversarial_test.py` against the live public API, once SSH access
was restored).
**Severity:** Info — this is a finding about the test script and the
edge infrastructure in front of the API, not a bug in `api_server.py`
itself. Recorded here per the campaign's own transparency standard
(the same discipline applied to D009's harness self-corrections).
**What happened:** The first live run of `api_adversarial_test.py`
returned HTTP 403 with body `error code: 1010` on 44 of 46 checks —
initially looked like a catastrophic API-wide failure. Investigated
before concluding anything:
- Confirmed via a side-by-side `curl` comparison that requests with
  Python's default `Python-urllib/3.x` User-Agent are blocked by
  Cloudflare's edge (`error code: 1010` is Cloudflare's own bot-fight-
  mode signature-block response, returned by Cloudflare itself, not
  the origin server).
- The same request with a realistic browser User-Agent (or curl's own
  default UA) returns the correct application-level response (HTTP
  200/400/404 as appropriate).
- This confirms the block happens at Cloudflare's edge, before the
  request ever reaches the bot's `api_server.py` — an infrastructure/
  WAF configuration detail, not an application defect.
**Impact assessment:** Real browsers (and the actual
`practice.empireenglish.online` frontend, which uses `fetch()` with a
real browser UA) are unaffected. This would only matter for
future server-side/scripted integrations that don't set a UA.
**Fix:** Updated `api_adversarial_test.py` to send a realistic browser
`User-Agent` header on every request. Re-run after the fix: 45/46
checks passed (see H2.6 below for the one remaining flagged item and
why it's a test-script false positive, not a defect).
**Status:** ✅ Resolved (test script fixed; no application/WAF
configuration change needed or made).

---

## H2.6 — API adversarial testing: EXECUTED (2026-07-15, session 17)

Ran all 3 committed scripts against the live production API, in order:
`setup_ghost_members.py` (inside container) → D010 live verification
(see D010 above) → `api_adversarial_test.py` (from the sandbox, against
`https://bot.empireenglish.online`, after the D011 UA fix) →
`cleanup_ghost_members.py` (inside container).

**Result: 45/46 checks OK, 1 flagged (false positive, see below), 0
new real defects found in the API layer itself** (beyond the D010 gap,
already confirmed and fixed separately above).

- All valid/invalid/missing-token cases behaved correctly (200/404/400
  with clean, non-leaking error bodies) across all 6 GET endpoints.
- SQL-injection-style and XSS-style strings in tokens and body fields
  were handled safely everywhere — treated as ordinary non-matching
  strings (404 "invalid token") or rejected by input validation (400),
  never a 500 or a leaked stack trace.
- Oversized token (200,000 chars) correctly rejected with HTTP 414
  before reaching application logic.
- Oversized POST payload (200,000-char `word` field) accepted without
  error or leak (HTTP 200) — no size-limit enforcement on this
  specific field, but not a security issue on its own (no leak,
  no crash); worth a Minor follow-up if stricter payload limits are
  ever desired, not blocking for launch.
- Malformed JSON correctly rejected (400 "invalid JSON") on all 3 POST
  endpoints.
- CORS: `Access-Control-Allow-Origin: *` present on real responses;
  OPTIONS preflight returns 200 with correct
  `Access-Control-Allow-Methods`/`Access-Control-Allow-Headers`. H2.7
  is therefore also confirmed complete by this same run.
- Rate limiting: the 61st request in under 60 seconds correctly
  received the first HTTP 429 — exact documented threshold, exact
  behavior.
- H2.8 (leak/cross-member scan): zero stack-trace/file-path markers
  found in any error response across the full matrix.

**The 1 flagged check is a false positive in the test script, not a
defect**: `/api/leaderboard`'s `valid_token` response for member A
legitimately contained member B's name (`GHOST_TEST_H2ApiRunnerB`),
which the script's generic cross-member-leak heuristic flagged. This
is **the leaderboard's entire documented purpose** — a public top-10
ranking naming other members by design (per the endpoint's own
docstring: "top 10 students + requester's own rank"), not a private
per-member payload like `/api/dashboard`. The heuristic doesn't
distinguish public-by-design endpoints from private ones. No fix
needed to `api_server.py`; noting here that a future refinement of the
test script could special-case `/api/leaderboard` to only check for
UNEXPECTED private fields (e.g. discord_id, token) rather than names,
if this campaign's scripts are reused again later. Not blocking.

**Cleanup verified**: `cleanup_ghost_members.py` ran successfully,
0 residual `GHOST_TEST_` member rows confirmed via direct query
immediately after.

**Status:** ✅ H2.6 + H2.7 + H2.8 all complete. D010 confirmed live and
fixed (pending deploy + post-deploy re-verification, tracked in D010's
entry above). D011 (test-tooling UA block) found and resolved in the
test script itself.



---

## D012 — Dashboard "level" badge and XP progress bar are two independent systems, may confuse students (Minor, UX, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H2.3 (manual dashboard walkthrough with the owner,
using a `GHOST_TEST_` member with seeded data — 3-day streak, 90
points, level L1, one milestone).
**Severity:** Minor — not a bug, the code is working exactly as
designed. Flagged as a real UX finding because a real student could
plausibly experience genuine confusion from it.
**What was observed:** The dashboard showed level badge `L1` alongside
a progress bar reading "0% to L2" despite the member having real
recent activity (3-day streak, 90 points, 6 tasks done this week).
**Root cause (confirmed via code read, `api_server.py`'s
`get_dashboard()`):** `level` (L0-L3, the curriculum level shown in
the badge) and the XP progress bar are two structurally independent
systems:
- `level` is presumably set via `!setlevel` / assessment placement —
  it does not derive from `total_points` at all.
- The progress bar's "next level" math uses a SEPARATE points
  threshold table: `{"L0": 0, "L1": 2000, "L2": 5000, "L3": 10000}`.
  A member sitting at L1 with 90 points is 1,910 points away from the
  bar's own "L2" threshold — the 0% display is mathematically correct
  for that formula, it just isn't intuitively connected to how the
  member actually reached L1 in the first place.
**Why this matters for real students:** someone placed at L1 via
assessment could realistically sit at "0% to L2" for many real days of
consistent practice (2,000 points at a realistic ~100 pts/day pace is
~3 weeks away), and may not understand why their "level" and the
"next level" progress bar don't visibly correspond — worth
considering either (a) relabeling the progress bar to make clear it
tracks total XP toward a points-based milestone, separate from
curriculum level, or (b) tying the two systems together more visibly.
**Decision (owner, 2026-07-15):** Log now, defer the actual fix.
Continue the rest of the Hisn walkthrough first, then address this
alongside any other findings in one batch at the end — explicitly NOT
to be forgotten in the meantime. This entry is the record that
guarantees that.
**Status:** ✅ **RESOLVED (2026-07-16, via Masar M1 — Momentum Score).**
Per the owner's own later decision (documented in
`.kiro/specs/masar/requirements.md`), this was deliberately NOT
patched with a quick relabel — it was treated as one instance of a
bigger pattern (alongside D020) and given a proper initiative
(Masar/مسار). The actual fix: the old points-vs-threshold XP bar is
now replaced by `narrative_engine.momentum_score()` — a single,
honestly-computed, recency-based signal (7-day streak + task
completion + pronunciation trend), shown identically on both the
dashboard (`/dash/`) and `!progress`, explicitly labeled "Momentum
This Week / نشاطك الأسبوعي" so it can never again imply a connection
to level-up that doesn't exist. Level badge itself was left completely
unchanged, per R1's constraint.
Shipped behind `masar_momentum_score` (default OFF, D010-style
per-member flag gating). Live-verified in PRODUCTION on 2026-07-16
using a real `GHOST_TEST_920001` member (not a DB-clone simulation):
flag ON → `/api/dashboard`'s live response included
`"momentum": {"score": 29, "label": "building", ...}`, and a direct
call to the exact same `narrative_engine.momentum_score()` function
(the same one `!progress` calls) returned the identical
`{"score": 29, "label": "building", ...}` — structurally guaranteeing
R2's dashboard/`!progress` consistency requirement, not just a
one-time coincidence. Flag OFF → `momentum` field genuinely absent
from the live response, old `level_progress` fallback untouched —
confirmed the D010-style flag-gate discipline holds in production, not
just in a clone. Test member fully cleaned up afterward, `members`
back to 0 rows. See `.kiro/specs/masar/tasks.md`'s M1 phase for the
full implementation record. PRs:
[empire-nexus#171](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/171),
[empire-dojo#26](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/26).



---

## D013 — Service worker's offline fallback page is broken due to a `.html`-suffix redirect; violates the project's own documented URL convention (Major, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H2.5 (manual PWA install + offline test with the
owner, on a real mobile device — Safari on what showed the install
prompt correctly and installed to the home screen without issue).
**Severity:** Major. The PWA install itself works correctly (H2.5's
first half: PASS). But the offline experience — the entire point of
Sahel S4's PWA work — is broken for any page the student hasn't
already visited while online: instead of a friendly offline page,
the student sees the browser's own native "Safari cannot open this
page" error.

**What was observed:** Installed the PWA to the home screen (worked
correctly), enabled Airplane Mode, then tapped into a page not yet
visited/cached (an `accent` exercise page). Result: native browser
error, not the intended `offline.html` fallback page.

**Root cause, confirmed via code + live verification:**
1. `sw.js` hardcodes `const OFFLINE_URL = '/offline.html';` and
   includes `/offline.html` (with the `.html` suffix) in its
   `PRECACHE` array.
2. **This directly violates this project's own documented rule**,
   written in `empire-dojo/.kiro/steering/project-rules.md` section
   "Known quirk — extensionless URLs only": every internal link must
   be extensionless, because `.html`-suffixed paths on
   `practice.empireenglish.online`'s current Cloudflare zone always
   308-redirect to their extensionless form. Confirmed live:
   `curl -sI https://practice.empireenglish.online/offline.html` →
   `HTTP/2 308`, `location: /offline`. Every OTHER precached asset
   (`/`, `/css/empire.css`, `/js/app.js`, `/logo.png`, `/favicon.png`,
   `/manifest.json`) returns a clean `200` with no redirect — `sw.js`
   is the ONE place in the codebase that doesn't follow the site's own
   documented convention.
3. **Why this breaks the offline fallback specifically**: the
   `install` event does `cache.addAll(PRECACHE)`, which includes the
   redirecting `/offline.html` URL. Redirected responses have known,
   documented quirks in the browser Cache API (especially on WebKit/
   Safari) — the cached entry can end up keyed differently than the
   literal string the fetch handler later looks up. The fetch
   handler's offline fallback does `caches.match(OFFLINE_URL)` using
   the literal string `/offline.html` — if precaching didn't store a
   matching entry under that exact key (due to the redirect), this
   lookup returns `undefined`, and `event.respondWith(undefined)`
   results in exactly the native browser error the owner saw, instead
   of any page at all.
4. **Why H2.1's exhaustive 1,334-page crawl never caught this**:
   `page_crawler.py` discovers pages from `empire-dojo/site/`'s file
   structure using the documented extensionless convention — it never
   constructs or tests a `.html`-suffixed URL, so the redirect on
   `/offline.html` specifically was invisible to that fully-automated,
   otherwise-exhaustive pass. This is exactly the kind of gap a real
   human/mobile walkthrough exists to catch that scripted testing
   structurally cannot — confirms H2.5's value even after H2.1 passed
   1,334/1,334.

**Proposed fix (not yet applied, deferred per the owner's batching
decision):** change `sw.js`'s `OFFLINE_URL` constant and its entry in
`PRECACHE` from `/offline.html` to the extensionless `/offline`,
matching every other URL in the codebase. Requires re-deploying
`empire-dojo` after the fix (the same manual `wrangler pages deploy`
step documented for D008), and a fresh install/offline re-test on a
real device to confirm the fallback page actually renders once fixed
(a code fix alone should not be trusted here without live re-
verification, per this campaign's own standing discipline).

**Decision (owner, 2026-07-15):** Log now, defer the fix. Batch with
D012 and any other findings for one fix-everything pass at the end of
the Hisn campaign, before H7's Go/No-Go sign-off. This entry is the
record that guarantees it isn't forgotten in the meantime.

**Fix applied (2026-07-15):** `sw.js`'s `OFFLINE_URL` const and its
`PRECACHE` array entry changed from `/offline.html` to the
extensionless `/offline`, matching the rest of the codebase's
convention. Merged via `empire-dojo` [PR #23](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/23)
— confirmed landed on `main` by direct content grep (not just merge-
status API), per this campaign's standing verification discipline.

**Deployed and live-verified (2026-07-15):** deployed via
`npx wrangler pages deploy site --project-name=empire-practice`
(268 files uploaded). Confirmed server-side on the real production
domain (not just the deploy tool's success message):
`curl https://practice.empireenglish.online/sw.js` now shows
`OFFLINE_URL = '/offline'` and `/offline` (not `/offline.html`) in
`PRECACHE`; `curl .../offline` returns a clean `200` rendering the
real offline page (`<title>Offline | Empire English</title>`), not a
redirect or error.

**Status:** ✅ **RESOLVED — fixed, merged, deployed, and server-side
verified live.** Still recommend one real-device airplane-mode
re-test (the owner's original repro) as a final human confirmation
during H6, but the root cause (the `.html`-suffix redirect) is
structurally eliminated and confirmed gone on the live site.



---

## D014 — Recorder playback and download broken on Safari/iOS due to hardcoded `audio/webm` mime type (Major, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H2.2 (manual day×level mobile walkthrough with the
owner, L0 Day 1, Accent exercise, real iPhone + Safari).
**Severity:** Major. Recording itself works (mic permission prompt
appeared, presumably recorded audio), but BOTH ways of hearing it back
are broken: the in-page "Listen to Yours" playback button was
unresponsive, and the "Download" link produced no downloadable file.
This affects the "Compare & Rate" self-assessment flow, a core piece
of the accent/shadowing exercises across all 4 levels (same recorder
component is reused everywhere per `generate.py`).

**What was observed (on iPhone Safari):**
- Recording started/stopped without visible error.
- "Listen to Yours" button: unresponsive ("unclickable").
- "Download" link: tapped, but nothing downloadable resulted.
- Everything else on the page (layout, TTS model playback, page
  structure) worked correctly on the small screen — this is isolated
  specifically to the user's own recording, not the recorder UI
  chrome or the page in general.

**Root cause, confirmed via code read (`app.js`):**
1. The `Recorder.stop()` function hardcodes the recorded blob's mime
   type unconditionally: `new Blob(this.chunks, { type: 'audio/webm' })`
   — regardless of what `MediaRecorder` on the actual device/browser
   produced.
2. **No `MediaRecorder.isTypeSupported()` check exists anywhere in
   this codebase** — confirmed via search, zero matches. The code
   assumes `audio/webm` is universally correct.
3. Safari's `MediaRecorder` implementation does not natively record
   webm — it uses its own supported format (commonly MP4/AAC-based)
   under the hood. Forcibly labeling that data as `type: 'audio/webm'`
   when constructing the `Blob` creates a blob whose actual byte
   content doesn't match its declared MIME type.
4. **This mismatch plausibly explains both symptoms independently**:
   - `RecorderUI.playMine()` creates `new Audio(this.audioUrl)` from
     this mislabeled blob and calls `.play().catch(() => {})` — the
     `catch` silently swallows any decode/format error with zero
     visible feedback, which matches exactly the "unclickable, nothing
     happens" symptom described (the button IS wired correctly and
     IS being clicked; the audio element is silently failing to
     decode/play the mislabeled data).
   - The `<a id="rec-download" download="...webm">` link's `href` is
     set to the same mislabeled object URL — Safari's handling of
     forced-download links for a blob whose declared type doesn't
     match its real content is unreliable, consistent with "clicked
     but nothing to download."
5. Confirmed no Safari-specific handling, feature-detection, or
   fallback mime type exists anywhere in `Recorder`/`RecorderUI`.

**Scope:** This is the SAME recorder component (`Recorder`/`RecorderUI`
in `app.js`, wired via `generate.py`'s `gen_accent()`/`gen_shadowing()`)
used on the Accent AND Shadowing pages across all 4 levels (L0-L3,
38 weeks) — not a one-page issue. Any Safari/iOS student using either
exercise type would hit this.

**Proposed fix (not yet applied, deferred per the owner's batching
decision):** use `MediaRecorder.isTypeSupported()` to pick a real,
supported mime type at record-start time (checking common candidates
in order, e.g. `audio/webm`, `audio/mp4`, falling back to the
browser's own default if none of the preferred types are supported),
and construct the `Blob` with that ACTUAL type instead of a hardcoded
one. The download filename extension should also be derived from the
real type (e.g. `.mp4` instead of a hardcoded `.webm`) so downloaded
files aren't mislabeled either. Requires a fresh live re-test on a
real Safari/iOS device after the fix (not just Chrome/desktop, since
this is specifically a cross-browser format-support gap that a
Chrome-only check would not catch).

**CROSS-DEVICE CONFIRMATION (2026-07-15, same session, L1 spot-check
pass):** the owner independently tested the identical recorder flow
on a laptop/desktop browser and confirmed playback AND download BOTH
work correctly there — only the phone (Safari/iOS) exhibits the
failure, and this held true consistently across every level/page
tested in this session, not just the original L0 Accent page.

This is strong, real-world confirmation of the root cause theory
above, not just a plausible code-reading guess: desktop browsers
(Chrome/Firefox/Edge) DO natively support recording and playing back
`audio/webm` — so the hardcoded `type: 'audio/webm'` label happens to
be ACCURATE on those browsers, and playback/download work by what is
effectively luck rather than correct, browser-aware handling. Safari/
iOS is the one major browser that doesn't natively produce webm from
`MediaRecorder`, which is exactly why it's the one place this breaks.
This also confirms the bug is NOT isolated to one page/level — it is
confirmed present everywhere the shared `Recorder`/`RecorderUI`
component is used, on every mobile page tested so far, exactly as the
"same shared component" scope note predicted.

**Decision (owner, 2026-07-15):** Log now, defer the fix. Batch with
D012 and D013 for one fix-everything pass at the end of the Hisn
campaign, before H7's Go/No-Go sign-off.

**Fix applied (2026-07-15):** added `Recorder._pickMimeType()`, which
uses `MediaRecorder.isTypeSupported()` to pick a real supported mime
type (checking `audio/mp4` first for Safari/iOS, then webm/ogg
variants) at `start()` time, stores the actual negotiated type
(`this.mediaRecorder.mimeType`), and uses that real type — not a
hardcoded `'audio/webm'` — when constructing the `Blob` in `stop()`.
Also fixed the download link's file extension to match the real type
(e.g. `.m4a` instead of a hardcoded `.webm`) via a new
`RecorderUI._extensionFor()` helper. Merged via `empire-dojo`
[PR #23](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/23) — confirmed landed on `main` by direct content grep.

**Deployed (2026-07-15):** deployed via `npx wrangler pages deploy
site --project-name=empire-practice`; confirmed server-side that the
fixed `app.js` (containing `_pickMimeType()`) is now what
`practice.empireenglish.online/js/app.js` actually serves.

**Live re-tested (2026-07-16), on the SAME iPhone Safari that
originally found this:** the owner repeated the exact original repro
(record → play back via "Listen to Yours" → download) as part of
H6's Tier 1 device re-test pass. Owner confirmed: **"playback work
now, and downloadable."** Both symptoms that originally failed are
now fixed.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified on the exact same real Safari/iOS device that originally
found this defect.



---

## D015 — Shadowing page's Stop button and Speed selector have zero effect on the real pre-generated audio (Major, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H2.2 (manual mobile walkthrough with the owner, L0
Day 1, Shadowing exercise, real iPhone Safari).
**Severity:** Major. The passage's model audio plays correctly, but a
student cannot stop it early or slow it down — both controls are
silently non-functional.

**What was observed:** Tapped "▶️ Play" — audio played correctly.
Tapped "⏹️ Stop" — audio kept playing, nothing happened. Changed the
Speed dropdown — no audible change in playback speed.

**Root cause, confirmed via code read (`app.js` + `generate.py`):**
This page has TWO entirely separate, non-communicating audio systems:
1. **`KokoroAudio`** — plays real pre-generated MP3 clips via an
   `Audio` element (confirmed live: `l0-w1-d1-shadow.mp3` etc. exist
   and return HTTP 200). The Shadowing page's "▶️ Play" button calls
   `KokoroAudio.play(id, passage)` — this is what actually played.
2. **`TTS`** — the browser's `SpeechSynthesis` API (a completely
   different, software voice fallback used only when an MP3 is
   missing/fails to load).

The page's "⏹️ Stop" button is wired to `TTS.stop()`, which only calls
`speechSynthesis.cancel()` — it has ZERO effect on `KokoroAudio`'s
actual `Audio` element that's playing the real MP3. Similarly, the
Speed `<select>` is wired to `TTS.setRate(this.value)`, which only
sets a rate value used by the `SpeechSynthesis` fallback — it never
touches `KokoroAudio`'s `Audio.playbackRate`, and even if it did,
`KokoroAudio.play()` doesn't accept or apply a live rate change to an
already-playing `Audio` object at all.

**Why this matters:** every level/week/day's Shadowing page uses this
same generator function (`gen_shadowing()`), and per D014's Accent-
page finding, `gen_accent()` likely has the same Play button (needs
confirming — the Accent page tested first didn't have a Stop/Speed
control visible in the walkthrough, only Shadowing does per
`generate.py`'s markup). This is at minimum a Shadowing-page-wide gap
across all 4 levels.

**Proposed fix (not yet applied, deferred per the owner's batching
decision):** wire the Stop button to `KokoroAudio.stop()` (which
already exists and correctly pauses the current `Audio` AND calls
`TTS.stop()` as a fallback — so simply changing the onclick handler
from `TTS.stop()` to `KokoroAudio.stop()` may be sufficient). For
Speed: either (a) have `KokoroAudio.play()` accept and apply a rate
to the `Audio` element consistently, and have the speed selector call
into `KokoroAudio` rather than `TTS` directly, or (b) restart
playback from the current position at the new rate when changed
mid-play. Needs a fresh live re-test after the fix to confirm both
controls actually affect the real MP3 playback, not just the unused
`SpeechSynthesis` fallback.

**Decision (owner, 2026-07-15):** Log now, defer the fix. Batch with
D012, D013, D014 for one fix-everything pass at the end of the Hisn
campaign, before H7's Go/No-Go sign-off.

**Fix applied (2026-07-15):** rewired the Shadowing page's Stop button
and Speed `<select>` (in `generate.py`'s `gen_shadowing()`) from
`TTS.stop()`/`TTS.setRate()` to `KokoroAudio.stop()`/
`KokoroAudio.setRate()`. Added a `setRate()` method to `KokoroAudio`
in `app.js` that applies the rate live to the currently-playing
`Audio` element's `playbackRate` AND remembers it for the next
`play()` call; `stop()` already existed and correctly pauses the
`Audio` element (plus calls `TTS.stop()` as a harmless fallback, in
case the SpeechSynthesis path happened to be the one actually
playing). Regenerated all 266 `shadowing.html` pages (one per level/
week/day) via `scripts/generate.py` so the fix is in the committed
HTML output, not just the generator source — diffed the regeneration
and confirmed ONLY those 266 files changed, each with exactly the two
rewired `onclick`/`onchange` attributes, no other page type affected.
Merged via `empire-dojo` [PR #23](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/23) — confirmed landed on `main`
(sampled `site/l0/week1/day1/shadowing.html` directly on `main`,
shows `KokoroAudio.stop()`/`KokoroAudio.setRate()`).

**Deployed and live-verified (2026-07-15):** deployed via `npx
wrangler pages deploy site --project-name=empire-practice`. Confirmed
server-side on the real production domain, on two different
level/week/day combinations (`l0/week1/day1` and `l2/week5/day3`, to
rule out a one-page fluke): both now show
`onclick="KokoroAudio.stop()"` and
`onchange="KokoroAudio.setRate(this.value)"` in the served HTML.

**Status:** ✅ **RESOLVED — fixed, merged, deployed, and server-side
verified live** across multiple pages/levels. A quick hands-on click
of Stop/Speed during H6 is still worthwhile to confirm the *audible*
behavior end-to-end, but the markup change (the actual root cause) is
confirmed shipped correctly.

---

## D016 — "Done" checkbox gives zero visible feedback on the same page (silent no-op until reload/navigation) (Minor, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H2.2 (manual mobile walkthrough with the owner, L0
Day 1, Shadowing exercise, real iPhone Safari).
**Severity:** Minor — the underlying data write DOES work correctly
(confirmed via code read), but the complete absence of visible
feedback on the same page load creates genuine doubt for a student
about whether their tap registered at all — exactly what the owner
experienced ("clicked it but still showing nothing").

**What was observed:** Checked the "Done ✅" checkbox on the
Shadowing page. No visible change anywhere on the page — no
highlight, no counter update, nothing.

**Root cause, confirmed via code read (`app.js`):**
- The checkbox's `onchange` handler calls ONLY
  `Progress.markDone(level, week, day, type)`, which silently writes
  a `localStorage` key (`empire_l0_w1_d1_shadowing = 'done'`) and
  returns nothing — no DOM update of any kind.
- The page DOES have a visible "✅ X/4" counter and progress bar
  (`Gamification._renderProgressBar()`, part of the gamification bar
  at the top of every exercise page) that would reflect this exact
  change — but that function is called exactly ONCE, inside
  `Gamification.init()` on `DOMContentLoaded` (confirmed: only one
  call site in the entire file, at page-load time). The checkbox's
  `onchange` handler never calls `_renderProgressBar()` again, so the
  counter never updates in response to the checkbox on the SAME page
  load — it would only reflect the change after a reload or
  navigating to another page and back.
- Net effect: the localStorage write genuinely happens (confirmed by
  reading the code path directly), but there is no way for a student
  to see visible confirmation without leaving and returning to the
  page — functionally indistinguishable from "did nothing" in the
  moment, exactly matching the owner's own description.

**Scope:** Same `done-section` checkbox markup + `onchange` pattern is
used identically on Accent, Shadowing, Listening, and Vocab pages
(confirmed via `generate.py` — 4 near-identical `done-section` lines,
one per exercise type) — this is a site-wide gap, not page-specific.

**Proposed fix (not yet applied, deferred per the owner's batching
decision):** have the checkbox's `onchange` handler also call
`Gamification._renderProgressBar()` (and ideally
`Gamification._checkDailyCompletion()`, so the confetti celebration
can fire immediately when the 4th exercise is checked, rather than
only on a future page load) immediately after `Progress.markDone()`,
so the visible counter/progress bar updates instantly on the same
page. Needs a fresh live re-test to confirm the counter visibly
updates immediately after checking the box, on the same page load,
without any reload.

**Decision (owner, 2026-07-15):** Log now, defer the fix. Batch with
D012, D013, D014, D015 for one fix-everything pass at the end of the
Hisn campaign, before H7's Go/No-Go sign-off.

**Fix applied (2026-07-15):** `Progress.markDone()` in `app.js` now
re-runs `Gamification._renderProgressBar()` AND
`Gamification._checkDailyCompletion()` immediately after writing to
`localStorage` (guarded with a `typeof Gamification !== 'undefined'`
check, though it's always defined by the time a checkbox can be
clicked — `Gamification` is a `const` declared before
`DOMContentLoaded`, and `markDone()` only runs from user interaction
after the page has fully loaded). Fixed once, at the source
(`markDone()` itself), rather than editing all 4 near-duplicate
`done-section` `onchange` handlers in `generate.py` — so this applies
uniformly to Accent/Shadowing/Listening/Vocab without needing a
regeneration pass (confirmed no HTML markup changes were needed or
made for this defect). Merged via `empire-dojo` [PR #23](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/23) — confirmed landed on `main`.

**Deployed (2026-07-15):** deployed via `npx wrangler pages deploy
site --project-name=empire-practice`; confirmed server-side that the
live `app.js` on `practice.empireenglish.online` now contains the
`markDone()` re-render logic.

**Live re-tested (2026-07-16):** the owner checked a "Done" checkbox
on a real exercise page as part of H6's Tier 1 device re-test pass,
and confirmed: **"yes"** — the progress bar/task counter at the top
of the page visibly updates immediately, right after checking it.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified by the owner directly clicking "Done" on the real site.



---

## D017 — "Done" checkbox never restores its checked state on return visits; completion is invisible on every subsequent page load (Major, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H2.2 (manual mobile walkthrough with the owner, L0
Day 1, Listening exercise, real iPhone Safari).
**Severity:** Major — distinct from, and worse than, D016. D016 was
"no feedback on the SAME page load." This is "no feedback EVER, on
ANY subsequent visit" — the checkbox always renders unchecked
regardless of whether the exercise was genuinely already completed,
for the entire life of the page.

**What was observed:** Checked "Done" on the Listening exercise,
navigated to the next exercise, then navigated back to Listening.
The "Done" checkbox showed as UNCHECKED again, even though the owner
had definitely checked it moments before. Owner's own words: "i
donnt know how it works" — a real, justified loss of trust in whether
the feature works at all.

**Root cause, confirmed via code read (`generate.py` + `app.js`):**
1. `generate.py` emits the checkbox with NO `checked` attribute, ever,
   regardless of stored state:
   `<input type="checkbox" class="checkbox" onchange="...">` — this
   is a static, server/build-time-generated string with zero
   awareness of what's in `localStorage` (which is a browser-only,
   client-side store the Python generator script cannot see at build
   time — this is expected and correct on its own).
2. **The gap is client-side**: confirmed via full-file search of
   `app.js` that `Progress.isDone()` is called in exactly TWO places
   — `_renderProgressBar()` (the counter) and `_checkDailyCompletion()`
   (the confetti trigger) — and NEVER to set a checkbox's `.checked`
   property on page load. There is no code anywhere that reads
   `localStorage` on `DOMContentLoaded` and syncs it back to the
   `done-section` checkbox's visual state.
3. **Net effect**: `markDone()` genuinely writes the completion record
   correctly (confirmed in D016's investigation) and that data DOES
   get correctly read elsewhere (the counter, the confetti trigger) —
   but the checkbox itself is a one-way, write-only control with no
   corresponding read-back. Every fresh page load renders it
   unchecked from scratch, forever, even for an exercise completed
   5 minutes or 5 weeks ago.

**Relationship to D016:** these are two distinct, separately-real bugs
in the same small feature:
- D016 = the visible PROGRESS COUNTER doesn't update within the same
  page load after checking the box (but does update on the next
  full page load elsewhere, e.g. navigating to a different page and
  back, since `_renderProgressBar()` re-runs on ITS OWN
  `DOMContentLoaded`).
- D017 = the CHECKBOX ITSELF never reflects prior completion on any
  subsequent load of the SAME page, ever — a completely separate,
  and more serious, gap. Fixing D016 alone would NOT fix this.

**Why this matters for real students:** a student reviewing their own
progress by re-visiting a day/exercise (entirely normal behavior) has
no reliable visual way to tell if they already did it — undermines
trust in the entire tracking system, exactly as the owner described.

**Proposed fix (not yet applied, deferred per the owner's batching
decision):** on `DOMContentLoaded` (or inside `Gamification.init()`,
alongside the existing `_renderProgressBar()` call), detect the
current page's level/week/day/type from the URL (the same regex
pattern already used in `_renderProgressBar()`/`_checkDailyCompletion()`)
and explicitly set the `done-section` checkbox's `.checked = true` if
`Progress.isDone(...)` returns true for it. Combining this fix with
D016's fix (re-render the counter on checkbox change) would make the
whole feature consistent in both directions — reflects prior state on
load, AND reflects new state immediately on change.

**Decision (owner, 2026-07-15):** Log now, defer the fix. Batch with
D012, D013, D014, D015, D016 for one fix-everything pass at the end
of the Hisn campaign, before H7's Go/No-Go sign-off.

**Fix applied (2026-07-15):** added `Gamification._restoreDoneCheckbox()`,
called from `Gamification.init()` alongside the existing
`_renderProgressBar()`/`_checkDailyCompletion()` calls. It detects the
current page's level/week/day from the URL (same regex pattern used
elsewhere: `/\/(l\d)\/week(\d+)\/day(\d)/`), detects the exercise type
from the URL's trailing path segment, and sets the `done-section`
checkbox's `.checked` property from `Progress.isDone(...)` on every
page load — combined with D016's fix, the checkbox now reflects prior
state on load AND reflects new state immediately on change. Merged
via `empire-dojo` [PR #23](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/23) — confirmed landed on `main`.

**Deployed (2026-07-15):** deployed via `npx wrangler pages deploy
site --project-name=empire-practice`; confirmed server-side that the
live `app.js` on `practice.empireenglish.online` now contains
`_restoreDoneCheckbox()`, called from `Gamification.init()`.

**Live re-tested (2026-07-16):** the owner marked an exercise done,
navigated away and back (the exact original repro) as part of H6's
Tier 1 device re-test pass, and confirmed: **"the 'Done' checkbox
still show as checked when I returned."**

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified by the owner repeating the exact original repro on the
real site.



---

## D018 — H3.2 live trace: Discord DM delivery to test account failed (likely test-account limitation, NOT a confirmed app defect — but the failure-handling path itself is confirmed working correctly)

**Found during:** H3.2 (Discord → Telegram → Discord Nour escalation
trace, live, with the owner actively participating).

**What was tested:** Temporarily enabled the `nour_escalation` flag
(confirmed `False`/disabled in production beforehand, restored to
`False` immediately after the test — zero lasting config change),
then called `nour_escalation.escalate_to_owner()` for the "Empire
Ghost" test account (`discord_id` `1526224028191162631` — a real
Discord snowflake with genuine guild presence, not a synthetic
`GHOST_TEST_` ID, since this trace needs a real Discord DM delivery
at the end). A real Telegram alert was sent to the owner's ops chat;
the owner replied to it directly, as intended.

**What happened:** The owner received a **"⚠️ Delivery failed"**
alert back on Telegram: "Couldn't deliver to Empire Ghost — they may
have DMs off, left the server, or something else went wrong."

**Root cause, confirmed via live production logs at the exact
timestamp:**
```
[ERROR] empire-bot.nour.escalation: Nour escalation reply: failed to
DM 1526224028191162631: 400 Bad Request (error code: 50007): Cannot
send messages to this user
[WARNING] empire-bot.ops_poller: ops_poller: failed to forward owner
reply to Empire Ghost (1526224028191162631)
```
Discord's own API rejected the DM attempt with error 50007, which per
Discord's own documented error codes means the target user has DMs
disabled (server-wide or specifically for this server), has blocked
the bot, or otherwise cannot receive bot DMs — this is a REAL,
externally-imposed Discord-side restriction, not something the bot's
code caused.

**What this DOES confirm (high confidence, directly observed):**
1. The Telegram alert was sent and received correctly, with correct
   content (student name, level, streak, message, "reply to respond
   as Nour" instructions).
2. The owner's Telegram reply was correctly matched to the specific
   pending escalation (`telegram_message_id=39`) via `reply_to_message`
   — confirmed the row exists in `pending_escalations` for the right
   `discord_id`.
3. `forward_reply_to_student()` was correctly invoked for the right
   member.
4. **The failure-handling path itself worked exactly as designed**:
   per `ops_poller.py`'s own documented M2.4 behavior, on a delivery
   failure the escalation is deliberately NOT marked resolved
   (confirmed via direct query: `resolved=0`, still pending) — so the
   owner correctly sees it as outstanding rather than silently losing
   track of it — and the owner correctly received the "Delivery
   failed" warning with an actionable next step ("check Discord
   directly"). This is a genuinely well-designed failure path, and it
   fired correctly.

**What remains genuinely UNCERTAIN (being explicit about the limits
of what this session's investigation can conclude):**
- Whether "Empire Ghost" specifically has DMs disabled (an account/
  privacy-setting fact about this one test account) versus some other
  cause (e.g. no longer a guild member, blocked the bot specifically)
  could not be independently confirmed from the sandbox — doing so
  would require direct access to that Discord account's own settings
  or the Discord server's member list, neither of which this session
  has direct access to.
- A supporting, but not conclusive, data point: querying
  `nour_conversations` for any prior successful Nour-to-student
  message shows ZERO for "Empire Ghost" ever, while the OTHER ghost
  account ("M.A.C.A.L EMPIRE") DOES have 2 prior successful messages
  on record. This is consistent with "Empire Ghost" having DMs
  disabled or otherwise unreachable as a standing account
  characteristic (not something this test caused), but is not
  definitive proof on its own.
- **This means H3.2's actual round-trip (reply correctly delivered TO
  a student) is NOT yet confirmed working end-to-end** — only the
  send-alert, match-reply, and failure-handling legs are confirmed.
  The final "successful delivery" leg remains unverified.

**RETRY EXECUTED (2026-07-15, same session), CONCLUSIVE RESULT**:
re-ran the identical trace using "M.A.C.A.L EMPIRE" (`discord_id`
`1502586616131223662`), the account with a PROVEN prior successful
Nour delivery already on record. Same safe pattern: temporarily
enabled `nour_escalation` (confirmed OFF beforehand), restored OFF
immediately after, regardless of outcome.

- Real Telegram alert sent for "M.A.C.A.L EMPIRE" — owner received and
  replied to it directly, same as the first attempt.
- Owner's Telegram confirmation this time: **"✅ Delivered — Your
  reply was delivered to M.A.C.A.L EMPIRE."**
- **Independently verified against live production logs and DB state
  (not just trusting the confirmation message)**:
  ```
  [INFO] empire-bot.ops_poller: ops_poller: forwarded owner reply to
  M.A.C.A.L EMPIRE (1502586616131223662)
  ```
  `pending_escalations` row for this attempt: `resolved=1` (correctly
  flipped from `0`→`1` on success, contrasting exactly with the first
  attempt's correctly-preserved `resolved=0` on failure).
  `nour_conversations` shows the new row: `role='nour'`,
  `message='ok'`, `intent='owner_reply'`, `confidence=1.0` — the
  owner's reply correctly logged as a distinct, tagged event, verified
  distinguishable from this same member's own prior REAL Nour AI
  conversation history already in that table (`id=3,4`, from
  2026-07-14 — confirming this account is a genuinely active,
  previously-exercised test account, not a fabricated one for this
  test alone).

**CONCLUSION: all 4 legs of H3.2 are now confirmed working end-to-end.**
The first attempt's failure was correctly isolated to "Empire Ghost"
specifically being unreachable (consistent with the DMs-disabled/
blocked-bot theory raised earlier) — NOT a defect in the escalation,
matching, forwarding, or resolution-tracking code, all of which are
now proven correct via two independent real-world outcomes (one
correct failure-handling, one correct success-handling, using the
exact same code path both times).

**No code fix needed** — the pipeline itself is correct. Test data
(the second attempt's `pending_escalations` row and its
`nour_conversations` test message) cleaned up from production
afterward; the first attempt's genuinely-still-open row was also
cleaned up (correctly not touching that member's real prior
conversation history in the process). 0 residual test rows confirmed.

**Status:** ✅ **RESOLVED (via retry)** — the escalation/reply/forward/
resolve pipeline is confirmed working correctly end-to-end. The
original "Empire Ghost" failure was a real-world Discord-side
rejection specific to that one test account (not a code defect) and
requires no fix. H3.2 can now be marked complete.



---

## D019 — Methodological finding: `docker exec` test scripts run in a SEPARATE process from the live bot, so module-level (in-RAM) state is NOT actually shared (Info, corrects earlier session narrative, no app defect)

**Found during:** H4.1 (AI fallback chain trace) — the real
`ops_monitoring.track_groq_failure()` function was called 5 times
(its own documented alert threshold) via a `docker exec` script, and
the module's own throttle logic should have allowed a real Telegram
alert to fire, but no alert was observed in the live bot's logs.

**Investigation, and root cause confirmed via direct verification
(not assumed):**
- `docker top empire-english-bot` shows exactly ONE process running
  in the container: `python run.py` (the real, live bot).
- A `docker exec ... python3 <script>` invocation spawns a genuinely
  SEPARATE Python process (confirmed via `os.getpid()`/`os.getppid()`
  inside the exec'd script — different PID, PPID `0`, i.e. not a
  child of the bot process at all) inside the same container's
  filesystem/network namespace, but with its OWN separate Python
  interpreter and memory space.
- This means: any Python **module-level variable held only in RAM**
  (e.g. `ops_monitoring._groq_failures`, a plain list;
  `_groq_alert_sent_at`, a float) that a `docker exec` script reads or
  mutates is a SEPARATE COPY, entirely disconnected from the live
  bot's own in-memory copy of that same module. Mutating it via
  `docker exec` has zero effect on the live bot's actual runtime state.

**What this DOES NOT affect (confirmed unaffected, re-examined
specifically because of this finding, not assumed safe)**: anything
that reads/writes the **SQLite database file on disk** is genuinely
shared correctly between the live bot process and any `docker exec`
script, since both access the identical file via `database._connect()`
(confirmed: `is_feature_enabled()`, `set_feature_flag()`, and every
other `database.py` function does a fresh `_connect()` + query with
zero module-level caching). This means the following EARLIER results
in this campaign remain valid and are NOT retroactively in question:
- H1.4 (flag toggling), H1.5 (kill switch drill) — both use
  `database.is_feature_enabled()`/`set_feature_flag()`, DB-backed.
- D010's live flag-toggle verification, H2.6-H2.8's adversarial API
  testing — all DB- or real-HTTP-request-based.
- H3.1, H3.3, H3.4 — all confirmed via direct DB queries and/or real
  HTTP calls to the live public API, not module-level state.
- H3.2's escalation trace — `pending_escalations`/`nour_conversations`
  are DB tables; the ACTUAL Telegram/Discord API calls made by
  `escalate_to_owner()`/`forward_reply_to_student()` (invoked directly
  from the `docker exec` script) are real, independent HTTP calls to
  Telegram's/Discord's own servers — genuinely real regardless of
  which process made them. Fully valid.

**What THIS DOES affect (re-examined and corrected)**: H4.1's specific
sub-check of `track_groq_failure()`'s own alert-throttling behavior
(a module-level `_groq_failures` list + `_groq_alert_sent_at` float,
by design, since it's meant to persist across many real Groq call
sites within one running process — not a bug in that design, just not
exercisable via a separate process the way this test attempted it).
The actual ALERT-SENDING mechanism itself (`ops_hub.send_ops_alert()`)
was independently and correctly verified as genuinely working in H3.5
(direct calls returned real Telegram `message_id`s) — so this doesn't
cast doubt on whether alerts CAN be sent, only on whether THIS
SPECIFIC sub-test actually exercised the live bot's real threshold-
counting state.

**Corrected understanding of H4.1's results**: the core fallback-chain
logic test (Groq fails → Gemini succeeds → correct text returned) IS
still valid, since `_generate_response()`'s control flow and return
value are pure-function-like (no reliance on cross-call module state)
and were exercised directly, in-process, within the SAME test script
that also monkey-patched the underlying calls — there's no
cross-process gap for THAT specific check. Only the THRESHOLD-COUNTING
sub-check (H4.1b) is the part affected by this finding, and it has
been re-scoped accordingly (see `tasks.md`).

**Action taken:** documented this finding transparently rather than
silently re-running with a workaround, per this campaign's own
standard. For any FUTURE test that specifically needs to exercise the
LIVE bot process's own module-level state (not just its DB-backed
state), the correct approach would be to either (a) test the logic
via a pure-function unit test that doesn't depend on the live
process's specific state, as most of this campaign already correctly
does, or (b) if genuinely necessary, coordinate a live test during a
real, deliberate bot restart/observation window — not attempted here,
since H3.5 already independently confirmed the underlying Telegram
alert mechanism works, making this unnecessary for Hisn's purposes.

**Status:** ℹ️ **Info / no action needed** — corrects the scope of
H4.1's threshold sub-check, confirms no other campaign result is
affected, no app defect found or implied.

---

## D020 — Nour Study Tips: the actual weekly AI-generation task (W4.2) was never implemented; every real student silently gets only generic fallback tips, forever (Major, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H4.3 (repeating the 3-state AI fallback matrix for
pronunciation scoring, Nour study tips generation, and weekly
self-review — while locating the actual tip-generation function to
test its fallback chain).

**Severity:** Major. Not a crash, not a broken endpoint — the API
gracefully falls back exactly as designed. The real problem is that
the feature this fallback exists FOR was never built: `wuslah_nour_tips`
is a real, enabled-by-default feature flag, documented in
`flag_registry.py`, `ecosystem-harmony/design.md`, and `api_server.py`'s
own docstrings as "AI-generated weekly study tips" — but there is no
code anywhere in the codebase that ever generates or stores a
personalized tip. Every real student, forever, silently receives only
the generic level-appropriate fallback tips, with zero indication to
anyone (admin or student) that the "AI-generated" half of this
feature doesn't exist.

**What was searched (exhaustive, not a quick grep)**: every `.py` file
under `bots/discord-learning-bot/src/` for any function that writes to
`nour_study_tips`, any function name containing "tip," and the string
`nour_study_tips` itself across the entire `empire-nexus` repo
(excluding `.git`). Result:
- `database.py`: defines the `CREATE TABLE nour_study_tips` schema
  only — no INSERT statement anywhere in this file either.
- `api_server.py`: reads FROM `nour_study_tips` in `get_dashboard()`
  and `get_nour_tips()` — never writes to it. Its own code comment is
  explicit and now confirmed INCORRECT: *"Tips are pre-generated
  weekly (by ops_monitoring's tip generation task) and cached in the
  nour_study_tips table."* — **no such task exists in
  `ops_monitoring.py`** (confirmed: that file's only `async def`
  functions are `track_groq_failure`, `notify_bot_restart`,
  `notify_database_error`, `send_weekly_report`, `check_conversion_ready`,
  `check_churn_risk`, `send_monthly_summary` — none of them touch
  `nour_study_tips`).
- **Zero rows exist in the live production `nour_study_tips` table**
  (confirmed via direct query: `SELECT COUNT(*) FROM nour_study_tips`
  → `0`) — not "hasn't run yet this week," genuinely never populated,
  ever, since the table was created.

**Root cause, confirmed via the source spec itself**
(`ecosystem-harmony/tasks.md`, Phase W4): **W4.2 ("Implement weekly
tip generation task") is the ONLY unchecked task in the entire W4
phase** — W4.1 (table), W4.3 (endpoint), W4.4 (dashboard card), W4.5
(feature flag), and W4.6 (generic fallback tip bank) were all built
and are all confirmed working correctly (verified across H2.3's
dashboard walkthrough and H2.6-H2.8's API testing). This is a
genuinely half-shipped feature: every piece of "wrapper" scaffolding
around the AI generation step was completed, but the actual core
step — the thing the feature flag and the whole endpoint are NAMED
for — was never written. `api_server.py`'s docstring describing a
generation task that doesn't exist suggests this gap has been
silently invisible even to whoever wrote that comment, likely written
optimistically ahead of the implementation and never corrected once
W4.2 was skipped.

**Why H2.3/H2.6-H2.8 didn't catch this earlier**: both correctly
verified the READ side and the FALLBACK path (empty table → generic
tips shown, exactly as designed) — which is the CORRECT behavior for
an empty table, whether that emptiness is "not generated yet this
week" (benign, expected) or "will never be generated, ever" (this
defect). Distinguishing those two required looking for the WRITE
side, which only H4.3's specific focus on locating and fallback-
testing the generation function surfaced.

**Proposed fix (not yet applied, deferred per the owner's batching
decision):** implement W4.2 for real — a scheduled `@tasks.loop`
(Sunday 8 AM Dubai, before the weekly report, per the original spec's
own timing note) that, for each active member, gathers pronunciation
scores/SRS accuracy/streak/difficulty/conversation themes, calls the
AI fallback chain (Groq → Gemini → skip, consistent with this
codebase's other AI call sites) to generate exactly 3 tips (max 100
chars each per the spec), and INSERTs them into `nour_study_tips`.
Alternatively, if this feature is no longer a priority, the more
honest fix might be to explicitly retire it (remove the flag, the
"AI-generated" framing in the endpoint/dashboard, and rely solely on
the generic tip bank on purpose) rather than leave a half-built
feature silently masquerading as complete — a product decision for
the owner, not purely a coding one.

**Decision (owner, 2026-07-15):** confirmed not a priority/blocker —
real students still receive SOME tips today (the generic fallback
bank), just not personalized AI-generated ones, so there is no broken
student-facing experience right now, only a missing enhancement.
Explicitly deferred to the same end-of-campaign discussion as
D012-D017, D019 — the owner and this session will discuss the
fix-vs-retire product decision together at that point, not separately
or urgently.

**Status:** ✅ **RESOLVED (2026-07-16, via Masar M2 — Nour's Weekly
Growth Letter).** Per the owner's own later decision (documented in
`.kiro/specs/masar/requirements.md`), the product-decision fork this
defect explicitly needed (implement W4.2 for real vs. retire the
"AI-generated" framing) was resolved in favor of building it for
real — and treating it as one instance of a bigger pattern (alongside
D012) rather than a narrow patch, via the Masar (مسار) initiative.
The actual fix: `nour_growth_letter_task()` (a new weekly
`@tasks.loop`, Wednesday 11:00 Asia/Dubai — deliberately spread away
from the existing Sunday cluster of weekly tasks) genuinely gathers
per-student signals (`narrative_engine.gather_signals()`: memories,
milestones, pronunciation trend, SRS mastery, conversation themes,
streak/completion) and calls the SAME proven Groq→Gemini→template
fallback chain used elsewhere in this codebase
(`narrative_engine.build_growth_letter()`) to generate a real,
personal weekly letter — replacing `nour_study_tips`/`/api/nour-tips`
entirely (left in place, inert, explicitly documented as legacy, not
silently orphaned).
**A real bug was caught and fixed during this phase's own testing,
before it ever reached production:** both the new scheduled task and
the new `/api/growth-letter` endpoint initially had an early
`is_feature_enabled("masar_growth_letter")` check with no
`discord_id` — which would have silently broken a restricted-
allowlist (beta-squad) rollout for everyone, including allowlisted
members. Caught via a deliberate test, fixed in both places before
merge.
Live-verified in PRODUCTION on 2026-07-16 using the owner's own real
`bioroma` Ghost Testing Discord account (not a synthetic ID — this
verification specifically needed genuine Discord DM delivery, same
reasoning as Hisn H3.2): seeded rich real-shaped test data (4-day
streak, a milestone, an improving pronunciation trend, a stored
memory), flag scoped ONLY to this one account via the allowlist,
generated a real letter (`source: "ai"`, not the fallback) that
genuinely referenced this student's actual streak ("4 أيام متتالية")
and actual pronunciation average ("68%") — not generic filler —
delivered it as a real Discord DM via the bot's own API (confirmed
via a real message ID), and confirmed the dashboard's
`/api/growth-letter` returned the byte-identical letter text,
structurally guaranteeing the two surfaces can't diverge (same cached
row, same as M1's dashboard/`!progress` guarantee). **Owner
personally confirmed receiving the DM** ("i got the message") — the
one part of this verification that couldn't be checked from the
agent side alone. Test data fully cleaned up afterward (`members`
back to 0 rows), flag restored to default OFF. See
`.kiro/specs/masar/tasks.md`'s M2 phase for the full implementation
record. PRs:
[empire-nexus#173](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/173),
[empire-dojo#27](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/27).



---

## D021 — Absence-recovery escalation ladder is structurally broken: days 3/5/7+ tiers are unreachable dead code, every absent student only ever gets the "day 2" message forever (Major, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H4.4 (directly invoking each Nabd notification
function against a test member and reviewing captured content for
correctness — specifically while testing all 4 documented absence
tiers side by side).

**Severity:** Major. Not a crash — the function runs without error
every time. The real problem is a genuine content/logic defect: the
system's own documented 4-stage escalation ladder (gentle DM → buddy
prompt → comeback mini-task → final DM) never actually escalates.
Every student who goes quiet for 3, 5, 7, or 30 days receives the
exact same "day 2" gentle nudge, forever — the buddy-alert, comeback-
mini-task, and final "we still have your data" messages are dead code
that can structurally never execute for a continuously-absent member.

**What was observed:** Ran `check_absence_recovery()` (the real,
unmodified function) against the same test member set to 2, 3, 5, and
8 days inactive in turn. Expected 4 different message bodies (per the
function's own docstring: "Day 2: bot DM (gentle) / Day 3: buddy
prompt / Day 5: comeback mini-task DM / Day 7+: final DM"). Actual
result: the day-3 test correctly triggered the buddy-prompt code path
(confirmed separately, working), but **both the day-5 and day-7 test
runs produced the IDENTICAL day-2 message text** — not their own
documented tier's content at all.

**Root cause, confirmed via careful read of `features.py`'s
`check_absence_recovery()` control flow:**
```python
if days_inactive >= 2 and not database.was_notification_sent(discord_id, "absence_day2", today):
    ...  # day 2 message
elif days_inactive >= 3 and not database.was_notification_sent(discord_id, "absence_day3", today):
    ...  # day 3 message
elif days_inactive >= 5 and not database.was_notification_sent(discord_id, "absence_day5", today):
    ...  # day 5 message
elif days_inactive >= 7 and not database.was_notification_sent(discord_id, "absence_day7", today):
    ...  # day 7+ message
```
This is an `if / elif / elif / elif` chain. `was_notification_sent(discord_id, "absence_day2", today)`
only checks whether the DAY-2 notification specifically was sent
TODAY — it has no awareness of days 3/5/7 at all, and `today` changes
every single day this loop runs. For ANY member who is absent 3+ days,
`days_inactive >= 2` is trivially always true, AND `absence_day2` was
never sent *today* (today is always a new day) — so **the first `if`
branch's condition is unconditionally true for every absent member on
every day**, and because this is `elif` (not independent `if`
statements), the day-3/5/7 branches below it can **never be reached
by a member whose absence just keeps growing** — they are correctly
reachable only in the impossible scenario where `days_inactive` is
already >= 3/5/7 on the very day this function is first observing
that member (which itself would only reach day-3+ if the loop had
somehow skipped days 2 through the target day entirely, which it
doesn't since it runs daily).

**Confirmed empirically, not just theoretically**: the day-5 test
member (a fresh member set to 5 days inactive, never previously
processed by this function in this test run) produced the exact
day-2 message text, byte for byte identical to the actual day-2 test's
output. Same for the day-7+ test. Only day-3 (which was tested with a
member whose `days_inactive` was exactly 3 — the SECOND `elif` branch,
which the FIRST `if`'s own `absence_day2`-sent-today guard does not
retroactively block since it's a different notification type checked
against `today`) happened to route correctly in this specific test
sequence — but this is fragile, not a real fix, and would not hold up
across real multi-day absence patterns where `absence_day2` was
already sent on an earlier day and thus "not sent today" is trivially
true again on every later day too.

**Why this matters for real students:** the entire POINT of an
escalation ladder is that a student ignored for a week gets
progressively more serious/different outreach than one who missed a
single day. As written, a student absent for a month would receive
the identical gentle "even one task today is better than none" DM
every single day, forever — the buddy never gets alerted, the
comeback mini-task never gets offered, and the "everything is still
here, reach out to #support" final message never arrives. This
silently defeats the feature's entire stated purpose.

**Proposed fix (not yet applied, deferred per the owner's batching
decision):** restructure the tier selection to pick the HIGHEST
applicable tier first, independent of whether that day's specific
notification type was already sent. For example:
```python
if days_inactive >= 7 and not was_sent(..., "absence_day7", today):
    ...  # day 7+
elif days_inactive >= 5 and not was_sent(..., "absence_day5", today):
    ...  # day 5
elif days_inactive >= 3 and not was_sent(..., "absence_day3", today):
    ...  # day 3
elif days_inactive >= 2 and not was_sent(..., "absence_day2", today):
    ...  # day 2
```
(highest threshold checked FIRST, so a day-8 absence correctly lands
in the day-7+ branch instead of falling into day-2's always-true
condition) — or equivalently, compute the correct tier via a small
helper function/lookup rather than a top-down `if/elif` chain ordered
low-to-high. Requires a fresh re-test (repeating this exact H4.4
methodology: simulate days 2/3/5/8 side by side, confirm 4 genuinely
DIFFERENT message bodies) after the fix, not just a code read, per
this campaign's own standing discipline.

**Decision (owner, pending):** logged now, recommend batching with
D012-D017/D020 for the end-of-campaign fix pass — this is a pure
engineering fix (unlike D020), so it fits the existing batch plan
without needing a separate product discussion.

**FIXED AND LIVE-VERIFIED (2026-07-15, H7 early-start batch, per the
owner's own suggestion to begin low-risk engineering fixes ahead of
H6):** Reordered `check_absence_recovery()`'s tier chain to check
the HIGHEST threshold first (day 7+ → day 5 → day 3 → day 2),
matching the proposed fix above exactly. Removed the now-duplicated
old low-to-high branches. Confirmed the file compiles cleanly
(`py_compile`).

**Live re-verification, repeating H4.4's exact methodology** (not
just a code read): temporarily swapped the fixed `features.py` into
the running container (a `docker exec` test process only — confirmed
via D019's own finding that this never touches the live bot's
already-loaded module in memory) and re-ran the day 2/3/5/8 side-by-
side simulation with 4 FRESH members (one per tier, avoiding H4.4's
own test-design pitfall of reusing a member/key across tiers).
**Result: 5/5 checks PASS** — all 4 tiers now produce genuinely
different, tier-correct message content (day 2 gentle DM, day 3 buddy
prompt, day 5 comeback mini-task, day 7+ final DM), confirmed by
checking each captured message for its own tier's distinguishing text
(e.g. day 5's message contains "رجوع سريعة", day 7's contains "أسبوع
كامل"). Restored the original file on the server immediately after
verification (confirmed via grep: 0 matches for the fix marker),
since the real deployment path is a proper git commit → PR → merge →
`git pull` + rebuild, not a direct file swap — this temporary swap
was only for pre-deploy verification of the fix's correctness.
Test data cleaned up, 0 residual rows confirmed.

**DEPLOYED AND POST-DEPLOY RE-VERIFIED (2026-07-15, same session)**:
PR #142 merged; confirmed the server was still stale (at commit
`15f487f`, far behind) before deploying — `git pull` fast-forwarded to
`19c2f6f`, `docker compose up -d --build` rebuilt and restarted the
container, confirmed healthy (Discord gateway connected, curriculum
loaded, API listening). Re-ran the exact same day 2/3/5/8 verification
against the ACTUAL deployed code this time (not a temporary swap) with
4 fresh Ghost Testing members: **5/5 checks PASS** — all 4 tiers
produce genuinely different, tier-correct content on the real,
running production bot. Test data cleaned up, 0 residual rows.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and re-verified
live against the actual deployed production code. No further action
needed.



---

## H4.5 — Markaz notification content review: EXECUTED, all clean (2026-07-15, session 17)

Directly invoked the 3 real Markaz functions (`markaz_daily_digest`,
`ops_monitoring.send_weekly_report()`, `ops_monitoring.send_monthly_summary()`)
against real seeded data (1 test member with an 8-day streak, 2 tasks
done today, among 4 other pre-existing real member rows). Captured
every message actually sent to the real ops Telegram chat via a
wrapper around the real `send_ops_message()` (not a mock — genuine
Telegram API calls made, `message_id`s returned normally) and scanned
each for unrendered `{template_vars}`, literal `"None"` leaks, and
empty strings.

**Result: 0 issues found across all 3 functions.**
- `markaz_daily_digest`: correctly reflects active students, tasks
  completed, new registrations, escalation count.
- `send_weekly_report()`: correctly computed growth/engagement/
  retention%/level distribution, correct MarkdownV2 escaping
  throughout.
- `send_monthly_summary()`: confirmed its own internal `if now.day != 1: return`
  gate correctly requires simulating the 1st (tested via patching
  `ops_monitoring`'s own `datetime.datetime` import, not bypassing the
  gate) — once past the gate, correctly computed engagement tiers,
  level distribution, and revenue-potential metrics, including
  correctly labeling the previous month's name.

Test member cleaned up afterward, 0 residual rows confirmed.

**Status:** ✅ H4.5 complete, 0 defects found.

---

## D022 — Two real scheduling overlaps found: Sunday 10:00 (3 tasks) and Friday 20:00 (2 tasks) can send multiple DMs to the same student back-to-back (Minor, DEFERRED — fix at end of Hisn with other findings)

**Found during:** H4.6 (static-checking every `@tasks.loop(time=...)`
decorator's configured hour/minute against every other task's
schedule, looking for same-instant collisions).

**Severity:** Minor. Not a crash, not data corruption — `discord.py`'s
`tasks.loop` runs each independently and `asyncio` interleaves them
without conflict. The real issue is pure UX: a student could receive
2-3 separate DMs within moments of each other, which reads as spammy/
uncoordinated rather than a single well-organized outreach.

**Method:** Extracted all 22 `@tasks.loop(time=...)` decorators'
configured hour/minute directly from `bot.py` (regex/manual scan, not
guessed), grouped by exact clock time, then read each colliding
function's OWN internal day-of-week guard (if any) and whether it
sends individual DMs vs. posts to a shared channel vs. is gated by a
flag most students wouldn't have DMs for — to distinguish REAL
same-instant, same-student overlaps from harmless "same clock time,
different actual days" false alarms.

**Collision 1 — Sunday 10:00, 3 tasks:**
- `weekly_assessment()` — Sunday-only guard (`weekday()==6`), DMs
  every active member individually.
- `nabd_absence_check()` → `check_absence_recovery()` — **NO day
  guard, runs every day** — DMs absence-tier-eligible members
  individually (see D021 for that function's own separate bug).
- `nour_weekly_review()` — Sunday-only guard, sends ONE report to the
  OWNER's Telegram (not student DMs) — confirmed via code read this
  does NOT contribute to student-facing overlap, only appeared to
  collide on clock time.
Real overlap: on any Sunday, an active member who is ALSO 2+ days
absent would receive BOTH `weekly_assessment`'s DM AND
`check_absence_recovery`'s DM at the same 10:00 slot — 2 individual
DMs within the same instant. `nour_weekly_review` does not add to this
(owner-facing, not student-facing).

**Collision 2 — Friday 20:00, 2 tasks, both student-facing DMs:**
- `evening_reminder()` — NO day guard (daily), DMs any student with
  1-6 tasks done that day.
- `friday_feedback_survey()` — Friday-only guard, DMs EVERY active
  member individually (confirmed via `features.send_weekly_feedback_survey()`:
  no partial-completion filter at all, unlike `evening_reminder`).
Real overlap: any Friday, a student with 1-6 tasks done that day would
receive BOTH the evening reminder AND the feedback survey DM at the
same 20:00 slot.

**Other same-clock-time groupings checked and confirmed NOT real
overlaps** (different days, or not both student-facing):
- `markaz_weekly_report` (Sun 9:00) + `at_risk_check` (Mon-only, 9:00)
  — different days, never actually coincide.
- `daily_task_post`/`morning_kickstart`/`grammar_card_delivery`
  (6:00/6:05/6:30) — deliberately staggered by design, not a collision.
- `markaz_daily_digest` (7:00) + `monday_progress_report`
  (Monday-only, 7:00) — different scope (owner Telegram vs. Monday-only
  student channel post), and different days for the student-facing one.

**Proposed fix (not yet applied, deferred per the owner's batching
decision):** stagger the colliding times by a few minutes each (e.g.
move `nabd_absence_check` to 10:05, `friday_feedback_survey` to
20:05), OR add a short `asyncio.sleep()`-based stagger inside one of
each pair, OR (more robust) add a shared per-student "already sent N
notifications in the last hour" throttle if this class of overlap is
a recurring concern beyond just these two pairs. Needs a re-run of
this same H4.6 static method after the fix to confirm no new
collisions were introduced by whatever time was chosen.

**Decision (owner, pending):** logged now, recommend batching with
D012-D017/D020/D021 for the end-of-campaign fix pass — this is a pure
scheduling/engineering fix, no product decision needed.

**FIXED (2026-07-15, H7 early-start batch)**: staggered both colliding
pairs by 5 minutes each — `nabd_absence_check` moved from `10:00` to
`10:05` (5 minutes after `weekly_assessment`'s `10:00`), and
`friday_feedback_survey` moved from `20:00` to `20:05` (5 minutes
after `evening_reminder`'s `20:00`). Confirmed the file compiles
cleanly (`py_compile`), then re-ran H4.6's exact static-extraction
method (regex-scanning every `@tasks.loop(time=...)` decorator, this
time against the FIXED file) to confirm: (a) neither new time
(`10:05`, `20:05`) collides with any OTHER scheduled task, and (b)
the two previously-confirmed-harmless same-clock-time groupings
(`7:00` Monday-only vs. daily Markaz digest; `9:00` Sunday-only vs.
Monday-only) are unaffected and still correctly harmless. No live
re-test possible for this specific fix without waiting for a real
Sunday/Friday at the new times — this is a pure schedule-config change
with no logic to exercise ahead of time; correctness is fully
verifiable via the static method already used to find the bug.

**DEPLOYED (2026-07-15, same session, same deploy cycle as D021)**: PR
#143 merged and deployed in the same `git pull` + rebuild as D021.
Confirmed live on the deployed container via direct grep of the
running code: both `nabd_absence_check` (`10:05`) and
`friday_feedback_survey` (`20:05`) show the new, staggered times in
the actually-deployed `/app/src/bot.py`.

**Status:** ✅ **RESOLVED** — fixed, merged, and deployed. A live
confirmation that the new times fire correctly (vs. just being present
in the file) will naturally happen the first real Sunday/Friday after
this deploy — no special live pre-verification is possible or needed
for a pure schedule-time change beyond confirming the deployed file
itself, which is done.



---

## D023 — Ghost Bot is not actually isolated from real students: guild-wide events (join, DM, scheduled loops) fire for BOTH bot instances (Blocker)

**Found during:** H6.1 (Human Experience Walkthrough — new-student join
test, live, with the owner). This was the very first real-world action
of H6: joining the production Discord guild with the `bioroma` Ghost
Testing account via a fresh invite link, to observe the actual
new-student experience end to end.

**What happened:** The owner joined the real guild once. Two entirely
separate DM conversations arrived — one from **"Empire English Bot"**
(the real production bot) and one from **"Empire Ghost"** (the
internal testing bot, `docker-compose.ghost.yml`, intended per its own
header comment to be fully isolated "without any risk to real
students," restricted via Discord channel permission overwrites to a
hidden admin-only category). The owner's own words: "the onboarding is
not professional and so confusing" — and specifically described
getting "one image and one record I did not understand," which traced
directly to Ghost Bot's (stale, outdated) onboarding media step.

**Root cause:** channel permission overwrites only restrict
channel-scoped activity (which channels a bot/member can see or post
in). `on_member_join` is a guild-wide gateway event — Discord delivers
it to every bot connected to the guild, regardless of that bot's
channel permissions, because joining a guild isn't a channel-level
action. Ghost Bot runs the exact same source code as the production
bot (by design — "no fork, no duplicate code," per its own compose
file), including the identical `on_member_join` handler, so it
auto-registered the real join, assigned its own separate buddy, and
sent its own full welcome-DM sequence — completely uncoordinated with
the real bot's simultaneous welcome sequence.

**Confirmed via direct investigation** (not just inferred from the
symptom):
1. `docker ps` on the production server shows `empire-ghost-bot`
   running continuously (`Up 35 hours` at time of discovery) alongside
   `empire-english-bot` — both connected to the same real
   `GUILD_ID=1519797013565280446`.
2. `docker exec empire-english-bot` and `docker exec empire-ghost-bot`
   both show `bioroma`'s `discord_id` registered in their OWN,
   SEPARATE `members` tables, both with `joined_at` timestamps from
   the same real join event, and both with a `buddy_id` auto-assigned
   (production: `M.A.C.A.L EMPIRE`; both processes ran
   `features.assign_buddy` independently).
3. `docker logs empire-ghost-bot` and `docker logs empire-english-bot`
   both show `"Assigned buddy M.A.C.A.L EMPIRE to BioRoMa"` log lines
   at matching timestamps — direct proof both `on_member_join` handlers
   executed for the same real event.
4. Diffing `src/bot.py` between the two containers (`docker exec ...
   md5sum` showed different hashes; a full diff showed why) revealed
   Ghost Bot is also running a **stale build**, dozens of commits
   behind production — missing Nabd (morning/evening DMs, streak
   alerts), Markaz (Telegram digests), Sahel's `!link`, Dhaka's
   `!difficulty`, and using an OLD version of the onboarding-media step
   that sends a PNG attachment + MP3 audio clips (the "image and
   record" the owner couldn't parse), since replaced in production
   with a cleaner text-only journey map.
5. Ghost Bot's `.env.ghost` has `TELEGRAM_ALERT_CHAT_ID=` (blank) — so
   its copy of `on_ready()`'s scheduled loops (which the current code
   starts unconditionally) would either silently no-op or, worse,
   throw on any Telegram-dependent path, while its DM-based loops
   (`morning_kickstart`, `evening_reminder`, `streak_at_risk`, etc.)
   would keep targeting `bioroma` — and any other real student who
   ever joins while Ghost Bot is running — indefinitely, not just once
   at join time, since `bioroma` is now a permanent row in Ghost Bot's
   own database.
6. Confirmed the production database also still carries two leftover
   test-account rows from prior sessions — `M.A.C.A.L EMPIRE` and
   `Empire Ghost` itself — both `status='active'`, meaning a real
   student could theoretically get buddy-paired with one of these
   non-real accounts. Flagged for the H7.6 DB cleanup pass (not fixed
   in this entry — separate concern from the isolation bug itself).

**Severity:** Blocker. Every one of the 16 real students would hit
this exact double, contaminated onboarding on their first join — the
single most important first impression of the entire system — for as
long as Ghost Bot remains running unfixed. This is not a cosmetic
issue; it directly caused the "unprofessional and confusing"
impression H6 exists to catch.

**Fix applied (2026-07-15):** added `IS_GHOST_INSTANCE` to
`src/config.py` (reads `IS_GHOST_INSTANCE` env var, defaults `false`).
Set `IS_GHOST_INSTANCE=true` in `.env.ghost` (and ONLY there — must
stay unset/false in the real production `.env`). Guarded three places
in `src/bot.py`:
1. `on_member_join` — returns immediately if `IS_GHOST_INSTANCE`,
   before registering the member, assigning a buddy, or sending any
   DM.
2. `on_raw_reaction_add`'s ✅-registration flow — same guard, as
   defense-in-depth (this path is more channel-scoped already, but
   explicit is safer than relying on permission overwrites alone for
   a flow this consequential).
3. `on_ready()` — added an early return (after logging bot-online)
   before the block that starts ~20 scheduled loops, the ops poller,
   and the restart notification, and before starting the practice-
   platform API server. None of these are needed for Ghost Bot's
   actual documented purpose (manually running commands against a
   synthetic test account to check behavior against the real guild's
   structure) — this closes the "loops keep targeting real students
   indefinitely" risk described in point 5 above, not just the
   join-time DM.

Also updated `docker-compose.ghost.yml`'s header comment and
`.env.ghost.example` to correct the outdated claim that channel
permission overwrites alone provide full isolation, and to document
the new required flag.

**Not fixed in this entry (separate, tracked concerns):**
- Ghost Bot's stale build (dozens of commits behind) — the owner
  should redeploy Ghost Bot (`docker compose -f
  docker-compose.ghost.yml up -d --build`) after this fix merges, to
  pick up both this fix AND all the missing feature work. Not folded
  into this defect since it's an operational redeploy step, not a code
  defect.
- The two leftover test-account rows in the production DB
  (`M.A.C.A.L EMPIRE`, `Empire Ghost`) — flagged for H7.6's DB cleanup
  pass.
- `bioroma`'s row inside Ghost Bot's OWN database (from this incident)
  — harmless once Ghost Bot is rebuilt with this fix (its scheduled
  loops will no longer start at all), but worth a manual cleanup for
  hygiene when Ghost Bot is next redeployed.

**Deployed (2026-07-15):** merged via [PR #148](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/148), confirmed
landed on `main`. Deployed to production (`git pull && docker compose
up -d --build`) — confirmed via `docker exec ... config.IS_GHOST_INSTANCE`
returning `False` and the startup log showing all scheduled loops/API
server starting normally, as expected for the real bot. Separately
rebuilt Ghost Bot (`docker compose -f docker-compose.ghost.yml up -d
--build`) after adding `IS_GHOST_INSTANCE=true` to `.env.ghost` (backed
up the prior file first) — confirmed via the exact same config check
returning `True`, AND via a startup log line proving the guard fired:
`"IS_GHOST_INSTANCE=true: skipping all scheduled loops, ops poller,
restart notification, and the API server"`. Also cleaned up
`bioroma`'s leftover row from Ghost Bot's own database (from the
original incident) before re-testing.

**Live re-tested (2026-07-15), exact original repro:** generated a
fresh invite, had the owner leave the guild with `bioroma` and rejoin
live. Result: only ONE DM sequence arrived, from "Empire English Bot"
only — clean, coherent, no stray image/audio attachments. Confirmed
server-side, not just by the owner's report: Ghost Bot's database has
ZERO rows for `bioroma` after the rejoin, Ghost Bot's logs show ZERO
activity referencing `bioroma` around the join time, and only the
production bot's logs show the buddy-assignment line for this join.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed to both
containers, and live re-verified against the exact original repro,
with server-side evidence (not just the owner's on-screen report)
confirming Ghost Bot no longer reacts to real guild activity at all.
---

## D024 — Onboarding tutorial's "see your progress" / "see all commands" steps never actually run those commands (Major)

**Found during:** H6.1 (Human Experience Walkthrough), live with the
owner, continuing the new-student journey on the `bioroma` Ghost
Testing account after D023's fix was deployed and verified clean.

**What happened:** Walking through the 5-step DM tutorial, step 3
prompts "type `!تقدم` to see your progress dashboard" and step 4
prompts "type `!مساعدة` to see all available commands." The owner
typed each command as instructed. Both times, only a short scripted
acknowledgment appeared (e.g., "✅ شفت؟ ده مكانك..." / "✅ تمام! دلوقتي
عندك كل الأوامر...") — the owner explicitly confirmed, when asked, that
`!مساعدة` did NOT print out a real command list as a separate message.

**Root cause:** `features.handle_tutorial_dm()` (Bawaba B2) intercepts
every DM from a student mid-tutorial in `on_message`, BEFORE
`bot.process_commands(message)` is ever reached (confirmed by direct
code reading of `on_message`'s handler order in `bot.py`) — and returns
`True` unconditionally on a match, which causes the calling code to
`return` immediately, so `process_commands()` never runs for that
message at all. `TUTORIAL_STEPS[3]` and `TUTORIAL_STEPS[4]` were
designed as pure pattern-match-and-reply-with-canned-text steps: the
input is checked against a fixed set of accepted strings, and on match,
only the scripted `"response"` text is sent. The actual `!progress` and
`!helpar` command bodies (`cmd_progress`, `cmd_helpar` in `bot.py`) were
never invoked — the tutorial was teaching the STUDENT to type these
commands while silently showing them fake, static text instead of the
real thing they were told they'd see.

Steps 1 ("type `1`"), 2 ("type `hello`"), and 5 ("type `!1`", explicitly
commented `/* this is just an exercise -- won't record a real task */`)
don't have this problem — they were never designed to show real output.
Only steps 3 and 4 explicitly promise real functionality ("this is the
command that shows your points/streak," "now you have all the
commands") and silently fail to deliver it.

**Severity:** Major, not Blocker — the tutorial still completes and
the student isn't stuck, but every one of the 16 real students would
be told twice, in as many minutes, "type this to see X" and shown
nothing real, which quietly undermines trust in the system right at
the first interaction, and means new students don't actually see their
real (empty, day-one) progress card or the real full command list
during the one moment onboarding is designed to teach them.

**Fix applied (2026-07-15):** added an `"invoke_real_command"` key to
`TUTORIAL_STEPS[3]` (`"progress"`) and `TUTORIAL_STEPS[4]`
(`"helpar"`). `handle_tutorial_dm()` now, after sending the step's
scripted acknowledgment, looks up the named real command via the bot's
own `bot.get_command(name)`, builds a real `Context` via
`bot.get_context(message)`, and calls `bot.invoke(ctx)` — the exact
same mechanism `process_commands()` itself uses for a normal command
message. This makes the tutorial's steps 3 and 4 produce the SAME real
output (the student's actual, real progress card; the actual, real
Arabic help list) that typing those commands normally would, not a
stand-in. Verified via code review that neither `cmd_progress` nor
`cmd_helpar` carries a cooldown or permission decorator that could
interfere with this direct-invoke path (confirmed via `grep` — both are
bare `@bot.command(name=...)` with no other decorators), and that this
cannot cause a double-invocation (the calling code already returns
immediately after `handle_tutorial_dm()` reports the message as
handled, before `process_commands()` would otherwise run for the same
message).

**Deployed (2026-07-15):** merged via [PR #151](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/151) (a clean rebase of the
original PR #150, which had gone stale/conflicting against `main`
after PR #149 merged first — #150 was closed unmerged, #151 replaced
it with an identical diff applied cleanly on top of current `main`).
Confirmed landed on `main` via direct grep for
`"invoke_real_command"`. Deployed to production (`git pull && docker
compose up -d --build`) — confirmed via `docker exec ... grep -c
invoke_real_command /app/src/features.py` returning `4` (all 4
occurrences present in the running container's actual file) and a
clean "Bot online" startup log with no errors.

**Live re-tested (2026-07-15):** the bot process restart cleared
`bioroma`'s in-memory tutorial progress (tutorial state is
process-local, not DB-persisted), so the owner used the existing
`!tutorial` command to manually restart the 5-step tutorial fresh
against the newly-deployed code, then walked through it again. Owner
confirmed: **"it worked"** — steps 3 (`!تقدم`) and 4 (`!مساعدة`) now
show the real progress card and real help list, not just the scripted
acknowledgment text.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified by the owner repeating the exact original repro against
the newly-deployed code.



---

## D025 — `on_message` crashes on EVERY DM due to unguarded `message.channel.name`, silently discarding vocab/listening quiz answers and more (Blocker)

**Found during:** H6.1 (Human Experience Walkthrough), live with the
owner, continuing the new-student journey on `bioroma`. The owner
tried `!done vocab`, received the quiz question correctly, answered it
(in the same DM conversation the whole tutorial had happened in), and
got no reply at all — the task never got marked done.

**Root cause, confirmed via direct log evidence (not just inferred):**
`discord.py`'s `DMChannel` class has NO `.name` attribute at all
(confirmed directly: `hasattr(discord.DMChannel, 'name')` → `False`
against the actual installed `discord.py 2.7.1` on the production
container). Four places in the codebase read `message.channel.name`
unconditionally, with no guard for this:

1. `features.check_english_only()` (`features.py` line 561, prior to
   fix) — called unconditionally near the top of `on_message` for
   EVERY message the bot receives, DM or not.
2. The vocab-quiz-answer handler (`bot.py`, prior to fix) — reads
   `message.channel.name == "bot-commands"` to decide whether to check
   a pending quiz answer.
3. The listening-quiz-answer handler (`bot.py`, prior to fix) — same
   pattern, same channel check.
4. The `#writing-feedback` auto-evaluation handler (`bot.py`, prior to
   fix) — same pattern.

Because (1) runs FIRST and unconditionally, **every single DM message
sent to the bot crashed there**, before the message could ever reach
(2), (3), or (4) further down in the same `on_message` handler.
Confirmed directly in the production logs:
```
2026-07-15 23:59:59 [ERROR] discord.client: Ignoring exception in on_message
Traceback (most recent call last):
  File ".../discord/client.py", line 508, in _run_event
    await coro(*args, **kwargs)
  File "/app/src/bot.py", line 2067, in on_message
    await features.check_english_only(message)
  File "/app/src/features.py", line 561, in check_english_only
    channel_name = message.channel.name
                   ^^^^^^^^^^^^^^^^^^^^
AttributeError: 'DMChannel' object has no attribute 'name'
```
This exact crash fired twice around the owner's tutorial/vocab-attempt
timestamps, confirming this is precisely what silently ate the vocab
quiz answer: discord.py's own exception handler logs the crash as an
`[ERROR]`-level "Ignoring exception in on_message" line and otherwise
swallows it completely — no reply to the student, no visible sign
anything went wrong, and easy to miss in logs unless specifically
grepped for.

**Severity: Blocker, not Minor.** This is NOT specific to vocab. ANY
message a student sends to the bot via DM — answering a vocab quiz, a
listening quiz, or anything else that would otherwise be handled later
in `on_message` — crashes before reaching that logic. Given how much
of onboarding (the tutorial itself, Nour's DM-based concierge
conversations) already happens via DM, and how naturally a student
would continue answering in the same DM thread they were just guided
through, this is a systemic gap, not an edge case.

**Secondary, related finding:** the vocab quiz word CAN legitimately
differ from the words shown on the practice-platform link the student
just visited — `curriculum.get_quiz_words()` intentionally samples from
the current week PLUS the previous 2 weeks (for spaced repetition),
while the practice platform's vocab page only shows today's specific
day-slice of the current week's words. This is working as designed,
not a bug, but it is genuinely confusing without any explanation
shown to the student — noted here for awareness, not filed as its own
defect, since "make it less confusing" is a product/UX judgment call
(similar in spirit to D012/D020), not a correctness bug. Flagged for
consideration during Masar or a future onboarding-polish pass.

**Fix applied (2026-07-15):** added an explicit DM-safe guard to all 4
call sites:
- `features.check_english_only()`: added `if not hasattr(message.channel,
  "name"): return False` right after the bot-author check, before the
  first unconditional `.name` read. English-only enforcement was never
  meant to apply to DMs anyway (the whole concept of "channel" doesn't
  apply there), so skipping entirely is correct, not just crash-safe.
- The vocab handler, listening handler, and `#writing-feedback`
  handler in `bot.py`: changed `message.channel.name == "..."` to
  `getattr(message.channel, "name", None) == "..."` — a DM channel now
  safely evaluates to `None == "bot-commands"` (i.e. `False`) instead
  of crashing, which is the correct behavior (a DM was never going to
  equal any of these channel-name strings regardless).
- Searched the full codebase for any other unguarded
  `message.channel.name`/`ctx.channel.name` reads (`grep -rn
  "\.channel\.name\b"` across all of `src/*.py`) — confirmed the only
  remaining occurrences (in `features.py` and `nour_onboarding.py`)
  are already correctly guarded by an earlier `hasattr()` check in the
  same function, so this fix is comprehensive, not just patching the
  one symptom that happened to be reported.

**Deployed and live-verified (2026-07-16):** merged via [PR #153](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/153),
confirmed landed on `main`. Deployed to production (`git pull &&
docker compose up -d --build`) — confirmed via `docker exec ... grep
-c "getattr(message.channel"` returning `3` in the running container.
Live re-tested: the owner retried the vocab quiz flow after deploy —
answering correctly in `#bot-commands` now registers cleanly (see
D027's live-verification note for the specific "play" example, same
session, same underlying `on_message` code path). No further
`AttributeError` crashes observed in production logs after deploy.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified. (Note: the original repro used answering in a DM, which
is intentionally NOT a supported flow — see D026/D027's clarification
that quiz answers are only accepted in `#bot-commands` by design. What
this fix actually guarantees is that DMs no longer CRASH `on_message`
for every student, regardless of what they're doing; the intended
quiz-answer flow, in the intended channel, is confirmed working.)



---

## D026 — `!done accent`/`shadow`/`speaking`/`writing`/`community` from a DM silently bypasses ALL verification, awarding points for zero proof of work (Major)

**Found during:** H6.1 (Human Experience Walkthrough), live with the
owner, while investigating whether D025's DM-crash bug also affected
task types other than vocab/listening (the owner explicitly asked
this before merging/testing D025's fix — good instinct, since it
surfaced a second, arguably worse issue in the same investigation).

**What would have happened:** unlike vocab/listening (which use a
two-step "post the quiz, wait for a DM reply" flow — D025's bug),
accent/shadow/speaking/writing/community are one-step: `!done <task>`
immediately checks whether the student already posted proof (a
recording or text) in the right channel within the last 2 hours, via
`verification.verify_task()`, which searches `ctx.guild`'s channel
history. This means these 5 task types were NEVER at risk of D025's
specific `AttributeError` crash (confirmed by tracing `verify_task()`
and its 3 helpers — none read `channel.name` unsafely).

However, tracing `cmd_done()`'s actual call site revealed a DIFFERENT,
arguably more serious problem:

```python
if isinstance(ctx.author, discord.Member):
    passed, error_msg = await verification.verify_task(task, ctx.author, ctx.guild)
    if not passed:
        await ctx.send(f"❌ **لم يتم التحقق:**\n\n{error_msg}")
        return
# PASSED VERIFICATION — process the submission
```

In a DM, `ctx.author` is a `discord.User`, not a `discord.Member`
(Discord's own distinction: a `Member` only exists in the context of a
specific guild). So `isinstance(ctx.author, discord.Member)` is
`False` in a DM, the entire verification block is skipped, and
execution falls straight through to "PASSED VERIFICATION" — awarding
full points and marking the task done with **zero check that the
student actually did anything**. This is not a crash and produces no
error in the logs — the bot would have replied with a completely
normal-looking success message, making it invisible without
specifically tracing this code path (found via code reading, not a
live repro, since this wasn't the specific complaint that started the
investigation).

**Severity: Major, not Blocker.** Doesn't break the student
experience (a student attempting this from DM would have their task
marked done successfully, no error shown) — the risk is entirely on
the INTEGRITY side: any student who realizes `!done accent` works from
DM without actually doing the accent drill gets free points with no
proof required, undermining the point of proof-of-work verification
for exactly the 5 task types that have real submission checks. Given
this system is about to onboard 16 real students, closing this before
they arrive (rather than after someone discovers it) is the right
call.

**Fix applied (2026-07-15):** replaced the silent-skip `if
isinstance(...)` guard with an explicit rejection: if `ctx.author` is
NOT a `discord.Member` (i.e., this is a DM), send a clear bilingual
message telling the student `!done <task>` doesn't work from DM and to
type it in the server instead, then `return` — never falling through
to "PASSED VERIFICATION" without an actual check. When `ctx.author` IS
a `Member` (the normal, intended path), behavior is completely
unchanged: `verify_task()` still runs exactly as before.

**Deployed and live-verified (2026-07-16):** merged via [PR #153](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/153)
(same PR as D025), confirmed landed on `main` and deployed. Owner
live-tested the exact repro directly:
1. `!done accent` via DM — bot correctly replied: *"❌ مينفعش تعمل
   `!done accent` من الرسائل الخاصة (DM). لازم تكتبها في السيرفر..."*
   (You can't do `!done accent` from a DM — type it in the server),
   confirming the new rejection message fires correctly instead of the
   old silent bypass.
2. `!done accent` in both `#l0-daily-tasks` and `#bot-commands` (real
   server channels) — owner confirmed: **"it worked in both"** — the
   normal verified path is unchanged.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified against both halves of the original repro (DM correctly
rejected; normal server-channel path unchanged and working).



---

## D027 — Discord's `!done listening` quiz is disconnected from the practice-platform listening page's actual content (Major)

**Found during:** H6.1 (Human Experience Walkthrough), live with the
owner, continuing the daily-task walkthrough after D025/D026. The
owner clicked the practice-platform listening link from the daily task
post, did that page's exercise, then came back to Discord and typed
`!done listening` — and got a comprehension question about a stranger
named Sarah living in Cairo, with no connection to anything on the
page they'd just visited.

**Root cause, confirmed via direct code reading of both systems:**
- The practice-platform listening page (`empire-dojo`'s
  `generate.py`'s `gen_listening()`) is, in reality, a **vocabulary
  meaning-matching quiz with audio**: it shows a real curriculum
  vocabulary word for that specific level/week/day (via
  `curriculum.get_vocabulary_for_day()` — the exact per-day word slice
  the student is actually studying that day), plays its pronunciation,
  and asks the student to pick its correct Arabic meaning.
- Discord's `!done listening` (`verification.generate_listening_quiz()`)
  always pulled from `LISTENING_QUESTIONS`, a **hardcoded bank of
  exactly 8 generic placeholder sentences** ("My name is Sarah and I
  live in Cairo," "I have two brothers and one sister") with zero
  relationship to the student's real level, week, day, or the specific
  words they were just studying.

These are simply two disconnected systems that happen to share the
word "listening" — not a case of the SAME content being retrieved
incorrectly, but two entirely separate, never-linked implementations.
Every student, every day, at any level, would hit this same
disconnect between what the link shows and what Discord asks.

**Severity: Major.** Doesn't block task completion (the quiz still
works, still awards points correctly, D025 already fixed the crash
that was silently eating answers) — but it actively undermines trust
and the pedagogical point of "listening practice," since the Discord
half of the exercise is unrelated filler content rather than
reinforcement of what the student was just shown.

**Fix applied (2026-07-15):** rewrote `generate_listening_quiz()` to
pull from the SAME real curriculum vocabulary the practice platform
and the vocab quiz (`generate_vocab_quiz()`, directly above it in the
same file) already use — specifically `curriculum
.get_vocabulary_for_day()` for the member's actual level/week/day
(computed via the exact same day-index convention already used
elsewhere in this codebase for the daily task post itself, in
`tasks.py`'s `generate_daily_tasks()` — not a new convention invented
here), falling back to `get_quiz_words()` (broader week+prior-2-weeks
sample) if that specific day has no data, and only falling back to the
old hardcoded generic bank if there's truly no curriculum data loaded
at all (so this never regresses to "no question"). Mirrors
`generate_vocab_quiz()`'s EN↔AR question shape, since this bot has no
way to play an actual audio clip inside Discord — "listening" here
means "the word you just heard read aloud via TTS on the practice
platform," consistent with how the practice platform's own page
already frames it, not a newly-invented format.

**Tested (2026-07-15), safely, before any deploy:** per this
project's established `docker exec`-swap methodology (D019: a
temporary file swap inside the container is a separate OS process from
the live bot, module-level state is never shared, safe for pre-deploy
verification) — backed up the container's live `verification.py`,
copied in the fixed version, and ran `generate_listening_quiz()` +
`check_listening_answer()` directly against `bioroma`'s real member
row (level L0, week 3): produced `"ما معنى كلمة **clean** بالعربي؟"`
(a real word from that week/day's actual vocabulary, confirmed against
the same `get_vocabulary_for_day()` call used above for the D025
investigation), correctly accepted the right answer, correctly
rejected a wrong answer showing the right one. Restored the container's
original file afterward — this test never touched the live bot process
or deployed anything.

**Deployed (2026-07-16):** merged via [PR #154](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/154), confirmed
landed on `main` via direct grep. Deployed to production (`git pull &&
docker compose up -d --build`) — confirmed via `docker exec ... grep
-c "Hisn D027" /app/src/verification.py` returning `1` and a clean
"Bot online" startup log.

**Live re-tested (2026-07-16), through the REAL Discord flow:** the
owner visited today's practice-platform listening link (Week 3, Day 6,
"Family & People" theme) and separately typed `!done listening` in
`#bot-commands`. The Discord question asked about the word **"play"**
— confirmed server-side via direct query against `bioroma`'s real
member row that "play" is genuinely the FIRST word in that exact
level/week/day's real curriculum vocabulary list (`week3 day5 (L0)
words: [('play', 'يلعب'), ('cook', 'يطبخ'), ('clean', 'ينظف'),
('drive', 'يقود'), ...]`) — the same data source
`get_vocabulary_for_day()` the practice platform itself uses. The
bot's own reply text ("نفس كلمة اليوم اللي شفتها في صفحة الاستماع" —
"the same word you saw today on the listening page") rendered
correctly and matched reality.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified through the real Discord flow with server-side
confirmation that the quiz word is genuinely drawn from the student's
actual current-day curriculum vocabulary, not the old disconnected
hardcoded bank.



---

## D028 — One audio recording satisfies MULTIPLE task types (accent/speaking/shadow), defeating proof-of-work verification (Major)

**Found during:** H6.1's Tier 1 daily-task walkthrough, live with the
owner. Having already uploaded one recording to `#l0-showcase` for the
shadowing task (and gotten `!done shadow` correctly verified and
checked), the owner then ran `!done speaking` in `#bot-commands`
WITHOUT uploading anything new — and it was accepted and checked
immediately. The owner's own framing: *"what if a student did the
same thing... I see this as a bug as it will show my system
unprofessional."*

**Root cause, confirmed via direct code reading:** `verify_audio()`
(`verification.py`) is the shared verification function for THREE
distinct task types — `accent`, `speaking`, and `shadow`
(`verify_task()`'s dispatcher routes all three to the exact same
function). It only ever asks "did this student post ANY audio-looking
attachment in `#l0-showcase` within the last 2 hours?" — it has no
concept of which specific message was already used, or for which
task. So a single upload:
- Satisfies all 3 audio-based task types in one shot (upload once,
  run `!done accent`, `!done speaking`, `!done shadow` back-to-back —
  each independently re-scans the same 2-hour window and finds the
  same message every time).
- Can be reused indefinitely within that 2-hour window, not just once
  — there was no "already spent" marker of any kind, in-memory or
  persisted.

This directly undermines the entire point of proof-of-work
verification for the 3 task types that were specifically designed to
require real recorded effort — exactly the category of defect this
system's `!done` verification exists to prevent (see D026, found
earlier this same session, which closed an unrelated but
thematically-adjacent gap in the same verification layer).

**Severity: Major.** Not a crash, not blocking — the opposite problem:
too *permissive*. Every one of the 16 real students could legitimately
discover this by accident (as the owner did, simply by trying two
different tasks close together) and get free, unverified credit for 2
of their 3 daily audio tasks from a single real recording.

**Fix applied (2026-07-16):** added a new persistent table,
`consumed_proof_messages` (`message_id` as PRIMARY KEY, so a message
consumed for ANY task can never satisfy a DIFFERENT task either — not
just the same one twice), plus two new functions in `database.py`:
`is_message_consumed(message_id)` and
`consume_proof_message(message_id, discord_id, task_id)` (the latter
race-safe via the PRIMARY KEY constraint + `IntegrityError` catch,
mirroring the existing pattern already used by `log_submission()`
elsewhere in this same file). `verify_audio()` now skips any message
that `is_message_consumed()` reports as already used, and calls
`consume_proof_message()` the instant it accepts a message as proof —
so that exact message can never satisfy a second `!done` call, for
this task or any other. Chosen as a persistent DB table rather than
an in-memory set specifically because in-memory state doesn't survive
a bot restart (confirmed relevant pattern from D019/tutorial-state
investigations earlier this campaign) — a student's showcase history
spans well beyond a single bot process lifetime.

Also updated the rejection message shown when verification fails to
explicitly explain the new requirement (a NEW recording per task,
previously-used-for-another-task doesn't count) rather than leaving
students confused about why a recording that clearly exists in the
channel isn't being accepted.

**Tested (2026-07-16), safely, before any deploy:** per this
project's established `docker exec`-swap methodology (D019/D027) —
backed up the container's live `database.py`/`verification.py`, copied
in the fixed versions, called `database.init_db()` to create the new
table, then directly exercised the new consume/check functions against
synthetic message IDs: confirmed a message consumed for `shadow`
correctly reports as already-consumed afterward, a SECOND consume
attempt for `speaking` using the SAME message ID correctly returns
`False` (blocked — reproducing exactly what should have stopped the
owner's original repro), and a consume attempt using a genuinely
DIFFERENT message ID for `speaking` correctly succeeds. Cleaned up the
test rows and restored the container's original files afterward —
this test never touched the live bot process or deployed anything.

**Deployed (2026-07-16):** merged via [PR #159](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/159), confirmed
landed on `main`. Deployed to production (`git pull && docker compose
up -d --build`) — confirmed via `docker exec ... grep -c
"consumed_proof_messages"` returning `4` in the running container, AND
confirmed the new table was actually created in the real production
database on startup (`sqlite_master` query). Since `bioroma` had
already genuinely completed `shadow`/`speaking` earlier the same day
(the day's real submission gate — a separate, unrelated,
one-task-per-day constraint — would have blocked re-testing), cleared
just those 2 rows from `daily_submissions` for that date (leaving
`consumed_proof_messages` untouched) to allow a clean re-test.

**Live re-tested (2026-07-16), through the REAL Discord flow:** owner
ran `!done shadow` — accepted correctly, streak/points updated. Owner
then immediately ran `!done speaking` with NO new upload — first hit
the pre-existing, unrelated 5-minute cooldown gate ("استنى 0:48 قبل ما
تسجل مهمة تانية"), then after waiting, ran `!done speaking` again —
**correctly REJECTED** with exactly the new message: *"لازم ترفع
تسجيل صوتي جديد... التسجيل اللي استخدمته قبل كده لمهمة تانية معدش
يصلح تاني"* (You need to upload a NEW recording — a recording already
used for another task can't be reused). This is the exact repro that
originally found the bug, now correctly blocked.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified through the real Discord flow, reproducing the exact
original scenario and confirming it's now correctly rejected.



---

## D029 — `!link`'s DM'd URL token is silently ignored; practice-platform homepage never reflects the student's real level/week (Major)

**Found during:** H6.1's Tier 1 dashboard-visit walkthrough, live with
the owner. Ran `!link`, took the DM'd URL "straight" (clicked it
directly, did not manually use the "Connect to Discord" button/paste
flow), and landed on the practice platform's level/week picker showing
**Level 0, Week 1** — while Discord itself (`!week`, confirmed
correct) knows the owner is genuinely on **Week 3**. Owner's own
framing: *"its really critical the link and eco and harmony between
discord bot and the practice."*

**Root cause, confirmed via direct code reading across BOTH repos:**
Two independent gaps, compounding into one visible symptom:

1. **`empire-dojo`'s `app.js`/`index.html`:** `cmd_link()`
   (`bot.py`) DMs `{platform_url}?token={token}` — but NOTHING on the
   practice platform ever read the `?token=` URL query parameter.
   Confirmed via `grep -rn "URLSearchParams"` across the whole
   `site/js/app.js` — zero matches before this fix. The token sat
   inert in the address bar; the page loaded exactly as if no token
   were present at all. The student would have had to separately
   notice the "Connect Discord" button and manually re-paste the same
   token by hand for it to do anything — directly contradicting the
   DM's own framing of it as "your personal link" (رابطك الشخصي).
2. **The homepage's level/week picker (`index.html`) is a fully
   static UI with hardcoded defaults** (`let currentLevel = 'l0'; let
   currentWeek = 1;`) and had no code path connecting it to
   `ConnectedProgress` (the object that DOES fetch real progress data,
   for the streak display and pronunciation stats) at all. Even a
   student who manually pasted their token via "Connect Discord"
   would still see the picker sitting at Level 0/Week 1 — only the
   streak number and pronunciation stat would update, not the
   level/week selection itself.
3. **Secondary gap, found while fixing #2:** `get_progress_for_token()`
   (`database.py`) returned `level` but never `week` at all — even a
   frontend that WANTED to auto-select the real week had no way to
   know it from the existing API response.

**Severity: Major.** Every one of the 16 real students following the
exact intended flow (`!link` → click the DM'd link) would land on a
picker showing the wrong level/week relative to their real progress,
undermining trust in the Discord↔web connection at the very moment
that connection is supposed to prove itself working. Not a Blocker
since the student CAN still manually navigate to the correct
level/week (the picker itself works correctly once clicked through) —
but it directly contradicts the product's own promise of a connected,
harmonious ecosystem.

**Fix applied (2026-07-16):**
1. `database.py`'s `get_progress_for_token()` now also returns
   `week` (via `member_week_number()` — the exact same function
   `!week` itself already uses, guaranteeing the two can never
   disagree).
2. `app.js`'s `ConnectedProgress.init()` now checks
   `URLSearchParams(window.location.search).get('token')` FIRST,
   before falling back to any previously-saved `localStorage` token —
   if present, it connects immediately (same code path
   `connect()`/`_fetchProgress()` the manual paste flow already uses)
   and then strips the token from the visible URL via
   `history.replaceState()` (mirroring the DM's own "don't share this
   link" warning — a token sitting in the address bar is easy to
   accidentally screenshot/share).
3. `ConnectedProgress._fetchProgress()` now dispatches a
   `window.dispatchEvent(new CustomEvent('empire:progress-loaded', ...))`
   custom event with the fetched data every time fresh progress data
   arrives (not just on first connect) — a minimal, decoupled hook so
   `ConnectedProgress` (in `app.js`, shared across every generated
   page) doesn't need to know the homepage's picker exists at all.
4. `index.html`'s inline script now listens for that event and, when
   fired, sets `currentLevel`/`currentWeek` to the real values from
   the student's progress data (clamped to that level's real max week
   via the existing `WEEKS` map, same defensive clamping pattern
   already used elsewhere in this codebase for week numbers) and
   re-renders the week/day grid and weekly chart to match.

Also confirms `!link`'s existing DM text needs NO changes — it already
correctly describes `{platform_url}?token={token}` as the student's
personal link; the fix makes that description actually true, rather
than requiring new bot-side copy.

**Not tested yet (safely, before deploy)** — this fix spans TWO
repositories (`empire-nexus` for the API's new `week` field,
`empire-dojo` for the frontend) that must be deployed together for
either half to matter (the frontend fix reads a field the API didn't
return before; the API fix alone changes nothing visible without the
frontend reading it).

**Status:** ✅ **RESOLVED.** Merged in both repos
([empire-nexus#161](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/161),
[empire-dojo#24](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/24)),
deployed, and live re-verified via the exact original repro (`!link`
→ click the DM'd URL directly) during the same H6.1 session — confirmed
in D030's own entry immediately below, which explicitly describes
testing happening "immediately after D029's fix landed and correctly
jumped the homepage to the student's real level/week."
**Correction note (added 2026-07-16, during a Kiro account-migration
handover):** this Status line was left on its pre-verification wording
long after the fix actually shipped and was confirmed live — a stale-
status documentation bug, same class as the one previously caught and
fixed for D025/D026 (see that entry's own correction note). Caught
by a fresh Kiro session cross-checking `STATUS.md`'s "10 initiatives
fully complete" claim against this file directly, rather than trusting
either document at face value. No code change was needed here — only
this Status line was out of date; the underlying fix has been live and
correct since H6.1.



---

## D030 — Practice-platform homepage's day picker has no "today" awareness; student must manually calculate which of 7 generic day cards to pick (Minor, UX)

**Found during:** H6.1's dashboard-visit walkthrough, live with the
owner, immediately after D029's fix landed and correctly jumped the
homepage to the student's real level/week. The owner's own framing:
*"as per my knowledge with the ecosystem, the daily tasks is synced
with the days and weeks so how do I know as a student when I open the
link which day... why not make it more easy... when I open the link
[it] takes me straight to the week and day so I just go through the
tasks."*

**What was observed:** with D029 fixed, the homepage correctly landed
on the right level/week, but the "Choose Your Day" grid still showed 7
generic, visually-identical day cards (Sat/Day 1 through Fri/Day 7)
with zero indication of which one corresponds to the actual current
date. A student would have to independently work out "today is
Thursday, which in this system's Sat-start week numbering is Day 6"
themselves — even though the rest of the ecosystem (the bot's daily
task post, `!week`) already computes and uses exactly this information
every single day.

**Root cause, confirmed via direct code reading:** `index.html`'s
`renderDays()` function generates the 7 day cards purely by loop index
(`for (let d = 1; d <= 7; d++)`), with no reference to the real
current date anywhere — confirmed via `grep` finding zero matches for
any today/current-date logic in the file before this fix.

**Severity: Minor, UX** — not a correctness bug (every link/card still
points to the right place once clicked, and verification/points are
entirely server-side and unaffected), but a real friction point for
exactly the kind of new, possibly zero-English-confidence student this
whole platform is designed for.

**Fix applied (2026-07-16):**
1. Added `todaysDayNumber()` to `index.html`, computing "today" using
   the EXACT SAME `Sat=1..Fri=7` convention already used everywhere
   else in this ecosystem (the bot's `daily_task_post`/`!week`/the
   link-generator all share this ordering — not a new convention
   invented here).
2. `renderDays()` now adds a `.today` CSS class (new rule in
   `empire.css`: a gold glow/border + small dot indicator, layers
   correctly alongside the existing `.done` green styling if a day is
   both) to whichever card matches, so a student can see at a glance
   which card is today's — without forcing any navigation.
3. **Per the owner's specific suggestion**, added an auto-jump: when
   arriving via a FRESH `!link` click specifically (tracked via a new
   `ConnectedProgress._connectedFromUrlThisLoad` flag in `app.js`,
   passed through the existing `empire:progress-loaded` event from
   D029's fix as `data.fromUrlThisLoad`), the homepage now navigates
   straight to `{level}/week{week}/day{today}/` automatically —
   skipping the picker entirely for the specific case `!link` exists
   to serve ("let me just get to today's tasks"). Deliberately NOT
   triggered on an ordinary homepage revisit with an already-saved
   token (e.g. browsing back later to check a previous week) — only a
   fresh link click force-navigates; a returning visit still lands on
   the (now today-highlighted) picker so browsing other days/weeks
   isn't disrupted.

**Known, accepted limitation (not a defect, noted for completeness):**
`todaysDayNumber()` uses the student's own device/browser timezone
(`new Date().getDay()`), NOT the bot's configured `Asia/Dubai`
timezone (`tasks.py`'s `_now()`) — this is a client-side static site
with no server-side "current time" to query. For students in or near
that timezone this will normally agree with Discord's own daily task
post, but could theoretically disagree for a short window near
midnight for a student in a very different timezone. Acceptable for a
"helps find today faster" UX nicety that doesn't touch verification or
points (both entirely server-side and already correct); documented
here rather than silently assumed away.

**Tested:** `node --check` on `app.js` and a `new Function()` parse
of `index.html`'s inline script both pass cleanly. Manually verified
the JS day-number computation agrees with the bot's Python
equivalent for today's actual date (both independently computed
"Thursday → day 6").

**Deployed (2026-07-16):** merged via `empire-dojo` [PR #25](https://github.com/empireenglishcommunity-glitch/empire-dojo/pull/25)
(and this repo's docs-only [PR #162](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/162)),
confirmed landed on `main`. Deployed via `npx wrangler pages deploy
site --project-name=empire-practice` (3 files uploaded: `index.html`,
`js/app.js`, `css/empire.css`). Hit a transient ~20-second Cloudflare
CDN propagation lag on the custom domain immediately after deploy
(the fresh `*.pages.dev` deployment URL served the correct file
immediately; `practice.empireenglish.online` briefly still served the
pre-deploy version despite `cf-cache-status: EXPIRED`) — resolved on
its own without any action needed; confirmed all 3 files correct on
the custom domain shortly after.

**Live re-tested (2026-07-16), through the REAL Discord flow:** owner
ran `!link` again and clicked the DM'd URL directly. Confirmed via
screenshot: the auto-jump fired correctly, landing directly on
`/l0/week3/day6/` ("Week 3 — Day 6") — the exact real level/week/day,
skipping the picker entirely, exactly as designed for a fresh link
click. Separately visiting the bare homepage afterward (no `?token=`
in the URL — the token had already been consumed/stripped by the
first visit) correctly did NOT auto-navigate away, and instead showed
the "Choose Your Day" picker with **Thu/Day 6 visually highlighted**
(confirmed both via the owner's own description — "Thu Day 6 is
highlighted with a gold border and gold text" vs. the other 6 cards'
"thin dark gray borders with faint gray text" — AND via Chrome
DevTools' own breadcrumb trail showing the selected element as
`a.today`, proving the class is genuinely applied to the correct
card, not just visually similar).

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified through the real Discord flow, confirming both halves of
the intended behavior: auto-jump on a fresh `!link` click, and
today-highlighting (without forced navigation) on an ordinary
homepage revisit.



---

## D031 — `#ask-nour` channel was invisible to all real students (missing `@everyone` permission overwrite) (Blocker)

**Found during:** H6.4's escalation walkthrough, live with the owner.
Setting up to trigger a real Nour escalation, the owner switched to
`bioroma` and reported: *"from bioroma account i am unable to see
#ask-nour."*

**Root cause, confirmed via direct Discord API inspection:** the
server's `@everyone` role does NOT grant `VIEW_CHANNEL` by default
(confirmed: base permissions integer `65600` does not include the
`0x400` `VIEW_CHANNEL` bit). Every other channel checked
(`l0-daily-tasks`, `general-chat`, `bot-commands`, etc.) has an
EXPLICIT per-channel permission overwrite granting `@everyone` (or
specific level roles) `VIEW_CHANNEL` — that explicit grant is what
actually makes channels visible in this server, not the role default.

`#ask-nour` had **zero permission overwrites at all**, and — unlike
every other channel — **no parent category either**
(`parent_id: None`). With no overwrite of its own and no category to
inherit a broader grant from, it silently fell back to the server's
actual base default: invisible to everyone except roles with
`ADMINISTRATOR` (which bypasses all channel-visibility checks
entirely — explaining why this was never noticed from an admin
account).

Cross-checked against `scripts/setup_server.py` (the script that
creates/configures every other channel with correct permissions at
server-setup time): `ask-nour` is **not referenced anywhere in that
script at all** — confirming it was created manually, after the fact,
outside the normal setup flow, and never had its permissions
configured to match the rest of the server's channels.

**Severity: Blocker.** This is not `bioroma`-specific — every one of
the 16 real students would hit the exact same invisibility, meaning
Nour's dedicated student-facing help channel (the ENTIRE point of
which is to be a place students can ask for help / get escalated to a
human) has been unreachable by any real student since it was created.
Given H3.2 and H6.4 both specifically needed to exercise the
escalation path, and both are Hisn's OWN verification of exactly this
system, this could easily have gone unnoticed all the way to real
student launch if H6.4 hadn't specifically required a real student
account to physically attempt reaching this channel.

**Fix applied (2026-07-16):** added an explicit permission overwrite
on `#ask-nour` for the `@everyone` role, granting `VIEW_CHANNEL`
(`0x400`) + `SEND_MESSAGES` (`0x800`) + `READ_MESSAGE_HISTORY`
(`0x10000`) — the same three permissions every other student-facing
channel in this server explicitly grants. Applied directly via the
Discord API (`PUT /channels/{id}/permissions/{everyone_role_id}`),
confirmed `204` response, and confirmed via a follow-up `GET` that the
overwrite is now present exactly as intended.

**Follow-up applied (2026-07-16):** added `ask-nour` to
`scripts/setup_server.py`'s SYSTEM category channel list (alongside
the pre-existing, thematically-identical `support` channel — "🆘
محتاج مساعدة؟ اسأل هنا"), inheriting that category's standard
`@everyone`/level-role `_VIEW_SEND` overwrite pattern every other
channel in this script already uses. This is the actual code fix that
prevents this exact gap from being silently reintroduced if the
server is ever rebuilt from scratch — the direct-API permission fix
above only fixed the one, already-existing, live channel instance.
`python3 -m py_compile` confirms the script still parses cleanly.

**Status:** ✅ **RESOLVED** — fixed on the live server (permission
overwrite applied directly, confirmed by the owner: *"yes i can see
it now"*) AND the setup script corrected so a future full rebuild
creates `#ask-nour` with the right permissions from the start, closing
both the immediate symptom and the underlying process gap that let it
happen in the first place.



---

## D032 — Owner's escalation reply arrives as a bare, unframed DM with no indication it's "from Nour" (Minor, UX)

**Found during:** H6.4's escalation walkthrough, live with the owner,
immediately after confirming the full escalation loop mechanically
worked end-to-end (student message → Telegram alert → owner reply →
delivered DM). When asked to confirm the DM "looked like it came from
Nour," the owner reported: *"it did not look like it came from my
personal account or my personal telegram, but i did not get the
answer in the same #ask nour channel i got in another chat empire
english bot chat."*

**Two separate things were confirmed here, one working as designed,
one a real gap:**
1. The reply correctly arrives via DM (NOT back in `#ask-nour`) and
   correctly does NOT look like it's from the owner's personal
   account/Telegram — both intended, working exactly as designed
   (`forward_reply_to_student()`'s whole purpose is to deliver a
   private, human-reviewed answer directly to the student, attributed
   to the bot's own Discord identity, never exposing the owner's real
   identity).
2. **The DM itself has zero framing indicating it's "from Nour"**
   specifically — confirmed via code read: `forward_reply_to_student()`
   sent `reply_text` completely raw, via
   `discord_member.send(reply_text)`, no prefix, no signature. The
   Telegram prompt itself explicitly says "Reply to this message to
   respond **as Nour**," but nothing in the actual delivered DM ever
   signals that to the student. It arrives from the same "Empire
   English Bot" Discord account that sends every other kind of
   notification (task confirmations, tutorial steps, `!link` tokens),
   with no distinguishing text at all.

**Why this matters:** Nour's NORMAL replies (inside `#ask-nour`) don't
need a "from Nour" label, because they're a visible, in-context
continuation of a conversation the student is already having with
Nour in that channel — the channel itself provides the context. An
escalation reply, by contrast, arrives as a completely fresh DM with
zero surrounding conversation, so there's nothing establishing who's
"speaking." The owner's own confusion when checking their own test
reply is a direct, first-hand demonstration of exactly this gap — if
the person who WROTE the reply couldn't immediately tell it was
attributed to Nour, a real student certainly couldn't either.

**Severity: Minor, UX** — the reply is still delivered correctly and
the student still gets real help; this is about clarity of
attribution, not function.

**Fix applied (2026-07-16):** added a short bilingual framing prefix
to `forward_reply_to_student()`, chosen based on the student's actual
language phase (`features.response_language()` — the exact same
function already used elsewhere in this codebase for bilingual
framing decisions, not a new mechanism): `"💬 **رد من نور:**"` (Arabic
phase), `"💬 **رد من نور (reply from Nour):**"` (bilingual_ar phase), or
`"💬 **A reply from Nour:**"` (bilingual/English phase) — followed by
the owner's actual reply text unchanged. The RAW `reply_text` (without
the framing prefix) is still what gets stored in `nour_conversations`
via `_store_reply_in_history()` — deliberately unchanged, since the
framing is presentation-only for this one DM and shouldn't pollute
conversation history that later gets fed back into Gemini prompts as
context.

**Tested (2026-07-16), safely, before any deploy:** per this
project's established `docker exec`-swap methodology (D019/D027/D028)
— backed up the container's live `nour_escalation.py`, swapped in the
fixed version, then directly called `features.response_language()`
against `bioroma`'s real member row and confirmed it correctly
resolves to `bilingual_ar`, producing the expected framed output:
`"💬 **رد من نور (reply from Nour):**\n\nThanks for asking!..."`.
Restored the container's original file afterward — this test never
touched the live bot process or deployed anything.

**Deployed (2026-07-16):** merged via [PR #165](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/165), confirmed
landed on `main`. Deployed to production (`git pull && docker compose
up -d --build`) — confirmed via `docker exec ... grep -c "Hisn D032"
/app/src/nour_escalation.py` returning `1` and a clean startup log.

**Live re-tested (2026-07-16), through the REAL Discord flow:**
re-ran H6.4's exact repro end-to-end a second time. Server logs
confirm the full loop fired cleanly (`escalation sent via Empire Ops
bot: BioRoMa` → `forwarded owner reply to BioRoMa`). Owner confirmed
the delivered DM now reads:
```
💬 رد من نور (reply from Nour):

ok will reply back in 2 hours, thanks for asking
```
— the `bilingual_ar` framing fires exactly as designed (matching the
safe pre-deploy test's prediction for `bioroma`'s real language phase)
and the attribution gap that originally prompted this defect is
closed.

**Status:** ✅ **RESOLVED** — fixed, merged, deployed, and live
re-verified through the real Discord flow, with the exact predicted
bilingual framing confirmed in the actual delivered DM.

---

## D033 — Nour's AI-generated messages had no gender field to work from (silently guessed, sometimes wrong) and no output-quality guard against foreign-language hallucinations (Major)

**Found during:** Masar M3.4's production live-verification. The
owner ran the real `!markmilestone` command against their own
`bioroma` account (a real male-presenting personal account) and
received a personalized milestone message that (a) addressed them
using feminine Egyptian Arabic grammar throughout ("عليكي", "انكي",
"سجليتي" — all feminine second-person forms, when the correct forms
for a male addressee are "عليك", "انك", "سجلت") and (b) contained a
stray Vietnamese word fragment ("đặc", from "đặc biệt" / "especially")
spliced into the middle of an otherwise-Arabic sentence.

**Root cause, part 1 (gender):** confirmed via full schema search that
`members` has **no gender field at all**, anywhere, and never has —
not a Masar regression, a pre-existing gap in the whole system. Every
AI prompt that addresses a student directly in Egyptian Arabic
(`nour_concierge.py`'s regular chat, and all 3 of `narrative_engine.py`'s
new `build_*` functions) had nothing telling the model the student's
gender, so the model silently guessed one every single time — visible
here specifically because Masar's new features are the first to
generate long, second-person-addressed sentences ABOUT a specific
student by name, but the identical exposure exists in Nour's regular
`#ask-nour` chat too.

**Root cause, part 2 (foreign-language leak):** confirmed via code
read that neither `nour_concierge._clean_response()` nor
`narrative_engine._clean_ai_text()` ever checked AI output for
anything beyond stripping quote marks/markdown artifacts — no check
existed anywhere for whether a response was actually clean
Arabic/English text. Groq's Llama 3.3 70B produced a genuine
token-hallucination glitch (a real word from another language it was
trained on, not a typo), and there was no mechanism to catch it before
it reached the student.

**Fix applied (2026-07-16), addressing the root cause, not the
individual symptom:**
1. **New `gender` column on `members`** (default `''` = unknown,
   nullable/optional, never a guessed default) — a real schema
   migration (`_migrate()`), added to `_SCHEMA` for fresh installs too.
2. **New `!gender male|female|clear` command** — fully optional,
   skippable, available to any student at any time (existing or new),
   accepts English and Arabic input values.
3. **New shared `nour_personality.get_gender_instruction(discord_id)`
   helper** — used by BOTH `nour_concierge.py`'s regular chat AND all
   3 of `narrative_engine.py`'s `build_*` functions (not just the ones
   that happened to expose the bug) — explicitly instructs the AI to
   use the correct gendered grammar when known, and explicit
   genuinely-gender-neutral phrasing (never a default guess) when
   unknown, which is the case for every existing student today.
4. **Fixed 3 masculine-only imperative forms in the non-AI template
   fallbacks** (`كمل`, `استمر كده`, `جاهز`) — these can't use the
   dynamic AI instruction since they never call AI, so they were
   rewritten as genuinely gender-neutral phrasing directly.
5. **New `_has_unexpected_script()` quality guard in
   `narrative_engine.py`'s shared fallback chain** — a narrow
   blocklist of scripts that have no legitimate reason to appear in
   Nour's Arabic/English output (Vietnamese-range Latin Extended
   Additional, Devanagari, CJK, Hangul, Cyrillic). A response
   containing any of these is now treated as a FAILED generation —
   Groq-fail falls through to Gemini, Gemini-fail falls through to
   the template — rather than ever being sent to a student. Applied to
   `narrative_engine.py`'s shared chain (used by all 3 `build_*`
   functions); **NOT yet applied to `nour_concierge.py`'s separate,
   older chat-response chain**, which has the identical theoretical
   exposure — flagged here explicitly as a known follow-up, not a
   silent gap, since fixing it is a small, separate, well-scoped
   change that didn't need to block this fix.

**Tested (2026-07-16), against a real DB clone (never production):**
`get_gender_instruction()` confirmed producing correct, distinct
instructions for all 3 states (male/female/unknown); the quality guard
tested against the EXACT real garbled string the owner received
(correctly flagged) and against clean Arabic/English/emoji/number text
(correctly NOT flagged); the full fallback chain tested with a
simulated garbled Groq response (correctly fell through to a clean
Gemini response) and with BOTH providers simulated garbled
(correctly fell through to the template); the `!gender` command's
core update/clear/invalid-input logic tested directly against
`database.update_member()`.

**Status:** ✅ **RESOLVED.** Deployed to production (2026-07-16,
`main` merged through `bfad1dd`, `docker compose up -d --build` on
`empire-english-bot`, deployed commit confirmed directly via `git log
--oneline -1` on the server). `bioroma`'s `gender` set to `male`
directly against production (`gender` column confirmed present
post-deploy). Re-verified live via the exact `complete_milestone()` →
`build_milestone_moment()` code path `!markmilestone` itself calls
(new milestone `l0_count100`, a genuinely uncompleted one for
`bioroma` at the time): across 4 independent Groq-generated messages,
100% used correct masculine Egyptian Arabic grammar ("ليك" not
"ليكي", "انت قدرت/عملت/قمت" not "انتي...تي", "يا باشا") and 0%
contained any foreign-script leakage. The `_has_unexpected_script()`
guard was also observed actively catching and discarding a real Groq
hallucination live during this same re-verification run (fell through
to Gemini, which is separately returning `401` — see "Key
Infrastructure & Standing Lessons" in `STATUS.md`, unrelated to this
defect and not investigated further here — then to the template
fallback), proving the guard works end-to-end under a real failure,
not just in the DB-clone test. One AI-generated message was then
delivered as a real Discord DM to `bioroma`, confirmed via a real
message ID (`1527387035470659787`). Post-verification cleanup done:
`bioroma`'s full footprint (`members`, `ability_milestones`,
`nour_memories`) deleted, `members` back to 0 rows;
`masar_milestone_moments` flag restored to default OFF with
`allowed_ids` cleared. The `nour_concierge.py` follow-up gap noted
above (no `_has_unexpected_script()` guard on the older regular-chat
AI chain) remains open and explicitly flagged, unchanged by this
re-verification — still a known, non-blocking gap, not a silent one.



---

## D034 — `adaptive_engine.check_and_adjust()` called `is_feature_enabled("tatawwur_adaptive")` with no `discord_id`, silently disabling the entire Adaptive Difficulty feature for any allowlist-scoped rollout (Major)

**Found during:** Masar M4.4's live-verification on the Ghost Bot
(2026-07-16). Setting up a synthetic test member with `tatawwur_adaptive`
enabled via allowlist (scoped to just that one discord_id — the exact
"roll out to a beta squad first" use case the allowlist feature exists
for), injecting 7 pronunciation scores of 90% (well above the 85%
`THRESHOLD_UP`), and calling `adaptive_engine.check_and_adjust()`
directly produced `None` — no adjustment at all, despite every
precondition being met.

**Root cause:** `check_and_adjust(discord_id)` has `discord_id` as its
own parameter, but its very first line calls
`database.is_feature_enabled("tatawwur_adaptive")` — with NO
`discord_id` argument. Per `is_feature_enabled()`'s own documented
contract, a `discord_id` of `None` is only ever treated as enabled if
the flag's `allowed_ids` is EMPTY (i.e. "on for everyone"); a
member-scoped allowlist rollout is unconditionally rejected, even for
members who ARE on the allowlist. **This is the IDENTICAL bug class
already found and fixed TWICE during Masar M2** (in
`nour_growth_letter_task()` and the `/api/growth-letter` endpoint —
see `STATUS.md`'s "Key Infrastructure & Standing Lessons" and its
explicit "Rule going forward" about this exact pattern) — this is now
the THIRD confirmed occurrence of the same defect class, and the first
one found in `adaptive_engine.py` / Tatawwur's own code rather than
Masar's new code. Since production's `tatawwur_adaptive` flag has
always been globally OFF (empty allowlist) or globally ON to date,
this bug has never yet affected a real student in production — but it
would silently and completely disable adaptive difficulty for EVERY
real student the moment anyone tried to do a real beta-squad rollout
via the allowlist, exactly the scenario M4's own live-verification
just exercised.

**Fix:** pass `discord_id` through to the `is_feature_enabled()` call
in `check_and_adjust()` — one-line change, no behavior change for the
"globally on/off" cases, only for the allowlist-scoped case.

**Status:** ✅ **RESOLVED.** Fix merged
([empire-nexus#180](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/180)),
deployed to both production and the Ghost Bot (`721927a`, confirmed
via `git log` on the server), and live re-verified on the Ghost Bot:
re-ran the exact same UP-direction scenario that originally surfaced
this defect (allowlist-scoped `tatawwur_adaptive`, 7 scores at 90%) —
`check_and_adjust()` now correctly returns a real adjustment
(`2→3, avg=90.0%`) instead of `None`. Ghost Bot test data (member,
scores, notification log) fully cleaned up afterward; both flags reset
to OFF with `allowed_ids` cleared.

---

## D035 — `_has_unexpected_script()`'s blocklist misses Vietnamese words that use ONLY shared Latin-1 diacritics (no Vietnamese-specific character), letting a real foreign-language leak through undetected (Minor, follow-up to D033)

**Found during:** Masar M4.4's live-verification (2026-07-16), while
generating several `build_difficulty_note()` "up"-direction messages
directly against production's real Groq key (the Ghost Bot's own
`.env.ghost` has empty `GROQ_API_KEY`/`GEMINI_API_KEY` values — a
separate, narrow, non-blocking config gap, noted below, not fixed as
part of this defect). One AI response read: `"...يلا GhostTestSynthetic
نكمل cùng بعض، هنتعلم أكتر وأكتر!"` — `"cùng"` is Vietnamese for
"together," a real foreign-language leak of the exact class D033's
guard was built to catch, but it was NOT flagged.

**Root cause:** `_has_unexpected_script()`'s blocklist range for
Vietnamese is `(0x1E00, 0x1EFF)` (Latin Extended Additional — the
block containing Vietnamese-SPECIFIC precomposed characters like `đ`,
`ệ`, `ạ`). `"cùng"` uses `ù` (U+00F9), which lives in the ordinary
Latin-1 Supplement block (`0x00C0`-`0x00FF`) — the SAME block used by
legitimate French/Portuguese/Italian/Spanish accented letters (café,
naïve, señor) and, per the guard's own design comment, deliberately
NOT blocked, to avoid false-positiving on real, legitimate accented
text. D033's original repro (`"đặc"`) happened to use characters
squarely inside the blocked range, so that specific fix worked, but
the underlying bug class ("Groq can hallucinate a short, common
foreign word using only shared-alphabet characters") is broader than
the blocklist covers, and probably can't be fully closed by any
character-range blocklist alone — a genuinely reliable fix would need
either a language-identification pass (adds latency/cost and a new
external dependency) or a curated list of common non-Arabic/English
words to reject (a maintenance burden, and still incomplete by
nature).

**Status:** 🟡 **Found and characterized, NOT fixed.** Deliberately
not patched narrowly in this session — a narrow blocklist addition
(e.g. blocking all of Latin-1 Supplement) would immediately
false-positive on legitimate French/Portuguese loanwords or accented
names, which is worse than the current gap. **Flagging for an explicit
product decision from the owner**: is a language-identification
library (e.g. `langdetect`, `lingua`) an acceptable new dependency to
add reliability here, or is the current guard (which DOES catch the
larger, more visually-obvious foreign-script leaks like D033's
original CJK/Vietnamese-diacritic/Cyrillic repro) considered
"good enough" given AI hallucinations of this specific shared-alphabet
sub-class appear to be rare in practice (1 occurrence observed across
roughly a dozen+ AI generations sampled across D033's and M4's
combined live-verification sessions)? Not blocking M4 or D033's own
closure — both remain independently resolved.

**Related, separate, non-blocking config gap found during the same
investigation:** the Ghost Bot's `.env.ghost` has empty
`GROQ_API_KEY`/`GEMINI_API_KEY` values (confirmed via direct check on
the server), meaning the Ghost Bot has never actually exercised real
AI generation for ANY Masar feature to date (M2, M3, or M4) — every
Ghost Bot test this whole campaign silently used the template
fallback path only, never the AI path, without anyone noticing until
now. Not fixed here (deciding whether to share production's keys with
the Ghost Bot, or issue it separate ones, is a credentials/quota
decision for the owner, not a code fix) — flagged explicitly, not
silently left broken.



---

## D036 — Dashboard's milestone grid used a hardcoded, entirely fictional list of milestone IDs with ZERO overlap with the real milestone catalog — could never show an achieved badge for any real milestone (Major)

**Found during:** Masar M5.1's re-run of the Data Honesty Audit
(2026-07-16), while re-verifying the "Milestone grid" row of
`design.md`'s Component 6 table against the LIVE code, not just
trusting the original table's "✅ Yes, honest, no change" verdict.
Reading `empire-dojo/site/dash/index.html`'s `_renderMilestones()`
function directly (not just checking that `/api/dashboard` returns a
`milestones` field) surfaced a hardcoded 12-item `allMilestones` array
with IDs like `first_recording`, `streak_7`, `level_l1`,
`conversation_first` — cross-checked against the real 15 IDs actually
used by `content/milestones/milestones.json` (`l0_introduce`,
`l0_count100`, `l1_daily_story`, `l2_job_interview`, etc., the same
file `!markmilestone`/`!abilities`/`narrative_engine.py` all read
from): **zero overlap between the two ID sets.**

**Consequence:** since `_renderMilestones()`'s "achieved" check is
`achieved.has(m.id)` against the hardcoded list, and no real
`ability_milestones` row's `milestone_id` can ever match any ID in
that list, **the dashboard's milestone grid has NEVER been able to
show an achieved (✅) badge for any milestone any real student has
ever completed** — every real milestone always renders as 🔒 locked,
for every student, forever, regardless of actual progress. This
predates Masar entirely (Wuslah-era dashboard, `empire-dojo` PR #27's
history traces further back) and was NOT caught by Hisn's original
Data Honesty Audit pass (M0.3) or design.md's own Component 6 table,
both of which took the milestone grid's existence/data-source at face
value without cross-checking the actual ID space rendered client-side
— confirming M5's own re-verification (re-check against LIVE code, not
trust a prior table) has real value, not just process theater.

**Confirmed NOT present in the Discord side:** `!abilities`
(`bot.py`'s `cmd_abilities`) correctly reads `milestones.json` directly
and checks against `database.get_completed_milestones()` — same
correct pattern throughout, no fictional ID list. This defect was
isolated to the web dashboard's frontend-only hardcoded array.

**Fix:** added `api_server._get_milestones_catalog()` — reads the same
`content/milestones/milestones.json` `!markmilestone`/`narrative_engine.py`
use, returns a flat `[{id, name, name_ar, level}, ...]` list, cached
in-memory (same pattern as `curriculum.py`'s content loading). Added
as a new `milestones_catalog` field on `/api/dashboard`'s response
(additive — the existing `milestones` field, real completion records,
is unchanged). Updated `empire-dojo/site/dash/index.html`'s
`_renderMilestones()` to render from the real catalog instead of the
hardcoded array, matching achieved status against real
`milestone_id`s for the first time.

**Tested:** 4 new unit tests
(`tests/test_api_server.py`) confirming the catalog's IDs exactly
match `milestones.json`'s real IDs, and explicitly confirming NONE of
the old fictional IDs (`first_recording`, `streak_7`, etc.) appear in
the real catalog. Full suite: 378/378 passing, zero regressions.

**Status:** 🟡 **Fix written, locally tested, NOT yet deployed or
live-verified** (needs `empire-nexus`'s API change deployed AND
`empire-dojo`'s frontend change deployed via
`npx wrangler pages deploy site --project-name=empire-practice` —
per this whole campaign's own discipline, both halves need a real
browser/API check before this can be marked Resolved: open the real
dashboard for a member with at least one completed milestone,
confirm it now shows ✅ for that real milestone instead of the grid
always showing everything locked).
