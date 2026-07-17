
# Design — Sahin: Discord Channel & Community Experience

## Guiding idea

Everything in this design follows one rule, chosen specifically because
the user has stated zero tolerance for breaking what already works:

> **Additive and reversible first. Any rename/merge/delete only after
> its blast radius is fully mapped in code, and always with an
> instant path back.**

```
Today's actual risk surface (confirmed in code, not assumed):
┌──────────────────────────────────────────────────────────────┐
│  bot.py / features.py / tasks.py / nour_onboarding.py         │
│  → discord.utils.get(guild.text_channels, name="EXACT STRING")│
│  → renaming that channel = SILENT no-op, no crash, no error    │
└──────────────────────────────────────────────────────────────┘
                              │
                 This is WHY D001-D006 and D031 happened —
                 channels touched outside setup_server.py drift
                              │
                              ▼
   Sahin's rule: every channel-name-carrying change gets a
   full `grep` sweep across the bot codebase BEFORE it ships,
   and setup_server.py is updated in the SAME PR as any live change.
```

## A real prior failure this design must not repeat

**Bawaba's B3.2** (`.kiro/specs/zero-english-onboarding/tasks.md`)
already tried an HTML2IMG-generated PNG infographic for onboarding and
had to REPLACE it — "PNG was low-res and unreadable on mobile."
Meanwhile, `eec-form`'s Goal Poster feature (using the exact same
`empire-html2img` container) works well in production today, because
it explicitly renders at **2x resolution (2160x3840)** with
large-format text designed for a phone screen.

**Conclusion, stated plainly so it can't be silently forgotten:**
HTML2IMG itself is proven and free — the problem was a careless first
implementation, not the tool. Sahin's cheat-sheet redesign (Component 4
below) explicitly copies the Goal Poster's working pattern (high DPI
scale factor, large legible fonts, tested against a real Discord mobile
preview render) and — critically — **never removes the text fallback**.
If the image version ever renders badly on a real device, the channel
still works via text, exactly like Bawaba's own onboarding guide does
today.

## Component 1 — Per-channel pinned "how to use this channel" posts [NEED]

**Design:**
- Extend `scripts/setup_server.py`'s existing `_post_content()` method
  (currently only handles `welcome`/`rules`/`roles-info`) into a
  data-driven `CHANNEL_GUIDES` dict: `{channel_name: guide_text}`,
  covering every student-facing channel (not admin/ghost-testing ones).
