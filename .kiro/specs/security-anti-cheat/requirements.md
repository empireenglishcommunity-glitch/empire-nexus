
# Requirements — System Security, Anti-Cheat & Copyright Protection ("Hissar")

> **Codename: Hissar** (حصار — siege/fortification). Internal name for
> this initiative, used throughout this spec and future commit
> messages/PRs for easy cross-referencing. Directory name
> (`security-anti-cheat`) stays literal/technical.

## Origin

The owner is about to invite 16 real, paying students (9 free + 7
paid) into the system. Once real money and real intellectual property
are involved, the threat model changes completely from "test
accounts only." The owner explicitly asked (paraphrased, confirmed
directly): "I want to secure my system from stealers and proof it
from cheaters — full security and copyrights. Think about every
possible scenario a student could manipulate the system."

## Real findings surfaced during context-gathering

These are concrete, code-verified vulnerabilities (not theoretical):

1. **The entire practice platform (1,330+ HTML pages + 266 Kokoro TTS
   audio files) is publicly accessible with ZERO authentication.**
   Anyone with the URL (`practice.empireenglish.online`) can download
   ALL curriculum content, ALL audio, every vocab list, every grammar
   pattern — no login, no token, no gating whatsoever. A competitor
   could `wget --recursive` the entire site in minutes.

2. **Token sharing is completely undetectable.** One student runs
   `!link`, gets a token, gives it to 5 friends who never paid — they
   ALL access the full dashboard, SRS system, progress data, growth
   letters. No IP logging, no device fingerprinting, no concurrent-
   session detection exists anywhere.

3. **No copyright notices on any content.** Practice pages have no
   visible ©, no "proprietary content" warning, no metadata. Audio
   files have no DRM. Nothing legal protects the curriculum.

4. **CORS is `Access-Control-Allow-Origin: *`** — any website anywhere
   can call the API. A third party could build their own frontend
   using the bot's own API endpoints for free.

5. **No `robots.txt` or `noindex` meta tags.** Search engines can
   index and publicly cache all curriculum content, making it findable
   and copyable by literally anyone searching for it.

6. **No Terms of Service exist.** If a student copies or
   redistributes content, there is zero legal standing to enforce
   anything because they never agreed to any terms.

7. **The `!done` cooldown is only 60 seconds** (code says
   `COOLDOWN_SECONDS = 60`), not 5 minutes as the help text implies —
   a student can spam 7 `!done` commands in 7 minutes with minimal
   real effort between them.

8. **All anti-cheat state is in-memory** (`_last_done_time`,
   `_voice_sessions`, `_pending_quizzes`) — a bot restart (which
   happens on every deploy) silently resets ALL cooldowns, all voice
   tracking, all pending quizzes. A student who knows deploys happen
   can exploit this timing window.

9. **The API exposes full student data via a URL query parameter**
   (`?token=xxx`) — tokens are trivially shareable (paste a URL), and
   anyone with a valid token sees another student's full progress,
   pronunciation scores, SRS state, and leaderboard position.

## Constraints

1. **$0 marginal cost.** No new paid services. Everything must work
   within existing infrastructure (self-hosted bot, Cloudflare Pages
   free tier, free AI APIs).
2. **No breaking existing functionality.** Every countermeasure must
   be additive or behind a feature flag — never regress something
   that already works for real students.
3. **Proportional response.** 16 students, not 16,000 — heavyweight
   solutions (OAuth providers, CDN-level DRM, hardware tokens) are
   disproportionate to the threat level. Prefer simple, effective
   mechanisms over complex ones.
4. **Arabic-first UX.** Any new student-facing message (error,
   warning, ToS) must be bilingual per existing project convention.
5. **Solo operator.** Solutions must not require ongoing manual toil
   to maintain (e.g. "manually check IP logs daily" is weak;
   "auto-alert on suspicious patterns" is strong).

## Requirements

### R1 — Content must not be freely downloadable by non-members
**User story:** As the owner of proprietary curriculum content, I want
only paying/registered community members to access the practice
platform's learning materials, so that non-paying people cannot
simply download or copy what I built.

**Acceptance criteria:**
1. WHEN an unauthenticated visitor accesses any practice page beyond
   the landing page THEN the system SHALL require a valid link token
   before rendering curriculum content (vocab, grammar, audio, drills).
