
# Tasks — Sahin: Discord Channel & Community Experience

> **How to use this file:** work top to bottom, phase by phase. Check off
> a task (`- [x]`) in the SAME commit/PR that completes it, so this file
> is always an accurate live progress record — never mark something done
> here until it's actually merged, deployed, AND live-verified, per this
> project's own established discipline (see `empire-chronicle/STATUS.md`).
>
> **If you are a fresh session/agent picking this up:** read
> `requirements.md` and `design.md` in this same directory first. Then
> resume at the first unchecked task below. **Do not skip Phase 0** —
> it re-verifies live state that a prior session may have assumed still
> holds.
>
> **Every phase below is tagged [NEED] or [WANT] per Requirement 5.**
> All [NEED] phases are sequenced before all [WANT] phases — stopping
> after any [NEED] phase leaves the system strictly better than before,
> with nothing half-finished.

---

## Phase 0 — Re-verify live state (do this FIRST, before any new code) [NEED]

> ✅ **PHASE 0 COMPLETE as of 2026-07-17.** Live audit performed,
> 1 real (Minor) defect found and fixed (D037), everything else
> confirmed still holding from prior sessions. Safe to move on to
> Phase 1.

- [x] **0.1** Fresh temporary SSH grant obtained.
- [x] **0.2** Wrote and ran a disposable, read-only audit script
  (inline, via `docker exec ... python3 -c "..."` against the live
  bot's own Discord token — not saved as a standalone file, since a
  single targeted run was sufficient and the project's own
  `page_crawler.py`/`api_adversarial_test.py` precedent shows
  throwaway scripts are an accepted pattern here). Printed every
  category, every channel (name/id/type/topic), every permission
  overwrite's raw allow/deny bitmask, and a dedicated orphan-channel
  scan (channels with `category=None`).
