# Tasks — Nour (نور): Autonomous Student Concierge

> **How to use this file:** same discipline as all other specs — work
> top to bottom, check off tasks. Each phase builds on the previous.

---

## Phase N0 — Foundation (Nour's Brain)

- [x] **N0.1** Create `data/nour_knowledge.md` — comprehensive knowledge
  base covering: all bot commands, daily task system, channels, practice
  platform, common problems, level advancement, FAQ. Written in a format
  Gemini can reference.
- [x] **N0.2** Add `nour_conversations` table to `database.py` schema
  (discord_id, role, message, intent, confidence, created_at).
- [x] **N0.3** Create `src/nour_concierge.py` with:
  - `handle_message(message)` — main entry point
  - `_build_context(discord_id, text)` — gather student data + history
  - `_classify_intent(text)` — question/technical/emotional/escalation
  - `_generate_response(context, message)` — call Gemini with system prompt
  - `_should_escalate(response, intent, message)` — confidence check
- [x] **N0.4** Add `_store_conversation()` and `_get_recent_conversation()`
  to database.py.
- [x] **N0.5** Wire into bot.py `on_message`: if DM and not a command,
  route to `nour_concierge.handle_message()`.
- [x] **N0.6** Create `#ask-nour` channel detection: if message in
  #ask-nour, route to Nour.

## Phase N1 — Human Touch + Channel Setup

- [x] **N1.1** Implement `_apply_human_touches()`: typing indicator,
  proportional delay (3-12s), occasional two-message split.
- [x] **N1.2** Add Nour's system prompt as a configurable constant in
  `config.py` (NOUR_SYSTEM_PROMPT) so it can be tuned without code changes.
- [x] **N1.3** Wire #ask-nour channel: bot responds to non-command
  messages there. Other channels are ignored (Nour only speaks when
  spoken to, except proactive outreach).
- [x] **N1.4** Test with 5+ real conversation scenarios (verify Nour
  responds contextually in Egyptian Arabic, uses student's name,
  references their data).

## Phase N2 — Proactive Outreach (Anti-Churn)

- [x] **N2.1** Create `src/nour_proactive.py` with scheduled check
  (runs every 2 hours via discord.ext.tasks loop).
- [x] **N2.2** Implement new-student check: joined 24h ago + 0 tasks →
  personal welcome DM from Nour (not system — personal).
- [x] **N2.3** Implement quiet-student check: 2 days no activity →
  warm check-in DM (uses their last activity as context).
- [x] **N2.4** Implement score-drop check: >20% decline over 3 days →
  encouraging DM with specific tip.
- [x] **N2.5** Implement first-milestone celebration: first 7/7 day →
  personal congratulations from Nour (separate from system celebration).
- [x] **N2.6** Add `nour_outreach_log` table to prevent double-sending
  (discord_id, outreach_type, date).
- [x] **N2.7** Gate behind feature flag: `nour_proactive`.

## Phase N3 — Escalation Pipeline

- [x] **N3.1** Implement `_escalate_to_owner()` in nour_concierge.py:
  sends Telegram message with student context + suggested response.
- [x] **N3.2** Implement owner reply handler: when owner replies to a
  Telegram escalation, forward the response to the student as Nour.
- [x] **N3.3** Add timeout check: if escalated issue has no owner
  response after 2 hours, Nour follows up with student ("Still
  checking, thanks for your patience").
- [x] **N3.4** Add escalation triggers: payment keywords, explicit
  owner request, real bugs (after Nour diagnosis fails), low confidence.
- [x] **N3.5** Gate behind feature flag: `nour_escalation`.

## Phase N4 — Onboarding Intelligence

- [x] **N4.1** Detect "first 48 hours" students and increase Nour's
  proactive engagement (check every 6h instead of every 2h for new joiners).
- [x] **N4.2** If student sends confused message in wrong channel →
  Nour gently redirects via DM (not public, to avoid embarrassment).
- [x] **N4.3** If student tries a command wrong (e.g. "done" without !)
  → Nour catches it and helps via DM.
- [x] **N4.4** Track "onboarding completion" metric: student used at
  least 3 commands successfully in first 3 days = onboarded.
- [x] **N4.5** If not onboarded by day 3 → Nour sends step-by-step
  walkthrough DM tailored to what they're missing.

## Phase N5 — Personality Refinement (after 1 week of real use) ✅ COMPLETE

- [x] **N5.1** Review real conversations: tune system prompt based on
  what worked and what felt robotic.
  → Implemented as an automated weekly self-review (`nour_personality.py`)
  that uses Groq to analyze Nour's own conversation patterns and sends
  improvement suggestions to the owner via Telegram. Shipped in PR #102.
- [x] **N5.2** Add "memory" persistence: Nour remembers key facts about
  a student across conversations (e.g. "they have a job that makes them
  busy on Tuesdays" → reference it later).
  → `store_memory()` / `get_memories()` in `nour_personality.py`. After
  each conversation, Groq extracts key facts and stores them per-student.
  Retrieved and injected into the system prompt on future conversations.
- [x] **N5.3** Add personality variations by time of day (morning: more
  energetic; evening: calmer, "rest well").
  → Time-of-day personality adaptation in `nour_personality.py`, modifies
  the system prompt based on Dubai timezone hour.
- [x] **N5.4** Add cultural awareness: Ramadan, Eid, Egyptian holidays →
  Nour acknowledges and adjusts expectations.
  → Cultural awareness module in `nour_personality.py` with Ramadan,
  Eid al-Fitr, Eid al-Adha, and Egyptian national holidays.

---

## Cross-phase notes

- **Nour uses the existing Gemini API** — no new AI provider needed.
- **Nour shares the bot process** — not a separate service. Just new
  handlers in on_message.
- **Feature flags:** `nour_concierge` (main), `nour_proactive` (outreach),
  `nour_escalation` (Telegram alerts). Each can be disabled independently.
- **Knowledge base** (`data/nour_knowledge.md`) must be updated whenever
  a new feature or command is added to the system.
- **Rate limiting:** Max 1 proactive DM per student per 6 hours (never spam).
- **Privacy:** Nour conversations stored for context but purged after 30 days.
- **Testing:** Use the Ghost bot (Empire Ghost#3420) for all testing before
  enabling on the production bot.
- **The golden rule:** If a student ever asks "are you a bot?" → Nour says
  "أنا نور من فريق Empire English 😊 في حاجة أقدر أساعدك فيها؟" (never
  confirm, never deny explicitly, redirect to helping them).
