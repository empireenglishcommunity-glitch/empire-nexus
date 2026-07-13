# 🤖 Empire Challenge Bot

A **100% free**, working Discord bot that runs the *30-day "Be Comfortable with
Being Uncomfortable"* challenge automatically — daily posts, progress tracking,
streaks, AI motivation, ranks, a leaderboard, and PDF certificates.

> دليل عربي مختصر في نهاية الملف 👇

---

## ✨ What it does (already built & tested)

| Feature | How |
|--------|-----|
| 📅 Auto-posts the daily challenge | Scheduled every day at the hour you choose |
| ✅ Tracks each person's progress & streaks | Free local SQLite database |
| 🧠 AI motivation in Arabic | Free Groq API (with built-in fallback if no key) |
| 🏅 Auto-assigns ranks | 🥉 بدأ الرحلة → 🥈 مثابر → 🥇 محارب → 👑 بطل المرونة |
| 🏆 Leaderboard | `!top` |
| 📜 PDF certificates | `!cert` generates a styled certificate |

### Commands
- `!join <your goal>` — register & set your goal
- `!today` — show today's challenge
- `!done <day> <feeling 1-10>` — log a completed challenge
- `!me` — your progress, streak & rank
- `!top` — leaderboard
- `!cert` — your PDF certificate
- `!recap <week>` — AI weekly summary (mods only)
- `!guide` — list all commands
- `!version` — bot version, Python/discord.py version info

**Admin/mod only:** `!status` (bot + challenge status summary), `!setday <1-30>`
(override the current challenge day), `!announce <message>` (post to the
challenge channel), `!reset` (⚠️ destructive — wipes all participant data,
requires reaction confirmation)

---

## 🛠️ Tech stack (everything free, no credit card)
- [discord.py](https://discordpy.readthedocs.io/) — the bot
- SQLite — built into Python, no server needed
- [Groq](https://console.groq.com) free API — the AI motivation
- [reportlab](https://www.reportlab.com/) — PDF certificates

---

## 🚦 SETUP — the parts only YOU can do

I built and tested all the code. These 4 steps need your own accounts/keys
(I cannot create them for you). Each takes ~2 minutes.

### ① Create the Discord bot & get its token
1. Go to <https://discord.com/developers/applications> → **New Application** → name it `Empire Challenge`.
2. Left menu → **Bot** → **Add Bot** → **Reset Token** → copy the token.
3. On the same Bot page, turn ON these toggles:
   - **MESSAGE CONTENT INTENT**
   - **SERVER MEMBERS INTENT**
4. Left menu → **OAuth2 → URL Generator**:
   - Scopes: `bot`
   - Bot Permissions: `Send Messages`, `Manage Roles`, `Attach Files`, `Read Message History`, `Mention Everyone`
   - Copy the generated URL, open it, and invite the bot to your server.

### ② Get the channel ID for daily posts
1. In Discord: **User Settings → Advanced → Developer Mode = ON**.
2. Right-click your `#تحدي-اليوم` channel → **Copy Channel ID**.

### ③ Get a free AI key (optional but recommended)
1. Go to <https://console.groq.com> → sign in (free, no card).
2. **API Keys → Create API Key** → copy it.
> If you skip this, the bot still works using built-in Arabic motivation messages.

### ④ Put your keys in the `.env` file
1. Copy `.env.example` to `.env`.
2. Paste your token, channel ID, Groq key, and set the post hour/timezone.

---

## 🧪 Running the tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

49 tests covering the challenge data, database, config, AI coach fallback,
and certificate generation. CI runs this automatically on every push/PR
that touches this bot (see `.github/workflows/challenge-bot-test.yml`).

## ▶️ Run it (free options)

### Option A — On your own computer (simplest, free)
```bash
cd empire-challenge-bot
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```
Keep the terminal open and the bot stays online.

### Option B — Free 24/7 hosting
Run the same commands on a free host so it stays online without your PC:
- **Railway**, **Render** (free web service / background worker), or
- An always-free VM (e.g. Oracle Cloud Free Tier).

Set the same `.env` values as environment variables on the host.

---

## ✅ What I already tested for you
- All 30 challenges load correctly
- Progress tracking, duplicate protection, and streak counting
- Rank thresholds (1 / 15 / 22 / 30)
- AI fallback messages (works with no API key)
- PDF certificate generation
- All modules compile without errors

The only thing I could **not** run is the live Discord connection — that needs
your bot token (step ①). Once you add it and run `python run.py`, it's live.

---

## 📌 TikTok note
TikTok does not offer a free, friendly automation API for posting to Live, so
that part stays manual: announce the daily challenge in your Live and point fans
to the Discord, where this bot handles everything automatically.

---

## 🇸🇦 دليل سريع بالعربية

هذا بوت ديسكورد مجاني 100% يدير تحدّي الـ 30 يومًا تلقائيًا: ينشر تحدّي اليوم،
يتابع تقدّم كل مشارك، يعطي تحفيزًا بالذكاء الاصطناعي، يوزّع الرتب، ويصدر شهادات PDF.

**الخطوات التي عليك أنت فعلها (لا أستطيع إنشاء حساباتك):**
1. أنشئ بوت من <https://discord.com/developers/applications> وانسخ التوكن، وفعّل
   خياري *Message Content* و *Server Members*.
2. فعّل *Developer Mode* في ديسكورد وانسخ معرّف قناة التحدّي.
3. (اختياري) احصل على مفتاح مجاني من <https://console.groq.com> للذكاء الاصطناعي.
4. انسخ ملف `.env.example` إلى `.env` واملأ القيم.

**التشغيل:**
```bash
pip install -r requirements.txt
python run.py
```

إن واجهتك أي مشكلة، أخبرني بالرسالة التي ظهرت وسأحلّها معك خطوة بخطوة. 💪
