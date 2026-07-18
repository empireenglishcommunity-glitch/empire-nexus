# Nour Intelligence Core — Implementation Tasks

> **Initiative #15 — Codename: Aql**
> Arabic: العقل
> Read `requirements.md` and `design.md` first. Phases are sequential;
> each is independently deployable and flag-gated. Old Nour
> (`nour_concierge.py` et al.) stays live and untouched through Phase
> A7 — this is a parallel-build-then-cutover migration, never a
> big-bang replacement.

---

## Phase A0: Foundation — Roles, Permissions, Schema ✅ COMPLETE

No user-visible change. Pure scaffolding, fully covered by unit tests
before any AI call is wired in.

- [x] A0.1: Add `OWNER_DISCORD_ID` to `config.py` (new env var)
- [x] A0.2: Create `src/nour/` package (`__init__.py`, `roles.py`, `permissions.py`)
- [x] A0.3: Implement `resolve_role()` per design.md Section 2
- [x] A0.4: Implement `KNOWLEDGE_DOMAINS` / `TOOL_REGISTRY` mappings per Section 3
- [x] A0.5: Add new DB tables: `knowledge_chunks`, `nour_episodic_summaries`,
      `journey_coverage`, `nour_tool_calls`, `nour_guardrail_events`,
      `nour_retrieval_log` (all additive, via `_SCHEMA` + `_migrate()`
      following this codebase's existing pattern)
- [x] A0.6: Add `category` column migration to existing `nour_memories` table
- [x] A0.7: Register `nour_aql_core` flag in `flag_registry.py`, default OFF
- [x] A0.8: Unit test: student-role permission mapping contains ZERO
      owner-only domain/tool names, under every red-team phrasing in a
      fixture list (this is the Requirements §5 acceptance test —
      write it now, before any retrieval/tool code exists, so it's
      testing the mapping itself, not yet the full pipeline)

**Deliverable:** Role/permission mechanism exists, tested, inert.

**Completion notes:**
- `src/nour/roles.py`: `Role` enum (OWNER, STUDENT populated;
  ADMIN/MODERATOR/COACH reserved), `resolve_role()`, `is_owner()`.
- `src/nour/permissions.py`: `KNOWLEDGE_DOMAINS`/`TOOL_REGISTRY` dicts
  plus `get_knowledge_domains()`/`get_tool_registry()`/
  `is_domain_allowed()`/`is_tool_allowed()` accessors that return an
  empty list (not a fallback) for unpopulated future roles.
- `tests/test_nour_permissions.py`: 42 tests — role resolution edge
  cases, owner-superset-of-student invariants, 6 owner-only domains +
  9 owner-only tools individually verified blocked for students,
  10 red-team phrasings (including Arabic and instruction-override
  framings) proving the mapping is blind to message content by
  construction, and explicit reserved-role-gets-zero-access checks.
- Full existing suite (441 tests) still passes — zero regressions.
- All new/modified files pass `scripts/bidi_check.py` and `py_compile`.
- `OWNER_DISCORD_ID` documented in `.env.example` (empty by default —
  safe, not fail-open).

---

## Phase A1: Knowledge Chunking + Embedding Pipeline ✅ COMPLETE

- [x] A1.1: Implement `chunk_markdown_file()` per design.md Section 4.1
      (split on `##` headers, cap ~500 tokens, split long chunks at
      paragraph breaks)
- [x] A1.2: Implement Gemini embedding client (`embed_text()`) reusing
      existing `GEMINI_API_KEY` config
- [x] A1.3: Build one-time embed script: chunk + embed all 11 existing
      `data/nour_knowledge/*.md` files into `knowledge_chunks` (domain =
      filename stem, matching existing `_KB_CATEGORIES` naming)
- [x] A1.4: Implement `database.get_chunks_by_domains(domains: list[str])`
- [x] A1.5: Implement in-process cosine similarity search (numpy) over
      packed BLOB vectors
- [x] A1.6: Implement `retrieve(query, role, top_k=4)` per Section 4.3,
      with fallback to the OLD `_KB_CATEGORIES` keyword function if the
      Gemini embedding call fails
- [x] A1.7: Unit test: retrieval for a student-role query never returns
      a chunk whose `domain` is not in `KNOWLEDGE_DOMAINS[Role.STUDENT]`
      — even when the SQL query is deliberately given an expanded
      domain list as a fault-injection test (defense-in-depth check on
      the data-layer boundary itself)
- [x] A1.8: Manual QA: run 20 real-style questions through retrieval,
      verify top-k chunks are actually relevant (informal spot-check
      before the formal golden-set test in A6)

**Deliverable:** Semantic retrieval works, correctly role-scoped,
tested against real content. Zero live traffic uses this yet.

**Completion notes:**
- `src/nour/knowledge/chunker.py`: `chunk_markdown_file()` splits on
  `##` headers, discards front-matter, splits oversized sections at
  paragraph breaks only (never mid-word/mid-sentence). 21 tests.
  Verified against all 11 real `data/nour_knowledge/*.md` files: 106
  chunks total, 0 frontmatter leaks.
- `src/nour/knowledge/embedder.py`: `embed_text()` (Gemini
  `gemini-embedding-001`, 768-dim, manual normalization, asymmetric
  RETRIEVAL_DOCUMENT/RETRIEVAL_QUERY task types), `pack_embedding()`/
  `unpack_embedding()` BLOB helpers, `cosine_similarity()`. 17 tests,
  all network calls mocked.
- `src/database.py`: `insert_knowledge_chunk()`,
  `clear_knowledge_chunks()`, `get_chunks_by_domains()`,
  `count_knowledge_chunks()`, `log_retrieval()`. 15 tests
  (`tests/test_nour_database_knowledge.py`).
- `src/nour/knowledge/retriever.py`: `retrieve(query, role, top_k=4,
  discord_id="")` — resolves allowed domains via
  `permissions.get_knowledge_domains(role)` (empty list short-circuits
  before any embedding call, e.g. for reserved roles), embeds the
  query, scores candidates by cosine similarity, falls back to the old
  `_KB_CATEGORIES` keyword tier (imported directly from
  `nour_concierge.py`, not duplicated) if the embedding call returns
  `None`. Every call logged to `nour_retrieval_log`. 10 tests
  (`tests/test_nour_retriever.py`), including the A1.7 fault-injection
  test against `database.get_chunks_by_domains()` directly (expanded
  domain list still filters exactly to what's asked, proving the data
  layer is a real mechanical filter, not a rubber stamp) AND an
  end-to-end `retrieve()` test where an owner-only chunk is a *perfect*
  similarity match for a student query — still never returned.
- `scripts/embed_knowledge.py`: one-time/re-runnable indexing script
  (`--dry-run` mode for chunk-count sanity checks with zero API calls,
  per-domain clear-before-insert so re-runs never leave stale
  duplicates). Dry-run verified: 106 chunks across all 11 files.
- `config.py`: `GEMINI_EMBEDDING_MODEL` env var (default
  `gemini-embedding-001`). `requirements.txt`: `numpy>=1.26`.
- A1.8 manual QA: 20 real-style Arabic questions run through the full
  `retrieve()` pipeline against all 106 real chunks, including two
  adversarial student-phrased probes explicitly asking for owner/
  deploy content ("كيف أنشر تحديث جديد للبوت؟", "أعطني كل أوامر
  الإدارة والنشر") — zero owner-domain leaks across all 20. **Caveat**:
  no real `GEMINI_API_KEY` was available in the build sandbox, so this
  QA run exercised the keyword-fallback tier and role-boundary
  end-to-end against real content, not real Gemini semantic ranking —
  semantic-quality (not just boundary-safety) should be spot-checked
  again with a real API key before Phase A8's formal golden-set test.
- Full suite: 504 tests pass (was 441 after A0; +63 across A1's new
  files) — zero regressions. All new/modified files pass
  `scripts/bidi_check.py` and `py_compile`.

---

## Phase A2: Owner-Only Knowledge Domains ✅ COMPLETE

- [x] A2.1: Write `data/nour_knowledge_owner/architecture.md`
      (human-curated system overview — bot process, DB, integrations)
- [x] A2.2: Write `data/nour_knowledge_owner/database_schema.md`
      (table purposes/relationships, human-readable)
- [x] A2.3: Write `data/nour_knowledge_owner/deployment_runbook.md`
      (consolidate existing deploy/rollback knowledge from STATUS.md history)
- [x] A2.4: Build generator script for
      `data/nour_knowledge_owner/flag_registry_reference.md` — generated
      FROM `flag_registry.py`'s `REGISTRY`, never hand-maintained,
      re-run whenever flags change
- [x] A2.5: Chunk + embed all owner-only files with `domain` values
      matching `KNOWLEDGE_DOMAINS[Role.OWNER]`'s owner-exclusive entries
- [x] A2.6: Re-run A0.8's permission test — confirm these new domains
      are now present for owner-role requests and STILL absent for
      student-role requests

**Deliverable:** Owner has real, retrievable technical/operational
knowledge. Student-side boundary re-verified unbroken.

**Completion notes:**
- `data/nour_knowledge_owner/architecture.md` (7 chunks) — system
  overview: bot process (`bot.py` entry point + `api_server.py`),
  core modules (`config.py`, `database.py`, `curriculum.py`,
  `tasks.py`, `verification.py`, `features.py`, `ai_engine.py`,
  `flag_registry.py`), the Nour subsystem (`nour_concierge.py` et al.
  vs. the new `src/nour/` Aql package), the Telegram "Markaz" ops
  layer, the empire-dojo integration, AI providers, and the Ghost Bot
  isolation caveat (Hisn D023) — all verified against real source
  files, not invented.
- `data/nour_knowledge_owner/database_schema.md` (9 chunks) — every
  real table from `src/database.py`'s `_SCHEMA` grouped by purpose
  (student/learning, operations/infra, notifications, Nour/memory,
  Aql's own 6 tables), explicitly flags the 2 superseded-but-inert
  tables (`nour_study_tips`, `student_journey`), and closes with a
  "code is the source of truth, this file follows" note matching the
  project's own migration discipline.
- `data/nour_knowledge_owner/deployment_runbook.md` (7 chunks) — real
  `scripts/deploy.py`/`rollback.py`/`backup.py` procedures (Hetzner
  VPS, git-SHA image tagging, health-check gate, manual DB-restore
  steps kept deliberately separate from code rollback), plus feature
  flags as the fastest true instant-revert mechanism (no redeploy),
  and an explicit "undocumented, ask the owner" section for secret
  rotation (no bot-specific rotation runbook exists in this repo/
  empire-chronicle today) rather than guessing at one.
- `data/nour_knowledge_owner/flag_registry_reference.md` (12 chunks)
  — GENERATED, not hand-written, by
  `scripts/generate_flag_reference.py` from `flag_registry.py`'s
  `REGISTRY` (51 flags, 10 initiatives at generation time). Script
  supports `--check` (CI-friendly staleness check, no writes) and is
  re-run any time a flag changes.
- `scripts/embed_knowledge.py` extended (not duplicated) to index
  BOTH `data/nour_knowledge/` and `data/nour_knowledge_owner/` — new
  `--owner-only`/`--student-only` flags, `--dry-run` verified: 141
  total chunks across all 15 files (106 student + 35 owner-only).
- `tests/test_nour_phase_a2.py` (8 tests): confirms all 4 real files
  exist and chunk to non-empty content, confirms their domain names
  (filename stems) are exactly the ones A0 pre-registered in
  `permissions.py`'s owner-only list and are absent from the student
  list, re-runs the A0.8-style boundary check against REAL indexed
  content from these 4 files (owner retrieval finds all 4 new
  domains; student retrieval finds none of them), confirms A1's
  pre-existing student domains are undisturbed after A2's additions,
  and confirms the committed `flag_registry_reference.md` is
  byte-identical to what the generator produces right now (catches
  drift if a flag changes without re-running the generator).
- Full suite: 512 tests pass (was 504 after A1; +8 for A2) — zero
  regressions. All new/modified files pass `scripts/bidi_check.py`
  and `py_compile`.
- Not built in A2 (deferred, no owner-only content/need yet): a
  `codebase_map` domain distinct from `architecture.md` — the
  `_OWNER_ONLY_DOMAINS` list in `permissions.py` reserves the name,
  but A2's 4 tasks didn't call for a separate file; `architecture.md`
  currently covers this ground. Revisit if `architecture.md` grows
  unwieldy enough to warrant a split.

---

## Phase A3: Tool Layer ✅ COMPLETE

- [x] A3.1: Implement student tool set (`get_my_progress`,
      `get_my_journey_coverage`, `get_my_recent_scores`,
      `get_leaderboard_position`) per Section 5.2 — `discord_id` bound
      server-side, never a model-supplied parameter
- [x] A3.2: Implement owner tool set as thin wrappers over EXISTING
      `ops_commands.py` functions per Section 5.3 — zero reimplementation
- [x] A3.3: Implement `execute_tool(name, discord_id, arguments)` dispatcher
      that validates `name` against the caller's `TOOL_REGISTRY[role]`
      before executing (defensive check — structurally redundant per
      Section 3, but present per this codebase's "double-check
      security-relevant logic" convention)
- [x] A3.4: Log every tool call to `nour_tool_calls` (name, args minus
      any sensitive values, latency, success/fail)
- [x] A3.5: Unit test: attempting to call an owner-only tool name
      through the student dispatcher path raises/returns an error, not
      a silent success — verifies A3.3's gate actually gates
- [x] A3.6: Unit test: every student tool's real function signature has
      NO parameter that could target a different student's data

**Deliverable:** Tool-calling works, correctly scoped, logged, tested.

**Completion notes:**
- `src/nour/tools/student_tools.py`: `get_my_progress`,
  `get_my_journey_coverage`, `get_my_recent_scores`,
  `get_leaderboard_position` — each takes exactly one parameter
  (`discord_id`, bound server-side by the dispatcher), matching a
  zero-parameter `TOOLS` schema offered to the model. Reuses existing
  `database.py` functions verbatim (`get_member`, `get_streak`,
  `member_week_number`, `tasks_completed_today`,
  `get_recent_scores`/`get_pronunciation_average`) — no new
  business logic, just tool-shaped reads.
- `src/nour/tools/owner_tools.py`: `get_student_status`,
  `get_roster_summary`, `get_system_health` delegate directly to
  `ops_commands.handle_check`/`handle_students`/`handle_status`
  (zero reimplementation, per design.md Section 5.3). `flag_student`
  delegates to `nour_ops_commands._cmd_flag`. `get_security_stats`
  reads `database.get_security_stats()` directly. `send_announcement`
  → `ops_commands.handle_announce`. `nudge_student` →
  `ops_commands.handle_nudge`. `toggle_feature_flag` →
  `database.set_feature_flag()` directly (tagged
  `updated_by="nour_owner_tool"` for audit-trail distinction from
  manual toggles). `explain_code_behavior` retrieves from a deliberate
  subset of owner domains (`architecture`/`codebase_map`/
  `database_schema` — NOT `deployment_runbook`/
  `flag_registry_reference`, which have their own dedicated tools)
  and returns raw grounding chunks, composition left to the future
  orchestrator (A5). A module-level `set_bot()`/`get_bot()`
  registration mechanism avoids a circular import with `bot.py`;
  calling a Discord-touching owner tool before a bot is registered
  raises `RuntimeError` with a clear message rather than a bare
  `AttributeError`.
- `src/nour/tools/dispatcher.py`: `execute_tool(name, role, discord_id,
  arguments)` — checks `permissions.is_tool_allowed(role, name)`
  first and raises `ToolError` (never a silent no-op, never a
  successful-looking empty result) if not permitted or if the name
  has no implementation; otherwise binds `discord_id` positionally
  for student-scoped tools or unpacks `arguments` as kwargs for owner
  tools, and logs every attempt (rejected, failed, or successful) to
  `nour_tool_calls` via the new `database.log_tool_call()`. A
  redaction extension point (`_REDACT_KEYS`) exists for any future
  tool with a genuinely sensitive parameter, currently empty since no
  A3 tool takes one. An import-time assertion guards against a tool
  name existing in both `student_tools.FUNCTIONS` and
  `owner_tools.FUNCTIONS`.
- `src/database.py`: `get_journey_coverage()` (read-only in this
  phase — returns real all-zero defaults for an unseen student;
  Phase A6.4 wires the write side to real signals),
  `get_member_rank()` (1-indexed rank by points, unlike
  `leaderboard()`'s top-N-only slice), `log_tool_call()`.
- `tests/test_nour_tools.py` (31 tests): A3.6 inspects every student
  tool's REAL function signature via `inspect.signature` (not just
  reading the code by eye) to confirm it's exactly `["discord_id"]`
  with no suspicious extra parameter, and confirms the model-facing
  schema declares empty `parameters: {}` for all four. A3.5 confirms
  `get_student_status` (owner-only) called through `Role.STUDENT`
  raises `ToolError` and is explicitly asserted to never return a
  value on the success path. Also covers: real student-tool data
  correctness, owner-tool delegation via a fake bot fixture,
  `RuntimeError` when no bot is registered, `explain_code_behavior`'s
  domain filtering, and A3.4's full logging matrix (successful,
  rejected, internally-failed, and unknown-tool-name attempts all
  produce exactly one `nour_tool_calls` row each with the correct
  `success` flag).
- `tests/test_nour_database_knowledge.py` extended (+8 tests) for the
  three new `database.py` functions.
- Full suite: 551 tests pass (was 512 after A2; +39 across A3's new
  files) — zero regressions. All new/modified files pass
  `scripts/bidi_check.py` and `py_compile`.
- Not built in A3 (deliberately deferred to later phases per
  tasks.md's own sequencing): wiring `owner_tools.set_bot()` into
  `bot.py`'s real startup (Phase A5, once an orchestrator actually
  exists to call these tools), and any Groq/Gemini function-calling
  schema translation (also Phase A5 — `TOOLS` lists here are
  provider-agnostic dicts, not yet formatted for either API).

---

## Phase A4: Output Guardrails ✅ COMPLETE

- [x] A4.1: Implement `check_script_conformance()` per Section 7,
      reusing the Arabic-range regex already proven in
      `scripts/bidi_check.py` / `features.py`
- [x] A4.2: Implement `check_bidi_structure()` as a direct import of
      `scripts.bidi_check.find_bidi_issues()` — not reimplemented
- [x] A4.3: Implement `check_role_leak()` with an initial
      `OWNER_LEAK_MARKERS` list (internal table names, deploy commands,
      flag internals) — start conservative, expand from real
      `nour_guardrail_events` log data post-launch
- [x] A4.4: Implement `guarded_generate()` wrapper: generate → check →
      retry-with-correction-hint once → template fallback
- [x] A4.5: Log every guardrail trigger to `nour_guardrail_events`
      (type: script/bidi/role-leak, original text hash, corrected
      or fell back to template)
- [x] A4.6: Stress test: reproduce the exact original bug conditions
      (long conversation, KB-heavy context, truncation-adjacent chunk
      sizes) 200 times against the new chunked-retrieval + guardrail
      pipeline — confirm 0 non-Arabic responses reach the "delivered"
      stage (SC1 acceptance test, run early and often, not just once
      at the end)

**Deliverable:** The original reported bug is mechanically
un-reproducible. This is the single most load-bearing phase relative
to the original complaint — do not skip or compress its testing.

**Completion notes:**
- `src/nour/guardrails.py`: `check_script_conformance()` (dominant-
  Arabic ratio >0.7 over actual letters only — digits/punctuation/
  emoji are script-neutral and never count against it, exactly
  matching design.md Section 7's formula; empty/emoji-only text
  correctly passes since there's no "wrong script" to detect absent
  any script at all), `check_bidi_structure()` (a genuine, verified
  passthrough to `scripts.bidi_check.find_bidi_issues()` — tested
  directly against that function's output for identical inputs, not
  just assumed to match), `check_role_leak()` (owner role always
  passes trivially; student role scanned against `OWNER_LEAK_MARKERS`
  — real internal table names, real deploy/rollback commands, real
  flag-internals terms, owner-identifying env var names — 18 entries
  at launch, every single one covered by its own parametrized test),
  `guarded_generate()` (generate → check all three → on any failure,
  retry once with a failure-type-specific Arabic-only correction hint
  → on second failure, fall back to `nour_concierge._TEMPLATE_RESPONSES`
  directly, not a duplicated list).
- `src/database.py`: `log_guardrail_event()` (hash only, never raw
  failing text — verified by a dedicated test that the original text
  literally does not appear anywhere in the logged row),
  `count_guardrail_events()`.
- **Real bug caught and fixed during this phase's own testing**: the
  first-written "bidi" correction hint text itself violated the bidi
  rule it was instructing the model to follow (two embedded LTR
  references, `#channel` and `!command`, joined by Arabic connector
  text on one line) — caught by running `bidi_check.py` against the
  new file as part of this phase's own verification step, not by a
  separate test written in advance. Fixed the hint's wording, then
  added a permanent regression test (`test_every_correction_hint_passes_
  bidi_structure_check` / `..._script_conformance_check`, parametrized
  over all three failure types) so a future edit to any hint's wording
  can never reintroduce this same category of self-defeating bug
  silently.
- `tests/test_nour_guardrails.py` (54 tests) — deliberately the most
  exhaustive test file in the Aql spec so far, per this phase's own
  "do not skip or compress its testing" instruction. Includes the
  **A4.6 stress test**: 200 deterministic (seeded) reproductions of
  the original bug conditions — a "flaky provider" that returns
  garbled/foreign-language/degenerate text (English, French, German,
  Japanese, Russian, bidi-broken Arabic, a real leak marker, empty
  string, whitespace-only, digits-only), with retries succeeding
  ~50% of the time and failing the other ~50% (forcing the template
  fallback path) — and asserts that **zero of the 200 delivered
  responses** fail any guardrail check. Also covers: the full
  `guarded_generate()` state machine (pass-first-try /
  retry-succeeds / retry-fails-falls-back), correct failure-type
  attribution when isolating each of the three checks independently,
  the owner role's exemption from `role_leak` specifically (not from
  script/bidi), and confirmation that a first-try pass is never
  logged at all (only actual triggers are).
- `tests/test_nour_database_knowledge.py` extended (+4 tests) for the
  2 new `database.py` functions.
- Full suite: 609 tests pass (was 551 after A3; +58 across A4's new
  files) — zero regressions. All new/modified files pass
  `scripts/bidi_check.py` and `py_compile`.
- Not built in A4 (deliberately deferred): wiring `guarded_generate()`
  into `nour_concierge.py`'s real `_generate_response()` call path —
  that is the actual cutover moment and belongs to a later phase
  (A9's phased migration), not this one. A4 built and exhaustively
  tested the mechanism in isolation; it has zero live effect until
  something calls it.

---

## Phase A5: Bounded Orchestrator + Intent Classification ✅ COMPLETE

- [x] A5.1: Implement `classify_intent()` — one cheap/fast LLM call,
      low max_tokens, categories per design.md Section 1
- [x] A5.2: Implement `handle_message()` orchestrator per Section 8 —
      role resolve → intent → memory assembly → bounded tool/retrieval
      loop (max 3 iterations) → guarded generation → memory write
- [x] A5.3: Wire Groq function-calling (`tools=` parameter) as primary
      LLM call path
- [x] A5.4: Wire Gemini function-calling as fallback path (verify
      current Gemini API function-calling support/format before
      implementing — API details can shift; confirm against live docs
      at implementation time rather than trusting this spec's
      point-in-time assumption)
- [x] A5.5: Preserve template-response last-resort tier (reuse existing
      `_TEMPLATE_RESPONSES` list)
- [x] A5.6: Escalation path check (payment/refund/cancel keywords) —
      route through EXISTING `nour_escalation.escalate_to_owner()`
      unchanged, before the orchestrator loop even starts (matching
      today's early-exit behavior in `handle_message()`)
- [x] A5.7: Unit test: a tool-calling loop that would exceed 3
      iterations is force-terminated into composition, never allowed
      to spiral (cost/latency safety valve, directly testing the
      "bounded" claim in the architecture)

**Deliverable:** Full orchestration pipeline functional end-to-end
against synthetic conversations. Still zero live traffic.

**Completion notes:**
- `src/nour/orchestrator.py`: `classify_intent()` (one low-max_tokens,
  temperature=0 Groq call, degrades to the safest default
  `"knowledge_question"` on any failure — missing key, network error,
  unparseable response). `handle_message(discord_id, text,
  channel_context="")` implements design.md Section 8's full pipeline:
  role resolve → fixed-keyword escalation check (unchanged
  `nour_concierge._should_escalate_immediately`) → intent
  classification (a SECOND, classifier-based escalation check, for
  defense in depth against phrasing the fixed list misses) → working
  memory (`database.get_recent_conversation`) + semantic memories
  (`nour_personality.get_memories`) + journey coverage
  (`database.get_journey_coverage`, student-only) → role-scoped
  retrieval (A1's `retrieve()`) → the bounded tool-calling loop → A4's
  `guarded_generate()` → conversation write (both turns, via the
  existing `nour_concierge._store_conversation`).
- **The bound is structural, not a suggestion**: `MAX_ITERATIONS = 3`,
  and the tool schema list passed to the LLM call is literally empty
  (`[]`) on the 3rd/final iteration — there is nothing for the model
  to request a tool call *with* at that point, not merely an
  instruction telling it not to. Verified by A5.7's test with a fake
  LLM that unconditionally requests a tool whenever any tool schema is
  present: it is still forced to produce real text on exactly the 3rd
  call, never a 4th.
- Provider abstraction: `_call_groq_with_tools()` /
  `_call_gemini_with_tools()`, both converting to/from ONE internal,
  provider-neutral message format (`_messages_to_openai_format()` /
  `_messages_to_gemini_contents()`), so a mid-loop provider switch
  (Groq fails on iteration 1 after succeeding on iteration 0) works
  correctly against the same accumulated message history.
  `_call_llm_with_tools()` is the Groq-primary/Gemini-fallback
  dispatcher, matching `nour_concierge._generate_response()`'s
  existing three-tier philosophy, now tool-aware at each tier.
- Gemini's function-calling format was verified against Google's live
  docs at implementation time (per A5.4's explicit instruction), not
  assumed from the spec's point-in-time text:
  https://ai.google.dev/gemini-api/docs/function-calling and
  https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/function-calling
  — `functionDeclarations` format, `type: "object"` schemas,
  zero-parameter tools correctly omit the `parameters` key entirely
  (documented as Optional) rather than sending an empty object.
- `src/nour/tools/dispatcher.py` extended with
  `get_tool_schemas_for_role(role)` — the orchestrator's actual
  enforcement point for design.md Section 3's "nothing to extract
  because it was never fetched" framing: a student-role request's
  tool schema list is constructed ONLY from
  `permissions.get_tool_registry(Role.STUDENT)`, so an owner-only
  tool's name/description/parameters never appear anywhere in a
  student request's payload to any LLM provider.
- Defense in depth preserved even though it should be structurally
  unreachable: if a tool_call name isn't in the schemas that were
  actually offered this iteration, the orchestrator silently discards
  it rather than executing it (tested explicitly in
  `test_a5_7_owner_only_tool_never_reaches_student_via_orchestrator`).
  A tool that raises internally is caught (`dispatcher.ToolError`) and
  fed back as an `{"error": ...}` tool-result message, not a crash.
- `tests/test_nour_orchestrator.py` (30 tests): intent classification
  (all 6 categories + 2 degradation paths), schema-conversion
  correctness for both providers, the full Groq→Gemini→template
  fallback chain, both escalation paths (fixed-keyword AND
  classifier-detected) confirmed to short-circuit BEFORE any LLM call
  via `assert_not_called()` (not just "the response looks right"),
  and the complete A5.7 bounded-loop suite: exact 3-call termination
  under an always-wants-a-tool model, early termination when a model
  answers directly on call 1, real tool-result data actually appearing
  in the 2nd call's message history (not just iteration counting), the
  owner-only-tool-leak defense, and internal tool-error handling.
- Full suite: 639 tests pass (was 609 after A4; +30 across A5's new
  file) — zero regressions. All new/modified files pass
  `scripts/bidi_check.py` and `py_compile`.
- Not built in A5 (deliberately deferred): wiring
  `orchestrator.handle_message()` into `bot.py`'s real message
  handler — that cutover belongs to Phase A9's phased migration.
  `nour_concierge.handle_message()` remains completely untouched and
  is still the only thing answering real messages today. Episodic
  summaries (design.md Section 6) are not yet part of context
  assembly — `_build_messages()` is structured so Phase A6 can add
  that section without changing the loop shape around it.

---

## Phase A6: Structured Memory ✅ COMPLETE

- [x] A6.1: Implement working-memory retrieval (last ~10 turns from
      existing `nour_conversations`, unchanged schema)
- [x] A6.2: Implement episodic summary generation — weekly per active
      student, reusing the Groq-summarization pattern from
      `nour_personality.run_weekly_review` redirected to per-student
      output into `nour_episodic_summaries`
- [x] A6.3: Extend semantic memory retrieval to filter by `category` +
      relevance to current topic (not all facts dumped regardless of
      relevance)
- [x] A6.4: Implement `journey_coverage` read/write functions —
      coverage flags flip on the SAME real signals Rawiya's triggers
      used (task completion, `!link` usage, channel visits), replacing
      the FSM's `_advance_step()` calls at those exact call sites in
      `bot.py` (`cmd_done`, `cmd_link`, daily check task)
- [x] A6.5: Wire journey-gap surfacing into context assembly (Section 6)
      — gaps become retrievable conversational material, not a
      scripted trigger
- [x] A6.6: Golden-set test: verify a multi-session conversation
      (simulate 3 separate days of chat) correctly references earlier
      context via episodic summary without needing full raw history
      re-sent every time

**Deliverable:** Memory is structured, bounded, and the onboarding
coverage model works without a rigid FSM.

**Completion notes:**
- `src/database.py`: `set_journey_coverage(discord_id, **flags)` —
  independent boolean flags (`knows_daily_tasks`, `knows_platform_link`,
  `knows_streaks`, `knows_channels`, `first_task_done`), upserting so
  the FIRST real signal for a student creates the row and every
  subsequent call only touches the flags it's actually given (a
  `!streak` view never accidentally resets `knows_channels` back to
  0). Degrades to a silent no-op (not a crash) for a `discord_id` with
  no `members` row yet, since `on_message`'s channel-visit signal can
  legitimately fire for a Discord user who has never run `!join`.
  `store_episodic_summary()`, `get_latest_episodic_summary()` (tie-broken
  by `id DESC`, same known-limitation workaround as
  `last_advancement_attempt()`'s existing precedent for
  second-resolution `datetime('now')` timestamps).
- `src/nour_personality.py`: `store_memory()`/`get_memories()` extended
  with a `category` parameter (defaults to `'general'`, so every
  existing call site's behavior is byte-for-byte unchanged).
  `get_memories_by_topic(discord_id, current_topic)` — a cheap keyword-hint
  match (same convention as `nour_concierge._KB_CATEGORIES`) against
  the current request's text, returning only memories in matched
  categories; degrades to full unfiltered recency if no category
  matches OR if a matched category has zero stored memories for this
  student (never silently returns nothing when real memories exist).
  `generate_episodic_summary()` (reuses `run_weekly_review()`'s exact
  Groq-call PATTERN, redirected to one student's own conversation
  history; returns `None` on missing key/no conversations/API
  failure, never raises) and `run_weekly_episodic_summaries()` (loops
  every active member, only stores a summary for students who
  actually had conversation activity in the window).
- `src/bot.py`: `journey_coverage` real-signal wiring at the exact
  call sites design.md's own framing calls for — `cmd_done` (fires
  `knows_daily_tasks`+`first_task_done` on the SAME real event
  `nour_journey.check_advancement("task_completed", ...)` already
  used), `cmd_link` (`knows_platform_link`, same signal as
  `"link_used"`), `cmd_streak` (`knows_streaks` — viewing the command
  IS the real signal that the student now knows it exists), and
  `on_message` (`knows_channels`, fired by posting in any of the 4
  "tour" channels `nour_journey.py`'s own `channels_tour` step
  introduces: daily-word, cheat-sheets, general-chat, ask-nour). The
  OLD FSM (`nour_journey.py`) is completely untouched and remains the
  only thing actually sending onboarding DMs today — both mechanisms
  coexist with zero user-visible effect until Phase A9's cutover
  reads `journey_coverage` instead of `student_journey`.
- New `aql_episodic_summary_task` (Sunday 10:30 AM, 30 min after the
  existing `nour_weekly_review`) calls
  `run_weekly_episodic_summaries()` — **explicitly gated behind a new
  `aql_episodic_summaries` flag, default OFF**. Unlike every other
  piece of Phase A1-A6 (which are dormant purely because nothing
  live calls them yet), this task loop WOULD start consuming real
  Groq API quota against every real student's real conversation
  history on a weekly schedule the moment this PR merges, even though
  writing new `nour_episodic_summaries` rows has zero effect on
  anything Nour's current live response path reads. The flag makes
  this phase's actual first live side effect a deliberate, separate
  decision, not an accidental one baked into "just building the
  mechanism" — matches this codebase's established deploy-dormant/
  release-separately discipline (Aegis Phase 1).
- `src/nour/orchestrator.py`: `_build_messages()` extended with an
  `episodic_summary` parameter (a `PAST CONTEXT` system-prompt
  section, omitted entirely when `None`) and now receives
  `get_memories_by_topic()`'s topic-filtered output instead of
  `get_memories()`'s unfiltered one. `handle_message()` fetches the
  latest episodic summary and topic-filtered facts as part of its
  existing context-assembly step — no change to the loop shape
  around it, exactly as A5's own completion notes anticipated.
- `tests/test_nour_memory.py` (29 tests): journey_coverage's
  independence-not-sequence property (flags settable in any order,
  partial updates never clobber untouched flags, invalid flag names
  silently ignored, FK-violation degrades to no-op), the real
  `cmd_done`/`cmd_link` call-site flag choices, topic-filtered memory
  retrieval (including both graceful-degradation paths), episodic
  summary generation (real Groq payload inspection, not just
  mocked-return-value checking, plus the missing-key/no-conversation/
  API-failure degradation paths), `_build_messages()`'s journey-gap
  and episodic-summary sections in isolation, an end-to-end
  `handle_message()` check that real gaps reach the real LLM payload,
  and the **A6.6 golden-set test**: a synthetic 3-session conversation
  (day 1's exam-anxiety disclosure, 12 unrelated turns across day 2-3
  pushing day 1 out of the ~10-turn working-memory window, then a
  day-3 follow-up) confirms the episodic summary's exam reference
  reaches the system prompt while day 1's raw message text is
  confirmed ABSENT from the working-memory turns actually sent.
- Full suite: 668 tests pass (was 639 after A5; +29 across A6's new
  file) — zero regressions. All new/modified files pass
  `scripts/bidi_check.py` and `py_compile`.
- Not built in A6 (deliberately deferred): actually reading
  `journey_coverage` (instead of `student_journey`) anywhere in a live
  code path, and enabling `aql_episodic_summaries` for real — both
  belong to Phase A9's phased cutover, not this phase.

---

## Phase A7: Rawiya Absorption — Proactive + Tutorials Integration ✅ COMPLETE

- [x] A7.1: Redirect `nour_proactive.py`'s message *generation* calls
      through `guarded_generate()` instead of their own separate,
      unguarded Groq call — detection logic itself UNCHANGED
- [x] A7.2: Confirm `nour_proactive.get_presence_level()` /
      `should_send_proactive()` graduated-presence logic requires zero
      changes (verify, don't assume, against the new orchestrator's
      call sites)
- [x] A7.3: Chunk + embed the 8 existing tutorial texts
      (`nour_tutorials.TUTORIALS`) into the retrievable knowledge base
      under a `tutorials` domain — confirm retrieval surfaces the exact
      pre-written text verbatim (these must NEVER be paraphrased by the
      model; they are pre-verified-correct content, retrieved and
      quoted, not regenerated)
- [x] A7.4: Decide + document: keep `nour_tutorials.check_and_send_tutorial()`'s
      trigger-based proactive dispatch (e.g. "3 wrong quiz answers in a
      row") as a SEPARATE proactive-push mechanism (student didn't ask,
      Nour proactively sends), distinct from retrieval (student DID ask,
      Nour retrieves) — these are different use cases, both valid, not
      one replacing the other
- [x] A7.5: Regression test: every one of Rawiya's proactive triggers
      still fires correctly and produces a guardrail-passing message

**Deliverable:** Rawiya's real value (detection + content) is fully
integrated into the new architecture; its rigid mechanism is gone.

**Completion notes:**
- `src/nour_proactive.py`: message generation split into
  `_generate_proactive_message()` (now calls `guarded_generate()`,
  Role.STUDENT, per design.md Section 8.2) wrapping the unchanged
  `_call_groq_for_proactive_message()` (the original prompt
  construction + per-type template-fallback-on-API-failure logic,
  untouched, now accepting an optional `correction_hint` threaded
  into the prompt for `guarded_generate()`'s retry tier). Every
  detection branch in `run_proactive_checks()` — the actual business
  logic this phase's own instruction says to leave UNCHANGED — is
  byte-for-byte identical to before this phase; only the call to
  generate the message text changed.
- **A7.2 finding**: the orchestrator (Phase A5) never calls into
  `nour_proactive.py` at all — proactive outreach is a separate,
  scheduled OUTBOUND push (a `@tasks.loop` in `bot.py`), not something
  invoked per incoming request. There is therefore zero coupling to
  verify; `get_presence_level()`/`should_send_proactive()` require no
  changes because nothing in the new architecture calls them, positively
  confirmed by a targeted search rather than assumed. Separately
  noted (pre-existing, unrelated to Aql, NOT fixed in this phase since
  A7 is absorption, not bug-fixing): these two functions are never
  actually called from `run_proactive_checks()` or anywhere else
  either — the graduated-presence logic exists but was never wired
  into a real send-decision call site, even before Aql.
- **A7.3**: `scripts/generate_tutorials_kb.py` generates
  `data/nour_knowledge/tutorials.md` DIRECTLY from
  `nour_tutorials.TUTORIALS` (same "generated, never hand-maintained"
  discipline as A2.4's `flag_registry_reference.md`) — this is what
  GUARANTEES the verbatim-retrieval guarantee mechanically rather than
  by convention: there is no second hand-copied version of this text
  that could ever drift from the original. Verified: chunking the
  generated file produces exactly 8 chunks, each one a byte-for-byte
  exact match to the corresponding `TUTORIALS` dict value (tested
  directly, not just chunk-count-checked). `tutorials` domain
  confirmed already present in both `Role.STUDENT` and `Role.OWNER`'s
  `KNOWLEDGE_DOMAINS` (pre-registered in Phase A0 per its own stated
  "ahead of the content existing" convention). End-to-end retrieval
  test confirms a real `retrieve()` call surfaces the tutorial's exact
  unmodified text.
- **A7.4 decision, documented directly in `nour_tutorials.py`'s module
  docstring**: `check_and_send_tutorial()`'s trigger-based proactive
  push is KEPT, not replaced by retrieval — retrieval serves "student
  asked a question" (now reachable via paraphrase-tolerant semantic
  search instead of exact keyword-trigger matching), the push
  mechanism serves "student didn't ask, but a real detected trigger
  means they need help now" (e.g. 3 wrong quiz answers in a row).
  Neither replaces the other. **Honest finding, documented rather
  than silently fixed** (out of scope for absorption): the real
  `bot.py` call sites that would need to detect
  `_get_tutorial_for_trigger()`'s trigger_type strings
  (`"recording_failed"`, `"wrong_channel_command"`, etc.) and invoke
  `check_and_send_tutorial()` don't actually exist yet — this predates
  Aql and is unrelated to the retrieval integration this phase adds.
- **A7.5 regression test + a real documentation bug found and fixed**:
  `nour_proactive.py`'s own module docstring claimed 5 checks (listing
  a "return after absence" condition with zero corresponding
  detection code) and `flag_registry.py`'s `nour_enhanced_proactive`
  description claimed "9 conditions" — neither number matched the 4
  real detection branches (`new_student`, `quiet_student`,
  `score_drop`, `first_milestone`) that actually exist in
  `run_proactive_checks()`. Both corrected in this phase (with an
  explanatory note in `nour_proactive.py`'s docstring, not a silent
  fix) rather than inventing a 5th/9th detection condition with no
  real signal behind it just to match the stale number. All 4 REAL
  triggers verified firing correctly via a full `run_proactive_checks()`
  integration test per trigger (fake guild/member/bot, real database
  rows, message generation mocked since A7.1's tests already cover
  it), plus a negative case confirming a healthy student matching none
  of the 4 conditions receives nothing.
- `tests/test_nour_phase_a7.py` (17 tests). Full suite: 686 tests pass
  (was 668 after A6; +18 across A7's new/modified files) — zero
  regressions. All new/modified files pass `scripts/bidi_check.py`
  and `py_compile`.
- Not built in A7 (out of scope, pre-existing gaps unrelated to Aql,
  documented not fixed): wiring real trigger detection call sites for
  `check_and_send_tutorial()`, and wiring `get_presence_level()`/
  `should_send_proactive()` into an actual send-decision call site.

---

## Phase A8: Shadow Mode + Golden-Set Validation

- [ ] A8.1: Build the 100-question student golden set (real-style
      questions across all knowledge domains) with human-verified
      correct answers
- [ ] A8.2: Build the 30-question owner golden set (operational +
      architectural questions)
- [ ] A8.3: Build the 50-prompt red-team set (role-leak attempts —
      direct requests, role-play framing, instruction-override attempts,
      obfuscated/translated phrasing)
- [ ] A8.4: Enable `nour_aql_core` flag for the owner's own Discord ID
      only (self-testing tier, matching this project's established
      pattern)
- [ ] A8.5: Run shadow mode: BOTH pipelines execute on every owner
      message; only OLD response is sent; NEW response logged
      side-by-side for manual comparison
- [ ] A8.6: Run all 3 golden/red-team sets against the NEW pipeline in
      isolation (not shadow mode — direct evaluation), record pass rates
- [ ] A8.7: Owner review + sign-off gate: SC1-SC4 pass bars met before
      proceeding to A9. If not met, return to the relevant earlier
      phase (do not patch symptoms at this stage — diagnose which
      component is under-performing and fix there)

**Deliverable:** Quantified evidence the new pipeline meets every
Requirements success criterion, reviewed by the owner, before any real
student sees it.

---

## Phase A9: Phased Live Cutover

- [ ] A9.1: Expand `nour_aql_core` allowlist to a small subset of real
      students (owner's choice — could be all 16, following the same
      "owner decides beta squad size" pattern used in prior initiatives)
- [ ] A9.2: New pipeline now sends its OWN response live for allowlisted
      users; monitor `nour_guardrail_events` and `nour_tool_calls` logs
      daily for the first week
- [ ] A9.3: Owner spot-checks real conversations for tone/correctness
      (not just automated pass rates — human judgment on real usage)
- [ ] A9.4: Expand allowlist to 100% (empty allowlist = on for everyone,
      matching existing flag semantics)
- [ ] A9.5: Full regression pass: every existing command, flag, and
      Telegram command still works unchanged post-cutover
- [ ] A9.6: Update `STATUS.md` / session continuity docs — mark
      Initiative #15 (Aql) as the live cognitive layer, Initiative #14
      (Rawiya)'s onboarding-FSM/single-shot-prompt components as
      superseded (not deleted yet — see A9.7)
- [ ] A9.7: Leave old `nour_concierge.py` et al. in the codebase,
      dormant, for one full release cycle as an instant-revert path
      (flip `nour_aql_core` OFF = zero-redeploy rollback) — schedule,
      don't yet execute, a future dedicated cleanup PR to remove it

**Deliverable:** Aql is the live Nour for 100% of students and the
owner. Old architecture is a documented, flag-gated fallback, not yet
deleted. Zero disruption confirmed via full regression.

---

## Explicit Non-Tasks (do not build in this initiative)

- No MCP server implementation (design.md Section 16 / roadmap item 2)
- No fine-tuning pipeline (design.md Section 16 / roadmap item 3)
- No hosted vector database migration (design.md Section 16 / roadmap item 4)
- No Admin/Moderator/Coach real content or tooling (mechanism only, A0.4)
- No changes to `empire-dojo` (practice platform), Discord server
  structure, Hissar security mechanisms, or Markaz's Telegram plumbing
  beyond calling its existing functions as tools (A3.2)

---

## Phase Execution Notes

- **A0-A4 can be built and fully tested with zero AI-provider live
  traffic** — they are pure infrastructure/logic. Do not rush to "see
  it talk" before this foundation is solid; the entire point of this
  rebuild is that the foundation was the problem last time.
- **A4 (guardrails) is the single highest-priority phase relative to
  the original complaint.** If time/effort must be triaged, this phase
  gets it first and gets the most repeated stress-testing.
- **A8 is a hard gate, not a formality.** Do not proceed to A9 without
  real pass-rate numbers against the golden/red-team sets, reviewed by
  the owner. This mirrors the "test everything together at the end"
  instruction already agreed for this initiative's predecessor.
- Suggested grouping for a single extended work session, if desired:
  **Session 1**: A0-A2 (foundation + knowledge, no AI calls yet).
  **Session 2**: A3-A5 (tools + guardrails + orchestrator).
  **Session 3**: A6-A7 (memory + Rawiya absorption).
  **Session 4**: A8-A9 (validation + cutover) — this session should
  never be rushed to fit a time constraint; SC1-SC4 must actually pass.
