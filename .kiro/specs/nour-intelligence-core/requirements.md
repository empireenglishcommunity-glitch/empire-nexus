# Nour Intelligence Core — Requirements

> **Initiative #15 — Codename: Aql (meaning: "the intellect/mind")**
>
> العقل
>
> Complete architectural replacement of Nour's cognitive layer. Not an
> extension of Rawiya (Initiative #14) — a rebuild of the *thinking*
> underneath it. Rawiya's detection logic and content are preserved and
> absorbed (see design.md, Component 8); its rigid onboarding FSM and
> single-shot prompt pattern are replaced.

---

## 0. Why This Exists (Problem Statement)

The current Nour (`nour_concierge.py` + siblings) is a single-shot
prompt-stuffing pattern: one text blob (student stats + memories +
2 truncated KB files + last 5 messages) goes into one LLM call, which
must produce a correct, safe, role-appropriate, grammatically perfect
Arabic answer in one shot, with no verification step, no real data
access, and no structural permission boundary. Every reported failure
traces to this shape, not to model quality:

| Symptom reported | Root cause (verified in code) |
|---|---|
| Generic chatbot behavior | No reasoning step; no tool calls; can't distinguish "answer from knowledge" vs "look up real data" vs "take an action" |
| Random foreign-language / garbled output | `_load_kb_file()` truncates at a hard 2000-char boundary with no regard for word/sentence edges, feeding the model a context block that ends mid-word — a known LLM script-drift trigger. No output validation exists to catch it before sending. |
| Limited ecosystem understanding | Retrieval is keyword-substring matching against 11 static files (`_KB_CATEGORIES` dict) — not semantic search. Falls back to `faq.md + system_overview.md` for anything unrecognized. |
| No role awareness / leak risk | Exactly one Nour exists. `owner_ops.md` sits in the same keyword-matched pool a student's question can reach. No structural separation between student-safe and owner-only knowledge. |
| Inconsistent / hallucinated answers | Nour cannot call any real function. Every "fact" about the platform or the student's own data is the model's best guess from a stuffed text summary, not a verified read. |
| Broken/confusing onboarding (Rawiya R8 finding) | The onboarding "journey" is a rigid linear state machine that had to *hijack* the AI response path (`try_message_triggered_advance`) to function — a scripted wizard wearing a conversational costume, not real understanding of where a student actually is. |

This spec exists to replace the *shape* of the system, not to patch
individual symptoms.

---

## 1. Vision

Nour becomes the single intelligence layer that understands and can
act on the entire Empire English ecosystem — Discord, the practice
platform, curriculum, operations — while strictly respecting who is
asking. She is:

- **For students**: an expert mentor who actually knows the platform,
  answers correctly from real knowledge and real data, and guides
  learning without ever feeling like a scripted bot.
- **For the owner**: a technical teammate with full-system visibility —
  operations, architecture, code behavior, debugging support, business
  insight — reachable from Telegram or Discord.
- **Structurally incapable** of crossing that line in either direction,
  by design, not by prompt instruction.

## 2. Objectives

1. Eliminate script-drift/foreign-language output through a hard,
   automated output gate — not a prompting fix.
2. Replace keyword-matching retrieval with real semantic search over a
   chunked, embedded knowledge base.
3. Give Nour real tool-calling access to the platform's actual data and
   actions (progress, security stats, announcements, flags) instead of
   text-summary guessing.
4. Enforce role-based knowledge and tool access as a structural
   boundary (separate retrieval indexes / tool registries per role),
   never a soft prompt instruction alone.
5. Replace the rigid onboarding state machine with a coverage-aware
   guide that assesses a student's real signals and weaves guidance
   naturally, preserving Rawiya's detection logic and tutorial content.
6. Ship with zero new paid infrastructure and zero disruption to the
   live system (16 real students, existing Discord/Telegram/practice
   platform integrations).

## 3. Success Criteria

| # | Criterion | Measurement |
|---|---|---|
| SC1 | Zero non-Arabic-script output reaches a student when Arabic was intended | Automated script-conformance gate; 0 incidents in 30-day post-launch window |
| SC2 | Correct-answer rate on a 100-question golden set (student-role) | ≥ 90% correct, ≥ 98% "not a fabricated fact" (verified against real KB/DB) |
| SC3 | Zero owner-domain content reachable via student-role conversation, including adversarial prompts | 0/50 red-team attempts succeed (see design.md Testing Strategy) |
| SC4 | Owner can retrieve accurate operational/technical answers about the live system | ≥ 90% correct on a 30-question owner golden set covering architecture, data, and ops |
| SC5 | Response latency acceptable for a chat experience | P50 < 4s, P95 < 10s end-to-end (including any tool round-trip) |
| SC6 | $0 net new recurring cost | Verified against Groq/Gemini free-tier limits at current + 5x scale (see design.md Cost Analysis) |
| SC7 | Zero disruption to existing students during rollout | Shadow-mode + flag-gated cutover; old Nour remains a working fallback throughout migration |
| SC8 | Onboarding coverage reaches parity or better than Rawiya's scripted journey | ≥ same % of new students complete first 7/7 day within 7 days, measured pre/post cutover |

---

## 4. User Personas & Roles

Mechanism must support N roles; **fully populated today: Owner and
Student only.** Admin/Moderator/Coach are structurally supported
(same permission model, just an empty/future allowlist) but not
staffed with real people yet — do not build UI or content specifically
for them beyond the mechanism itself.

### 4.1 Owner (fully populated)
- Identity: a single configured Discord ID (`config.OWNER_DISCORD_ID`),
  not a role or keyword match.
- Access: unrestricted — every knowledge domain (student + owner-only),
  every tool (student tools + owner tools), full technical/architectural
  explanation capability, real debugging assistance, strategic analysis.
- Channel: Telegram (via Markaz/Empire Ops bot) primarily; Discord DM
  also supported (owner is also technically a "member").
- Never rate-limited or presence-graduated — the owner's access is
  always maximal.

### 4.2 Student (fully populated)
- Identity: any registered member (`database.get_member()` returns a
  row) who is NOT the configured owner ID.
- Access: student knowledge domain only (system usage, curriculum,
  troubleshooting, motivation) + student tool set only (own progress,
  own journey coverage, own history). Cannot retrieve owner-only
  knowledge or call owner-only tools under any phrasing, prompt
  injection attempt, or conversational framing.
- Channel: Discord DM, `#ask-nour` channel.
- Subject to graduated presence (inherited from Rawiya R6 — preserved).

### 4.3 Admin / Moderator / Coach (mechanism only, not populated)
- The permission architecture (Section 5) must accept additional roles
  defined by a discord_id → role mapping table with zero code changes
  beyond adding rows and a role-to-domain/tool mapping entry.
- Not implemented with real content, real people, or real tool grants
  in this initiative. Explicitly deferred.

---

## 5. Role-Based Permission Architecture (Functional Requirement)

**Given** any incoming message to Nour (Discord DM, `#ask-nour`, or
Telegram from the owner),
**When** the system resolves who is asking,
**Then** it must determine, before any knowledge retrieval or tool
consideration happens:
1. The resolved `Role` (owner | student | future-role).
2. The exact set of knowledge domains that role may retrieve from.
3. The exact set of tools that role may invoke.

**This resolution must be structural** (a lookup producing a fixed,
enumerable set), not something the LLM decides or that a prompt
instructs it to respect. A student conversation must have **no
retrieval index reference and no tool schema reference** to owner-only
resources in the context sent to the model at all — there is nothing
to leak because it was never fetched, not because the model was told
not to share it.

**Acceptance:** Feeding the exact owner-only knowledge index and owner
tool schemas into a student-role request must be *impossible* by
construction — i.e., the code path for building a student request
literally does not have a reference to owner resources available to
retrieve, verified by a unit test that asserts the student context
builder's output contains zero owner-domain chunk IDs even when asked
to explain owner-domain topics via every phrasing in the red-team set.

---

## 6. Functional Requirements

### FR1 — Grounded Knowledge Retrieval
Nour must answer platform/curriculum/system questions using semantic
retrieval over an embedded, chunked knowledge base scoped to the
asker's role — not keyword matching, not the full raw file.

### FR2 — Real Data via Tool Calls
For any question requiring the asker's actual current data (streak,
level, points, journey coverage, security stats, roster, system
health), Nour must call a real function against the live database —
never approximate from a stale text summary embedded in the prompt.

