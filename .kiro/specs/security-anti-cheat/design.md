
# Design — Hissar: System Security, Anti-Cheat & Copyright Protection

## Guiding idea

Security at this scale (16 students, $0 budget) is about **raising the
cost of abuse above the value of the content** — not making it
theoretically impossible. A determined, technically skilled attacker
will always find a way; the goal is that a lazy student sharing their
login or a casual competitor looking to copy content hits real
friction rather than finding everything wide open.

## Component 1 — Content gating: practice platform access control [NEED]

**Current state:** Every page at `practice.empireenglish.online` is a
static HTML file on Cloudflare Pages — publicly accessible, no auth.

**Design — token-gated rendering (client-side, zero-cost):**
The practice pages ALREADY have a "Connect" flow (localStorage token).
Extend this into a gate:

1. **Every practice page** (accent, vocab, listening, shadowing) checks
   for a valid token in localStorage on load. If no token → redirect
   to the connection page (`/dash/` or a dedicated `/connect/`). The
   CONTENT divs are hidden by default (CSS `display:none`) and only
   shown after a token validation API call succeeds.

2. **API-side token validation:** new lightweight endpoint
   `GET /api/validate-token?token=xxx` → returns `{valid: true/false}`
   (no student data, just a yes/no — fast, cheap, hard to abuse).

3. **Meta tags on all practice pages:**
   `<meta name="robots" content="noindex, nofollow">`
   Prevents Google from caching/indexing the curriculum.

4. **`robots.txt`** at site root:
   ```
   User-agent: *
   Disallow: /l0/
   Disallow: /l1/
   Disallow: /l2/
   Disallow: /l3/
   Disallow: /audio/
   Allow: /
   Allow: /dash/
   ```

**What this does NOT prevent** (accepted limitations):
- A student with a valid token can still view-source and copy HTML.
  This is inherent to web content and can't be prevented without
  DRM ($$$). Accepted — see "watermarking" below for the mitigation.
- The audio files are still technically fetchable if someone knows
  the URL pattern. Mitigated by removing the predictable directory
  listing (Cloudflare Pages doesn't serve directory listings by
  default, but individual file URLs still work if guessed).

## Component 2 — Token sharing detection [NEED]

**Design — lightweight IP+fingerprint logging:**

1. **Log every API request's IP** in a new `token_access_log` table:
   ```sql
   CREATE TABLE IF NOT EXISTS token_access_log (
       id          INTEGER PRIMARY KEY AUTOINCREMENT,
       token       TEXT NOT NULL,
       ip_address  TEXT NOT NULL,
       user_agent  TEXT DEFAULT '',
       accessed_at TEXT NOT NULL DEFAULT (datetime('now'))
   );
   CREATE INDEX IF NOT EXISTS idx_token_access ON token_access_log(token, accessed_at);
   ```

2. **Daily analysis** (new scheduled task): for each active token,
   count distinct IPs in the last 24h. If a token shows 3+ distinct
   IPs → log a warning. If 5+ → auto-flag and send a Telegram alert
   to the operator via the existing Markaz ops bot.

3. **`!revoke @user` admin command:** immediately deletes the user's
   link token from `link_tokens`, forcing them to re-run `!link` to
   get a new one. The old token stops working instantly for anyone
   who had it shared.

4. **Token rotation on suspicious activity:** if a token is flagged,
   auto-revoke it and DM the student: "Your access link was reset
   for security. Please type `!link` again to get a new one."

## Component 3 — Anti-cheat hardening [NEED]

**Design — 3 targeted fixes for known bypass patterns:**

1. **Increase cooldown to 3 minutes** (from 60 seconds):
   `COOLDOWN_SECONDS = 180`. This alone makes farming 7 tasks take
   21+ minutes minimum instead of the current 7 minutes — still
   achievable legitimately, but removes the "spam !done in 7 minutes
   with minimal effort" exploit.

2. **Persist cooldown state in the database** (not in-memory):
   New `last_done_at` column on the `members` table (or a lightweight
   `anti_cheat_state` table). On every `!done`, write the timestamp
   to the DB. On every `!done` check, read from the DB. This survives
   bot restarts — a deploy no longer silently resets all cooldowns.

3. **Progressive quiz delay on wrong answers:**
   After a wrong vocab/listening answer, impose a 30-second wait
   before the student can retry (`_pending_quizzes[discord_id]
   ["retry_after"]`). After 3 wrong answers in a row, impose a
   5-minute lockout for that specific task type for that day.
   Prevents brute-force guessing.

