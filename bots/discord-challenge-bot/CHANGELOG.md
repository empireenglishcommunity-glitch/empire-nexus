# Changelog

All notable changes to the **Empire Challenge Bot** are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-06-22

### Added
- **12 Discord commands:** `!join`, `!done`, `!today`, `!me`, `!top`, `!cert`, `!recap`, `!guide`, `!version`, `!status`, `!setday`, `!announce`, `!reset`
- **Daily auto-post scheduler** with configurable hour and timezone
- **Progress tracking** with SQLite (streaks, completion count, duplicate protection)
- **4-tier rank system** (بدأ الرحلة → مثابر → محارب → بطل المرونة) with auto-role assignment
- **AI motivation** via Groq free API (llama-3.3-70b-versatile) with Arabic fallback pool
- **PDF certificates** with Cairo Arabic font, gold-on-black design, RTL support
- **Leaderboard** with medal emojis and configurable limit
- **Weekly recap** generation (AI or templated fallback)
- **`!version` command** showing bot version, Python version, discord.py version
- **Global error handler** with friendly Arabic messages for all command errors
- **Settings persistence** in SQLite (`settings` table) — survives Docker restarts
- **Backup utility** (`scripts/backup.py`) with 14-day rotation
- **30 curated challenges** across 4 domains (ذهني/جسدي/لغوي/اجتماعي), 4 difficulty levels
- **Content package:** TikTok captions (AR + EN), poster text, launch scripts, promo scripts
- **Docker deployment** with proper volume separation (DB + output)
- **GitHub Actions CI** — automated tests on push/PR
- **Full test suite** — 49 tests covering all modules

### Fixed
- Docker volume mount: separated DB and output volumes (was mounting entire `/app`)
- `!setday` persistence: now stores in database instead of `.env` file
- Dockerfile HEALTHCHECK pointing to correct persistent DB path

### Security
- `.env` excluded from git and Docker builds
- Admin commands require `manage_guild` or `administrator` permission
- `!reset` requires reaction confirmation within 30 seconds
- No secrets in source code — all via environment variables

---

## [Unreleased]

_Future improvements will be tracked here before tagging the next release._
