# 🚀 Deployment Guide — Empire Challenge Bot

> How to deploy the bot so it runs 24/7 for free (or near-free).
> Three options below — pick whichever matches your setup.

---

## Prerequisites (all options)

Before deploying, you need these credentials ready:

1. **Discord bot token** — from https://discord.com/developers/applications
2. **Channel ID** — the `#تحدي-اليوم` channel where daily challenges post
3. **Groq API key** (optional) — from https://console.groq.com (free, no card)

Create your `.env` file from the example:
```bash
cp .env.example .env
# Edit .env with your real values
```

---

## Option A — Docker (Recommended for VPS) 🐳

The simplest and most reliable method. Works on any Linux VPS.

### 1. Install Docker
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

### 2. Clone and configure
```bash
git clone https://github.com/empireenglishcommunity-glitch/EEC-REPO.git
cd EEC-REPO/bots/discord-challenge-bot
cp .env.example .env
nano .env   # Fill in your token, channel ID, etc.
```

### 3. Launch
```bash
docker compose up -d
```

### 4. Verify
```bash
docker compose logs -f   # Watch logs (Ctrl+C to exit)
docker compose ps        # Check status
```

### 5. Update (after pulling new code)
```bash
git pull
docker compose up -d --build
```

### 6. Stop
```bash
docker compose down
```

**Database persistence:** The SQLite database is stored in a Docker volume (`bot-data`).
It survives container restarts and rebuilds. To back it up:
```bash
docker cp empire-challenge-bot:/app/challenge.db ./backup_challenge.db
```

---

## Option B — Direct Python (Simplest, any machine) 🐍

Run directly without Docker. Good for testing or simple VPS setups.

### 1. Requirements
- Python 3.10+ (3.12 recommended)
- pip

### 2. Setup
```bash
cd empire-challenge-bot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # Fill in your values
```

### 3. Run
```bash
python run.py
```

### 4. Keep alive with systemd (Linux)
Create `/etc/systemd/system/empire-challenge-bot.service`:
```ini
[Unit]
Description=Empire Challenge Discord Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/home/youruser/EEC-REPO/bots/discord-challenge-bot
Environment=PATH=/home/youruser/EEC-REPO/bots/discord-challenge-bot/.venv/bin
ExecStart=/home/youruser/EEC-REPO/bots/discord-challenge-bot/.venv/bin/python run.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable empire-challenge-bot
sudo systemctl start empire-challenge-bot
sudo systemctl status empire-challenge-bot   # Verify
```

**View logs:**
```bash
journalctl -u empire-challenge-bot -f
```

---

## Option C — Free Cloud Hosting ☁️

### Oracle Cloud Free Tier (best free option, always-free VM)

1. Sign up at https://cloud.oracle.com (free tier, no charge)
2. Create an **Always Free** Ampere A1 instance (ARM, 1 CPU, 6 GB RAM)
3. SSH in, then follow **Option A** (Docker) or **Option B** (direct Python)

### Railway (free tier, ~500 hrs/month)

1. Go to https://railway.app → New Project → Deploy from GitHub repo
2. Set the **Root Directory** to `empire-challenge-bot`
3. Add environment variables (from your `.env`) in the Railway dashboard
4. Railway auto-detects the Dockerfile and deploys

### Render (free tier, background worker)

1. Go to https://render.com → New → Background Worker
2. Connect your GitHub repo
3. Set **Root Directory** to `empire-challenge-bot`
4. Set **Build Command:** `pip install -r requirements.txt`
5. Set **Start Command:** `python run.py`
6. Add environment variables in the dashboard

> ⚠️ Free tiers on Railway/Render may sleep after inactivity. Oracle Free Tier
> is truly always-on and recommended for production.

---

## Monitoring & Maintenance

### Check bot is alive
Send any message to the bot on Discord, or check the channel for today's post.

### Database backup (recommended: daily cron)
```bash
# Add to crontab (crontab -e):
0 3 * * * cp /path/to/challenge.db /path/to/backups/challenge_$(date +\%Y\%m\%d).db
```

Or use the included backup script:
```bash
python scripts/backup.py
```

### Update the bot
```bash
cd EEC-REPO/bots/discord-challenge-bot
git pull

# If using Docker:
docker compose up -d --build

# If using systemd:
sudo systemctl restart empire-challenge-bot
```

### Troubleshooting

| Symptom | Fix |
|---------|-----|
| Bot doesn't come online | Check `DISCORD_TOKEN` is correct; check logs |
| Daily post doesn't appear | Verify `CHALLENGE_CHANNEL_ID`; check timezone in `.env` |
| No AI motivation messages | Get a free key from console.groq.com (or leave empty for built-in messages) |
| Certificate looks wrong | Ensure `fonts/Cairo-Variable.ttf` is present |
| `ModuleNotFoundError` | Activate venv / reinstall: `pip install -r requirements.txt` |

---

## Security Notes

- **Never commit `.env`** — it's in `.gitignore`
- Store your Discord token securely (it grants full bot access)
- The SQLite database contains only Discord user IDs and usernames (no passwords/emails)
- Groq API key is free-tier; if leaked, revoke and regenerate at console.groq.com

---

## Architecture Summary

```
┌────────────────────────────┐
│  Your VPS / Cloud Host     │
│                            │
│  ┌──────────────────────┐  │
│  │  empire-challenge-bot │  │
│  │  (Python / Docker)    │  │
│  │                       │  │
│  │  discord.py ←→ Discord API  │
│  │  SQLite DB (local)    │  │
│  │  Groq AI (optional)   │  │
│  └──────────────────────┘  │
└────────────────────────────┘
        │
        ▼
┌────────────────────┐
│  Discord Server    │
│  #تحدي-اليوم      │  ← Daily auto-posts
│  (all channels)    │  ← Responds to commands
└────────────────────┘
```

> Total cost: **$0/month** (Oracle Free Tier + Groq free API + Discord free).
> No vendor lock-in. Self-hosted. You own everything.
