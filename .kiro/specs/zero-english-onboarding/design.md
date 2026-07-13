# Design — Bawaba: Zero-English Onboarding

## Architecture: Layered Accessibility

The system already works for students with some English. Bawaba adds
**layers on top** — each layer makes the system accessible to a lower
level of English literacy, without changing what's underneath:

```
Layer 5: Gradual English injection (bot language evolves over weeks)
Layer 4: First-day channel + buddy voice prompt
Layer 3: Interactive tutorial quest (learn by doing)
Layer 2: Emoji-react alternatives (zero typing)
Layer 1: Arabic aliases + number commands (zero English typing)
Layer 0: Current system (requires English literacy) ← unchanged
```

A student at any level of English finds the layer that works for them
and "enters" the system there. As they progress, they naturally move
toward Layer 0 (the full English interface) — which is the actual
learning goal.

---

## Component 1 — Arabic Command Aliases (Layer 1)

**Design:** A lookup table in `bot.py` mapping Arabic strings to
existing command handlers. NOT separate commands — the same handler
function, just reached via a different input string.

```python
ARABIC_ALIASES = {
    "انضم": "join",
    "تم": "done",
    "خلص": "done",
    "تقدم": "progress",
    "مساعدة": "help",
    "سلسلة": "streak",
    "مستوى": "level",
    "أسبوع": "week",
    "تقييم": "assess",
    "ترتيب": "top",
    "سلسلات": "streaks",
    "حالة": "systemstatus",
    "صيانة": "maintenance",
}

ARABIC_TASK_ALIASES = {
    "نطق": "accent",
    "مفردات": "vocab",
    "محاكاة": "shadow",
    "كلام": "speaking",
    "استماع": "listening",
    "كتابة": "writing",
    "مجتمع": "community",
}
```

Implementation: override `on_message` to check if a message starts with
`!` followed by an Arabic alias, and if so, rewrite it to the English
equivalent before `bot.process_commands()` runs. This means EVERY
existing command handler works with Arabic input for free — no per-
command changes needed.

## Component 2 — Number-Based Task Commands (Layer 1)

