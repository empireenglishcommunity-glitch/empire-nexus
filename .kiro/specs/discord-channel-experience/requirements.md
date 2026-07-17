# Requirements — Discord Channel & Community Experience ("Sahin")

> **Codename: Sahin** (صَقر — falcon). Internal name for this initiative,
> used throughout this spec and future commit messages/PRs for easy
> cross-referencing. Directory name (`discord-channel-experience`) stays
> literal/technical so it's discoverable without knowing the codename.

## Origin

The user is preparing to run the Discord server as the primary,
professional, paid learning community for Empire English — 16 real
students (9 free + 7 paid) are expected to join, though **the
production database is confirmed at 0 real members as of this
writing**, which is the rare, low-risk window this whole initiative is
timed to use.

User's explicit ask, gathered across a multi-turn conversation and
confirmed directly with them before writing this spec:

1. Every channel should have a **pinned, Arabic-language post**
   explaining what the channel is for and how to use it — to reduce
   repeated "what is this channel for" questions from Arabic-speaking
   students.
2. `#ask-nour` was reported as "not classified in any category" — this
   turned out to already be fixed by Hisn's D031 fix (moved into the
   SYSTEM category with correct permissions), but must be **re-verified
   live**, not assumed fixed from a prior session's notes.
3. A full **permissions review** across every channel/category, to
   prevent any future problem for real students and make onboarding
   "go easy."
4. A full, **channel-by-channel creative brainstorm** to make every
   channel practical, professional, and content-rich, with **harmony
   between channels, categories, the bot, and the practice webpage
   (`empire-dojo`)** — explicitly requested to be written up as a full
   spec (requirements → design → phased implementation), the same way
   "Aegis" was, and executed in order.
5. Any other **needed** (not merely wanted) improvement should be
   folded into this plan — the user explicitly asked that "needs" and
   "wants" be kept distinct so priority is never ambiguous.
6. Investigate unlocking more Discord platform features/themes to make
   this "the best community ever" — investigated and clarified with the
   user: this is Discord's real-money **Server Boost** mechanism.
   **The user has explicitly said they cannot spend money on this —
   Server Boosts are OUT OF SCOPE for this spec, in full.** See
   "Explicitly out of scope" below.
7. The `#cheat-sheets` channel specifically was called out as
   unprofessional, poorly organized, and hard for students to
   understand — with an explicit suggestion to look at image-based
   cheat sheets, referencing the AI image-generation pipeline
   (`macal-empire-image-forge`) trained earlier in this project.

## Real findings surfaced while gathering context for this spec

These are concrete, code-verified facts (not assumptions) that directly
shape the requirements below:

1. **The weekly Vocabulary Cheat Sheet was never actually wired up.**
   `content/prompts/cheat_sheets.json` defines the prompt and
   `content/prompts/README.md` marks it "✅ deployed," but no code path
   in `bot.py`/`features.py`/`tasks.py` ever calls it or posts its
   output anywhere. Only the separate **Grammar Pattern Card**
   (`grammar_card_delivery()`, Wednesdays) actually posts to
   `#cheat-sheets` today. This is the SAME root-cause pattern already
   found and fixed 3 times this project (D012, D020, D036): a feature
   fully designed and marked complete, with zero real call site. Real
   students today would see an occasional grammar-card wall of text and
   **nothing else** in `#cheat-sheets` — no weekly vocabulary reference
   at all.
2. **Every channel lookup in the bot is by exact name string**
   (`discord.utils.get(guild.text_channels, name="...")`), across
   `bot.py`, `features.py`, `nour_onboarding.py`, `tasks.py`. There is
   no channel-ID-based lookup anywhere. **Renaming a channel silently
   breaks any bot feature keyed to its old name — no crash, no error,
   just a silent no-op** (confirmed in `grammar_card_delivery()`, which
   at least logs a warning; other lookups do not even do that).
