# /sync — Repository Closing Protocol

> **⚠️ SUPERSEDED 2026-07-12.** This file is kept only as historical
> record. The current, canonical protocol lives in
> `empireenglishcommunity-glitch/Kiro-Master-Index/.kiro/steering/AI-AGENT-PROTOCOL.md`
> — follow that version, not this one. This file predates that
> consolidation and had already drifted slightly from `Claude` repo's
> copy of the same rules (the exact problem the consolidation fixes).

## Trigger
When the user sends `/sync`, execute the full repository closing protocol below.

## Protocol Steps

### 1. Session Review
- Identify ALL changes made during the current session
- List every system, workflow, file, or infrastructure component that was modified
- Distinguish between completed work and remaining open items

### 2. Code & Configuration Verification
- Verify all modified code compiles/runs without errors
- Confirm no secrets, debug artifacts, placeholder values, or temporary hacks remain in committed code
- Check that deployed systems (n8n workflows, bots, infrastructure) match repository documentation
- Validate that any credentials referenced use proper placeholder patterns (never real values in repo)

### 3. Documentation Sync
- Update `PROJECT_STATUS.md` to reflect current state
- Create or update checkpoint file in `docs/checkpoints/` for significant sessions
- Ensure all architectural decisions made during the session are documented
- Update README or relevant docs if project structure changed
- Record any new configurations, URLs, or system details

### 4. Repository Cleanup
- Remove files that are no longer relevant
- Ensure no duplicate or conflicting documentation exists
- Verify `.gitignore` covers all sensitive/generated files
- Check for untracked files that should be committed or ignored
- Ensure consistent file naming and organization

### 5. Commit & Push
- Stage all changes
- Write a descriptive commit message summarizing the session's work
- Push to the appropriate branch (never directly to main unless explicitly requested)
- Create a Pull Request if the changes are substantial

### 6. Final Report
Deliver a structured summary:
```
═══════════════════════════════════════
  /sync — SESSION CLOSE REPORT
═══════════════════════════════════════

COMPLETED:
  - [list of completed items]

FILES CHANGED:
  - [list of files modified/created/deleted]

SYSTEMS MODIFIED:
  - [n8n workflows, bots, infrastructure changes]

DOCS UPDATED:
  - [documentation files updated]

OPEN ITEMS:
  - [anything remaining for next session]

SYSTEM HEALTH:
  - [status of all running services]

NEXT SESSION PRIORITIES:
  - [recommended next steps in priority order]
═══════════════════════════════════════
```

## Rules
- Always push to a branch, never directly to main (unless user requests it)
- Never commit real API keys, tokens, or passwords — use references/placeholders
- If the session had no code changes (only discussion/planning), note that and skip commit
- The checkpoint file is only created for sessions with significant implementation progress
- Be honest about what's incomplete — never mark something as done if it isn't verified
