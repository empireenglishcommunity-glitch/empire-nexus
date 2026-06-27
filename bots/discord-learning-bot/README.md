# Empire English Learning Bot

> The Learning Operating System for Empire English Community — a Discord bot that delivers daily tasks, tracks progress, evaluates submissions, and guides learners from L0 to L3.

## Features

- **7 daily tasks** delivered at 6 AM (accent, vocab, shadowing, speaking, listening, writing, community)
- **AI-powered feedback** on writing submissions (Gemini + Groq fallback)
- **Streak tracking** with gamification (points, leaderboards, bonuses)
- **Weekly assessments** with scored dimensions
- **Level progression** (L0 → L1 → L2 → L3) with advancement exams
- **Automatic server setup** (roles, channels, permissions via setup script)
- **Arabic-first** instruction with bilingual support

## Quick Start

```bash
# 1. Configure
cp .env.example .env
nano .env  # Fill in DISCORD_TOKEN, GUILD_ID, GEMINI_API_KEY

# 2. Run with Docker (recommended)
docker compose up -d

# 3. Verify
docker compose logs -f
```

## Commands

| Command | Description |
|---------|-------------|
| `!join <goal>` | Register and set your learning goal |
| `!done <task>` | Mark a task as completed |
| `!progress` | View your progress dashboard |
| `!streak` | View your streak info |
| `!level` | Level info and advancement requirements |
| `!week` | This week's curriculum focus |
| `!top` | Points leaderboard |
| `!streaks` | Streak leaderboard |
| `!help` | Show all commands |

**Admin:** `!status` `!setlevel @user L#` `!announce <msg>` `!members`

## Architecture

```
src/
├── bot.py        ← Discord bot (commands, events, scheduled tasks)
├── config.py     ← All settings from .env
├── database.py   ← SQLite persistence (members, streaks, assessments)
├── tasks.py      ← Task generation, formatting, delivery
└── ai_engine.py  ← Gemini/Groq API calls, evaluation, generation

content/          ← AI prompt library (25 prompts) + curriculum data
data/             ← L0 weeks 1-8 (vocabulary, speaking, writing)
scripts/          ← setup_server.py (auto-configures Discord server)
```

## Deployment

Deployed on Hetzner VPS at `/opt/empire-english-bot/`:

```bash
ssh root@77.42.43.250
cd /opt/empire-english-bot
git pull && docker compose up -d --build
```

## Requirements

- Python 3.12+
- discord.py >= 2.3
- At least one AI key (Gemini recommended, Groq as fallback)
- Discord bot token with MESSAGE_CONTENT and MEMBERS intents

## Monthly Cost: $0

Runs on existing Hetzner server. AI via Gemini/Groq free tiers.