### FR3 — Owner Operational Capability
The owner must be able to ask Nour (via Telegram or DM) operational and
technical questions about the live system — student status, security
posture, flag states, architecture/code behavior explanations — and
receive answers grounded in real current data and real documentation,
not generic AI knowledge about Discord bots in general.

### FR4 — Owner Action Capability
The owner must be able to instruct Nour to take real actions —
send an announcement, nudge a specific student, flag a student, toggle
a feature flag — through natural language, executed via tool calls
against the existing, already-built command functions (`ops_commands.py`),
not reimplemented.

### FR5 — Coverage-Aware Onboarding (replaces Rawiya's FSM)
For a new student, Nour must be aware of which onboarding topics are
covered based on real signals (registered, completed ≥1 task, used
`!link`, visited key channels, days active) and weave uncovered topics
into natural conversation — not execute a fixed, linear script that
advances only on exact trigger matches.

### FR6 — Micro-Tutorial Content Preserved
The 8 existing pre-written MSA tutorials (`nour_tutorials.py`) must
remain available as grounded knowledge content the retrieval layer can
surface — not discarded, not regenerated per-call by the model (their
value is exact, pre-verified correctness).

### FR7 — Proactive Detection Preserved
The 9 proactive-outreach detection conditions (silence, score drop,
milestone, channel ignorance, streak-bonus proximity, exam readiness,
repeated failure, return-after-absence, new-and-inactive) must remain
as a scheduled detection engine. Message *generation* for these
outreach events should route through the new guarded generation path
(FR8) instead of an unguarded separate Groq call.