- Reuse the exact idempotency check already in `_post_content()`
  (skip if the bot's own message with length > 100 already exists in
  the channel's last 5 messages) — no new logic needed, just a bigger
  content map.
- **Pin, don't just post** — `_post_content()` currently sends but does
  not pin. Add `await message.pin()` after sending (Discord API call
  already available via `discord.py`), so the guide survives being
  pushed down by daily chat activity — this is the actual point of
  Requirement 1, not just "a message exists somewhere in scroll
  history."
- **Content style** (Arabic-first, per the project's bilingual
  precedent and the user's explicit ask): each guide is short (3-5
  lines), states (a) what this channel is FOR, (b) what to post here /
  what NOT to post here, (c) what happens next (bot response? human
  reply? nothing, it's just for reading?). Example for
  `#l0-showcase`:
  ```
  🎙️ **إيه ده الروم؟**
  هنا بتشارك تسجيلاتك الصوتية وتحتفل بتقدمك!

  ✅ حمّل تسجيلك بعد ما تخلص المهمة الصوتية اليومية
  ✅ رد على زمايلك بكلام إيجابي (بالإنجليزي!)
  ❌ متبعتش نص أو أسئلة هنا — ده مكانه #ask-nour أو #support

  بعد الرفع: البوت بيسجل تقدمك تلقائيًا 🔥
  ```
- **Coverage list** (derived directly from `setup_server.py`'s
  `CATEGORIES_CONFIG`, one guide per student-facing channel — ~35
  channels once ADMIN/Ghost-Testing are excluded): every WELCOME,
  SYSTEM, LEVEL 0-3, COMMUNITY, ACCOUNTABILITY, RESOURCES, and FEEDBACK
  channel gets one. Exact channel list enumerated in `tasks.md`'s
  Phase 1 so nothing is silently skipped.

## Component 2 — Live audit + fix: categorization and permissions [NEED]

**Design — two-pass, both required before either is trusted:**

**Pass A (read-only, first):** a small, disposable Python script
(consistent with this project's existing pattern —
`page_crawler.py`/`api_adversarial_test.py` from Hisn, `diff_against_live.py`
from Aegis) that connects via the bot's own token, and for every real
channel/category on the live guild prints: name, category, type, and
every permission overwrite's raw bitmask. This produces a **point-in-time
ground-truth table** — not a guess, not "should be fine because D031
was fixed last session."

**Pass B (fix, only after Pass A's table is reviewed):** cross-reference
Pass A's live table against `setup_server.py`'s `CATEGORIES_CONFIG`
line by line. Any mismatch becomes a numbered defect entry (continuing
this project's `defect_log.md` sequence past D036), fixed with the
established two-part rule:
1. Fix it live via the Discord API (or by re-running
   `setup_server.py`, which is already idempotent — `.edit()`s existing
   channels/categories rather than erroring).
2. Update `setup_server.py` itself in the same PR if the live fix
   reveals the script was wrong/incomplete (exactly how D006 and D031
   were closed — the live fix alone is not enough, the script must
   also be correct for a future rebuild).

**Known things to specifically re-verify** (not re-derive from
scratch — these are exactly what Hisn already found once, and the
whole point of Sahin's own re-verification discipline is to confirm
they're STILL true, not assume it):
- `#ask-nour` is inside the SYSTEM category with `@everyone` granted
  `VIEW_CHANNEL`+`SEND_MESSAGES`+`READ_MESSAGE_HISTORY` (D031's fix).
- No duplicate/corrupted-emoji categories exist (D001-D003's fix).
- `دليل-القنوات` is present under WELCOME (D006's fix).
- Every category's `@everyone` overwrite matches the *documented
  reasoning* in `setup_server.py`'s own inline comments (SYSTEM/LEVEL
  0/COMMUNITY/ACCOUNTABILITY/RESOURCES/FEEDBACK deliberately grant
  `@everyone` view+send because brand-new members need `#bot-commands`
  before they have any level role — this is intentional, not a bug, and
  Pass A/B must not "fix" it back to fully locked).

## Component 3 — Channel-by-channel review: keep / enhance / merge / archive [NEED + WANT, separated per-channel]

**Design:** a structured pass over every channel in
`setup_server.py`'s `CATEGORIES_CONFIG`, each one getting one of 4
verdicts, recorded as a table in `tasks.md`'s Phase 3 (not left
implicit):

| Verdict | Meaning | Risk level |
|---|---|---|
| **Keep** | Already serves its purpose, no change needed | None |
| **Enhance** [tag per-item] | Real content/behavior gap exists (e.g. `#cheat-sheets`'s missing vocab sheet) | Low — additive only |
| **Merge/consolidate** | Two channels have overlapping-enough purpose that combining reduces confusion | **Highest risk — full code-reference audit required before any merge, see Component 6** |
| **Archive** (never delete) | Genuinely unused; hidden via `@everyone` deny-view rather than deleted, fully reversible | Low — reversible by construction |

**Preliminary read from context already gathered** (to be confirmed
during live execution, not assumed final):
- `#video-library`, `#podcast-recs`, `#book-club` (RESOURCES) —
  currently pure placeholders with a topic string and nothing else;
  likely **Enhance** candidates (real weekly curated content) or
  **Merge** into a single `#resources-library` if usage data (message
  count) shows near-zero independent activity — decision deferred to
  live data, not guessed now.
- `#missed-day-report` — present in the ORIGINAL design doc
  (`LEARNING_SYSTEM_IMPLEMENTATION_PLAN.md`) but **not present** in the
  live `setup_server.py` at all — confirms it was already dropped
  during build, not an oversight to "fix." No action needed; noted so
  a future session doesn't rediscover this as a false alarm.
- `#daily-word` (COMMUNITY) — defined with a topic but no confirmed
  bot-side poster found in `bot.py`/`tasks.py` during context-gathering
  — likely another **Enhance** candidate (same "designed but never
  wired up" pattern as the vocabulary cheat sheet) — to be confirmed
  with a direct grep during Phase 3, not assumed from this doc alone.

## Component 4 — `#cheat-sheets` redesign: the flagship [NEED]

**Design, in three parts:**

**4a — Close the real gap first (before any visual redesign):** wire up
the ALREADY-WRITTEN Weekly Vocabulary Cheat Sheet prompt
(`content/prompts/cheat_sheets.json`, prompt #1) into a new
`@tasks.loop` scheduled task in `bot.py`, modeled directly on the
existing, working `grammar_card_delivery()` (same channel lookup, same
day-of-week trigger pattern, same graceful-skip-if-channel-missing
logic) — posting on a DIFFERENT day than the Wednesday grammar card
(e.g. Sunday, matching this project's existing "don't cluster weekly
posts on the same day" precedent from Masar M2's growth-letter
scheduling). This alone — even with zero visual changes — closes Real
Finding #1 and is the single highest-value, lowest-risk fix in this
whole spec.

**4b — Visual upgrade, image-based, WITH the B3.2 lesson explicitly
applied:**
- New HTML template (same technique as `eec-form`'s poster: HTML/CSS →
  `empire-html2img` → PNG), styled with the Empire dark/gold brand
  (`EMPIRE_BRAND_UNIVERSE.md`'s palette), rendering the week's 8-10
  vocabulary words in a clean, legible grid: English word, simplified
  pronunciation, Arabic translation, one example sentence.
- **Explicit anti-regression checklist before this ever reaches a real
  channel** (directly addressing why B3.2 failed):
  1. Render at minimum 2x scale factor (matching the Goal Poster's
     proven 2160×3840-class approach, adapted to a landscape/vocab-grid
     aspect ratio rather than a portrait poster).
  2. Font size chosen so text is legible when Discord's own client
     downscales the image for its inline chat preview (test against a
     REAL phone screen, not just the full-res file opened on a laptop
     — this exact gap is what made B3.2 fail silently until a human
     actually looked at a phone).
  3. Ship behind a NEW feature flag (`cheat_sheets_visual`, default
     OFF) so it can be tested by the operator alone first, exactly per
     Aegis's own flag-then-release discipline — never flipped on for
     all students until confirmed legible on a real device.
  4. **The text-based version from 4a is NEVER removed** — if
     `cheat_sheets_visual` stays off, or is disabled again after a bad
     real-world render, students still get a fully-functional text
     cheat sheet every week, matching exactly how Bawaba's own
     onboarding guide today has no image dependency at all.

**4c — Occasional brand art, using `macal-empire-image-forge`
sparingly [WANT, not NEED]:** a manually-triggered (not automated —
this pipeline requires a Kaggle GPU session, it cannot run unattended
on a schedule) admin command or documented manual process to generate
one piece of on-brand decorative art (e.g. a monthly "Level Up"
celebration banner, a seasonal cover image for `#announcements`) using
the existing trained LoRA. This is explicitly separate from and
secondary to 4a/4b — it never carries content students must be able to
read.

## Component 5 — `empire-dojo` ↔ Discord harmony [NEED]

**Design (smallest safe first step, not a redesign of either
system):**
- Add one clearly-placed "Join our Discord community" call-to-action
  on `empire-dojo`'s existing pages (landing page and/or `/dash/`
  dashboard — exact placement decided during Phase 5 by looking at the
  live page layout, not guessed here), linking to a real, working
  Discord invite. This closes Real Finding #7's one-directional gap
  with a single, low-risk, purely-additive change — no existing
  `empire-dojo` behavior is touched.
- Confirm (does not yet exist — must be created and treated as a
  semi-permanent value, not regenerated per session) a **non-expiring
  or long-lived Discord invite link**, generated once via Discord's own
  Server Settings → Invites, stored in `empire-dojo`'s config the same
  way `PRACTICE_PLATFORM_URL` is stored in the bot's config today
  (a plain constant, not a secret).
- **[WANT, lower priority]** Shared visual identity pass: confirm the
  dashboard's existing dark/gold theme (already built per Wuslah) and
  Discord's role colors/embed colors use the literal same hex values
  from `EMPIRE_BRAND_UNIVERSE.md` — a consistency check, not new
  design work.

## Component 6 — The rename/merge safety net [process, applies to any Component above that touches an existing channel name]

**This is not optional scaffolding — it is the actual mechanism that
prevents Sahin from becoming D001-D006 or D031 all over again.**

Before ANY existing channel is renamed or merged (never applies to
brand-new channels, which have no existing references to break):

1. `grep -rn "<exact-current-name>" bots/discord-learning-bot/src/`
   across the whole bot source tree. Record every hit.
2. For each hit, confirm whether it's a literal channel-name lookup
   (must be updated) or just an unrelated string coincidence (rare, but
   check — don't assume every match matters).
3. Update every real hit AND `setup_server.py`'s own channel
   definition, in the SAME commit/PR as the rename.
4. Run the full test suite (`pytest tests/`) — channel-name references
   inside f-strings/messages won't be caught by tests, but this at
   least confirms nothing else broke.
5. Only THEN apply the rename live via the Discord API (or a
   `setup_server.py` re-run), immediately followed by a live
   confirmation that the renamed channel's dependent bot features still
   fire correctly (e.g. if `#cheat-sheets` were ever renamed, manually
   trigger `grammar_card_delivery()`'s logic path and confirm it still
   finds the channel).

**If any Component above's Phase in `tasks.md` does NOT need to rename
an existing channel to achieve its goal, prefer that path — this
safety net exists because renames are the single highest-risk category
of change here, not because renames are forbidden outright.**

## What this design deliberately does NOT do

- **No Server Boosts, in any form.** Confirmed explicitly out of scope
  by the user — no animated icons, no vanity URL, no boosted audio
  quality anywhere in this design. The only visual-identity changes
  considered (Component 5's shared-brand-color check) require zero
  spend and work within the server's free base tier.
- **No deletion of any existing channel, category, role, or message.**
  "Archive" always means hidden (permission deny), never deleted —
  fully reversible by construction, per the user's explicit "don't lose
  what we built" instruction.
- **No new paid service, dependency, or hosting.** Every mechanism here
  runs on infrastructure that already exists and is already free:
  the bot's own process, `empire-html2img` (already running), Gemini/
  Groq free tiers (already in use), Cloudflare Pages free tier (already
  in use for `empire-dojo`).
- **Does not touch Aegis, Masar, Hisn, Wuslah, Markaz, or any other
  completed initiative's own code paths**, except where Component 2's
  audit finds a genuine channel/permission defect that must be fixed
  regardless (same standard this project has always applied — a real,
  live defect gets fixed the moment it's found, not deferred
  indefinitely).

## Open design questions (flag to user, don't guess)

1. **`#cheat-sheets` visual redesign (Component 4b) timing:** should
   the image-based version be attempted at all in this spec's first
   pass, or should Phase 1 ship ONLY the text-based fix (4a) and treat
   the visual upgrade as a deliberately separate, later phase — given
   the real B3.2 precedent of an image approach failing once already?
   My recommendation, stated so it's a deliberate choice not a silent
   default: **ship 4a alone first, prove it live for at least one real
   week, and only then decide whether 4b is worth the added testing
   burden** — but this is the user's call, not mine to assume.
2. **Channel merge candidates (Component 3):** `#video-library`/
   `#podcast-recs`/`#book-club` — worth merging into one channel now,
   or leave as three separate (low-risk either way, since merging is
   the higher-risk category per Component 6) until real usage data
   exists once students are actually invited? Recommendation: **defer
   any merge decision until real usage data exists** — right now there
   are 0 real students, so "low activity" would be guaranteed and
   uninformative either way.
