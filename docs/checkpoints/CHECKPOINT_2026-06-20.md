# Daily Checkpoint — June 20, 2026 (End of Day)

**Project:** Empire English Community — Bot Automation System  
**Session Duration:** Full day (~12+ hours)  
**Primary Focus:** Migration from Make.com to n8n self-hosted

---

## Executive Summary

Today was a major infrastructure day. The project migrated from Make.com (ops-limited, paid at scale) to a self-hosted n8n instance on Hetzner Cloud with a permanent Cloudflare Tunnel. The infrastructure is now production-grade and the bot workflow is partially rebuilt in n8n.

---

## What Was Completed Today ✅

### Infrastructure (PERMANENT — never needs to be touched again)
- ✅ Hetzner Cloud server provisioned (CX23, Helsinki, $7.09/mo)
- ✅ Docker + n8n installed and running
- ✅ n8n owner account created (Mahmoud Ashri)
- ✅ Telegram Bot credential connected and tested in n8n
- ✅ Google Sheets Service Account created + connected in n8n
- ✅ Domain purchased: `empireenglish.online` ($1.18/year, Namecheap)
- ✅ Domain added to Cloudflare (free plan)
- ✅ Nameservers pointed from Namecheap to Cloudflare
- ✅ **Permanent Cloudflare Named Tunnel** configured and running as a system service
- ✅ **Permanent URL: `https://bot.empireenglish.online`** — HTTPS, never changes, survives restarts
- ✅ n8n WEBHOOK_URL updated to permanent domain

### Bot Workflow (Partially Built)
- ✅ Workflow created: "Empire Bot — Main"
- ✅ Telegram Trigger node configured (Message + Callback Query — single trigger)
- ✅ Switch node configured with 8 routes (start, quiz_start, resource, how, call, community, menu, quiz_answer)
- ✅ /start route: Switch → Google Sheets "Append or Update" (Subscribers) → Google Sheets "Append" (Events) → Send Message
- ✅ CRM integration WORKS: rows are created/updated in Subscribers tab ✅
- ✅ Event logging WORKS: JOINED_BOT events appear in Events tab ✅

### Documentation
- ✅ PR #15 merged: Bug fixes patch (Make.com era)
- ✅ PR #16 merged: Phase 1 Implementation Spec
- ✅ PR #17 merged: n8n Migration Plan
- ✅ PR #18 merged: Project Audit & Handover Document

### Issues Resolved
- ✅ Oracle Cloud signup failure → pivoted to Hetzner
- ✅ n8n secure cookie error → fixed with N8N_SECURE_COOKIE=false
- ✅ Google Sheets OAuth requires domain → pivoted to Service Account (better for production)
- ✅ Private key format error → fixed by extracting with PowerShell command
- ✅ Telegram "only one trigger per bot" conflict → merged into single trigger with multiple update types
- ✅ Cloudflare quick tunnel URL changing → PERMANENTLY FIXED with named tunnel + domain

---

## What Is In Progress (Partially Complete) 🟡

### /start Route — Send Message Node
- **Status:** Node exists, CRM works, but the Telegram "Send message" has an inline keyboard issue
- **Problem:** n8n's button builder requires using the visual "Add Button" interface (Text + Callback Data fields), not raw JSON paste
- **Fix needed:** Rebuild the 5 buttons using n8n's visual button builder (5 rows, each with Text + Callback Data)
- **Estimated time:** 10 minutes

### Other Switch Routes (not yet built)
- menu route: needs Send Message with 5-button keyboard
- quiz_start route: needs quiz Q1 message
- quiz_answer route: needs Q2-Q7 handlers + scoring Code Node + plan delivery
- resource route: needs stub message + event log
- how route: needs 3 messages + event log
- call route: needs booking message
- community route: needs stub message + event log

---

## What Remains (Not Started) ⬜

| # | Task | Estimated Effort |
|---|---|---|
| 1 | Fix /start Send Message buttons (visual builder) | 10 min |
| 2 | Build menu route | 10 min |
| 3 | Build resource, how, call, community routes | 30 min |
| 4 | Build quiz flow (Q1-Q7 + Code Node scoring + plan delivery) | 2 hours |
| 5 | Build A5 Booking Sync (separate webhook workflow) | 30 min |
| 6 | Build A8 Daily Backup workflow | 15 min |
| 7 | Build Hot-lead Alert | 15 min |
| 8 | Run T1-T10 acceptance tests | 1 hour |
| 9 | Switch Cal.com webhook to permanent n8n URL | 5 min |
| 10 | Go LIVE (activate workflow) | 5 min |
| 11 | Phase 1: discussion group, content, weekly report, nudges | Days/weeks |

---

## Exact Resume Point (Where to Start Tomorrow)

### Immediate Next Action:
**Fix the /start route's "Send a text message" node — rebuild the inline keyboard buttons using n8n's visual button builder.**

### Context for resumption:
1. Open n8n at: `https://bot.empireenglish.online`
2. Open workflow: "Empire Bot — Main"
3. Open the "Send a text message" node (last node in the /start route)
4. The inline keyboard currently has a parsing error
5. Clear the keyboard section, then use "Add Keyboard Row" + "Add Button" to create 5 rows:
   - Row 1: Text = `🎯 حدّد مستواي (دقيقتان)` / Callback Data = `quiz`
   - Row 2: Text = `🎁 هديتي المجانية` / Callback Data = `resource`
   - Row 3: Text = `📚 كيف يعمل Empire` / Callback Data = `how`
   - Row 4: Text = `📅 احجز مكالمة مجانية` / Callback Data = `call`
   - Row 5: Text = `💬 انضم للمجتمع` / Callback Data = `community`
6. Execute workflow → send /start → bot should reply with welcome + working buttons
7. Then proceed to build the remaining routes (menu, resource, how, call, community)
8. Then the quiz (biggest piece — ~2 hours)

---

## Infrastructure Reference (Quick Access)

| System | URL / Access |
|---|---|
| **n8n** | `https://bot.empireenglish.online` |
| **n8n (direct IP)** | `http://77.42.43.250:5678` |
| **Server SSH** | `ssh root@77.42.43.250` |
| **Telegram Bot** | @EmpireEnglishBot |
| **Google Sheets CRM** | "Empire CRM" (shared with service account) |
| **Cal.com** | `https://cal.com/empireenglish/level-call` |
| **Cloudflare** | `dash.cloudflare.com` (empireenglish.online) |
| **Hetzner** | `console.hetzner.cloud` (project: Empire English) |
| **Domain** | `empireenglish.online` (Namecheap, NS → Cloudflare) |
| **Make.com (legacy)** | `eu1.make.com` — scenarios OFF, kept as reference |

---

## Risks & Notes

1. **The Cloudflare tunnel is a systemd service** — it auto-starts on reboot. Permanent.
2. **n8n is a Docker container with `restart: always`** — it auto-starts on reboot. Permanent.
3. **Make.com scenarios are OFF** — the bot token is still there but not active. Can be emergency fallback.
4. **The "3 American Sounds" PDF/audio** — still not produced (stubbed in bot). Not blocking.
5. **Phase 1 content** — spec is written, execution hasn't started. Waiting for bot to go live.

---

## Session Metrics

- PRs created today: 4 (PR #15, #16, #17, #18)
- Infrastructure cost locked in: $7.09/mo (Hetzner) + $1.18/yr (domain) = ~$86/year total
- Make.com equivalent at scale: $192-1,200/year → **saving 55-93% permanently**
- Bot operations: UNLIMITED (vs. 1,000/mo on Make.com free tier)

---

*End of Checkpoint — June 20, 2026*
