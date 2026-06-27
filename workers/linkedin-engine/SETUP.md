# 🤖 LinkedIn Content Engine — Setup Guide

[![smoke test](https://github.com/empireenglishcommunity-glitch/EEC-REPO/actions/workflows/linkedin-engine-smoke-test.yml/badge.svg)](https://github.com/empireenglishcommunity-glitch/EEC-REPO/actions/workflows/linkedin-engine-smoke-test.yml)

Generates a daily, **brand-voice** LinkedIn post (hook + body + hashtags) with Gemini's
free tier and sends it to you on **Telegram** with buttons:

> **[✅ Approve & Save] [🔄 Regenerate] [🔁 Other hook] [✏️ Tweak] [🖼️ New image] [🎠 Carousel] [⏭️ Skip]**

Nothing is auto-published. You tap once (~60 seconds), copy the approved block, and paste
it into LinkedIn's free native scheduler. That human touch is exactly what the 2026
algorithm rewards — and it keeps you 100% inside LinkedIn's Terms.

**Cost: $0.** Cloudflare Workers (free) + Gemini free tier + Telegram (free).

---

## What you need (all free, ~10 minutes)

1. **Telegram bot token** — message **@BotFather** → `/newbot` → copy the token.
2. **Your Telegram chat id** — message **@userinfobot** → copy the number. Then press **Start** on your new bot so it can message you.
3. **Gemini API key** — https://aistudio.google.com/apikey (no credit card).
4. *(Optional)* **Groq API key** — https://console.groq.com (free secondary fallback).

---

## Option A — Dashboard (no CLI, matches the sales-bot workflow) ✅ easiest

1. Go to **dash.cloudflare.com → Workers & Pages → Create → Worker** → name it `linkedin-engine` → **Deploy**.
2. **Edit code** → delete the default → paste the entire contents of **`worker.js`**.
3. **Settings → Variables and Secrets** → add these (type *Secret* for the keys):
   | Name | Value |
   |---|---|
   | `TELEGRAM_TOKEN` | token from BotFather |
   | `ADMIN_CHAT_ID` | your id from @userinfobot |
   | `GEMINI_API_KEY` | key from AI Studio |
   | `GROQ_API_KEY` | *(optional)* |
   > Don't want to use variables? You can instead paste the values into the `*_FALLBACK`
   > constants at the top of `worker.js`. Variables are safer.
4. **Settings → Bindings** →
   - **Add → KV namespace** → create one (e.g. `linkedin-kv`) → set **Variable name = `KV`** exactly.
   - **Add → AI** (Workers AI) → set **Variable name = `AI`** (this powers image generation, Phase 2). Optional but recommended.
   - **Deploy**.
5. **Connect Telegram** — open this URL in your browser (swap in your token + worker URL):
   ```
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=<YOUR_WORKER_URL>&drop_pending_updates=true
   ```
   You should get `{"ok":true,...}`.
6. **Daily auto-post** — **Settings → Triggers → Cron Triggers → Add** → `0 5 * * *`
   (05:00 UTC = 07:00 Cairo / 09:00 Dubai). Adjust to your preferred morning time.

## Option B — CLI (wrangler)

```bash
cd linkedin-engine
npx wrangler kv namespace create KV     # paste the returned id into wrangler.toml
npx wrangler secret put TELEGRAM_TOKEN
npx wrangler secret put ADMIN_CHAT_ID
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put GROQ_API_KEY    # optional
npx wrangler deploy
# then set the Telegram webhook (step 5 above) to your deployed URL
```

---

## Try it

- Message your bot **`/new`** → within a few seconds you get a full draft with buttons.
- Tap **🔁 Other hook** to cycle hook variants, **✏️ Tweak** → reply with a note like
  *"shorter"* / *"more sarcasm"* / *"add a real stat"* to rewrite it, **🔄 Regenerate**
  for a brand-new angle, **✅ Approve & Save** to store it and get a clean copy block.
- Every morning the cron sends one automatically.

**Admin commands:** `/new` · `/queue` · `/export` · `/clearqueue` · `/stats` · `/pillars` · `/version`

---

## The phases (what each button/feature does)

**Phase 1 — Text + cockpit** (works out of the box)
Daily draft to Telegram. Buttons: Approve / Regenerate / Other hook / Tweak / Skip.

**Phase 2 — Images** (needs the `AI` binding)
Each draft auto-generates an on-brand image (matte black + gold) via Cloudflare Workers AI
(Flux). Tap **🖼️ New image** to regenerate. Edit `BRAND_IMAGE_STYLE` in `worker.js` to change
the look; set `AUTO_IMAGE = false` to only generate on demand and save quota.

**Phase 3 — Carousels** (needs the Apps Script web app)
Tap **🎠 Carousel** → the engine writes 6 slides, builds a branded Google Slides deck, exports
a PDF, and sends you the link. Upload that PDF to LinkedIn as a **document** post.
Setup: open `carousel.gs`, follow its header steps (paste into script.google.com, add a `TOKEN`
script property, deploy as a Web app), then set `CAROUSEL_WEBAPP_URL` + `CAROUSEL_TOKEN` on the
Worker (same token string on both sides).

**Phase 4 — Publishing**
- Default: **Approve** gives you a clean copy block to paste into LinkedIn's free native scheduler.
- Batch: **/export** dumps every approved post as separate messages for fast weekly scheduling.
- Optional: set `PUBLISH_WEBHOOK_URL` and each approved post is also POSTed there (wire it to
  Buffer / Make / Zapier / your own endpoint).

**Phase 5 — Reliability + self-tuning** (automatic)
- Fallback chain: Gemini → Groq → built-in evergreen bank (never an empty day).
- Topic rotation self-tunes from your own **approve/skip** behaviour (see `/stats`).
- Every approved post comes with **3 first-comment ideas** (post one to boost reach).
- **Idea inbox:** just text the bot any raw idea — it becomes your next draft.

---

## 🔑 Make it sound like YOU (most important step)

The voice is **already encoded from your MACAL Empire Brand Bible** ("Common Sense First" —
authoritative, sarcastic-but-never-cruel, paternal; hook → analogy → punchy close). The full
reference lives in `brand/macal-brand-bible.md`. Open `worker.js` to fine-tune:

- **`BRAND_VOICE`** — the persona summary (already set to the MACAL voice).
- **`BEST_POSTS`** — currently holds 3 example posts written *in your voice* from the bible's
  templates. Swap these for your **real top-performing posts** when you have them — that's the
  single biggest quality lever.
- **`SARCASM_MAX_LEVEL` / `SARCASM_PROBABILITY`** — your sarcasm dial (set high: ~half of posts).
- **`PROMO_EVERY_N_POSTS` / `PROMO_BRANDS`** — soft mentions of Macal Empire / Empire English Community.
- **`BRAND_IMAGE_STYLE` / `BRAND_HANDLE`** — matte black + gold empire look; carousel footer.
- **`LANGUAGE`** — `"en"`, `"ar"`, or `"mix"`.
- **`PILLARS` / `FORMATS` / `HASHTAG_BANK`** — your topics, post styles, and hashtags.

Redeploy after editing (dashboard: **Deploy**; CLI: `npx wrangler deploy`).

---

## How reliability works

`Gemini` → if it fails/rate-limits → `Groq` (if configured) → built-in **EVERGREEN** bank.
You will **never** get an empty day. Topic rotation also avoids repeating the last few pillars.

---

## ملخّص سريع بالعربي

- البوت بيكتبلك بوست LinkedIn يومي بصوتك ويبعتهولك على تيليجرام بأزرار:
  **موافقة / إعادة توليد / هوك تاني / تعديل / تخطّي**. مفيش نشر تلقائي — إنت اللي بتوافق.
- مجاني ١٠٠٪ (Cloudflare + Gemini + Telegram).
- التركيب زي بوت المبيعات بالظبط: انسخ `worker.js` في Cloudflare، حط الأسرار، اعمل KV باسم `KV`،
  فعّل الـ webhook، وحط Cron يومي.
- **أهم خطوة:** افتح `worker.js` وحط ٦–١٠ من أحسن بوستاتك في `BEST_POSTS` عشان يطلع بصوتك إنت.
- جرّب: ابعت `/new` للبوت.
