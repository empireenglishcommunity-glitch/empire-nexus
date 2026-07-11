# Empire English Community — Project Status

> **Last Updated:** July 11, 2026
> **Status:** Phase 0 COMPLETE | Phase 1 (Content) IN PROGRESS | Learning System DEPLOYED — **Full L0-L3 curriculum now complete (see below)**

> **This file was stale for 2 weeks (last dated June 27) and did not reflect the Discord Learning Bot's actual state.** The section below, "Discord Learning Bot — Deep Audit & Remediation (2026-07-11)", documents what was found and fixed. Treat this file, not the June 27 snapshot, as current.

---

## Current State

Empire English Community is a **system-driven English learning program** for Arabic speakers, focused on American accent mastery. All core infrastructure is built, deployed, and running.

### Live Systems

| System | Platform | Status |
|--------|----------|:------:|
| Telegram Sales Bot (v13) | Cloudflare Worker | LIVE |
| Discord Learning Bot | Docker on Hetzner | LIVE |
| Discord Challenge Bot | Docker on Hetzner | LIVE |
| LinkedIn Engine (v3.0) | Cloudflare Worker | LIVE |
| n8n (7 workflows) | Docker on Hetzner | RUNNING |
| MCP Server | Docker on Hetzner | RUNNING |
| Server Monitoring | systemd timer (60s) | ACTIVE |
| Daily Backups | Cron (3 AM) | ACTIVE |

### Phase Completion

| Phase | Description | Status |
|:-----:|-------------|:------:|
| 0 | Funnel (bot, quiz, CRM, automations, booking sync) | COMPLETE |
| 1 | Content (6 weeks posts, discussion group, KPIs) | IN PROGRESS |
| L0 | Learning System (Discord, curriculum, bot, 8 weeks) | DEPLOYED |
| 2 | Growth (paid ads, content scaling) | NOT STARTED |
| 3 | Scale (team, multi-level, paid tools) | NOT STARTED |

---

## Infrastructure

| Layer | Details | Cost |
|-------|---------|:----:|
| Server | Hetzner CX23, Helsinki, 77.42.43.250 | $7/mo |
| Routing | Cloudflare Tunnel → bot.empireenglish.online | $0 |
| MCP | mcp.empireenglish.online (AI workflow building) | $0 |
| Workers | Cloudflare (Telegram bot + LinkedIn engine) | $0 |
| CRM | Google Sheets (Service Account) | $0 |
| AI | Gemini + Groq (free tiers) | $0 |
| Monitoring | Telegram watchdog (60s) + BetterStack (3min) | $0 |
| **Total** | | **$7/mo** |

---

## What's Ready for Launch

- 36 Telegram channel posts (6 weeks)
- 14 Word of the Day posts
- Discussion group seeding content
- L0 curriculum: 448 vocabulary words, 56 speaking missions, 56 writing prompts
- 30-day challenge (all 30 days with tasks, tips, AI coaching)
- PDF certificates (Arabic, auto-generated)
- Landing pages (EN + AR, not yet hosted)
- LinkedIn engine generating daily posts

---

## Immediate Next Steps (Priority Order)

1. Fix Gemini API key on Hetzner (requires home network SSH)
2. Test Discord bot commands (!help, !join, !done, !progress, !streak)
3. Assign Founder role in Discord server
4. Create KPI_Weekly + Stories tabs in Google Sheets CRM
5. Add Cal.com webhook URL in Cal.com dashboard
6. Schedule Week 1 Telegram posts
7. Deploy landing pages to Cloudflare Pages
8. Recruit 3-5 pilot members for Discord learning system
9. Start approving LinkedIn Engine daily posts

---

## Key Decisions (Locked)

| Decision | Rationale |
|----------|-----------|
| n8n over Make.com | No ops limits, self-hosted, zero vendor lock-in |
| Cloudflare Workers for bots | Always-on, zero-cost, no process management |
| No AI in Telegram sales bot | AI free tiers unreliable; keyword bank = 100% uptime |
| SQLite for Discord bots | Single-file DB, zero setup, perfect for <10K users |
| Gemini + Groq dual fallback | Free tiers, no credit card, graceful degradation |
| Docker for all server processes | Isolation, reproducibility, survives updates |
| Google Sheets CRM (Service Account) | Free, familiar, credential type: googleApi |

---

## Discord Learning Bot — Deep Audit & Remediation (2026-07-11)

A full end-to-end audit of `bots/discord-learning-bot/` was performed after discovering the June 29 commit claiming "L1/L2/L3 curriculum data" complete had NOT actually delivered working, verified content for two of the three levels. Everything below was found and fixed in this session — code changes are in `src/`, content changes are in `data/` and `content/`.

### What was actually broken (found via direct code tracing, not assumption)

