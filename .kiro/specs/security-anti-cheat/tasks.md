
# Tasks — Hissar: System Security, Anti-Cheat & Copyright Protection

> **How to use this file:** work top to bottom, phase by phase.
> P0 and P1 MUST be done before students are invited. The rest can
> follow incrementally. Check off tasks in the same commit that
> completes them.

---

## Phase P0 — Immediate zero-risk hardening (do FIRST, before any students) [NEED]

- [ ] **P0.1** Add `robots.txt` to `empire-dojo/site/` root:
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
- [ ] **P0.2** Add `<meta name="robots" content="noindex, nofollow">`
  to every practice page template (accent.html, vocab.html,
  listening.html, shadowing.html across all levels/weeks/days) —
  this is in the `scripts/generate.py` page generator, not individual
  files. One line in the template = 1,330+ pages protected.
- [ ] **P0.3** Add copyright footer to every practice page (same
  approach — one line in the generator template):
  ```html
  <div style="text-align:center;padding:20px 0;color:var(--text-muted);font-size:0.7rem">
    © 2026 Empire English Community. All rights reserved.
    هذا المحتوى ملكية خاصة ومحمي بحقوق الطبع والنشر.
  </div>
  ```
- [ ] **P0.4** Add HTML watermark comment to generated pages (in the
  generator template, top of `<body>`):
  ```html
  <!-- Empire English Community | Proprietary Content | Unauthorized reproduction prohibited -->
  ```
- [ ] **P0.5** Regenerate all practice pages (`python scripts/generate.py`)
  and deploy to Cloudflare Pages. Verify: `robots.txt` accessible,
  meta tags present, copyright visible, watermark in source.

## Phase P1 — Legal protection (before students arrive) [NEED]

- [ ] **P1.1** Write Terms of Service in Arabic (MSA, bidi-safe per
  Sahin's standing rule). Content must cover:
  - Content ownership (all materials are proprietary)
  - Prohibition on redistribution/copying/sharing
  - Account sharing prohibition (one person per account)
  - Acceptable use (learning only, no commercial reuse)
  - Consequences of violation (suspension without refund)
  - Data collection disclosure (what the bot tracks)
- [ ] **P1.2** Enable Discord's built-in **Rules Screening** on the
  server — members must click "I agree" before accessing any channel.
  The screening message should reference the ToS.
- [ ] **P1.3** Pin the full ToS in `#rules` (alongside the existing
  community rules that are already there).
- [ ] **P1.4** Add a one-line ToS acceptance reminder in the bot's
  `on_member_join` welcome DM flow (Bawaba): "By using this server,
  you agree to our Terms of Service in #rules."

## Phase P2 — API hardening [NEED]

- [ ] **P2.1** Restrict CORS: change `_cors_headers()` in
  `api_server.py` to only return `Access-Control-Allow-Origin` for
  allowed origins (`practice.empireenglish.online` and the
  `.pages.dev` preview URL). Return no CORS header for unknown
  origins.
- [ ] **P2.2** Tighten rate limit from 60/min to 20/min per token.
  (Verify this doesn't break the dashboard's own normal usage pattern
  first — the dashboard makes ~5-8 requests on load.)
- [ ] **P2.3** Review every API endpoint's response payload: confirm
  no endpoint leaks other students' private data. Document findings.
- [ ] **P2.4** Remove `recording_url` from the `voice_portfolio`
  field in `/api/dashboard`'s response (or gate it — currently
  exposes direct audio URLs that could be scraped).

## Phase P3 — Content gating on practice pages [NEED]

- [ ] **P3.1** Modify the practice page template (in `generate.py`)
  to wrap all curriculum content in a `<div id="gated-content"
  style="display:none">` — content is present in HTML but invisible
  until JS validates the token.
- [ ] **P3.2** Add a token validation check on page load: if no token
  in localStorage → show a "Connect your account" prompt (same style
  as `/dash/`'s existing connect flow) instead of the content.
- [ ] **P3.3** New API endpoint `GET /api/validate-token?token=xxx`
  → returns `{"valid": true/false}`. Lightweight, no student data
  exposed, just a gate check.
- [ ] **P3.4** On successful validation, show the `#gated-content`
  div. On failure (invalid/expired token), show the connect prompt.
- [ ] **P3.5** Regenerate all pages, deploy, verify: an anonymous
  visitor sees the connect prompt, a valid-token visitor sees
  content.

## Phase P4 — Anti-cheat hardening [NEED]

- [ ] **P4.1** Increase `COOLDOWN_SECONDS` from 60 to 180 (3 minutes).
  Gate behind a flag (`hissar_strict_cooldown`, default ON) so it can
  be reverted instantly if students complain it's too restrictive.
- [ ] **P4.2** Persist cooldown state in the database: add
  `last_done_at TEXT DEFAULT NULL` to the `members` table. On every
  `!done`, write the timestamp. On every `!done` check, read from DB
  instead of the in-memory dict. This survives bot restarts.
- [ ] **P4.3** Progressive quiz delay: after a wrong answer, impose
  30-second retry delay. After 3 consecutive wrong answers for the
  same task type in one day, impose a 5-minute lockout. Tracked in a
  new `quiz_attempts` table or in-memory with DB persistence.
- [ ] **P4.4** Register new flags in `flag_registry.py`:
  `hissar_strict_cooldown` (default ON), `hissar_quiz_lockout`
  (default ON).

## Phase P5 — Token sharing detection [NEED]

- [ ] **P5.1** New `token_access_log` table (schema in design.md).
  Log IP + User-Agent on every API request that includes a valid
  token.
- [ ] **P5.2** Daily scheduled analysis task: for each token active
  in the last 24h, count distinct IPs. Flag tokens with 3+ distinct
  IPs. Alert via Markaz ops bot for 5+ distinct IPs.
- [ ] **P5.3** New admin command `!revoke @user`: deletes the user's
  link token, forces re-link. Logs the revocation.
- [ ] **P5.4** Auto-revoke + DM on high-confidence sharing detection
  (5+ IPs): revoke token, DM student in Arabic: "تم إعادة تعيين
  رابط الوصول الخاص بك لأسباب أمنية. اكتب `!link` للحصول على رابط
  جديد."

## Phase P6 — Monitoring & alerting [WANT]

- [ ] **P6.1** Integrate suspicious-token alerts into the existing
  Markaz daily digest (morning Telegram report already exists — just
  add a "Security" section if any flags were tripped).
- [ ] **P6.2** Weekly security summary in the Sunday Markaz report:
  tokens flagged, rate limits hit, quiz lockouts triggered.
- [ ] **P6.3** `!security` admin command: quick status showing active
  tokens, any flagged ones, last 24h distinct IPs per token.

---

## Cross-session bookkeeping

- [ ] Update `empire-chronicle/STATUS.md` when phases complete.
- [ ] If students are invited before all phases are done, record
  exactly which phases were complete at that point (same discipline
  as Aegis and Sahin).
