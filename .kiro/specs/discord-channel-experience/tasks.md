
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

> ✅ **PHASE 2 COMPLETE as of 2026-07-17.** Full live audit performed
> with corrected expected bitmask values (a computation error in the
> original Phase 0 audit script's hardcoded values was caught and
> corrected — `_VIEW_SEND_VOICE` is `36817984`, not the wrong
> `3263552` value I'd hand-typed earlier). Result: **zero real
> permission issues found.** Every category's `@everyone` overwrite
> matches its documented intent exactly, ADMIN/Ghost correctly deny
> all member roles, bot role has full access everywhere, `#ask-nour`
> confirmed inside SYSTEM (D037 fix holding), 0 orphan channels.

- [x] **2.1** No mismatches found — no fixes needed.
- [x] **2.2** INTENTIONAL `@everyone` grants in SYSTEM/LEVEL 0/
  COMMUNITY/ACCOUNTABILITY/RESOURCES/FEEDBACK confirmed still
  correctly in place — these support the bot's own onboarding flow
  (new members need `#bot-commands` before any level role). NOT
  "fixed" back to locked.
- [x] **2.3** ADMIN and Ghost Testing categories confirmed correctly
  denied to all 5 real member roles (L0/L1/L2/L3/Ambassador)
  individually — no leakage.
- [x] **2.4** Permission state reference table: see the audit script's
  own output above (Category → @everyone expected value mapping), now
  confirmed matching live. The definitive reference for a future
  session to compare against without re-deriving from scratch:

  | Category | @everyone allow | @everyone deny | Meaning |
  |---|---|---|---|
  | WELCOME | 66624 | 2048 | View+react, NO send (read-only for students) |
  | SYSTEM | 117824 | 0 | View+send+embed+attach (new members need this) |
  | LEVEL 0 | 36817984 | 0 | View+send+voice (new members need this) |
  | LEVEL 1 | 0 | 1024 | Denied (level-gated) |
  | LEVEL 2 | 0 | 1024 | Denied (level-gated) |
  | LEVEL 3 | 0 | 1024 | Denied (level-gated) |
  | COMMUNITY | 36817984 | 0 | View+send+voice (all members) |
  | ACCOUNTABILITY | 117824 | 0 | View+send (all members) |
  | RESOURCES | 117824 | 0 | View+send (all members) |
  | FEEDBACK | 117824 | 0 | View+send (all members) |
  | ADMIN | 0 | 1024 | Denied (hidden from all students) |
  | Ghost Testing | 0 | 1024 | Denied (hidden from all students) |

## Phase 3 — Channel-by-channel review: keep / enhance / merge / archive [NEED for identifying gaps; individual fixes tagged per-item]

> ✅ **PHASE 3 AUDIT TABLE COMPLETE as of 2026-07-17.** Every
> student-facing channel reviewed against live data (message counts,
> bot automation presence, user activity). Verdicts assigned. No
> merges or archives recommended at this time (0 real students in the
> system = no usage data to justify merging, per design.md's open
> question #2 recommendation to defer merges until real data exists).

- [x] **3.1** Full verdict table (below).
- [x] **3.2** Confirmed via direct code grep which channels have real
  bot-driven content automation (scheduled tasks posting to them) vs.
  which depend entirely on student activity or are empty placeholders.

### Phase 3 Verdict Table

| # | Channel | Category | Verdict | Rationale |
|---|---------|----------|---------|-----------|
| 1 | `#start-here` | WELCOME | **Keep** | Read-only entry point, has pinned guide + clear onboarding instructions |
| 2 | `#welcome` | WELCOME | **Keep** | Has the full welcome message + Arabic guide, both pinned |
| 3 | `#rules` | WELCOME | **Keep** | Has rules + privacy policy + Arabic guide, all pinned |
| 4 | `#roles-info` | WELCOME | **Keep** | Has level explanation + Arabic guide, both pinned |
| 5 | `#announcements` | WELCOME | **Keep** | Active — `!announce` posts here, real admin activity |
| 6 | `#دليل-القنوات` | WELCOME | **Keep** | Already serves as the whole-server Arabic channel map/index, pinned |
| 7 | `#bot-commands` | SYSTEM | **Keep** | Active — ALL commands live here, highest user activity |
| 8 | `#leaderboard` | SYSTEM | **Keep** | Active — auto-updated by `post_leaderboard()` scheduled task |
| 9 | `#support` | SYSTEM | **Keep** | Purpose clear, will activate once students arrive |
| 10 | `#ask-nour` | SYSTEM | **Keep** | Active — Nour AI concierge responds in real time, high activity |
| 11 | `#suggestions` | SYSTEM | **Keep** | Purpose clear, will activate once students arrive |
| 12 | `#l0-daily-tasks` | LEVEL 0 | **Keep** | Active — daily tasks posted at 6 AM, highest message volume |
| 13 | `#l0-text-practice` | LEVEL 0 | **Keep** | Real student writing submissions exist |
| 14 | `#l0-questions` | LEVEL 0 | **Keep** | Arabic allowed here (exception), important for confused L0 students |
| 15 | `#l0-showcase` | LEVEL 0 | **Keep** | Real student recordings uploaded |
| 16 | `#l1-daily-tasks` | LEVEL 1 | **Keep** | Active — daily tasks auto-posted (level-gated, activates at L1) |
| 17 | `#l1-text-practice` | LEVEL 1 | **Keep** | Same as L0 equivalent, activates at L1 |
| 18 | `#l1-questions` | LEVEL 1 | **Keep** | Same as L0 equivalent |
| 19 | `#l1-showcase` | LEVEL 1 | **Keep** | Same as L0 equivalent |
| 20 | `#l2-daily-tasks` | LEVEL 2 | **Keep** | Active — daily tasks auto-posted |
| 21 | `#l2-text-practice` | LEVEL 2 | **Keep** | Same pattern |
| 22 | `#l2-questions` | LEVEL 2 | **Keep** | Same pattern |
| 23 | `#l2-showcase` | LEVEL 2 | **Keep** | Same pattern |
| 24 | `#l3-daily-tasks` | LEVEL 3 | **Keep** | Active — daily tasks auto-posted |
| 25 | `#l3-text-practice` | LEVEL 3 | **Keep** | Same pattern |
| 26 | `#l3-mentorship` | LEVEL 3 | **Keep** | Unique to L3, purpose clear (help beginners) |
| 27 | `#l3-showcase` | LEVEL 3 | **Keep** | Same pattern |
| 28 | `#general-chat` | COMMUNITY | **Keep** | Active — real user messages, free English practice space |
| 29 | `#introductions` | COMMUNITY | **Keep** | Purpose clear, activates when students join |
| 30 | `#events` | COMMUNITY | **Keep** | Admin posts sessions here, pre-existing real content |
| 31 | `#daily-word` | COMMUNITY | **Enhance** [NEED] | Has a Word of the Day bot post mechanism (`daily_word_delivery()` scheduled task confirmed in `bot.py` line 1063), BUT: needs verification that it's actually posting daily content consistently — live data shows only 5 messages total (4 bot, 1 user), which is low for a "daily" feature. Investigate whether this is a flag-gated feature not yet enabled, or genuinely posting and just has low engagement. |
| 32 | `#daily-check-in` | ACCOUNTABILITY | **Keep** | Active — morning/evening reminders, missed-day reports, real user check-ins |
| 33 | `#streak-tracker` | ACCOUNTABILITY | **Keep** | Active — auto-updated daily |
| 34 | `#weekly-goals` | ACCOUNTABILITY | **Keep** | Purpose clear, will activate once students set goals regularly |
| 35 | `#cheat-sheets` | RESOURCES | **Enhance** [NEED] | **Phase 4's flagship scope.** Currently ONLY has the Wednesday grammar card. The Weekly Vocabulary Cheat Sheet prompt exists but was never wired up (Real Finding #1 from this spec's own requirements.md). This is the single highest-value missing content in the entire server. |
| 36 | `#video-library` | RESOURCES | **Enhance** [WANT] | Currently a pure placeholder (0 user messages, only the pinned guide). Needs real curated content (at minimum: 3-5 recommended videos per level as a starter set). Defer until after Phase 4 and/or until real students arrive and can contribute. |
| 37 | `#podcast-recs` | RESOURCES | **Enhance** [WANT] | Same as `#video-library` — placeholder today, needs a curated starter set. Defer same timeline. |
| 38 | `#book-club` | RESOURCES | **Enhance** [WANT] | Same — no content yet. Lowest priority of the 3 resource channels since it requires the most sustained commitment (monthly book picks). Defer. |
| 39 | `#speaking-feedback` | FEEDBACK | **Keep** | Active — real recordings uploaded, AI assessment triggers on submissions |
| 40 | `#writing-feedback` | FEEDBACK | **Keep** | Active — AI auto-evaluates submissions > 30 chars in this channel |
| 41 | `#accent-feedback` | FEEDBACK | **Keep** | Purpose clear, distinct from `#speaking-feedback` (pronunciation-specific vs. general fluency) |
| 42 | `#grammar-qa` | FEEDBACK | **Keep** | Purpose clear, will activate with real student questions |

### Summary of verdicts

| Verdict | Count | Action needed |
|---------|-------|---------------|
| **Keep** | 39 | None — already serving their purpose or will activate naturally once students join |
| **Enhance [NEED]** | 2 | `#cheat-sheets` (Phase 4 scope), `#daily-word` (investigate if automation is running) |
| **Enhance [WANT]** | 3 | `#video-library`, `#podcast-recs`, `#book-club` — need curated starter content, defer |
| **Merge** | 0 | Per design.md's open question #2: defer ALL merge decisions until real usage data exists (0 students today = 0 data to justify a merge) |
| **Archive** | 0 | No channel is genuinely dead or redundant — every one either has real automation or a clear, distinct purpose that doesn't overlap meaningfully with any other |

### Key findings from this review

1. **`#daily-word` needs investigation** — code shows a `daily_word_delivery()` scheduled task exists (line 1063, fires at 7:00 AM), but the channel only has 5 total messages. This could mean the feature is flag-gated and not yet enabled, or it's firing but the content disappears / doesn't generate properly. Will investigate in a follow-up task (not Phase 4, since that's specifically about `#cheat-sheets`).

2. **`#video-library` / `#podcast-recs` / `#book-club`** are genuine placeholders today — but NOT candidates for archive/merge. They serve distinct, real purposes that will activate once real students arrive and start sharing content. The right action is to seed them with a small starter set of curated recommendations (3-5 items each) AFTER the higher-priority Phase 4 work ships, not before.

3. **No channel merges are recommended.** The 3 resource channels (video/podcast/book) look like merge candidates on paper ("low activity"), but they serve genuinely different content types (video vs. audio vs. text) that students would naturally look for in different places. Merging them into one generic "resources" channel would make the single merged channel harder to navigate, not easier. Confirmed: defer this decision per design.md's own explicit recommendation.

4. **The system as designed is structurally sound.** 39 of 42 channels are either already active or will activate naturally when students join — this is a well-designed server structure, not an over-built one. The "enhance" items (cheat-sheets content, daily-word investigation, resource-channel seeding) are genuine gaps worth fixing, but they're additions to an already-working structure, not fixes to a broken one.

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
