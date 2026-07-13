# Requirements — Production-Safe Deploys ("Aegis")

> **Codename: Aegis.** Internal name for this initiative, used throughout
> this spec and future commit messages/PRs for easy cross-referencing.
> Directory name (`production-safe-deploys`) stays literal/technical so
> it's discoverable without knowing the codename.

## Origin

User is about to invite **16 real, paying students** (9 free-tier + 7
paid) into the Discord learning system for the first time. Everything
built and tested so far (including the 2026-07-12/13 stress-testing
pass, PRs #44/#10) was verified against synthetic data or a handful of
test accounts — **none of it has been exercised against real student
traffic.** Once real students are active, the cost of a visible bug
changes completely: this is a **paid, marketed-as-professional product**,
and a broken command or a corrupted streak in front of a paying customer
is a trust/reputation event, not just a bug ticket.

User's explicit ask (paraphrased, confirmed with them directly before
writing this spec): *"I want to keep enhancing/fixing/editing the bot and
practice webpage after real students join, without affecting their
experience, because they're paying money and expect a professional
system."* They also explicitly asked for **creative, non-standard
solutions** ("think big and out of the box"), and for the resulting plan
to be **written down persistently** so it survives a session ending or a
different Kiro account/agent picking up the work.

## Constraints (do not violate these while designing solutions)

1. **Budget:** the entire project runs on one Hetzner CX23 (~$7/mo) plus
   free tiers (Gemini/Groq AI, Cloudflare Pages, GitHub Actions free
   minutes). No new paid services, no "just add a staging cluster."
2. **No new secrets/vendor lock-in** beyond what's already in use,
   consistent with `.kiro/steering/project-rules.md`'s architecture
   principles (zero vendor lock-in, self-hosted preferred).
3. **Solo operator + AI agents**, not a team — solutions must not require
   ongoing manual toil to keep working (e.g. "remember to always run X by
   hand" is a weak solution; "X runs itself and tells you if it fails" is
   a strong one).
4. **SSH/API access is always temporary** in this working pattern (keys
   never survive between sessions, per `empire-chronicle`'s
   `AI-AGENT-PROTOCOL.md`) — any solution that assumes persistent server
   access to function is fragile by this project's own established norms.