1. **L1/L2/L3 students were silently served Level 0 content.** `curriculum.py` only ever loaded accent/grammar drills from `content/l0/`, and three separate call sites (`tasks.py`, `verification.py`, `features.py`) failed to pass the student's real `level` into the vocabulary/curriculum lookup functions — every level defaulted to `"L0"`. This affected daily vocabulary, speaking missions, writing prompts, spaced-repetition quizzes, and the weekly grammar card.
2. **L2 and L3 had zero real vocabulary.** `data/l2_weekN.json` and `data/l3_weekN.json` had `"vocabulary": []` in every single file, and their `speaking_missions`/`writing_prompts` were mechanically templated placeholder strings (e.g. `"Write an essay (150+ words) arguing for or against an aspect of {theme}."`) — not real curriculum, despite the June 29 commit message.
3. **A filename-parsing bug in `curriculum.py`** assigned week numbers by *alphabetical sort position* rather than parsing the number from the filename. This is silently wrong for any level with 10+ weeks (Python string-sorts `"week10"` before `"week2"`) — it would have corrupted L1 (10 weeks) and L2 (12 weeks) the moment real per-week content existed. Found and fixed during L1 content verification, before it could cause live damage.
4. **The `!exam` advancement flow was a dead end.** Submissions were collected via DM into an in-memory Python dict that was never written to the database — the 30-day cooldown check was structurally unreachable (always saw "no prior attempt"), no admin was ever notified of a completed submission despite a code comment claiming otherwise, and a bot restart would silently lose an in-progress submission with no trace. There was no command to resolve an exam or trigger the promised automatic role promotion.
5. **Two minor security hygiene issues**: `config.py` hardcoded a real production Google Sheet ID as a source-code fallback default (not a credential, but a bad pattern), and `.env.example` had a real-looking Telegram chat ID instead of a placeholder.

### What was fixed

- `src/curriculum.py`: accent/grammar loading is now genuinely per-level, parses week numbers directly from filenames (regex, not sort position), and returns `None` honestly for any level/week with no content yet — no more silent L0 substitution.
- `src/tasks.py`, `src/verification.py`, `src/features.py`: all three now correctly thread the student's real level through to curriculum lookups.
- `src/bot.py`: the weekly grammar-card scheduler now loops over all 4 levels (previously checked only L0).
- `src/database.py`: `advancement_exams` table extended (via a safe, idempotent `ALTER TABLE` migration — verified against a simulated copy of the live server's existing schema) with `status`, `speaking_recording_url`, `writing_submission`, `resolved_at`, `resolved_by` columns. New functions: `create_pending_exam()`, `pending_exams()`, `get_exam_by_id()`, `resolve_exam()`.
- `src/features.py`: exam DM collection now persists to the database and notifies every admin (guild members with `manage_guild` permission) via DM with the exact resolve command.
- `src/bot.py`: new admin commands `!examqueue` (list pending exams) and `!examresult <id> pass|fail` (resolves the exam; on pass, calls the existing `set_level()` + role-reassignment logic and DMs the student).
- `src/config.py`, `.env.example`: removed the hardcoded real Sheet ID default; cleaned up placeholder values.
- **All 38 weeks of curriculum content across L0-L3 are now real and complete**: L1 (10 weeks) and L2 (12 weeks) accent + grammar content written from scratch, grounded explicitly in the Learning System Blueprint's Table 19 (sound patterns by level) and §5.3/§5.4 (linking/rhythm rules) wherever the blueprint assigns a specific week; L2 and L3 vocabulary/speaking/writing rewritten from empty/templated to real, hand-written content; L3 accent content grounded in Table 10/§5.6 (Accent Refinement: Micro-Phonetics) and Table 11 (Mastery Tiers), since Table 19 does not extend phoneme assignments past L2. Full detail and word-count tables are in `bots/discord-learning-bot/data/README.md` and the Learning System Blueprint's changelog.

### Verified, not assumed

Every fix above was tested by actually running `curriculum.load_all()` and asserting the correct content resolves for all 38 weeks across all 4 levels (zero mismatches), and the exam flow was tested against both a fresh database and a simulated copy of the live server's existing (pre-migration) schema to confirm the `ALTER TABLE` migration is safe.

### Explicitly deferred (not done this session — needs your input, not more of my guessing)

- **Google Sheets CRM wiring**: `config.py` has had `SHEET_ID`/`GOOGLE_SERVICE_ACCOUNT_EMAIL` settings for a while, but no code anywhere actually calls the Google Sheets API. Building this requires a real service account and a defined sheet schema I don't have access to — deferred rather than guessed at.
- **Discord server permission drift**: two ad-hoc Python scripts (`fix_permissions.py`, `fix_all_permissions.py`, in the `Claude` repo, not this one) were run directly against the live Discord server and never folded back into this repo's versioned `scripts/setup_server.py`. Reconciling this needs someone with live server access to compare current state against the script.

---

## Repository

All code, content, documentation, and infrastructure live in this single repository:
`empireenglishcommunity-glitch/EEC-REPO`

See [README.md](README.md) for the full structure map and [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md) for the technical audit.
