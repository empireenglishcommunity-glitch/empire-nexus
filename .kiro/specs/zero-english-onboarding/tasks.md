# Tasks — Bawaba: Zero-English Onboarding

> **How to use this file:** same discipline as the Aegis spec — work top
> to bottom, check off tasks in the same commit/PR that completes them.
> Each phase ships behind a feature flag, tested on the ghost bot first.

---

## Phase B0 — Arabic Command Aliases + Number Commands (highest impact, lowest effort)

- [ ] **B0.1** Add the Arabic alias rewriting logic to `bot.py`'s
  `on_message` — intercept messages starting with `!` + an Arabic word
  from the lookup table, rewrite to the English equivalent, then let
  `bot.process_commands()` handle it normally. Include task aliases
  (نطق=accent, مفردات=vocab, etc.) for `!تم` arguments.
- [ ] **B0.2** Add number-based task mapping to `cmd_done` — if the
  argument is a digit 1-7, map to `config.DAILY_TASKS[n-1]["id"]`.
  Also handle `!تم 1` through `!تم 7`.
- [ ] **B0.3** Add an Arabic `!مساعدة` response — a full help message in
  Arabic showing all Arabic aliases and number commands, sent when the
  student uses the Arabic help alias.
- [ ] **B0.4** Gate behind feature flag `bawaba_aliases`. Test on ghost
  bot (`?تم 1`, `?انضم`, `?مساعدة`), then enable for everyone.
- [ ] **B0.5** Add tests: Arabic alias rewriting produces correct English
  commands; number mapping covers all 7 tasks; unknown numbers rejected.

## Phase B1 — Emoji-React Registration + Task Completion

- [ ] **B1.1** Add `on_raw_reaction_add` handler: detect ✅ reaction on
  designated "welcome" messages → auto-register the user if not already
  registered. Send Arabic confirmation DM.
- [ ] **B1.2** After posting daily tasks, bot adds 1️⃣-7️⃣ reactions to
  its own message. Detect student reactions on daily task posts →
  trigger the same verification + submission flow as `cmd_done`.
- [ ] **B1.3** Gate behind feature flag `bawaba_reactions`.
- [ ] **B1.4** Add tests: reaction-based registration creates member;
  duplicate reaction is no-op; number reaction maps to correct task.

## Phase B2 — Interactive Tutorial Quest (on first join)

- [ ] **B2.1** Implement the 5-step DM tutorial state machine in
  `features.py` (pattern: `_pending_tutorials` dict, same as exam DM
  collection). Steps: type 1 → type hello → type !تقدم → go to channel
  and type !1 → completion message. Awards 15 points.
- [ ] **B2.2** Trigger the tutorial after registration (both command-based
  and reaction-based registration paths). Replace the current 4-message
  welcome DM wall with: 1 short greeting + start the tutorial.
- [ ] **B2.3** Handle edge cases: student goes idle mid-tutorial (resume
  where they left off on next DM); student types something unexpected
  (gentle Arabic nudge back to the current step); student completes
  tutorial twice (no-op, no double points).
- [ ] **B2.4** Gate behind feature flag `bawaba_tutorial`.
- [ ] **B2.5** Add tests: tutorial completes end-to-end; points awarded
  once; resumption works; completion is idempotent.

## Phase B3 — Voice-First + Visual Onboarding

- [ ] **B3.1** Write Arabic scripts for 4 voice clips (welcome, register,
  daily tasks, mark done). Generate via Kokoro TTS on the server.
  Evaluate quality — if Arabic voice sounds unnatural, flag to user
  for manual recording instead.
- [ ] **B3.2** Generate the visual journey map (HTML template → PNG via
  empire-html2img). Arabic labels, step arrows, clean design.
- [ ] **B3.3** Integrate into the welcome DM: send the PNG as an
  attachment + the 4 audio clips as file attachments (or links to
  hosted files if Discord attachment size is a concern).
- [ ] **B3.4** Add the Day-0 video YouTube link to the welcome DM (the
  actual video is created by the user, not the agent — just wire the
  link). Use a feature flag or a config value so the link can be
  updated without a code change.
- [ ] **B3.5** Gate behind feature flag `bawaba_multimedia`.

## Phase B4 — Buddy-Guided First Day

- [ ] **B4.1** Extend `assign_buddy()` to send a richer DM to the buddy:
  include the new student's name, their level, today's first task
  (pulled from curriculum), and a specific action suggestion ("Send
  them a voice message in Arabic explaining...").
- [ ] **B4.2** Gate behind feature flag `bawaba_buddy_prompt`.

## Phase B5 — Gradual English Injection

- [ ] **B5.1** Add `response_language(discord_id) -> str` function to
  `features.py` or a new `localization.py` module. Returns "arabic" /
  "bilingual_ar_first" / "bilingual" based on member's week number.
- [ ] **B5.2** Create an extended `bl()` helper that respects the
  member's language phase (week 1: Arabic only; week 2-3: Arabic +
  English; week 4+: current bilingual). Apply to `cmd_done` responses,
  `cmd_progress`, streak messages, and the daily task post.
- [ ] **B5.3** For "arabic" phase: bot responses use ONLY Arabic text,
  command hints show numbers/Arabic aliases instead of English commands.
- [ ] **B5.4** Gate behind feature flag `bawaba_gradual_english`.
- [ ] **B5.5** Add tests: response_language returns correct phase for
  week 1/2/3/4+ members; bl_extended outputs correct format per phase.

## Phase B6 — First-Day Channel (simplified approach)

- [ ] **B6.1** Add `#start-here` (or `#يوم-واحد`) channel to
  `setup_server.py` — visible to @everyone, pinned message with the
  visual map + Arabic explanation + video link.
- [ ] **B6.2** Update the welcome DM to prominently direct new members
  to this channel FIRST: "روح #start-here وابدأ من هناك"
- [ ] **B6.3** Gate behind feature flag `bawaba_start_channel`.

---

## Cross-phase notes

- **Feature flag naming:** all use the `bawaba_` prefix for easy
  identification via `!flag list`.
- **Ghost bot testing:** test each phase on the ghost bot (`?` prefix)
  before enabling on production — per the Aegis workflow.
- **Phase 7 (Aegis marketing):** once B0 is live and verified with
  real students, post the first bilingual `!announce` — "You can now
  use Arabic commands! / دلوقتي تقدر تستخدم أوامر بالعربي!" — this
  simultaneously completes Aegis Phase 7 and announces Bawaba to
  students.
- **The Day-0 video (B3.4)** requires the user to record it themselves
  (a screen recording of the real Discord mobile app). The agent's job
  is to wire the link, not create the video content.
- **Kokoro Arabic quality (B3.1):** must be tested before committing.
  If it sounds robotic, fall back to user-recorded audio. Infrastructure
  is the same either way.