3. **This exact fragility has already caused real, documented
   incidents**: D001-D006 (corrupted/duplicated categories, permission
   drift from the setup script) and D031 (`#ask-nour` invisible to
   every real student for an unknown period) both trace back to
   channels/categories being created or edited outside
   `scripts/setup_server.py`, which is supposed to be the single source
   of truth.
4. **The image-generation pipeline (`macal-empire-image-forge`) is a
   real, working SDXL LoRA trained on the Empire brand aesthetic
   (dark/gold, imperial/luxury architectural and object photography),
   but it has NO text-rendering capability and is not a push-button
   API** — it runs on Kaggle's free GPU tier via a manual, session-based
   workflow (minutes per image, no persistent server). It is well
   suited to occasional decorative brand art, and NOT well suited to
   generating vocabulary tables or grammar cards with legible text —
   SDXL models are notoriously unreliable at rendering readable text
   inside an image, and this pipeline's own prompts don't attempt it.
5. **`empire-scribe`'s existing HTML2IMG service** (a self-hosted,
   already-running Docker container on the same Hetzner server, used
   today for the Student Goals Form poster feature) is a proven,
   zero-new-cost pattern for turning structured HTML/CSS into a clean,
   branded image — reliable, instant, no GPU session required. This is
   the right tool for cheat-sheet content specifically; the LoRA
   pipeline is the right tool for occasional hero/decorative art.
6. **No channel currently has a per-channel "what is this for" pinned
   post.** `#welcome`/`#rules`/`#roles-info` get one-time bot-posted
   content via `setup_server.py`, but every other functional channel
   (daily-tasks, showcase, feedback channels, resources, etc.) does
   not.
7. **`empire-dojo` (the practice webpage) has zero Discord-facing
   cross-links today.** Integration is one-directional: the bot links
   students TO the practice platform (`PRACTICE_PLATFORM_URL`), but the
   practice platform never references Discord channels, invites, or
   community content back.

## Constraints (do not violate these while designing solutions)

1. **Zero tolerance for breaking anything currently working.** The user
   has explicitly stated significant time was invested building the
   current system and it must not be lost or destabilized. Every change
   in the design/tasks that follows must be additive-first; any
   necessary rename/merge must include a full code-reference audit and
   update in the same PR, never a bare Discord-side rename.
2. **No new paid services, no Server Boosts, no budget spend of any
   kind.** Confirmed directly with the user. Every solution must work
   within the existing $0-marginal-cost infrastructure (self-hosted bot,
   free-tier AI APIs, the existing HTML2IMG container, Cloudflare Pages
   free tier).
3. **Arabic-first, practical, professional** — all student-facing
   content (pinned posts, cheat sheets, channel topics) must be
   genuinely usable by Arabic-speaking students with limited English,
   consistent with the bilingual-by-default precedent already
   established in this project (session 6's website + Discord bilingual
   UI work).
4. **`scripts/setup_server.py` remains the single source of truth** for
   server structure. Any new channel, category, permission pattern, or
   pinned-content mechanism must be added there first, then applied
   live — never the reverse (live-first, script-later is exactly the
   process gap that caused D031).
5. **SSH/API access is always temporary** in this working pattern (keys
   never survive between sessions). Any live Discord change requires a
   fresh access grant, a pre-change state snapshot (export current
   channel/permission state before touching it), and a live
   re-verification after — the same discipline already used throughout
   this project's defect-fixing history (D033-D036).
6. **Must not regress anything already shipped** — Masar (all M0-M5),
   Hisn (D001-D036 resolved, D035's scope closed), Aegis (feature
   flags, backups, deploy tooling) all remain untouched and working.

## Requirements

### Requirement 1 — Every channel must explain itself to a new Arabic-speaking student
**User story:** As a new Arabic-speaking student, I want to immediately
understand what each channel is for and how to use it without having to
ask, so that I feel confident navigating the server from day one.

