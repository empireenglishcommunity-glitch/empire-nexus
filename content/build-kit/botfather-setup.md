# Build Kit — Accounts, BotFather & Cal.com Setup (the hands-on steps)

These are the steps that require **your** logins/secrets — they can't be done from the repo. Each is short and copy-paste. Do §1 first (accounts), then §2 (bot), then §3 (Cal.com), then return to `make-scenarios.md`.

---

## 1. Accounts to create (free)

| Account | How | Note |
|---|---|---|
| **Telegram bot** | In Telegram, chat **@BotFather** → `/newbot` | Save the **token** somewhere private (password manager) |
| **Google account** | A dedicated one (e.g., `ops.empireenglish@…`) | Owns the `Empire CRM` Sheet + backups |
| **Make.com** | makecom signup, free tier | Connect Telegram + Google Sheets here |
| **Cal.com** | cal.com signup, free tier | Booking |
| **MailerLite or Brevo** | signup, free tier | Account only in Phase 0 (drips are Phase 2) |

> **Token safety:** the bot token goes **only** into the Make.com Telegram connection. Never paste it into the Sheet, this repo, or chat.

---

## 2. BotFather — create & configure the bot

### 2.1 Create
1. Open **@BotFather** → `/newbot`.
2. Name: `Empire English` · Username: something ending in `bot` (e.g., `EmpireEnglishBot`).
3. Copy the **token**.

### 2.2 Set the commands (`/setcommands`)
Send `/setcommands`, pick the bot, paste:
```
start - ابدأ / Start
menu - القائمة / Menu
help - مساعدة / Help
language - تغيير اللغة / Switch language
stop - إيقاف الرسائل / Stop messages
```

### 2.3 Set the description & about (optional, recommended)
- `/setdescription` → short Arabic-led line, e.g.:
  `بوت Empire English: حدّد مستواك، احصل على هدية مجانية، واحجز مكالمة. / Find your level, get a free gift, book a call.`
- `/setabouttext` → one line summary.

### 2.4 Menu button (optional)
`/setmenubutton` → set to open the main menu command, or leave default (the 5 inline buttons appear from A1).

### 2.5 Deep link (for channel CTAs)
Your channel posts link to the bot with a tracked start param:
```
https://t.me/<YourBotUsername>?start=ch_<campaign>
```
- The `start=` payload arrives in the `/start` update → store as `source` in A1.
- Example: `?start=ch_welcome`, `?start=ch_quizpost`.

### 2.6 Link the discussion group (engagement, spec/blueprint)
1. Create a Telegram **group**, link it to your **channel** (Channel → Manage → Discussion).
2. Put the group invite link into the Sheet `Config` → `GROUP_INVITE`.

---

## 3. Cal.com — booking event

1. Create an event type: **"Empire English — Free Level & Roadmap Call"**, 15–20 min.
2. Add buffers + a daily cap (protect focus — capacity is high, but avoid all-day fragmentation).
3. Booking questions: name, Telegram @username, goal.
4. **Tracking:** your bot's "Book a call" button opens the Cal.com link with:
   ```
   https://cal.com/<you>/level-call?src=bot&tid=<telegram_id>
   ```
   The bot fills `<telegram_id>` at click time. A5 reads `tid` from the webhook to match the CRM row.
5. **Webhook:** Cal.com → Settings → Webhooks → add the **A5 custom webhook URL** (from Make.com). Trigger on *Booking Created*.
6. Confirmation + reminder emails: enable Cal.com's built-ins (cuts no-shows).
7. Paste the booking link into Sheet `Config` → `CALL_URL`.

---

## 4. Config values to fill (Sheet `Config` tab)

After the above, fill these rows in the `Config` tab:

| key | paste |
|---|---|
| `CALL_URL` | your Cal.com link incl. `?src=bot&tid=` |
| `DISCORD_INVITE` | your Discord invite |
| `GROUP_INVITE` | your Telegram discussion-group link |
| `RESOURCE_LINK` | the "3 American Sounds" file URL (or leave blank → bot serves text + "audio coming soon") |
| `FOUNDER_ALERT_CHAT_ID` | your personal Telegram chat id (message the bot, read it from the update) |

Leave the `SCORE_*`, `LEVEL_BAND_*`, threshold rows at their defaults unless you want to tune.

---

## 5. Order of operations recap
1. Accounts (§1) → 2. Bot + token + commands + deep link + group (§2) → 3. Cal.com event + webhook (§3) → 4. Import the 4 CSVs into `Empire CRM` → 5. Build A1–A9 (`make-scenarios.md`) → 6. Fill Config (§4) → 7. Run acceptance tests T1–T10 (`README.md`).

> When T1–T10 all pass, **Gate 0→1 opens** and Phase 1 (content rhythm + weekly report) can begin.