5. **Must not regress anything already shipped** — the 12 stress-test
   fixes (PR #44) and the XSS fix (PR #10) are live; this initiative adds
   a safety layer around future changes, it doesn't redo past work.

## Real finding surfaced while gathering context for this spec

Two commits (`7f685f1` "Deep cleanup: lint, dead code, deps, docs" and
`5829134` "Add database backup mechanism for discord-learning-bot" — a
full `scripts/backup.py` + 154 lines of tests, modeled on the sibling
`discord-challenge-bot`'s existing backup script) were pushed to branch
`test/ai-engine-and-features-coverage` **after** PR #43 had already
merged an earlier point on that same branch into `main`. Confirmed via
`git merge-base --is-ancestor` that neither commit is in `main` today —
they are real, tested, working code, currently invisible and unused.
Since automated backups are directly relevant to this spec's own goals,
recovering this is **Phase 0** of the implementation plan (see
`tasks.md`), not a separate cleanup task.

## Requirements

### Requirement 1 — Deploys must be invisible to students when nothing is wrong
**User story:** As a paying student, I want the bot and practice website
to always feel reliable and professional, so that I trust the product I
paid for.

**Acceptance criteria:**
1. WHEN a routine code change is deployed to the live bot THEN the
   system SHALL NOT produce any player-visible downtime longer than a
   single Discord gateway reconnect (a few seconds).
2. WHEN a routine change is deployed to `empire-dojo` THEN the system
   SHALL NOT serve a broken or partially-regenerated page at any point
   during the deploy (Cloudflare Pages atomic-swap deploys already
   satisfy this for the website side — this requirement is about not
   accidentally bypassing that guarantee, e.g. by hand-editing files on
   a live deploy target).
3. WHEN a deploy is in progress THEN admins SHALL have a way to signal
   this state (e.g. a bot presence/status change) so an admin manually
   checking on the system doesn't mistake a deploy-in-progress blip for
   an outage.

### Requirement 2 — Every change must be verifiable before it touches real data
**User story:** As the operator, I want to test any bot or webpage change
against realistic scenarios before it can affect a real student's
progress, points, streak, or exam record.

**Acceptance criteria:**
1. WHEN a code change is proposed for the bot THEN the system SHALL
   provide a way to exercise it against a disposable, realistic-shaped
   dataset without writing to the real production SQLite database.
2. WHEN a code change needs to be tested against an edge case that would
   naturally take real calendar time to occur (e.g. "a member on day 13
   of a streak," "a member 29 days into the exam cooldown") THEN the
   system SHALL provide a way to manufacture that state synthetically
   rather than waiting for real time to pass.
3. WHEN a code change is proposed for `empire-dojo` THEN the system
   SHALL provide a way to view the fully-rendered result on a real,
   shareable URL before it can reach the live production domain.
4. WHEN a change is merged and deployed THEN an automated check SHALL
   confirm the deployed system is in a known-good state (specific,
   checkable facts — e.g. "curriculum loaded: 38 weeks," "N commands
   registered including the new one" — not just "the container is
   running").

### Requirement 3 — Every deploy must be reversible in under a minute
**User story:** As the operator, I want any deploy that turns out to be
bad to be undoable almost instantly, without needing to debug under
pressure while students are watching.

**Acceptance criteria:**
1. WHEN a deploy is about to modify the live bot container THEN the
   system SHALL automatically snapshot the production database
   immediately beforehand, with no manual step required.
2. WHEN a deploy is about to modify the live bot container THEN the
   previous working image SHALL remain available and startable without
   needing to rebuild it from source.
3. IF a deploy is discovered to be broken THEN the operator SHALL be
   able to restore both the previous code and the pre-deploy database
   snapshot with a single documented command sequence.

### Requirement 4 — New features must be releasable independently of when they're deployed
**User story:** As the operator, I want to merge and deploy code changes
whenever is convenient for me, and separately decide when real students
actually see the new behavior — including the ability to test a new
feature on myself or a trusted few before anyone else sees it.

**Acceptance criteria:**
1. WHEN a new user-facing behavior is added THEN the system SHALL
   support enabling it for a specific, named allowlist of Discord user
   IDs before enabling it for everyone.
2. WHEN a feature that is live for real students starts misbehaving
   THEN an admin SHALL be able to disable that specific feature via a
   single command, without needing a code change, a redeploy, or any
   bot downtime.
3. WHEN a feature flag's state changes THEN the system SHALL persist
   that state across bot restarts (i.e. it must live in the database,
   not in memory).

### Requirement 5 — Regressions must be caught automatically, not by a student noticing first
**User story:** As the operator, I want the system itself to notice if a
change broke something, rather than finding out from a paying student's
complaint.

**Acceptance criteria:**
1. WHEN any pull request is opened against the bot's codebase THEN an
   automated check SHALL run the full test suite AND simulate a
   realistic multi-day student journey (join → multiple days of tasks →
   streak → weekly assessment → exam flow) against a disposable
   database, verifying the resulting data matches expected invariants
   (correct point totals, correct streak values, no lost submissions).
2. WHEN any pull request is opened against `empire-dojo`'s generator
   THEN an automated check SHALL regenerate the full site and verify
   every page parses as well-formed HTML with no injection-shaped
   content surviving unescaped (formalizing the manual verification
   already performed during the 2026-07-13 XSS fix into a permanent,
   unskippable guardrail).
3. WHEN a `empire-dojo` change is about to be promoted to production
   THEN the system SHALL support comparing the new output against the
   currently-live site for a representative sample of pages, surfacing
   any unexpected differences beyond the ones the change was meant to
   make.

### Requirement 6 — Operational rigor should visibly reinforce the "professional, premium" brand
**User story:** As the operator marketing this as a professional,
high-value system, I want the *evidence* of that professionalism (rapid
fixes, transparent communication, reliability) to be visible to students,
not just true behind the scenes.

**Acceptance criteria:**
1. WHEN a new feature is safely rolled out to all students THEN the
   system SHALL support announcing it via the bot's existing
   `!announce` mechanism in the established bilingual (English/Arabic)
   style, framed as an improvement delivered to them.
2. WHEN the operator wants to demonstrate system reliability THEN a
   simple, publicly viewable status artifact SHALL exist (e.g. a status
   page or command) showing uptime / last-verified-healthy information,
   without introducing a new paid service.

### Requirement 7 — This plan itself must survive the session, the account, or the agent changing
**User story:** As the operator, I want to be able to close this session,
open a brand-new Kiro session (possibly a different account or a
different underlying agent), and pick up exactly where this plan left
off without re-explaining the goal or re-deriving the design.

**Acceptance criteria:**
1. WHEN this spec is created THEN it SHALL be committed to
   `empire-nexus` (not left only in chat) at
   `.kiro/specs/production-safe-deploys/`, containing `requirements.md`
   (this file), `design.md`, and `tasks.md`.
2. WHEN this spec is created THEN `empire-chronicle`'s `STATUS.md` and
   `README.md`'s "Next Session Priorities" SHALL be updated with a
   pointer to it, since that repo is the established cross-session entry
   point for any future session per `AI-AGENT-PROTOCOL.md`.
3. WHEN a task in `tasks.md` is completed THEN it SHALL be checked off
   in the same commit that completes it, so the file itself is always an
   accurate, current progress record — not a plan that drifts from
   reality (the same discipline this project's `SESSION_CONTINUITY.md`
   already enforces for session-level history).

## Explicitly out of scope for this spec
- Rebuilding or replacing anything already shipped and working (the 12
  stress-test fixes, the XSS fix, buddy rotation, `!attention`).
- The unrelated open items already tracked in `empire-chronicle`
  (`empire-annex` disposition, `app.empireenglish.online`'s Vercel step,
  Google Sheets CRM). These stay parked per the user's explicit
  instruction to prioritize this work first, unless something among
  them becomes actually critical/broken-in-production.
- Migrating off SQLite, off Hetzner, or off the current $7/mo
  infrastructure. The goal is safety *within* the existing budget
  reality, not a platform migration.
