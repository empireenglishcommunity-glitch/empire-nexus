# CHECKPOINT — July 11, 2026 — Secret Leak Remediation

## Session Summary

Follow-up security session across all three Empire English repositories to fix hardcoded credentials found during PR work and a subsequent broader sweep. This checkpoint documents what was leaked, what was fixed, what still needs to be rotated on the live infrastructure, and confirms the sweep is complete.

---

## Leaks Found & Fixed

| # | Repo | File(s) | Secret | Fix | PR |
|---|------|---------|--------|-----|----|
| 1 | `EEC-REPO` | `infrastructure/n8n-workflows/EMPIRE-BOT-FINAL.json` (7x), `docs/checkpoints/CHECKPOINT_2026-06-25.md` | Telegram bot token | Replaced with `{{ $env.TELEGRAM_BOT_TOKEN }}` n8n expression; added `.env.example`; redacted checkpoint doc | [#29](https://github.com/empireenglishcommunity-glitch/EEC-REPO/pull/29) |
| 2 | `EEC-REPO` | `scripts/fix_quiz.py`, `docs/checkpoints/CHECKPOINT_2026-06-25.md` | n8n-MCP server auth token (`EmpireMCP2026SecureToken`) | Deleted one-off script (already ran, no ongoing purpose); redacted checkpoint doc | [#29](https://github.com/empireenglishcommunity-glitch/EEC-REPO/pull/29) (added as follow-up commit) |
| 3 | `Claude` | `fix_discord_workflows.py` | n8n API key (JWT, `X-N8N-API-KEY`) | Deleted one-off script (already ran, no ongoing purpose) | [#49](https://github.com/empireenglishcommunity-glitch/Claude/pull/49) |

**Note on leak #2:** this was found during a follow-up sweep, not the original task list. It was only referenced in the checkpoint doc originally reported, but the actual hardcoded value was also live in `scripts/fix_quiz.py`, which the initial pass missed.

---

## Sweep Method (for repeatability)

Ran regex searches across all three repos for common secret shapes:
- Telegram bot tokens: `\d{8,10}:[A-Za-z0-9_-]{35}`
- JWTs: `eyJ[A-Za-z0-9_-]{10,}`
- Generic key/token assignments: `API_KEY\s*=`, `auth\s*=\s*["']`, `Bearer [A-Za-z0-9._-]{20,}`, `SECRET\s*=\s*["']`
- Known leaked literal values, to confirm zero remaining occurrences after each fix

**Result after fixes:** no matches for any of the above patterns remain in `EEC-REPO`, `Claude`, or `zai-placement-test` (the latter had none to begin with — Task 1 was a clean feature branch, not a leak fix).

This was a targeted regex sweep, not an exhaustive secret-scanning tool run (e.g. `gitleaks`, `trufflehog`). Recommend running one of those across full git history as a follow-up (see below) since regex alone can miss obfuscated or oddly-formatted secrets.

---

## ⚠️ Action Required — Rotate These Live Secrets

None of the fixes above scrub git history — the plaintext values are still recoverable by anyone who clones the repo and inspects old commits. **All three must be rotated on the live systems:**

| Secret | Where it's used | Rotation steps |
|--------|------------------|----------------|
| Telegram bot token | Empire Bot (n8n workflow `EMPIRE-BOT-FINAL.json` / `lC9SVi4JDXZvAogr`) | 1. Message **@BotFather** → `/revoke` (or `/token`) on the bot → get new token. 2. Set `TELEGRAM_BOT_TOKEN` env var on the n8n server (Hetzner). 3. Restart/redeploy the n8n container so the env var is picked up. |
| n8n-MCP auth token (`EmpireMCP2026SecureToken`) | `empire-n8n-mcp` Docker container on Hetzner, exposed via Cloudflare Tunnel at `mcp.empireenglish.online` | 1. Generate a new random token. 2. Update the MCP container's env/config with the new token. 3. Redeploy the container. 4. Update any client (AI agent tooling) that calls the MCP server with the new token. |
| n8n API key (JWT used in `fix_discord_workflows.py`) | `bot.empireenglish.online` n8n instance API | 1. In n8n → **Settings → API** → revoke the old key → create a new one. 2. Update `infrastructure/n8n-mcp/.env` (`N8N_API_KEY`) on the server with the new key. 3. Restart the MCP container so it picks up the new key. |

**Also recommended (bcrypt migration, from the earlier session):** users on legacy SHA-256 hashes in `zai-placement-test` are already forced to reset — no separate "secret" to rotate there, but confirm the migration script (`migrate:force-reset-passwords`) has actually been run against production once PR #21 is merged.

---

## Verification Performed

- [x] Confirmed zero remaining occurrences of each leaked literal value in-repo (`grep_search` across the full repo for each exact token string)
- [x] Confirmed the one-off scripts (`fix_quiz.py`, `fix_discord_workflows.py`) are not referenced by any other file, doc, or CI workflow before deleting them
- [x] Confirmed all 3 fixes are on pushed branches with open PRs (not just local commits)
- [ ] **Not yet done:** actual rotation of the three live secrets above (requires access to Hetzner server / n8n admin / @BotFather — outside the scope of what this agent session can perform)
- [ ] **Not yet done:** full git-history scrub (e.g. `git filter-repo` / BFG) if the team decides the exposure window warrants it, in addition to rotation

---

## Open PRs From This Effort

| PR | Repo | Status |
|----|------|--------|
| [#21](https://github.com/empireenglishcommunity-glitch/zai-placement-test/pull/21) | zai-placement-test | Open — force password reset (SHA-256→bcrypt) |
| [#29](https://github.com/empireenglishcommunity-glitch/EEC-REPO/pull/29) | EEC-REPO | Open — Telegram token + MCP token fixes |
| [#49](https://github.com/empireenglishcommunity-glitch/Claude/pull/49) | Claude | Open — n8n JWT key removal |

---

## Next Session Priorities

1. Merge all 3 PRs above
2. Rotate the 3 live secrets per the table above
3. Run the `migrate:force-reset-passwords` script in production once PR #21 is merged and deployed
4. Consider running a proper secret-scanner (gitleaks/trufflehog) over full history for all repos as a one-time deeper check
5. Consider a pre-commit hook or CI secret-scanning step to prevent recurrence