### FR8 — Output Guardrails (hard requirement, not best-effort)
Every response destined for a student, in any Arabic-required context,
must pass, before being sent:
1. **Script-conformance check** — response is dominantly Arabic script
   (plus digits/punctuation/emoji); a response that fails is retried
   once with a corrective instruction, then falls back to a
   pre-written template if the retry also fails. **A garbled or
   wrong-language response must never reach a student, under any
   circumstance.**
2. **Bidi structural check** — reuses the existing, already-correct
   `scripts/bidi_check.py` logic (`find_bidi_issues()`); a response
   with 2+ embedded LTR islands in one Arabic line is reformatted
   (retry with instruction) before sending.
3. **Role-leak check** (student-role only) — response is scanned
   against an owner-domain marker list; any match blocks the response
   and forces regeneration without owner-adjacent context, as
   defense-in-depth behind the structural retrieval boundary (FR/Section 5).

### FR9 — Never Silent
If every AI provider fails and every guardrail retry fails, Nour must
still respond with a pre-written, warm, MSA, bidi-safe template — the
existing "never silence" philosophy in this codebase is preserved and
strengthened, never weakened.

### FR10 — Conversation Memory, Structured
Nour must remember: (a) recent turn-by-turn conversation (working
memory), (b) durable facts about a student (semantic memory, extended
with categorization), and (c) a compact summary of older history
(episodic memory) so long-running conversations don't require
unbounded raw history in every prompt.

---