- [x] **0.3** Compared live output against `setup_server.py`
  channel-by-channel. Results:
  - **50 live text+voice channels, exact 1:1 match against
    `setup_server.py`'s full channel list** — 0 unexpected live
    channels, 0 missing expected channels.
  - D001-D004 (corrupted emoji, duplicate LEVEL 2 category, leftover
    default categories) — confirmed still fixed, no recurrence.
  - D006 (`دليل-القنوات` under WELCOME) — confirmed still present and
    correctly placed.
  - **D031 found PARTIALLY regressed**: `#ask-nour`'s permission
    overwrite was still correct (D031's actual Blocker-severity fix
    holds — the channel is visible and usable), but the channel was
    STILL an orphan (`category=None`), never actually re-parented into
    SYSTEM. Logged and fixed as **D037** (see 0.5).
  - Production `members` table: **1 row**, not 0 as last confirmed —
    `bioroma` (the owner's own account), joined 2026-07-16 23:35:34,
    with genuine associated activity (Nour conversation, a real
    `!link` use, a real morning DM). Confirmed this is real, organic
    owner activity between sessions, NOT leftover test data or
    anything this session did — left untouched, flagged to the owner
    as an FYI rather than assumed to need cleanup.
  - All 5 Masar feature flags + `tatawwur_adaptive` confirmed still
    OFF with empty allowlists — no drift.
- [x] **0.4** Recorded as **D037** in `defect_log.md` (continuing the
  D001-D036 sequence) — full detail: root cause (category-reparent
  step of D031's original fix was apparently never applied, only the
  permission-overwrite half was), impact (cosmetic/organizational, NOT
  a repeat Blocker since the channel was never actually invisible this
  time), and a second, more subtle bug this same fix closed (see 0.5).
- [x] **0.5** Fixed D037 live: `channel.edit(category=<SYSTEM>,
  sync_permissions=False)`, verified via a direct `fetch_channel()`
  call (not the cached guild object, which showed stale data on the
  same client instance — a real gotcha worth remembering for any
  future live Discord-API script). Confirmed the existing `@everyone`
  overwrite was fully preserved by the re-parent. Re-ran the full
  orphan scan afterward: **0 orphan channels remain anywhere on the
  server.** Also discovered and confirmed-fixed a second, more subtle
  bug via the same action: `setup_server.py`'s own channel-lookup logic
  only searches WITHIN a category's channel list, so while `#ask-nour`
  was an orphan, a future full rebuild via this script would have
  SILENTLY CREATED A DUPLICATE channel rather than finding/fixing the
  orphaned one — confirmed via a direct dry-run of the script's exact
  lookup line that this is no longer possible now that the channel is
  correctly parented. No `setup_server.py` code change was needed —
  the script's logic was always correct for a correctly-parented
  channel; the live DATA was wrong, not the script.

## Phase 1 — Pinned "how to use this channel" posts [NEED]

> Purely additive — no existing channel, permission, or bot behavior is
> touched. Lowest risk phase in this entire spec; safe to execute in
> full even if Phase 0 finds something that needs more time to fix.

- [ ] **1.1** Write the `CHANNEL_GUIDES` content map in
  `scripts/setup_server.py` (or a new sibling module,
  `scripts/channel_guides.py`, imported by the setup script — decide
  based on how large the map gets; keep `setup_server.py` readable).
  Cover every student-facing channel below (excludes ADMIN and Ghost
  Testing categories — those are operator/testing-only, not
  student-facing):

  **WELCOME:** `start-here`, `welcome`, `rules`, `roles-info`,
  `announcements`, `دليل-القنوات` (this one may already effectively
  BE a channel guide for the whole server — confirm its existing
  content during 1.1 before writing a redundant pin for itself).

  **SYSTEM:** `bot-commands`, `leaderboard`, `support`, `ask-nour`,
  `suggestions`.

  **LEVEL 0-3 zones (per level, ×4):** `lX-daily-tasks`,
  `lX-text-practice`, `lX-questions`, `lX-showcase` (L3 also gets
  `l3-mentorship`). Voice channels (`lX-voice-1/2`, `l3-debate`) do
  not support pinned text messages the same way — use the channel
  TOPIC field instead (already partially set; confirm/enhance).

  **COMMUNITY:** `general-chat`, `introductions`, `events`,
  `daily-word`.

  **ACCOUNTABILITY:** `daily-check-in`, `streak-tracker`,
  `weekly-goals`.

  **RESOURCES:** `cheat-sheets` (coordinate with Phase 4 — don't
  write a pin that contradicts the 4a/4b redesign), `video-library`,
  `podcast-recs`, `book-club`.

  **FEEDBACK:** `speaking-feedback`, `writing-feedback`,
  `accent-feedback`, `grammar-qa`.

- [ ] **1.2** Extend `ServerSetup._post_content()` to (a) iterate the
  new `CHANNEL_GUIDES` map alongside the existing 3 hardcoded entries,
  and (b) call `.pin()` on any newly-sent guide message (the 3 existing
  entries — welcome/rules/roles-info — should also be pinned if they
  aren't already; check live during Phase 0's audit).
- [ ] **1.3** Run `python3 -m py_compile scripts/setup_server.py` and
  the full `pytest tests/` suite (confirms nothing else in the bot
  broke — this script isn't itself unit-tested, but a syntax/import
  error here would still be worth catching before a live run).
- [ ] **1.4** Run the script against the LIVE server (idempotent —
  `.edit()`s existing channels, only creates what's missing). Confirm
  live: every listed channel now has a pinned guide message, in
  Arabic, readable, not truncated by Discord's message-length limits.
- [ ] **1.5** Update `defect_log.md` or a dedicated completion note —
  this phase doesn't fix a "defect" per se, but should still be
  recorded as done, per Requirement 6.3's discipline.

## Phase 1 (cont'd) — bidi text fix, live deployment + cleanup [NEED]

> ✅ **PHASE 1 IS NOW FULLY COMPLETE, LIVE-VERIFIED CLEAN.** Owner
> flagged a real Arabic/English mixed-direction (bidi) readability
> issue after Phase 1's initial deployment — resolved via PR #192
> (`scripts/bidi_check.py`, a reusable checker + regression test),
> then deployed and verified live on the real production server.

- [x] Found and fixed 15 bidi issues across 13 `CHANNEL_GUIDES`
  entries (see `defect_log.md`/PR #192 for full detail) — a single
  Arabic line with 2+ embedded LTR (channel/command) tokens produces
  disorienting visual reading order per the Unicode Bidirectional
  Algorithm, not a wording mistake specific to any one line.
- [x] Built `scripts/bidi_check.py` as a permanent, reusable checker
  (not a one-off fix) — `find_bidi_issues()`/`find_bidi_issues_in_dict()`
  — plus a regression test
  (`tests/test_bidi_check.py::test_real_channel_guides_have_zero_bidi_issues`)
  that runs against the REAL live `CHANNEL_GUIDES` content, so this
  class of bug is caught automatically by CI/the test suite going
  forward, not just by a human reading it again.
- [x] Documented a new standing rule in `.kiro/steering/project-rules.md`
  (never write an Arabic line with 2+ embedded LTR tokens; run
  `bidi_check.py` before shipping new Arabic content with inline
  channel/command references) — also documented the scoped
  MSA-vs-Egyptian-dialect exception for this file in the same edit.
- [x] Deployed to production (`fad8a6e`, confirmed via `git log` on
  the server) and re-ran `setup_server.py` for real against the live
  guild.
- [x] **Live cleanup, done in 3 passes as real drift was discovered
  at each step** (documenting the full process since it wasn't
  perfectly linear — useful for a future session doing something
  similar):
  1. Unpinned the 14 originally-wrong-pinned messages from the
     idempotency bug (PR #190).
  2. Unpinned + deleted the 2 exact-duplicate messages caused by the
     trailing-whitespace bug (`#welcome`, `#roles-info`) and 1
     orphaned duplicate in `#rules` (PR #191).
  3. **Found via a stricter live audit** (checking "exactly 1 pin
     total per channel", not just "at least 1 correct pin exists")
     that **16 channels still had their ORIGINAL Egyptian-colloquial
     pin from Phase 1's very first run sitting alongside the new
     correct MSA pin** — e.g. `#suggestions` had 2 pins: the correct
     new one AND the old one, both technically "present," but only
     the strict single-pin check caught that the old one was never
     actually removed. Unpinned + deleted all 16, then found and
     deleted 21 further stale UNPINNED leftover messages (old
     Egyptian-colloquial and intermediate pre-bidi-fix versions still
     sitting in channel history, cluttering it even though correctly
     never pinned).
- [x] **Final live verification, done STRICTLY this time**: for
  every one of the 38 `CHANNEL_GUIDES` channels, confirmed exactly 1
  pin total (not "at least 1 correct pin among possibly several") and
  that pin's content matches expected exactly, AND re-ran
  `find_bidi_issues()` directly against the live pinned content
  (not just the source file) to confirm zero bidi issues in what
  students will actually see. All 38 confirmed clean. Zero remaining
  stale/leftover messages anywhere (separately confirmed via a full
  history scan).

**Lesson recorded for future phases of this spec**: a verification
check that only confirms "the correct content exists somewhere" is
NOT sufficient after multiple content-editing passes on the same
channel — always also check "and nothing ELSE incorrect is still
pinned/present," since iterative fixes on live, already-populated
channels can leave old versions behind even when the new version is
correctly added.

## Phase 2 — Permission audit + fix [NEED]

> Depends on Phase 0's ground-truth table already existing.

- [ ] **2.1** For every mismatch found in Phase 0.3/0.5 that wasn't
  already fixed as part of Phase 0, apply the fix using the two-part
  rule: live fix via Discord API or a `setup_server.py` re-run, AND a
  `setup_server.py` correction in the same PR if the script itself was
  wrong.
- [ ] **2.2** Specifically re-verify (don't skip) the INTENTIONAL
  `@everyone` grants in SYSTEM/LEVEL 0/COMMUNITY/ACCOUNTABILITY/
  RESOURCES/FEEDBACK categories are still correctly in place — these
  are not bugs, they support the bot's own onboarding flow (a
  brand-new member with no level role yet must be able to see
  `#bot-commands`). Do NOT "fix" these back to fully locked — confirm
  this is understood before touching any of these categories.
- [ ] **2.3** Confirm the ADMIN and Ghost Testing categories are
  correctly denied to all real member roles (`@everyone` and all 4
  level roles + Ambassador) — these must never leak.
- [ ] **2.4** Write up the final, confirmed-correct permission state as
  a short reference table in this spec's `design.md` (append a
  "Confirmed Permission State — <date>" section) so a future session
  has a fast comparison point without re-running Phase 0's full audit
  from scratch every time.

## Phase 3 — Channel-by-channel review: keep / enhance / merge / archive [NEED for identifying gaps; individual fixes tagged per-item]

- [ ] **3.1** Walk every channel in `setup_server.py`'s
  `CATEGORIES_CONFIG` and assign one verdict (Keep / Enhance / Merge /
  Archive) per Component 3's table. Record the full table in this
  file (append below this task) or in `design.md` — pick one location
  and keep it there, don't split across both.
- [ ] **3.2** For every **Enhance** verdict, confirm via a direct grep
  of `bot.py`/`features.py`/`tasks.py` whether real content/behavior
  already exists and is just underused, or whether it's genuinely
  missing (the "designed but never wired up" pattern already found 4
  times this project — D012, D020, D036, and Real Finding #1 above).
  Specifically confirm/deny during this task:
  - `#daily-word` — does anything actually post a daily word? (flagged
    as unconfirmed in `design.md`)
  - `#video-library`/`#podcast-recs`/`#book-club` — confirmed
    placeholder-only (topic string, no poster logic) per context
    gathered for this spec — re-confirm live, don't just trust this
    note.
- [ ] **3.3** For each confirmed-missing "Enhance" item, open a
  separate, small, focused PR (one per channel/feature, not one giant
  PR) — mirrors how Masar's own phases (M1/M2/M3/M4) were each shipped
  independently. Do not bundle Phase 3 enhancements with Phase 4's
  cheat-sheet work even if they feel similar — keep blast radius small
  and reviewable.
- [ ] **3.4** For any **Merge** candidate, apply Component 6's full
  rename/merge safety net BEFORE touching anything live. Per
  `design.md`'s open question, the recommendation is to DEFER any
  merge decision until real student usage data exists — confirm this
  with the user before doing any merge work in this phase.
- [ ] **3.5** For any **Archive** candidate, apply via permission deny
  only (`@everyone` + all level roles denied view) — never delete the
  channel, its history, or remove it from `setup_server.py` (comment it
  as archived with a dated note instead, so a future rebuild doesn't
  silently resurrect it without context).

## Phase 4 — `#cheat-sheets` redesign (the flagship) [NEED for 4a; NEED-pending-user-decision for 4b per design.md's open question; WANT for 4c]

- [ ] **4.1 [4a — the real fix]** Implement a new `@tasks.loop`
  scheduled task in `bot.py` (model directly on the existing
  `grammar_card_delivery()`), wiring up the ALREADY-WRITTEN Weekly
  Vocabulary Cheat Sheet prompt (`content/prompts/cheat_sheets.json`
  prompt #1) end to end: generate via the existing AI engine → format
  as clean Discord text (bilingual, matching this project's existing
  bilingual precedent) → post to `#cheat-sheets` on a day that does NOT
  collide with the Wednesday grammar card (e.g. Sunday).
- [ ] **4.2** Add real unit tests for the new formatting function
  (mirroring how `format_grammar_card()` is presumably tested — check
  and match existing test conventions in `tests/test_features.py`).
- [ ] **4.3** Gate behind a NEW feature flag (`vocab_cheat_sheet`,
  default OFF), per this project's Aegis-established flag-then-release
  discipline. Test live via the Ghost Bot first (isolated DB/token,
  zero production risk) before ever enabling on production.
- [ ] **4.4** Live-verify on the Ghost Bot: trigger the new task
  manually, confirm a real, well-formatted message posts to the Ghost
  Bot's own test channel equivalent, confirm the content genuinely
  reflects that week's real vocabulary theme (not a stale/hardcoded
  example).
- [ ] **4.5** Deploy to production with the flag still OFF. Enable
  manually for one real cycle, confirm it posts correctly to the real
  `#cheat-sheets` channel at the expected time, THEN consider it
  [NEED]-complete. **Do not proceed to 4.6 (the visual version) until
  4.1-4.5 are fully live-verified — per `design.md`'s explicit
  recommendation to prove the text version first.**
- [ ] **4.6 [4b — visual redesign, PENDING USER DECISION per
  `design.md`'s open question #1 — do not start without an explicit
  go-ahead]** If approved: build the HTML/CSS template for the
  vocabulary grid, matching the Goal Poster's proven high-DPI-scale
  pattern (2x render, large legible fonts). Render via the existing
  `empire-html2img` container (already running, zero new
  infrastructure). Gate behind `cheat_sheets_visual` (default OFF).
  **Explicit anti-regression check before this flag is ever enabled
  for real students:** view the rendered image as Discord's own
  mobile-client inline preview would show it (not the full-resolution
  file on a desktop) — this exact gap is what made Bawaba's B3.2 PNG
  infographic fail silently until a human looked at a real phone. If
  it fails this check, this task stops here and 4a's text version
  remains the permanent primary path — that is a fully acceptable
  outcome, not a failure of this phase.
- [ ] **4.7 [4c — occasional brand art, WANT, lowest priority]**
  Document (do not automate — this pipeline needs a manual Kaggle GPU
  session) the exact manual steps for generating one piece of on-brand
  decorative art from `macal-empire-image-forge` for occasional use
  (e.g. a monthly celebration banner). This is optional polish,
  sequenced last, and never carries content students must read.

## Phase 5 — `empire-dojo` ↔ Discord harmony [NEED]

- [ ] **5.1** Generate one long-lived (non-expiring, no use-limit)
  Discord invite link via Server Settings → Invites (a manual,
  one-time owner action — cannot be done via bot API alone without
  `create_invite` permission scoping decisions that are simplest done
  directly by the owner).
- [ ] **5.2** Add the invite link as a plain config constant in
  `empire-dojo` (matching how `PRACTICE_PLATFORM_URL` is a plain
  constant in the bot's `config.py` today — not a secret).
- [ ] **5.3** Add one clearly-placed "Join our Discord community" CTA
  to `empire-dojo`'s live page(s) — exact placement decided by looking
  at the real, current page layout (landing page and/or `/dash/`)
  during this task, not guessed in advance. Purely additive — no
  existing `empire-dojo` behavior is touched or removed.
- [ ] **5.4** Deploy via the existing Cloudflare Pages pipeline
  (`npx wrangler pages deploy site --project-name=empire-practice`,
  per this project's own established deploy command), verify live on
  the real custom domain (`practice.empireenglish.online`), confirm the
  invite link actually works (join test, using the Ghost Bot's
  identity or a disposable test account, never a real student
  account).
- [ ] **5.5 [WANT, lower priority]** Confirm Discord role/embed colors
  match `EMPIRE_BRAND_UNIVERSE.md`'s documented hex palette exactly —
  a pure consistency check, fix only if a genuine mismatch is found
  (not a redesign).

## Phase 6 — Close-out and documentation [NEED, process]

- [ ] **6.1** Update `empire-chronicle/STATUS.md` to reflect Sahin's
  completion (or current phase, if stopped partway through
  deliberately) — same discipline as every prior initiative's closeout
  (Masar, Hisn, Aegis).
- [ ] **6.2** Cross-reference any new defects found during Phase 0/2's
  audits with their fixing PRs in `defect_log.md`, continuing the
  D001-D036 numbering sequence.
- [ ] **6.3** Final full re-verification sweep (mirrors every prior
  initiative's own close-out discipline): confirm `main` in
  `empire-nexus`/`empire-dojo` matches what's deployed to production
  (`git log` on the server, not the merge API), confirm all new feature
  flags are in their intended default state, confirm the full test
  suite passes, confirm zero open PRs remain.

---

## Cross-session bookkeeping (do this whenever ANY phase above changes state)

- [ ] Keep `empire-chronicle/STATUS.md`'s "immediate next action"
  section pointing at this spec's current phase until Phase 6 closes
  it out.
- [ ] If real students are invited partway through this spec's
  execution, add a dated note directly in this file marking exactly
  which phases were complete *at the moment of invite* — mirrors
  Aegis's own equivalent bookkeeping rule, and is the single most
  important checkpoint this spec exists to protect given the "don't
  break what we built" constraint.