**Design:** `!1` through `!7` map to the 7 tasks in `config.DAILY_TASKS`
order (same order as the daily post's numbered list). Also `!تم 1`
through `!تم 7`.

Implementation: a small lookup in `cmd_done` — if the task argument is
a digit 1-7, map it to `config.DAILY_TASKS[int(task)-1]["id"]`. Three
lines of code.

## Component 3 — Emoji-React Registration (Layer 2)

**Design:** When a new member joins (or in a welcome channel), post a
message with ✅ reaction. On reaction_add from a non-bot, non-registered
user → auto-register them (same as `!join` with no goal). For daily
tasks: the daily task post gets number reactions (1️⃣-7️⃣) added by the
bot itself. A student reacting with a number → treated as `!done <task>`.

Implementation:
- `on_raw_reaction_add` event handler
- Check: is this reaction on a "registrable" message? Is the user not
  yet registered? → `register_member()`
- Check: is this reaction on today's daily task post? Is it a number
  emoji? → trigger the same verification flow as `cmd_done`

**Key constraint:** verification still runs. A ✅ on the accent task
still requires an audio upload in #showcase first. The reaction is the
*trigger*, not a bypass.

## Component 4 — Visual Journey Map (Layer 2)

**Design:** A PNG infographic generated via `empire-html2img` (already
running on the server at port 3200). Shows the student's path:
- Arabic text labels
- Arrows connecting steps
- Screenshots/mockups of what each step looks like
- Sent as an attachment in the welcome DM (alongside the text)

Implementation: an HTML template → rendered to PNG via the existing
html2img service → cached (same image for all L0 students until the
flow changes). Sent in `on_member_join` as a file attachment.

## Component 5 — Voice-First Onboarding (Layer 2/3)

**Design:** Pre-generated Arabic audio clips (Kokoro TTS on the server,
port 8880) explaining:
1. "Welcome + what this server is" (30s)
2. "How to register" (30s)
3. "How daily tasks work" (45s)
4. "How to mark tasks done" (30s)

These are **pre-generated once** (not on-the-fly per student) and
stored as MP3 files in the repo or on the server. Sent as Discord
file attachments in the welcome DM sequence.

**Language:** Egyptian Arabic (informal, matching the existing bot
messages' register). Script written by the bot/agent, recorded via
Kokoro's Arabic voice.

## Component 6 — Interactive Tutorial Quest (Layer 3)

**Design:** A DM-based interactive sequence triggered on first join
(after registration). 5 steps:

1. "اكتب الرقم 1" → student types `1` → "ممتاز! ده أول أمر ليك"
2. "دلوقتي اكتب: hello" → student types `hello` → "أول كلمة إنجليزي! 🏆"
3. "اكتب: !تقدم" → shows their progress (0 points, day 1) → explains what it means
4. "روح قناة #bot-commands واكتب: !1" → waits for them to do it in the channel → confirms
5. "تمام! كده انت جاهز. كل يوم الساعة 6 الصبح هتلاقي مهام جديدة"

Awards `POINTS_PER_TASK` (15 points) on completion — immediate
gratification, student sees the number go up.

Implementation: state machine in `features.py` (same pattern as the
exam DM collection — `_pending_tutorials` dict tracking which step
each student is on).

## Component 7 — Day-0 Video (Layer 2)

**Design:** A 3-minute screen-recorded walkthrough hosted on YouTube
(free). Link sent in the welcome DM. Shows:
- What the server looks like on mobile
- Where to find #bot-commands
- How to type the first command
- What the daily tasks look like

This is a **content creation task**, not a code task. The bot just
needs to include the YouTube link in the welcome message.

## Component 8 — Gradual English Injection (Layer 5)

**Design:** A function `response_language(discord_id)` that returns
one of: `"arabic"`, `"bilingual_ar_first"`, `"bilingual"` (current).
Based on the member's `joined_at` week number:
- Week 1: `"arabic"`
- Week 2-3: `"bilingual_ar_first"`
- Week 4+: `"bilingual"`

Every bot response that currently uses bilingual text wraps it in a
helper that respects this setting. The `bl()` function (already exists
in `tasks.py`) gets an extended version that checks the member's
language phase.

## Component 9 — Buddy-Guided First Day (Layer 4)

**Design:** Extend `features.assign_buddy()` to also DM the buddy with:
- WHO just joined (name, not just "a new member")
- A specific action: "Send them a voice message in Arabic explaining
  their first task"
- WHAT their first task is today (pulled from the actual curriculum)

The buddy DM is in Arabic. The buddy is expected to reach out via
Discord voice message (press-and-hold to record) — natural for the
audience, requires zero English from either party.

## Component 10 — First-Day Channel (Layer 4)

**Design:** A channel `#يوم-واحد` (or `#start-here`) that:
- Is visible to `@everyone` (new members can see it)
- Contains a pinned Arabic-only explanation with the visual map
- Has a ✅ reaction message ("React when you're ready to see the full
  server")
- On reaction: the bot assigns the L0 role (which grants access to
  level channels) and optionally hides this channel from them

**Alternative (simpler):** Instead of hide/reveal mechanics (complex
Discord permission changes per-user), just make this channel the
FIRST thing mentioned in the welcome DM — "Go to #start-here first"
— and rely on the tutorial quest + buddy to guide them from there.
The simpler version achieves 90% of the cognitive-load-reduction
benefit with 10% of the implementation complexity.

---

## Open Design Questions (flag to user if needed during implementation)

1. **Kokoro Arabic voice quality:** Kokoro-82M's Arabic voice may not
   sound natural enough for a native speaker. Test it first before
   committing to voice-first onboarding — if it sounds robotic, a
   manually-recorded voice (from you) would be much better. The
   infrastructure (sending audio DMs) is the same either way.

2. **Video creation:** The Day-0 video requires a screen recording.
   This is best done by YOU on your phone (showing the real Discord
   mobile app) rather than fabricated by an agent. The code just needs
   to include the YouTube link once you've uploaded it.

3. **First-Day channel vs. simpler approach:** Full channel hide/reveal
   (Component 10) requires per-user permission overwrites, which are
   operationally complex and can drift. The simpler "just mention
   #start-here prominently" approach is recommended unless you feel
   strongly about the locked-until-ready mechanic.