## 7. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Budget** | $0 net new recurring cost. Groq (primary LLM + function calling), Gemini (fallback LLM + embeddings), SQLite (all storage, including vectors as BLOBs). No hosted vector DB, no fine-tuning, no paid embedding API, no new third-party service. |
| **Latency** | P50 < 4s, P95 < 10s end-to-end, including any single tool round-trip. Existing human-touch typing-delay simulation preserved on top of this. |
| **Reliability** | Triple-fallback AI provider chain preserved (Groq → Gemini → template). Guardrails degrade to template, never to silence or to an unguarded raw response. |
| **Safety / Privacy** | Owner-only knowledge and tools structurally unreachable from student context (Section 5). No student's personal data included in another student's context. Escalation-worthy topics (payment/refund/cancel) still route to the owner via Telegram, unchanged from current behavior. |
| **Scalability** | Must remain correct and performant from 16 real students today to a realistic 100-200 student horizon without architecture changes (see design.md Scalability Strategy) — re-evaluate only if that ceiling is exceeded. |
| **Maintainability** | Adding a new knowledge fact = editing/adding a markdown file + re-running a chunk/embed step, not editing code. Adding a new tool = one Python function + one schema entry, following the existing `ops_commands.py` `@command()` registration pattern already proven in this codebase. |
| **Zero Breaking Changes** | Every existing command, table, channel, Telegram integration, and flag continues to function unchanged throughout migration. New behavior is additive and flag-gated; the old `nour_concierge.py` path remains a working, selectable fallback until the new path is validated and fully cut over. |
| **Arabic-First** | All student-facing content and generation defaults MSA (Modern Standard Arabic), bidi-safe, mobile-first phrasing. This requirement is inherited unchanged from Rawiya Initiative 14 R2/R9 and reinforced by FR8's hard gate rather than left to prompt instruction alone. |
| **Observability** | Every tool call, every guardrail trigger (script-drift catch, bidi reformat, role-leak block), and every retrieval miss must be logged for analysis and continuous improvement (see design.md Monitoring). |

---

## 8. Explicit Non-Goals (This Initiative)

- **No fine-tuning.** Rejected: solves a capability problem we don't
  have; the architecture, not model IQ, is the current bottleneck.
- **No hosted vector database.** Rejected: infrastructure and monthly
  cost disproportionate to a corpus of a few hundred–few thousand
  chunks; SQLite + in-process cosine similarity is sufficient at this
  scale (see design.md for the numeric justification and the revisit
  trigger).
- **No multi-agent system** (multiple autonomous LLM agents
  coordinating). Rejected for now: adds coordination overhead, cost
  multiplication, and new failure surfaces disproportionate to a
  16–200 student community with a small team. One bounded orchestrator
  with tool-calling covers the real requirement.
- **No MCP (Model Context Protocol) server.** Rejected for now: MCP's
  value is exposing tools across independent service/process
  boundaries; Nour today lives in one process that already owns the
  database, Discord client, and every internal function directly. The
  tool layer is designed so it *can* become an MCP server later with
  minimal rework (Section on Future Roadmap in design.md), but building
  it now is premature abstraction with no current consumer.
- **No full population of Admin/Moderator/Coach roles** with real
  content or real people in this initiative — mechanism only.
- **No rewrite of the practice platform (`empire-dojo`)** — untouched.
- **No changes to Discord server structure, role-gate, Hissar security,
  or Markaz's existing Telegram plumbing** — Nour Intelligence Core
  integrates with these, does not modify them.

---

## 9. Constraints (Inherited + New)

- $0 budget, hard constraint (unchanged from Rawiya).
- Zero tolerance for breaking existing work (unchanged).
- MSA/bidi-safe, checker-verified (unchanged, now hard-gated at
  runtime, not just at authoring time).
- Must work with current AI providers (Groq primary, Gemini fallback) —
  both must support OpenAI-compatible function/tool calling for the
  orchestrator design to work; verified feasible for both as of this
  writing (see design.md).
- Must integrate with existing Markaz (Telegram ops hub) without
  duplicating its plumbing (`ops_hub.py`, `ops_poller.py`,
  `ops_commands.py` are reused, not reimplemented).
- Spec lives at `empire-nexus/.kiro/specs/nour-intelligence-core/`.
- Supersedes `nour-overhaul` (Initiative #14 / Rawiya) as the
  *cognitive* layer; Rawiya's shipped detection logic, content, and
  Telegram command surface are absorbed per design.md Component 8, not
  deleted wholesale.