2. WHEN a search engine crawls the practice platform THEN it SHALL
   NOT be able to index or cache curriculum content pages (only the
   public landing page should be indexable).
3. WHEN audio files (TTS clips) are requested THEN they SHALL NOT be
   directly accessible via a predictable URL pattern without a valid
   session/token.

### R2 — Token sharing must be detectable and limitable
**User story:** As the operator, I want to know if one student's token
is being used by multiple people, so I can take action before
non-paying users consume resources meant for paying members.

**Acceptance criteria:**
1. WHEN a token is used from a new IP address or device fingerprint
   THEN the system SHALL log this event for later review.
2. WHEN a token shows usage patterns consistent with sharing (e.g.
   simultaneous requests from different locations, or usage during a
   student's known quiet hours from a different timezone) THEN the
   system SHALL flag it for admin attention.
3. WHEN the operator wants to revoke a compromised token THEN a
   simple command (`!revoke @user`) SHALL invalidate it immediately,
   forcing the student to re-link.

### R3 — Anti-cheat must be hardened against known bypass patterns
**User story:** As the operator of a paid system where progress =
value, I want the streak/points/verification system to be resistant
to gaming, so that achievements genuinely reflect real effort.

**Acceptance criteria:**
1. WHEN a `!done` command is issued THEN the cooldown between tasks
   SHALL be meaningful enough to prevent rapid-fire farming (minimum
   3-5 minutes, not the current 60 seconds).
2. WHEN the bot restarts (deploy) THEN anti-cheat state (cooldowns,
   pending quizzes, voice session tracking) SHALL survive the restart,
   not silently reset to zero.
3. WHEN a student repeatedly fails vocab/listening quizzes and
   retries immediately THEN the system SHALL apply progressive delay
   (not allow instant retry after a wrong answer — prevents
   brute-force guessing).

### R4 — Legal protection must exist before students are invited
**User story:** As the business owner, I want enforceable legal terms
in place so that if a student copies, redistributes, or resells my
content, I have standing to take action.

**Acceptance criteria:**
1. WHEN a student joins the Discord server THEN they SHALL be
   required to accept Terms of Service (via Discord's built-in Rules
   Screening) that explicitly cover: content ownership, prohibition
   on redistribution, account sharing prohibition, and consequences
   of violation.
2. WHEN a student accesses the practice platform THEN a visible
   copyright notice SHALL be present on every page.
3. WHEN curriculum content is served THEN it SHALL contain embedded
   attribution that survives copy-paste (e.g. a watermark comment in
   the HTML, or a visible footer).

### R5 — API must not be usable by unauthorized third parties
**User story:** As the operator, I want my API to serve only my own
practice platform, not be a free backend for anyone who discovers
the endpoints.

**Acceptance criteria:**
1. WHEN an API request arrives THEN the system SHALL check the
   `Origin`/`Referer` header and reject requests from unauthorized
   domains (not `Access-Control-Allow-Origin: *` for everything).
2. WHEN an abnormal volume of requests arrives from a single token
   THEN the rate limit SHALL be strict enough to prevent bulk data
   extraction (current 60/min is too generous for 16 students).
3. WHEN the API returns student data THEN it SHALL NOT include data
   belonging to other students (confirmed: leaderboard already only
   shows names+points, not private data — verify this holds for all
   endpoints).

### R6 — This plan must survive the session
**User story:** Standard — same as every prior spec.

**Acceptance criteria:**
1. Committed to `empire-nexus` at `.kiro/specs/security-anti-cheat/`.
2. `empire-chronicle/STATUS.md` updated with a pointer.
3. Tasks checked off in the same commit that completes them.

## Explicitly out of scope

- **Full OAuth/SSO login system** (disproportionate for 16 students;
  the token-based approach is adequate if hardened — revisit at 100+
  students).
- **DRM on audio files** (technically infeasible on the web without a
  paid DRM service; watermarking is the practical alternative).
- **Encrypting curriculum JSON data at rest** (the threat is network-
  level access, not server compromise — if someone has SSH, game over
  regardless).
- **Anti-screen-recording** (technically impossible on any platform;
  focus on making bulk automated scraping hard, accept that a
  determined individual can always manually screenshot one page at a
  time — that's not a scalable threat).
- **Payment gateway integration** (separate business concern, not a
  security fix).
