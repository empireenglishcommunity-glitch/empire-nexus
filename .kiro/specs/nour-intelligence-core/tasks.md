# Nour Intelligence Core — Implementation Tasks

> **Initiative #15 — Codename: Aql**
> Arabic: العقل
> Read `requirements.md` and `design.md` first. Phases are sequential;
> each is independently deployable and flag-gated. Old Nour
> (`nour_concierge.py` et al.) stays live and untouched through Phase
> A7 — this is a parallel-build-then-cutover migration, never a
> big-bang replacement.

---

## Phase A0: Foundation — Roles, Permissions, Schema

No user-visible change. Pure scaffolding, fully covered by unit tests
before any AI call is wired in.

- [ ] A0.1: Add `OWNER_DISCORD_ID` to `config.py` (new env var)
- [ ] A0.2: Create `src/nour/` package (`__init__.py`, `roles.py`, `permissions.py`)
- [ ] A0.3: Implement `resolve_role()` per design.md Section 2
- [ ] A0.4: Implement `KNOWLEDGE_DOMAINS` / `TOOL_REGISTRY` mappings per Section 3
- [ ] A0.5: Add new DB tables: `knowledge_chunks`, `nour_episodic_summaries`,
      `journey_coverage`, `nour_tool_calls`, `nour_guardrail_events`,
      `nour_retrieval_log` (all additive, via `_SCHEMA` + `_migrate()`
      following this codebase's existing pattern)
- [ ] A0.6: Add `category` column migration to existing `nour_memories` table
- [ ] A0.7: Register `nour_aql_core` flag in `flag_registry.py`, default OFF
- [ ] A0.8: Unit test: student-role permission mapping contains ZERO
      owner-only domain/tool names, under every red-team phrasing in a
      fixture list (this is the Requirements §5 acceptance test —
      write it now, before any retrieval/tool code exists, so it's
      testing the mapping itself, not yet the full pipeline)

**Deliverable:** Role/permission mechanism exists, tested, inert.

---

## Phase A1: Knowledge Chunking + Embedding Pipeline

- [ ] A1.1: Implement `chunk_markdown_file()` per design.md Section 4.1
      (split on `##` headers, cap ~500 tokens, split long chunks at
      paragraph breaks)
- [ ] A1.2: Implement Gemini embedding client (`embed_text()`) reusing
      existing `GEMINI_API_KEY` config
- [ ] A1.3: Build one-time embed script: chunk + embed all 11 existing
      `data/nour_knowledge/*.md` files into `knowledge_chunks` (domain =
      filename stem, matching existing `_KB_CATEGORIES` naming)
- [ ] A1.4: Implement `database.get_chunks_by_domains(domains: list[str])`
- [ ] A1.5: Implement in-process cosine similarity search (numpy) over
      packed BLOB vectors
- [ ] A1.6: Implement `retrieve(query, role, top_k=4)` per Section 4.3,
      with fallback to the OLD `_KB_CATEGORIES` keyword function if the
      Gemini embedding call fails
- [ ] A1.7: Unit test: retrieval for a student-role query never returns
      a chunk whose `domain` is not in `KNOWLEDGE_DOMAINS[Role.STUDENT]`
      — even when the SQL query is deliberately given an expanded
      domain list as a fault-injection test (defense-in-depth check on
      the data-layer boundary itself)
- [ ] A1.8: Manual QA: run 20 real-style questions through retrieval,
      verify top-k chunks are actually relevant (informal spot-check
      before the formal golden-set test in A6)

**Deliverable:** Semantic retrieval works, correctly role-scoped,
tested against real content. Zero live traffic uses this yet.

---

## Phase A2: Owner-Only Knowledge Domains

- [ ] A2.1: Write `data/nour_knowledge_owner/architecture.md`
      (human-curated system overview — bot process, DB, integrations)
- [ ] A2.2: Write `data/nour_knowledge_owner/database_schema.md`
      (table purposes/relationships, human-readable)
- [ ] A2.3: Write `data/nour_knowledge_owner/deployment_runbook.md`
      (consolidate existing deploy/rollback knowledge from STATUS.md history)
- [ ] A2.4: Build generator script for
      `data/nour_knowledge_owner/flag_registry_reference.md` — generated
      FROM `flag_registry.py`'s `REGISTRY`, never hand-maintained,
      re-run whenever flags change
- [ ] A2.5: Chunk + embed all owner-only files with `domain` values
      matching `KNOWLEDGE_DOMAINS[Role.OWNER]`'s owner-exclusive entries
- [ ] A2.6: Re-run A0.8's permission test — confirm these new domains
      are now present for owner-role requests and STILL absent for
      student-role requests

**Deliverable:** Owner has real, retrievable technical/operational
knowledge. Student-side boundary re-verified unbroken.

---

## Phase A3: Tool Layer

- [ ] A3.1: Implement student tool set (`get_my_progress`,
      `get_my_journey_coverage`, `get_my_recent_scores`,
      `get_leaderboard_position`) per Section 5.2 — `discord_id` bound
      server-side, never a model-supplied parameter
- [ ] A3.2: Implement owner tool set as thin wrappers over EXISTING
      `ops_commands.py` functions per Section 5.3 — zero reimplementation
- [ ] A3.3: Implement `execute_tool(name, discord_id, arguments)` dispatcher
      that validates `name` against the caller's `TOOL_REGISTRY[role]`
      before executing (defensive check — structurally redundant per
      Section 3, but present per this codebase's "double-check
      security-relevant logic" convention)
- [ ] A3.4: Log every tool call to `nour_tool_calls` (name, args minus
      any sensitive values, latency, success/fail)
- [ ] A3.5: Unit test: attempting to call an owner-only tool name
      through the student dispatcher path raises/returns an error, not
      a silent success — verifies A3.3's gate actually gates
- [ ] A3.6: Unit test: every student tool's real function signature has
      NO parameter that could target a different student's data

**Deliverable:** Tool-calling works, correctly scoped, logged, tested.

---

## Phase A4: Output Guardrails

- [ ] A4.1: Implement `check_script_conformance()` per Section 7,
      reusing the Arabic-range regex already proven in
      `scripts/bidi_check.py` / `features.py`
- [ ] A4.2: Implement `check_bidi_structure()` as a direct import of
      `scripts.bidi_check.find_bidi_issues()` — not reimplemented
- [ ] A4.3: Implement `check_role_leak()` with an initial
      `OWNER_LEAK_MARKERS` list (internal table names, deploy commands,
      flag internals) — start conservative, expand from real
      `nour_guardrail_events` log data post-launch
- [ ] A4.4: Implement `guarded_generate()` wrapper: generate → check →
      retry-with-correction-hint once → template fallback
- [ ] A4.5: Log every guardrail trigger to `nour_guardrail_events`
      (type: script/bidi/role-leak, original text hash, corrected
      or fell back to template)
- [ ] A4.6: Stress test: reproduce the exact original bug conditions
      (long conversation, KB-heavy context, truncation-adjacent chunk
      sizes) 200 times against the new chunked-retrieval + guardrail
      pipeline — confirm 0 non-Arabic responses reach the "delivered"
      stage (SC1 acceptance test, run early and often, not just once
      at the end)

**Deliverable:** The original reported bug is mechanically
un-reproducible. This is the single most load-bearing phase relative
to the original complaint — do not skip or compress its testing.

---

## Phase A5: Bounded Orchestrator + Intent Classification

- [ ] A5.1: Implement `classify_intent()` — one cheap/fast LLM call,
      low max_tokens, categories per design.md Section 1
- [ ] A5.2: Implement `handle_message()` orchestrator per Section 8 —
      role resolve → intent → memory assembly → bounded tool/retrieval
      loop (max 3 iterations) → guarded generation → memory write
- [ ] A5.3: Wire Groq function-calling (`tools=` parameter) as primary
      LLM call path
- [ ] A5.4: Wire Gemini function-calling as fallback path (verify
      current Gemini API function-calling support/format before
      implementing — API details can shift; confirm against live docs
      at implementation time rather than trusting this spec's
      point-in-time assumption)
- [ ] A5.5: Preserve template-response last-resort tier (reuse existing
      `_TEMPLATE_RESPONSES` list)
- [ ] A5.6: Escalation path check (payment/refund/cancel keywords) —
      route through EXISTING `nour_escalation.escalate_to_owner()`
      unchanged, before the orchestrator loop even starts (matching
      today's early-exit behavior in `handle_message()`)
- [ ] A5.7: Unit test: a tool-calling loop that would exceed 3
      iterations is force-terminated into composition, never allowed
      to spiral (cost/latency safety valve, directly testing the
      "bounded" claim in the architecture)

**Deliverable:** Full orchestration pipeline functional end-to-end
against synthetic conversations. Still zero live traffic.

---

## Phase A6: Structured Memory

- [ ] A6.1: Implement working-memory retrieval (last ~10 turns from
      existing `nour_conversations`, unchanged schema)
- [ ] A6.2: Implement episodic summary generation — weekly per active
      student, reusing the Groq-summarization pattern from
      `nour_personality.run_weekly_review` redirected to per-student
      output into `nour_episodic_summaries`
- [ ] A6.3: Extend semantic memory retrieval to filter by `category` +
      relevance to current topic (not all facts dumped regardless of
      relevance)
- [ ] A6.4: Implement `journey_coverage` read/write functions —
      coverage flags flip on the SAME real signals Rawiya's triggers
      used (task completion, `!link` usage, channel visits), replacing
      the FSM's `_advance_step()` calls at those exact call sites in
      `bot.py` (`cmd_done`, `cmd_link`, daily check task)
- [ ] A6.5: Wire journey-gap surfacing into context assembly (Section 6)
      — gaps become retrievable conversational material, not a
      scripted trigger
- [ ] A6.6: Golden-set test: verify a multi-session conversation
      (simulate 3 separate days of chat) correctly references earlier
      context via episodic summary without needing full raw history
      re-sent every time

**Deliverable:** Memory is structured, bounded, and the onboarding
coverage model works without a rigid FSM.

---

## Phase A7: Rawiya Absorption — Proactive + Tutorials Integration

- [ ] A7.1: Redirect `nour_proactive.py`'s message *generation* calls
      through `guarded_generate()` instead of their own separate,
      unguarded Groq call — detection logic itself UNCHANGED
- [ ] A7.2: Confirm `nour_proactive.get_presence_level()` /
      `should_send_proactive()` graduated-presence logic requires zero
      changes (verify, don't assume, against the new orchestrator's
      call sites)
- [ ] A7.3: Chunk + embed the 8 existing tutorial texts
      (`nour_tutorials.TUTORIALS`) into the retrievable knowledge base
      under a `tutorials` domain — confirm retrieval surfaces the exact
      pre-written text verbatim (these must NEVER be paraphrased by the
      model; they are pre-verified-correct content, retrieved and
      quoted, not regenerated)
- [ ] A7.4: Decide + document: keep `nour_tutorials.check_and_send_tutorial()`'s
      trigger-based proactive dispatch (e.g. "3 wrong quiz answers in a
      row") as a SEPARATE proactive-push mechanism (student didn't ask,
      Nour proactively sends), distinct from retrieval (student DID ask,
      Nour retrieves) — these are different use cases, both valid, not
      one replacing the other
- [ ] A7.5: Regression test: every one of Rawiya's 9 proactive triggers
      still fires correctly and produces a guardrail-passing message

**Deliverable:** Rawiya's real value (detection + content) is fully
integrated into the new architecture; its rigid mechanism is gone.

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
