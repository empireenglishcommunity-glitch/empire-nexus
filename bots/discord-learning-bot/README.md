# Empire English Learning Bot

> The Learning Operating System for Empire English Community — a Discord bot that delivers daily tasks, tracks progress, evaluates submissions, and guides learners from L0 to L3.

## Features

- **7 daily tasks** delivered at 6 AM (accent, vocab, shadowing, speaking, listening, writing, community)
- **AI-powered feedback** on writing submissions (Gemini + Groq fallback)
- **Streak tracking** with gamification (points, leaderboards, bonuses)
- **Weekly assessments** with scored dimensions
- **Level progression** (L0 → L1 → L2 → L3) with advancement exams — submissions persist to the database and admins are notified via DM to resolve with `!examresult`
- **Automatic server setup** (roles, channels, permissions via setup script)
- **Arabic-first** instruction with bilingual support
- **Full 38-week curriculum** across all 4 levels (vocabulary, speaking, writing, accent drills, grammar cards) — see `data/README.md` for the exact word/lesson counts per level

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

**Admin:** `!status` `!setlevel @user L#` `!announce <msg>` `!members` `!examqueue` `!examresult <id> pass|fail`

## Architecture

```
src/
├── bot.py          ← Discord bot (commands, events, scheduled tasks)
├── config.py       ← All settings from .env
├── database.py     ← SQLite persistence (members, streaks, assessments, advancement exams)
├── curriculum.py   ← Loads + serves per-level vocabulary/accent/grammar content (see data/README.md)
├── tasks.py        ← Task generation, formatting, delivery
├── verification.py ← Anti-cheat: proof-of-work gates, cooldowns, vocab/listening quizzes
├── features.py     ← Buddy system, surveys, reports, exam DM collection, at-risk outreach
└── ai_engine.py    ← Gemini/Groq API calls, evaluation, generation

content/            ← AI prompt library (25 prompts) + per-level accent/grammar drill content
                      (content/{l0,l1,l2,l3}/{accent,grammar}/weekN_*.json)
data/               ← Per-level vocabulary/speaking/writing content, ALL 4 levels, 38 weeks total
                      (see data/README.md for exact counts and the content pipeline explained)
scripts/            ← setup_server.py (auto-configures Discord server)
```

> **Content status:** all 4 levels (L0-L3, 38 weeks) have real, verified curriculum content as of 2026-07-11. See `data/README.md` for the full breakdown and history of what was previously missing/templated.

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