**Acceptance criteria:**
1. WHEN a student opens any student-facing text channel THEN a pinned
   message SHALL be visible, written primarily in Arabic (mirroring the
   project's existing bilingual precedent — Arabic-first with English
   channel/command names kept literal where students need to type or
   recognize them), explaining the channel's purpose and exactly how to
   use it (what to post, what NOT to post, what happens after posting).
2. WHEN `scripts/setup_server.py` is re-run against a fresh or existing
   server THEN it SHALL be able to create and pin this content
   idempotently (matching the existing pattern already used for
   `#welcome`/`#rules`/`#roles-info` — skip if already posted, don't
   duplicate).
3. WHEN a channel's purpose changes in the future THEN there SHALL be
   one clear place (the setup script's content map) to update the
   pinned explanation, not scattered ad-hoc messages.

### Requirement 2 — `#ask-nour` and every other channel must be correctly categorized and visible
**User story:** As a student, I want every channel to be inside a
sensible category and visible/usable according to my level, so I never
hit an invisible or broken channel.

**Acceptance criteria:**
1. WHEN the live Discord server's current channel/category structure is
   inspected THEN it SHALL be compared directly against
   `scripts/setup_server.py`'s definitions (channel-by-channel,
   category-by-category), not assumed correct from a prior session's
   defect-log entry.
2. IF any channel is found uncategorized, miscategorized, or missing
   the standard `@everyone`/level-role permission overwrites its
   category's pattern requires THEN it SHALL be fixed directly on the
   live server AND the fix SHALL be reflected in
   `scripts/setup_server.py` in the same change (never one without the
   other — this is the exact process gap that caused D031).
3. WHEN this requirement's work is complete THEN a fresh full read of
   every channel's category, type, and permission overwrites SHALL be
   recorded as a point-in-time audit table in this spec's `design.md`
   or a dedicated audit note, for future sessions to compare against.

### Requirement 3 — Permissions must be reviewed and hardened end-to-end
**User story:** As the operator, I want confidence that no channel can
surprise a real student (invisible channel, wrong write access, an
admin channel leaking to members) before or after real students join.

**Acceptance criteria:**
1. WHEN every category's permission overwrites are reviewed THEN each
   SHALL be checked against its OWN stated purpose (e.g. admin
   categories deny all member roles; level-zone categories correctly
   gate by level; universally-visible categories like SYSTEM/COMMUNITY
   correctly grant `@everyone` per the already-documented onboarding
   requirement — new members need `#bot-commands` before they have any
   level role).
2. WHEN a permission gap or inconsistency is found THEN it SHALL be
   logged (same defect-log discipline as D001-D036) and fixed with the
   same "live fix + script fix, together" rule as Requirement 2.2.
3. WHEN this requirement's work is complete THEN a simple, repeatable
   verification method SHALL exist (a script or a documented manual
   check) so a future session can re-verify permissions match intent
   without re-deriving the whole audit from scratch.

### Requirement 4 — Every channel must have practical, professional, non-generic content and purpose
**User story:** As a student paying for a professional English-learning
product, I want every channel I open to feel intentional, useful, and
worth my time — not a generic, half-used, or confusing placeholder.

