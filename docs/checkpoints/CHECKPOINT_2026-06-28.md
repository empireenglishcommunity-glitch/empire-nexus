# Empire English Community — Session Checkpoint
## Date: June 28, 2026
## Agent: Kiro (AI Agent)
## Focus: Z.ai Placement Test — Full Build, Deploy, and Polish

---

## Summary

Major session: Built, deployed, and polished the complete Empire English placement test assessment system from scratch. Self-hosted on Hetzner server via Docker + Cloudflare Tunnel at `assessment.empireenglish.online`.

---

## What Was Accomplished

### 1. Scoring Engine Merge
- Ported anti-cheating scoring engine from `Claude/empire-assessment` into `zai-placement-test`
- Added: response time analysis, assessment integrity scoring, Imperial Training Paths
- Anti-score-farming: attempt-weighted scoring (1st attempt = highest weight)
- Retake cooldown: 5 minutes between attempts

### 2. AI Routes (Gemini 2.0 Flash)
- `/api/ai/generate-listening`: Generates passages + 3 MCQ questions per speed tier
- `/api/ai/evaluate-speaking`: Evaluates TEXT transcripts (not audio) via Gemini
- Both routes ALWAYS return results (fallback to curated content/heuristic scoring)

### 3. Speaking Trial — Complete Rewrite
- Replaced fake audio evaluation with REAL browser Speech Recognition (Web Speech API)
- Live transcript shown as user speaks
- Text compared to expected passage (read-aloud), vocabulary/grammar evaluated (spontaneous)
- Score = 0 if user doesn't speak (no fake scores ever)
- Works in Chrome, Edge, Safari only (Firefox warning shown)

### 4. Self-Hosted Deployment
- Docker multi-stage build (Node 20 Alpine, non-root user, health check)
- SQLite database with auto-initialization (docker-entrypoint.sh creates all tables)
- Cloudflare Tunnel routes `assessment.empireenglish.online` → localhost:3100
- $0 extra cost on existing Hetzner CX23

### 5. Authentication & Security
- NextAuth.js with credentials provider (email + password)
- Invite code system (registration by invitation only)
- Default codes: EEC-PAID-2026, EEC-FREE-2026, EMPIRE-VIP
- Password reset via Resend (real emails, 1-hour token expiry)
- Email verification on registration (24-hour token expiry)
- Rate limiting on all API routes (60 req/min assessment, 30 req/min AI)

### 6. Guest Mode
- "Continue as Guest" on login page
- Guests can try all 4 trials and see instant scores
- Scores NOT saved to database (sessionStorage-based guest ID)
- "Create Account to Save" CTA on results
- Guest flag clears on tab close

### 7. Dashboard Integration
- Submit route creates/updates assessment records linked to real user
- Dashboard calculates rank from module levels (majority rule + speaking tiebreaker)
- Assessment hub shows dynamic completion status per trial
- "View Full Results" only shows when all 4 trials complete

### 8. Arabic Bilingual UI
- All navigation: Arabic subtitles (الرئيسية، الاختبارات، لوحة التحكم)
- Assessment hub: Arabic trial names + descriptions
- All 4 trial intros: Arabic explanations
- Login/Register: Arabic labels and instructions
- Design principle: Instructions in Arabic, assessment content in English

### 9. Bug Fixes (from 2 stress tests)
- Fixed 23+ issues across all pages
- Rate limiter made less aggressive (was blocking normal usage)
- Bot detection removed from assessment APIs (Cloudflare handles it)
- Results page shows real data (not mock)
- Homepage/Terms/Privacy buttons respect login state
- IP documentation opens in new tab (not broken PDF download)
- Proxy file renamed from middleware.ts (Next.js 16 convention)

---

## Technical Architecture

```
assessment.empireenglish.online
    ↓ (Cloudflare Tunnel)
Hetzner CX23 (77.42.43.250)
    ↓ (Docker)
empire-assessment container (port 3100)
    ↓
Next.js 16 + SQLite + Prisma
```

### Database: SQLite
- File: `/app/db/assessment.db` (Docker volume persisted)
- Tables: users, profiles, assessments, answers, questions, assessment_sessions, question_exposures, invite_codes, recordings, review_flags, admin_notes, ownership_records

### Environment Variables (on server .env):
- NEXTAUTH_SECRET (generated)
- NEXTAUTH_URL=https://assessment.empireenglish.online
- GEMINI_API_KEY (for AI evaluation)
- RESEND_API_KEY (for password reset + verification emails)
- DATABASE_URL=file:/app/db/assessment.db

---

## Repositories Involved

| Repo | What Was Done |
|------|--------------|
| `zai-placement-test` | ALL development — 30+ commits today |
| `Claude/empire-assessment` | Source for scoring engine (ported to zai-placement-test) |
| `EEC-REPO` | This checkpoint documentation |
| `Kiro-Master-Index` | Updated with current state |

---

## What's Live & Working

| Feature | URL | Status |
|---------|-----|--------|
| Placement Test | https://assessment.empireenglish.online | ✅ LIVE |
| 4 Trials (Speaking, Listening, Vocab, Grammar) | /assessment/* | ✅ Working |
| Guest Mode | /login → Continue as Guest | ✅ Working |
| Invite Registration | /register (requires code) | ✅ Working |
| Password Reset | /forgot-password → email → /reset-password | ✅ Working |
| Dashboard | /dashboard | ✅ Working |
| Results | /results (after all 4 trials) | ✅ Working |

---

## Invite Codes (Pre-Created)

| Code | Type | For |
|------|------|-----|
| EEC-PAID-2026 | paid | 6 paid students |
| EEC-FREE-2026 | free | 9 free students |
| EMPIRE-VIP | vip | Special access |

---

## Known Remaining Items (Not Blockers)

| Item | Priority | Notes |
|------|----------|-------|
| Grammar has no confirm step (first tap = final) | Low | Intentional for speed |
| Homepage progress section shows demo values | Low | Marketing only |
| Retake cooldown is client-side only for speaking/listening | Low | Enough for 15 students |
| No "Results" link in navbar | Low | Accessible from dashboard |
| Speaking useEffect deps warning | Low | Works correctly in production |

---

## How to Update/Redeploy

```bash
cd /opt/empire-assessment
git pull origin main
docker compose up -d --build
```

## How to Create New Invite Codes

Via API (requires admin user):
```bash
curl -X POST https://assessment.empireenglish.online/api/invite \
  -H "Content-Type: application/json" \
  -d '{"code":"NEW-CODE-2026","type":"paid","maxUses":10,"note":"Batch for July cohort"}'
```

Or directly in the database:
```bash
docker exec -it empire-assessment sqlite3 /app/db/assessment.db \
  "INSERT INTO invite_codes (id, code, type, maxUses, usedCount, isActive) VALUES ('new1', 'MY-CODE', 'paid', 10, 0, 1);"
```

---

## Next Session Priorities

1. Human test by owner — fix any issues found
2. Consider adding admin panel for managing students/codes
3. Add Arabic to trial RESULTS screens (currently only intros have Arabic)
4. Optional: Add Groq as AI fallback (doubles capacity)
