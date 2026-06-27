# 🤖 LinkedIn Content Automation System — Zero-Budget Brainstorm & Architecture

> Goal: automate ~95% of daily LinkedIn content (topic → idea → copy → hooks → hashtags →
> image → carousel → schedule → publish) at **100% free, zero ongoing cost**, with the
> lowest possible daily involvement — without getting your account penalized or banned.
>
> Built to reuse infrastructure you already run: **Cloudflare Workers + KV**, **Telegram bots**,
> **Google Apps Script**, **GitHub**. You're already an expert in all four.

---

## 0) The two hard truths that shape everything (June 2026)

Before any architecture, two facts kill the naive "bot that posts while I sleep" idea:

1. **No free, ToS-safe auto-publish to a *personal* LinkedIn profile exists.**
   LinkedIn's posting permission (`w_member_social`) is locked behind app review and is built
   for Company Pages, not personal profiles. The only "full autopilot" path is a browser bot
   that logs in as you — which **violates LinkedIn's Terms and risks a permanent ban** of the
   exact asset you're growing. Source: [Compliant LinkedIn API approaches, 2026](https://programminginsider.com/pulling-linkedin-profile-data-without-scraping-3-compliant-approaches/).

2. **Fully autonomous AI posting now *reduces* reach.**
   LinkedIn's **May 2026 algorithm update** rewards comments over likes and penalizes posts
   whose average dwell time falls under ~10 seconds — and raw AI posts lose on both counts.
   Source: [Forbes, Jun 17 2026](https://www.forbes.com/sites/jodiecook/2026/06/17/why-human-written-posts-are-outperforming-ai-on-linkedin/).

**Conclusion / reframe:** The win is **not** 100% autonomy. It's automating the *labor* that
drains you (ideation, drafting, hooks, hashtags, images, carousels, organizing, scheduling)
while keeping a **~60-second human checkpoint** that the algorithm actively rewards. This makes
the system free, reliable, *and* higher-performing than a hands-off firehose.

> _Content from external sources was rephrased for licensing compliance._

---

## 1) Verified free building blocks (current limits)

| Layer | Free tool | Free limit (2026) | Role in system |
|---|---|---|---|
| **Always-on brain** | Cloudflare Workers + KV + Cron | 100k req/day, KV storage, cron triggers | Orchestrator. *You already run this.* |
| **Text generation** | Google Gemini API (`2.5 Flash-Lite`) | 15 RPM / **1,000 requests/day** | Post copy, hooks, slide text |
| **Text backup** | Gemini `2.5 Flash` (250/day), Groq, Llama/Qwen free | stackable to thousands/day | Fallback chain |
| **Image generation** | **Cloudflare Workers AI** (Flux-1-schnell / SDXL) | ~10,000 neurons/day ≈ **230 images/day** | On-brand post images |
| **Carousel render** | **Google Apps Script + Google Slides → PDF** | unlimited, free | Branded multi-slide carousels |
| **Storage / CDN** | Cloudflare R2 (10GB free) or Google Drive | generous | Image + PDF hosting |
| **Content database** | Google Sheet (via Apps Script) | unlimited | Calendar + status + analytics log |
| **Delivery / control** | Telegram Bot API | free, unlimited | Your daily "cockpit" (approve/tweak) |
| **Publish (safe)** | LinkedIn **native scheduler** | free, personal profiles, 3 months ahead, desktop | Final, ToS-safe publish |
| **Publish (semi-auto)** | Buffer / Metricool / TypeGrow **free tiers** | ~10 queued posts, 1 LinkedIn channel | Optional hands-off queue |

Sources: [Gemini free-tier limits 2026](https://www.aifreeapi.com/en/posts/gemini-api-free-tier-complete-guide),
[Cloudflare Workers AI free image generation, Mar 2026](https://bagrounds.org/ai-blog/2026-03-20-cloudflare-free-image-generation),
[free LinkedIn schedulers incl. native scheduler, Jun 2026](https://postplanify.com/blog/best-linkedin-scheduler).
_All limits paraphrased for compliance; verify before relying on exact numbers._

**Key takeaways from the research:**
- **Cloudflare Workers AI is the image winner** (most generous free image quota, and you already
  have a Cloudflare account). Pollinations now requires an API key; Hugging Face's free image
  budget is tiny.
- **LinkedIn's own native scheduler is the safest free publishing endpoint** — it supports personal
  profiles and lets you queue up to 3 months ahead. The catch: desktop-only, manual paste, no API.
- **Buffer/Metricool/TypeGrow free tiers** can publish to LinkedIn via official partner access
  (lower ban risk than a browser bot), but with small queue/channel caps.

---

## 2) The content engine (the part that's 100% automatable, free)

Everything *except* the final publish can run unattended. Pipeline:

```
            ┌─────────────────────────── Cloudflare Worker (daily cron) ───────────────────────────┐
            │                                                                                       │
 [1] Topic   →  [2] Idea   →  [3] Draft copy  →  [4] 3 hooks  →  [5] hashtags  →  [6] image  →  [7] carousel (opt)
  rotation       expand        (brand voice +      pick best       (curated         (CF AI         (Apps Script
  (KV matrix)   (Gemini)       Baxter dial +                       bank + 1-2        Flux,           → Slides → PDF)
                               promo rotation)                     trending)         on-brand)
            │                                                                                       │
            └──────────────→ [8] store package in KV/Drive + log row in Google Sheet ───────────────┘
                                                  │
                                                  ▼
                            [9] deliver finished package to Telegram cockpit (evening before)
                                                  │
                          ┌────────────[✅ Approve] [✏️ Tweak] [🔄 Regenerate] [⏭️ Skip]──────────┐
                          ▼                                                                        ▼
            [10a] push to Buffer free queue                          [10b] you paste into LinkedIn native scheduler
                  (hands-off)                                              (~30–60 sec, ToS-safe, algorithm-friendly)
                                                  │
                                                  ▼
                          [11] morning of: post goes live → you spend 5 min replying to
                               first comments (this is what the 2026 algorithm rewards)
```

### Component design details

**[1] Topic rotation — a "content matrix" in KV.**
Store your pillars and rotate so the same pillar never lands two days running.
- Pillars: `investing, markets, trading, real-estate, AI, marketing, social-media, design, modeling, cooking, writing, life-coaching, entrepreneurship`.
- Formats: `contrarian-take, personal-story, how-to, listicle, case-study, question/poll, myth-bust, carousel-deep-dive`.
- Each day = `pillar × format`, chosen by weighted random while excluding the last 7 used
  (stored in KV as `recent:[]`). This guarantees variety and avoids the "AI sameness" trap.
- Weight pillars by what performs (read back from the Sheet analytics log → self-tuning).

**[2]–[3] Idea + draft (Gemini, free).**
The single biggest quality lever is the **master brand-voice system prompt**, which contains:
- Your voice rules (tone, sentence length, formatting, emoji policy).
- **5–8 few-shot examples of your *best real posts*** — this is what makes output sound like *you*, not generic AI. Pin them in the prompt.
- A **Mike-Baxter sarcasm dial (0–3)** applied *probabilistically* (e.g. only ~1 in 4 posts gets intensity 2–3) so it stays a seasoning, not a gimmick.
- A **promo rotation rule**: every Nth post (e.g. 1 in 6) softly weaves in Macal Empire / Empire English Community with a clear CTA; the rest are pure value.
- Anti-AI-detection guidance: vary openings, avoid "In today's fast-paced world…", short punchy lines, one idea per post.

**[4] Hooks.** Generate 3 variants; auto-pick the strongest or let you tap your favorite in Telegram. Hooks matter more than ever because of the 10-second dwell rule.

**[5] Hashtags.** A curated bank per pillar in KV (3–5 max) + optionally 1–2 trending. Over-hashtagging looks spammy and dilutes reach.

**[6] Images — Cloudflare Workers AI (Flux-schnell).**
Append a **fixed brand-style suffix** to every prompt so all images share your black-+-gold
"empire" identity (you already use this theme on the EEC landing pages and bot). Store in R2/Drive.

**[7] Carousels — the clever, fully-free route.**
Carousels are usually the painful part. Free pipeline:
1. Gemini writes 5–8 slides of copy (title + 1 line each).
2. **Google Apps Script fills a branded Google Slides template** with that copy.
3. Export the deck **as PDF** → LinkedIn accepts PDFs as native "document" carousels.
4. Store the PDF in Drive, send the link to Telegram.
This is 100% free, unlimited, on-brand, and reuses your Apps Script skills. (Alternative: render
HTML/CSS slides via Cloudflare Browser Rendering, but Slides→PDF is simpler and more reliable.)

**[8] Storage + [Content management].**
A **Google Sheet is your content database/calendar**: columns for `date, pillar, format, hook,
body, hashtags, image_url, carousel_url, status (draft/approved/scheduled/posted), likes,
comments`. Apps Script writes rows; you can view it on your phone. This doubles as the analytics
feedback loop that re-weights topic rotation.

**[9] Delivery — the Telegram "cockpit".**
This is literally the **approval-gate pattern you already built in `worker.js`** for the sales
bot. Each evening the Worker sends you one Telegram message: hook + body + hashtags + attached
image (+ carousel PDF link), with inline buttons `[✅ Approve & Schedule] [✏️ Tweak] [🔄 Regenerate]
[⏭️ Skip]`. Zero new skills — you've shipped this exact mechanic before.

**Reliability trick — the "evergreen buffer".**
Pre-generate **~50 evergreen posts** and store them in KV. If Gemini is down or rate-limited, or
you skip, the system serves an evergreen post instead. **You never have an empty day.** This single
mechanism is what turns a flaky free-tier stack into something dependable.

---

## 3) Candidate architectures, ranked

### 🥇 #1 — "Telegram Cockpit" (RECOMMENDED daily driver)
Worker brain generates the full package → delivers to Telegram each evening → you tap **Approve**
→ it pushes to Buffer free queue **or** you paste into LinkedIn's native scheduler.
- **Pros:** ~60 sec/day; reuses your entire existing stack; brand-voice safe; **algorithm-friendly**
  (human-touched); ToS-safe; near-zero new code (extends `worker.js`).
- **Cons:** ~1 minute of daily involvement (which is a *feature* in the post-May-2026 world).

### 🥈 #2 — "Weekly Batch + LinkedIn Native Scheduler" (most robust, ToS-perfect)
Every Sunday the Worker/Apps Script generates a **full week** of posts + images + carousels into
the Google Sheet board. You spend ~15 min once a week pasting them into LinkedIn's free native
scheduler (queues 3 months out).
- **Pros:** dead simple; 100% ToS-safe; extremely robust; batching beats daily friction.
- **Cons:** 15 min/week of manual pasting; native scheduler is desktop-only.

### 🥉 #3 — "Buffer Free Auto-Queue" (most hands-off that's still safe)
Worker generates → pushes straight to Buffer free queue via Buffer's integration; Buffer publishes
on schedule. You only intervene to skip/edit.
- **Pros:** closest to true autopilot while staying on an official partner (lower ban risk).
- **Cons:** Buffer free caps (~10 queued posts, ~1 LinkedIn channel, limited media); less control;
  occasional reconnect needed.

### #4 — "Make.com / n8n orchestration"
Use Make free (≈1,000 ops/mo) or self-hosted n8n to wire the pipeline visually.
- **Pros:** flexible, less code.
- **Cons:** free-hosting friction for always-on n8n; Make's LinkedIn module still needs LinkedIn
  API access; you already have a *better, free, always-on* brain in Cloudflare. Adds a dependency
  for little gain.

### ❌ #5 — "Full Browser-Automation Autopilot" (do NOT do this)
GitHub Actions cron → Playwright logs into LinkedIn → posts automatically.
- **Pros (on paper):** truly zero daily effort.
- **Cons (in reality):** **violates LinkedIn ToS → ban risk** on your primary brand asset; breaks on
  2FA / anti-bot checks / selector changes; requires storing your LinkedIn password in a runner;
  **and the algorithm penalizes the raw AI output anyway.** Most "automated," worst outcome.

---

## 4) Recommended implementation path

**Run #1 (Telegram Cockpit) as the daily driver, with #2 (weekly batch) as the booster.**
Approved posts go to LinkedIn's native scheduler (safest) or Buffer free (most hands-off).
This gives maximum automation of *labor*, zero budget, full ToS safety, and — because of the human
checkpoint + comment engagement — *better* reach than full autopilot.

### Phased build (each phase is independently useful)

> ✅ **Status: Phases 1–5 are built** and live in `linkedin-engine/` (single Cloudflare
> Worker `worker.js` + `carousel.gs` Apps Script). All flows are covered by a smoke test
> (`linkedin-engine/_test.mjs`). Phase 0 (your brand corpus) is the only remaining manual
> step, and the Google Sheet analytics log is optional (self-tuning currently uses your
> in-app approve/skip behaviour instead — no Sheet required).

**Phase 0 — Brand-voice corpus (you, ~1 hour, one-time).**
Collect your 8–10 best-performing posts + a written description of your voice. This is the fuel for
everything; quality of output is capped by this. *(Paste them into `BEST_POSTS` in `worker.js`.)*

**Phase 1 — Text engine ✅ built.**
Cloudflare Worker + KV: approval-weighted topic matrix + Gemini draft + 3 hooks + hashtags →
delivered to Telegram with Approve/Regenerate/Other-hook/Tweak/Skip buttons.
*(This alone removes ~70% of your daily effort.)*

**Phase 2 — Image engine ✅ built.**
Cloudflare Workers AI (Flux-schnell) with the fixed `BRAND_IMAGE_STYLE` suffix; auto-attaches an
on-brand image to each draft (toggle `AUTO_IMAGE`), plus a "🖼️ New image" button to regenerate.

**Phase 3 — Carousel engine ✅ built.**
`carousel.gs` Apps Script: branded Google Slides deck filled with Gemini slide copy → exported as
PDF → shareable link in Telegram via the "🎠 Carousel" button. Upload the PDF to LinkedIn as a
document post.

**Phase 4 — Publishing integration ✅ built.**
Approve → clean copy block for LinkedIn's native scheduler; `/export` for weekly batch scheduling;
optional `PUBLISH_WEBHOOK_URL` to push approved posts to Buffer/Make/Zapier/your endpoint.

**Phase 5 — Reliability + self-tuning ✅ built.**
Evergreen fallback bank in code; AI fallback chain (Gemini → Groq → evergreen); topic rotation
self-tunes from your approve/skip behaviour (`/stats`); comment-seeder ideas on every approval;
and an idea inbox (text the bot any thought → it becomes your next draft).

---

## 5) Risks, bottlenecks & mitigations

| Risk / bottleneck | Impact | Mitigation |
|---|---|---|
| No free personal-profile posting API | Can't fully auto-publish | Native scheduler (manual paste) or Buffer free (official partner); keep human checkpoint |
| Browser-bot posting | **Account ban** | Don't. Use approved partner / native scheduler only |
| 2026 algorithm penalizes raw AI | Reach collapse | Human 60-sec polish + reply to early comments; vary formats; few-shot brand voice; strong hooks (10-sec dwell rule) |
| Gemini free rate limits / outages | Missed day | Fallback chain + 50-post evergreen buffer in KV |
| Free-tier data used for training | Privacy | Never feed secrets/PII into prompts on free tier |
| "AI sameness" / detectable voice | Audience fatigue | Format rotation, sarcasm dial, your real-post few-shots, occasional manual seed topics |
| Buffer free caps | Limited queue | Use native scheduler for overflow; batch weekly |
| Carousel complexity | Hard to automate | Google Slides → PDF route (free, unlimited, on-brand) |
| Single point of failure (one Worker) | Whole pipeline down | Worker is stateless + KV-backed; evergreen buffer means worst case = still posts |

---

## 6) Out-of-the-box ideas worth stealing

- **Self-improving rotation:** feed last 30 days of likes/comments from the Sheet back into the
  topic weights — the system learns which pillars/formats win for *you*.
- **"Comment seeder":** have the engine also draft 3 thoughtful first-comment replies so your
  5-minute morning engagement (the algorithm's favorite signal) is half-prepared.
- **Repurpose loop:** every top post auto-spawns a carousel version 30 days later (different format,
  same idea) — infinite content from your winners.
- **Cross-brand weaving:** the promo-rotation rule can alternate Macal Empire vs. Empire English
  Community so neither feels spammy.
- **Voice drift guard:** monthly, the system samples 5 generated posts and asks Gemini to compare
  them against your few-shot corpus for tone drift — a free QA check.
- **Idea inbox via Telegram:** text the bot a raw thought any time → it parks it in KV and turns it
  into a polished post on the next slot. Captures your real insights with zero friction.

---

## 7) Bottom line

- **Don't chase 100% autonomy** — it's impossible for free *and* counterproductive on LinkedIn in 2026.
- **Do automate the 95% that drains you**, and keep a ~60-second human checkpoint that the algorithm
  rewards.
- **Reuse what you already own:** Cloudflare Worker + KV (brain), Telegram (cockpit), Apps Script +
  Slides (carousels), Google Sheet (calendar) — all free, all familiar.
- **Start with Phase 1** (text engine → Telegram). It removes most of the daily pain in one evening
  and proves the pipeline before you build images and carousels.

---

*Sources are linked inline. External content was paraphrased/summarized for licensing compliance;
verify current free-tier limits before relying on exact numbers, as providers change them often.*