**Acceptance criteria:**
1. WHEN each of the ~50 existing channels is reviewed individually
   THEN a decision SHALL be recorded for each one: keep as-is (already
   good), enhance (needs real content/behavior it's currently missing),
   merge/consolidate (overlaps meaningfully with another channel), or
   archive (genuinely unused, hidden rather than deleted per the
   no-destructive-changes constraint).
2. WHEN `#cheat-sheets` specifically is addressed THEN it SHALL
   deliver BOTH: (a) the currently-missing weekly Vocabulary Cheat
   Sheet (Real Finding #1 above — this prompt already exists and only
   needs a real call site), and (b) a genuinely improved, organized,
   legible visual format — using the self-hosted HTML2IMG pipeline for
   structured content (vocabulary tables, grammar cards) and the
   `macal-empire-image-forge` LoRA sparingly for occasional on-brand
   decorative/cover art, never for content requiring legible text.
3. WHEN any channel is enhanced THEN the resulting content generation
   SHALL run on the existing free-tier AI APIs (Gemini/Groq) and the
   existing self-hosted HTML2IMG container — no new paid service.
4. WHEN this requirement's work is complete THEN the harmony explicitly
   requested by the user SHALL be demonstrable: at least one real,
   working cross-link exists from `empire-dojo` (the practice webpage)
   back toward the Discord community (e.g. a visible "join us on
   Discord" / community CTA), closing the currently one-directional
   integration gap (Real Finding #7).

### Requirement 5 — Needs vs. wants must stay explicitly separated throughout
**User story:** As the operator with limited time and no budget for
this initiative, I want to always know which proposed change is solving
a real, current problem versus which is a nice-to-have, so I can cut
scope without re-reading the whole plan.

**Acceptance criteria:**
1. WHEN any enhancement idea is proposed in `design.md` or `tasks.md`
   THEN it SHALL be explicitly tagged **[NEED]** (a real, current gap:
   broken promise, confusing UX, fragility risk, or missing feature
   with real demand) or **[WANT]** (a genuine improvement, not blocking
   anything).
2. WHEN `tasks.md`'s phases are ordered THEN all [NEED]-tagged work
   SHALL be sequenced before [WANT]-tagged work, so that stopping early
   at any phase boundary still leaves the system strictly better than
   before with no half-finished, broken enhancement in progress.

### Requirement 6 — This plan itself must survive the session, the account, or the agent changing
**User story:** As the operator, I want to be able to close this
session and resume this exact plan later — a different session, a
different Kiro account, even a different underlying agent — without
re-explaining the goal or re-deriving the design.

**Acceptance criteria:**
1. WHEN this spec is created THEN it SHALL be committed to
   `empire-nexus` at `.kiro/specs/discord-channel-experience/`,
   containing `requirements.md` (this file), `design.md`, and
   `tasks.md`.
2. WHEN this spec is created THEN `empire-chronicle`'s `STATUS.md`
   SHALL be updated with a pointer to it, since that repo is this
   project's established cross-session entry point.
3. WHEN a task in `tasks.md` is completed THEN it SHALL be checked off
   in the same commit that completes it — accurate, current, never
   drifting from reality, per this project's own established
   discipline.

## Explicitly out of scope for this spec

- **Discord Server Boosts, in full.** Investigated and clarified with
  the user (animated icon/banner, more emoji slots, vanity URL, higher
  audio quality, etc. are all real, but cost real money per month with
  no free path). **The user explicitly cannot spend money on this —
  do not design, recommend, or budget for Server Boosts anywhere in
  this initiative.** If a genuinely free visual/branding improvement
  exists that does NOT require boosting (e.g. a static custom server
  icon/banner the owner already has rights to upload, which is free up
  to the server's base tier limits), that remains in scope as a [WANT]
  — only the paid boost mechanism itself is excluded.
- **Rebuilding or replacing anything already shipped and working**
  (Aegis's feature flags/deploy tooling, Masar's M0-M5, Hisn's
  D001-D036 fixes, Wuslah's dashboard/API unification). This spec adds
  to and hardens the channel/community layer; it does not redo prior
  work.
- **Training a new or different AI image model.** The existing
  `macal-empire-image-forge` LoRA is used as-is, for the narrow use
  case it's actually good at (occasional brand art) — retraining,
  fine-tuning, or building a text-rendering-capable model is a much
  larger, separate project not requested here.
- **Migrating the practice webpage or bot off their current
  hosting/stack.** Any `empire-dojo` cross-link work uses the existing
  Cloudflare Pages deployment as-is.
- **Building a moderation team or new admin roles.** Permission review
  (Requirement 3) audits and fixes the EXISTING role/permission model;
  it does not introduce new roles or a moderation program.
