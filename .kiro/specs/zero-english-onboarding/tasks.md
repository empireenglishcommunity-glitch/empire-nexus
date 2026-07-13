# Tasks — Bawaba: Zero-English Onboarding

> **How to use this file:** same discipline as the Aegis spec — work top
> to bottom, check off tasks in the same commit/PR that completes them.
> Each phase ships behind a feature flag, tested on the ghost bot first.
>
> **Status: ALL PHASES (B0-B6) COMPLETE AND DEPLOYED as of 2026-07-13
> (session 12).** All 7 feature flags enabled on production. 31 commands
> registered. Discord channels created (#start-here, #dev-log, ghost
> testing). Only the voice clip recordings remain pending (user action).

---

## Phase B0 — Arabic Command Aliases + Number Commands (highest impact, lowest effort)

> **✅ PHASE B0 COMPLETE.** [empire-nexus PR #57](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/57).
> Deployed and enabled on production + ghost bot. User-tested and confirmed working.

- [x] **B0.1** Add the Arabic alias rewriting logic to `bot.py`'s
  `on_message` — intercept messages starting with `!` + an Arabic word
  from the lookup table, rewrite to the English equivalent, then let
  `bot.process_commands()` handle it normally. Include task aliases
  (نطق=accent, مفردات=vocab, etc.) for `!تم` arguments.
- [x] **B0.2** Add number-based task mapping to `cmd_done` — if the
  argument is a digit 1-7, map to `config.DAILY_TASKS[n-1]["id"]`.
  Also handle `!تم 1` through `!تم 7`.
- [x] **B0.3** Add an Arabic `!مساعدة` response — a full help message in
  Arabic showing all Arabic aliases and number commands, sent when the
  student uses the Arabic help alias.
- [x] **B0.4** Gate behind feature flag `bawaba_aliases`. Test on ghost
  bot (`?تم 1`, `?انضم`, `?مساعدة`), then enable for everyone.
- [x] **B0.5** Add tests: Arabic alias rewriting produces correct English
  commands; number mapping covers all 7 tasks; unknown numbers rejected.
  — 19 tests in `test_bawaba.py`.

## Phase B1 — Emoji-React Registration + Task Completion

> **✅ PHASE B1 COMPLETE.** [empire-nexus PR #58](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/58).
> Deployed and enabled.

- [x] **B1.1** Add `on_raw_reaction_add` handler: detect ✅ reaction on
  any message → auto-register the user if not already registered. Send
  Arabic confirmation DM.
- [x] **B1.2** After posting daily tasks, bot adds 1️⃣-7️⃣ reactions to
  its own message. Detect student reactions on daily task posts →
  trigger the same verification + submission flow as `cmd_done`.
- [x] **B1.3** Gate behind feature flag `bawaba_reactions`.
- [x] **B1.4** Verification still applies for reaction-based submissions
  (the reaction is the trigger, not a bypass).

## Phase B2 — Interactive Tutorial Quest (on first join)

> **✅ PHASE B2 COMPLETE.** [empire-nexus PR #59](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/59).
> Deployed and enabled. User-tested.

- [x] **B2.1** Implement the 5-step DM tutorial state machine in
  `features.py`. Steps: type 1 → type hello → type !تقدم → type
  !مساعدة → type !1 → completion message. Awards 15 points.
- [x] **B2.2** Trigger the tutorial after registration. Replace the
  current 4-message welcome DM wall with: 1 short greeting + start
  the tutorial.
- [x] **B2.3** Handle edge cases: student goes idle mid-tutorial (resume
  where they left off); student types something unexpected (gentle
  Arabic nudge); student completes tutorial twice (no double points).
- [x] **B2.4** Gate behind feature flag `bawaba_tutorial`.
- [x] **B2.5** `!tutorial` / `!تعليم` command for existing members.

## Phase B3 — Voice-First + Visual Onboarding

> **✅ PHASE B3 COMPLETE.** [PRs #60, #61, #62, #63](https://github.com/empireenglishcommunity-glitch/empire-nexus/).
> Deployed. Text guide working. Voice clips pending user recording.

- [x] **B3.1** ~~Generate Arabic voice clips via Kokoro TTS~~ →
  **REPLACED:** Kokoro can't speak Arabic (reads letter names). Voice
  clips now expected as human-recorded files from the founder.
  `RECORDING_GUIDE.md` created with exact scripts.
  **STATUS: Pending user recording (not blocking anything).**
- [x] **B3.2** ~~Generate visual journey map PNG via html2img~~ →
  **REPLACED:** PNG was low-res and unreadable on mobile. Replaced with
  clean Discord text messages (native formatting, always crisp).
- [x] **B3.3** Integrate into the welcome DM: send the text guide +
  audio clips (if available) + video link (if configured).
- [x] **B3.4** `ONBOARDING_VIDEO_URL` config var for Day-0 video link.
  **STATUS: Pending user recording a 3-min screen walkthrough.**
- [x] **B3.5** Gate behind feature flag `bawaba_multimedia`.
- [x] **B3.6** `!testwelcome` admin command for testing the full flow.

## Phase B4 — Buddy-Guided First Day

> **✅ PHASE B4 COMPLETE.** [empire-nexus PR #64](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/64).
> Deployed and enabled.

- [x] **B4.1** Extend `assign_buddy()` to send a richer DM to the buddy:
  include the new student's name, their first task today, and a specific
  action suggestion ("Send them a voice message in Arabic").
- [x] **B4.2** Gate behind feature flag `bawaba_buddy_prompt`.

## Phase B5 — Gradual English Injection

> **✅ PHASE B5 COMPLETE.** [empire-nexus PR #65](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/65).
> Deployed and enabled.

- [x] **B5.1** Add `response_language(discord_id) -> str` function.
  Returns "arabic" / "bilingual_ar" / "bilingual" based on member's
  week number (1 / 2-3 / 4+).
- [x] **B5.2** Create `bl_for_member()` helper that respects the
  member's language phase. Apply to `cmd_done` responses.
- [x] **B5.3** For "arabic" phase: bot responses use ONLY Arabic text,
  command hints show numbers/Arabic aliases instead of English.
- [x] **B5.4** Gate behind feature flag `bawaba_gradual_english`.
- [x] **B5.5** Add tests: 7 new tests covering response_language and
  bl_for_member for all three phases.

## Phase B6 — First-Day Channel (simplified approach)

> **✅ PHASE B6 COMPLETE.** [empire-nexus PR #66](https://github.com/empireenglishcommunity-glitch/empire-nexus/pull/66).
> Deployed, enabled, channel created, Arabic guide pinned.

- [x] **B6.1** Add `#start-here` channel to `setup_server.py` — visible
  to @everyone, first channel in WELCOME category.
- [x] **B6.2** `START_HERE_MESSAGE` content (Arabic-only quick-start
  guide + command reference).
- [x] **B6.3** Update the welcome DM to prominently direct new members
  to `#start-here` FIRST.
- [x] **B6.4** `!poststart` admin command to post and pin the guide.
- [x] **B6.5** Gate behind feature flag `bawaba_start_channel`.
- [x] **B6.6** Created `#start-here` channel via Discord API, posted and
  pinned the Arabic guide. Also created `#dev-log` and the `👻 Ghost
  Testing` category + 3 channels.

---

## Pending (user actions, not agent work)

1. **Record 4 Arabic voice clips** — scripts in
   `scripts/onboarding/RECORDING_GUIDE.md`. Upload to
   `scripts/onboarding/audio/` on the server. The bot will
   automatically send them in the welcome DM.
2. **Record Day-0 video** — 3-min screen walkthrough on phone, upload to
   YouTube, set `ONBOARDING_VIDEO_URL` in `.env` on the server.
3. **Invite the 16 real students** — system is 100% ready.