## Component 4 — Legal protection [NEED]

**Design — 3 documents, deployed before students arrive:**

1. **Terms of Service** (Arabic, pinned in `#rules`):
   - Content is proprietary and owned by Empire English Community
   - Redistribution, copying, or sharing of any content (text, audio,
     curriculum data) is prohibited
   - Account sharing is prohibited (one person per account)
   - Violation → immediate suspension without refund
   - Use Discord's built-in **Rules Screening** to require acceptance
     before any channel access

2. **Copyright footer** on every practice platform page:
   ```html
   <p>© 2026 Empire English Community. All rights reserved.
   هذا المحتوى ملكية خاصة ومحمي بحقوق الطبع والنشر.</p>
   ```

3. **HTML watermark** embedded in curriculum pages (invisible to users,
   visible to anyone who copies the source):
   ```html
   <!-- Empire English Community | Proprietary Content | Unauthorized copying prohibited | ID: {token_hash} -->
   ```
   This creates a trail: if copied content surfaces online, the
   watermark identifies which token was used to access it, linking
   back to the specific student who leaked it.

## Component 5 — API hardening [NEED]

**Design:**

1. **Restrict CORS origin** to only the real practice platform domain:
   ```python
   ALLOWED_ORIGINS = {
       "https://practice.empireenglish.online",
       "https://empire-practice-8l0.pages.dev",
   }
   ```
   Return `Access-Control-Allow-Origin` only if the request's
   `Origin` header matches. Otherwise, no CORS header → browser
   blocks the response. (Note: this doesn't prevent server-side
   scrapers, but blocks casual "build your own frontend" attempts.)

2. **Tighten rate limit** from 60/min to 20/min per token (16
   students × normal usage is maybe 5-10 requests per session, not
   60 — the current limit was designed for stress-testing, not
   production security).

3. **Strip unnecessary data from API responses:**
   Review every endpoint — ensure no endpoint exposes data belonging
   to OTHER students (leaderboard shows names+points only, already
   safe). Ensure pronunciation audio URLs are not exposed (they
   currently are via `voice_portfolio` — consider removing `url` field
   from the API response or making it token-gated).

## Component 6 — Monitoring & alerting [WANT]

**Design (enhancement, not blocking):**

1. **Suspicious activity Telegram alert** via Markaz ops bot:
   - Token used from 3+ IPs in 24h
   - Same token used for 2+ concurrent API requests (impossible for
     one human in one browser)
   - Rate limit hit repeatedly (indicates scraping attempt)

2. **Weekly security digest** (append to existing Sunday Markaz
   report): "0 suspicious tokens this week" or "1 token flagged:
   bioroma, 4 distinct IPs" — so the operator sees it without
   actively checking.

## Phased implementation order

| Phase | Components | Risk | Effort |
|---|---|---|---|
| **P0** | robots.txt + noindex meta tags + copyright footer | Zero risk (additive only) | 30 min |
| **P1** | Terms of Service (Discord Rules Screening + #rules pin) | Zero risk | 1 hour |
| **P2** | CORS restriction + rate limit tightening | Low risk (test first) | 1 hour |
| **P3** | Content gating (token check on practice pages) | Medium risk (could break if token flow has a bug) | 2-3 hours |
| **P4** | Anti-cheat hardening (cooldown increase + DB persist + quiz delay) | Low risk (behind flag) | 2-3 hours |
| **P5** | Token sharing detection (IP logging + analysis + !revoke) | Low risk (additive) | 2-3 hours |
| **P6** | Monitoring & alerting | Low risk (additive) | 1-2 hours |

**P0 and P1 MUST be done before students are invited.** The rest can
be done incrementally after, since the token system already provides
a basic gate and the existing anti-cheat verification (audio proof,
quiz verification) is already functional if imperfect.

## What this design deliberately does NOT do

- **Does not implement DRM** (requires paid services, disproportionate
  for 16 students, technically futile on the web anyway).
- **Does not build a login/password system** (the token-based approach
  is adequate for this scale — tokens are already cryptographically
  secure, 22 chars, URL-safe, one per student).
- **Does not prevent all possible cheating** — accepts that a
  determined student with technical skills will always find edge
  cases. The goal is making casual abuse (sharing a link, spamming
  !done, downloading all content) require real effort rather than
  being trivially easy.
- **Does not store passwords or sensitive auth credentials** — stays
  consistent with the project's existing "tokens, not passwords"
  approach.
