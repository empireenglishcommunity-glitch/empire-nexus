"""Markaz (مركز) Phase M3 — Quick-action Telegram commands.

Owner-facing commands that can be sent directly to @empire_ops_eec_bot
without needing Discord open. Dispatched from ops_poller._handle_update()
when a message begins with '/' and isn't a reply to another message.

All handlers receive (args: str, bot) and return a response string
(already MarkdownV2-formatted) to send back to the owner. Handlers
must never raise — they catch their own errors and return a friendly
error message instead.
"""
import datetime
import logging
from typing import Optional

import discord

from . import config, database, ops_hub, maintenance, changelog

logger = logging.getLogger("empire-bot.ops_commands")


# ============================================================
#  COMMAND REGISTRY
# ============================================================

COMMANDS: dict[str, callable] = {}


def command(name: str):
    """Decorator to register a Telegram command handler."""
    def decorator(func):
        COMMANDS[name] = func
        return func
    return decorator


async def dispatch(text: str, bot) -> Optional[str]:
    """Parse a /command from the message text and dispatch to the right
    handler. Returns the response message (MarkdownV2-formatted) to send
    back, or None if the text isn't a recognized command.

    Called from ops_poller._handle_update() for standalone (non-reply)
    messages that start with '/'.
    """
    if not text.startswith("/"):
        return None

    parts = text.split(None, 1)
    cmd_name = parts[0].lower().split("@")[0]  # strip @botname suffix
    args = parts[1] if len(parts) > 1 else ""

    handler = COMMANDS.get(cmd_name)
    if not handler:
        available = ", ".join(sorted(COMMANDS.keys()))
        return f"❓ Unknown command: `{ops_hub.escape_markdown(cmd_name)}`\n\nAvailable: {ops_hub.escape_markdown(available)}"

    try:
        return await handler(args, bot)
    except Exception as e:
        logger.error(f"ops_commands: error in {cmd_name}: {e}")
        return f"❌ Error running `{ops_hub.escape_markdown(cmd_name)}`: {ops_hub.escape_markdown(str(e)[:200])}"


# ============================================================
#  /status — bot uptime, API health, active student count
# ============================================================

@command("/status")
async def handle_status(args: str, bot) -> str:
    """System health snapshot."""
    member_count = database.member_count()
    today_subs = database.total_submissions_today()

    # Level breakdown
    levels = {}
    for lvl in ["L0", "L1", "L2", "L3"]:
        levels[lvl] = len(database.members_at_level(lvl))

    # Uptime from heartbeat
    last_hb = database.get_setting("last_heartbeat", "")
    hb_status = "✅" if last_hb else "⚠️ no heartbeat"

    # AI providers
    groq = "✅" if config.GROQ_API_KEY else "❌"
    gemini = "✅" if config.GEMINI_API_KEY else "❌"

    # Bot connection
    bot_ok = "✅" if bot.is_ready() else "❌"

    lines = [
        "*🤖 Empire English Bot — Status*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"*Version:* `{ops_hub.escape_markdown(config.BOT_VERSION)}`",
        f"*Discord:* {bot_ok} \\| Guilds: {len(bot.guilds)}",
        f"*Heartbeat:* {hb_status}",
        f"*AI:* Groq {groq} \\| Gemini {gemini}",
        "",
        f"*👥 Students:* {member_count} registered",
        f"  🌱 L0: {levels['L0']} \\| 💪 L1: {levels['L1']} \\| 🚀 L2: {levels['L2']} \\| 👑 L3: {levels['L3']}",
        f"*✅ Today:* {today_subs} submissions",
    ]
    return "\n".join(lines)


# ============================================================
#  /students — list active students with level + streak
# ============================================================

@command("/students")
async def handle_students(args: str, bot) -> str:
    """List active students. Paginated — send '/students 2' for page 2."""
    PAGE_SIZE = 10
    try:
        page = max(1, int(args.strip())) if args.strip() else 1
    except ValueError:
        page = 1

    members = database.all_active_members()
    total = len(members)

    if total == 0:
        return "👥 No active students registered yet\\."

    # Sort by streak descending for a useful default view
    for m in members:
        streak_data = database.get_streak(m["discord_id"])
        m["_streak"] = streak_data[0] if streak_data else 0
    members.sort(key=lambda m: m["_streak"], reverse=True)

    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(page, total_pages)
    start = (page - 1) * PAGE_SIZE
    page_members = members[start:start + PAGE_SIZE]

    lines = [
        f"*👥 Active Students* \\(page {page}/{total_pages}, {total} total\\)",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for i, m in enumerate(page_members, start=start + 1):
        name = (m.get("discord_name") or "Unknown").split("#")[0]
        safe_name = ops_hub.escape_markdown(name)
        level = m.get("level", "?")
        streak = m["_streak"]
        lines.append(f"{i}\\. *{safe_name}* — {level}, 🔥{streak}d")

    if total_pages > 1:
        lines.append("")
        lines.append(f"📄 Page {page}/{total_pages} — send `/students {page + 1}` for next")

    return "\n".join(lines)


# ============================================================
#  /flag — toggle feature flags from Telegram
# ============================================================

@command("/flag")
async def handle_flag(args: str, bot) -> str:
    """Toggle or list feature flags.

    /flag           — list all flags with current state
    /flag <name> on  — enable a flag
    /flag <name> off — disable a flag
    """
    args = args.strip()

    if not args:
        # List all flags
        flags = database.list_feature_flags()
        if not flags:
            return "🚩 No feature flags configured\\."
        lines = ["*🚩 Feature Flags*", "━━━━━━━━━━━━━━━━━━━━", ""]
        for f in flags:
            state = "🟢" if f["enabled"] else "🔴"
            safe_name = ops_hub.escape_markdown(f["name"])
            lines.append(f"  {state} `{safe_name}`")
        lines.append("")
        lines.append("Toggle: `/flag <name> on` or `/flag <name> off`")
        return "\n".join(lines)

    parts = args.split()
    flag_name = parts[0]

    if len(parts) < 2:
        # Just show this flag's state
        enabled = database.is_feature_enabled(flag_name)
        state = "🟢 ON" if enabled else "🔴 OFF"
        return f"🚩 `{ops_hub.escape_markdown(flag_name)}` is currently *{state}*"

    action = parts[1].lower()
    if action in ("on", "enable", "1", "true"):
        database.set_feature_flag(flag_name, enabled=True, updated_by="telegram_ops")
        return f"🟢 `{ops_hub.escape_markdown(flag_name)}` is now *ON*"
    elif action in ("off", "disable", "0", "false"):
        database.set_feature_flag(flag_name, enabled=False, updated_by="telegram_ops")
        return f"🔴 `{ops_hub.escape_markdown(flag_name)}` is now *OFF*"
    else:
        return f"❓ Unknown action `{ops_hub.escape_markdown(action)}`\\. Use `on` or `off`\\."


# ============================================================
#  /nutq — pronunciation feature controls (WHO + HOW MANY)
# ============================================================

NUTQ_FLAG = "tatawwur_pronunciation"


def _nutq_resolve(q: str) -> list:
    """Resolve a student query (discord_id or a name substring) to a list of
    (discord_id, name) matches. A digit query is taken as an id verbatim."""
    q = (q or "").strip()
    if not q:
        return []
    if q.isdigit():
        row = database.get_member(q)
        return [(q, (row.get("discord_name") if row else q) or q)]
    ql = q.casefold()
    return [(str(m["discord_id"]), m.get("discord_name") or "?")
            for m in database.all_active_members()
            if ql in (m.get("discord_name") or "").casefold()]


def _nutq_name(discord_id: str) -> str:
    row = database.get_member(discord_id)
    return (row.get("discord_name") if row else discord_id) or discord_id


@command("/nutq")
async def handle_nutq(args: str, bot) -> str:
    """Control the pronunciation ('Grade my best read') feature.

    /nutq                         — who has it + daily-grade caps
    /nutq grant <name|id>         — give it to a student
    /nutq revoke <name|id>        — take it away from a student
    /nutq everyone                — turn it on for ALL students
    /nutq off                     — turn it off for everyone
    /nutq cap <name|id> <n>       — set that student's grades/day
    /nutq cap <name|id> default   — revert to the global default
    """
    em = ops_hub.escape_markdown
    parts = (args or "").strip().split()
    sub = parts[0].lower() if parts else "status"

    # ── status (default) ────────────────────────────────────────────────
    if sub in ("", "status", "who", "list"):
        st = database.feature_flag_status(NUTQ_FLAG)
        default_cap = config.NUTQ_AZURE_MAX_CALLS_PER_DAY
        lines = ["*🗣️ Nutq — pronunciation feature*", "━━━━━━━━━━━━━━━━━━━━", ""]
        if not st["enabled"]:
            lines.append("Status: 🔴 *OFF* for everyone")
        elif st["everyone"]:
            lines.append("Status: 🟢 *ON for EVERYONE*")
        else:
            lines.append(f"Status: 🟢 ON for *{len(st['allowed_ids'])}* student\\(s\\):")
            for did in sorted(st["allowed_ids"]):
                cap = database.nutq_daily_cap_override(did)
                cap_txt = f"{cap}/day" if cap is not None else f"{default_cap}/day \\(default\\)"
                lines.append(f"  • {em(_nutq_name(did))} — {em(cap_txt)}")
        lines.append("")
        lines.append(f"Default cap: *{default_cap}* grade\\(s\\)/day")
        lines.append("")
        lines.append("`/nutq grant <name>` · `/nutq revoke <name>`")
        lines.append("`/nutq everyone` · `/nutq off`")
        lines.append("`/nutq cap <name> <n>` · `/nutq cap <name> default`")
        return "\n".join(lines)

    # ── everyone / off ──────────────────────────────────────────────────
    if sub in ("everyone", "all"):
        database.set_feature_flag(NUTQ_FLAG, enabled=True, allowed_ids="", updated_by="telegram_ops")
        return "🟢 Pronunciation feature is now *ON for everyone*\\."
    if sub in ("off", "disable", "nobody"):
        database.set_feature_flag(NUTQ_FLAG, enabled=False, updated_by="telegram_ops")
        return "🔴 Pronunciation feature is now *OFF* for everyone\\."

    # ── grant / revoke ──────────────────────────────────────────────────
    if sub in ("grant", "add", "on", "revoke", "deny", "remove"):
        if len(parts) < 2:
            return "Usage: `/nutq grant <name or id>` \\(or `revoke`\\)\\."
        matches = _nutq_resolve(" ".join(parts[1:]))
        if not matches:
            return "❓ No student matched\\. Try their exact name or discord id\\."
        if len(matches) > 1:
            names = ", ".join(em(n) for _, n in matches[:8])
            return f"⚠️ That matched *{len(matches)}* students \\({names}\\)\\. Be more specific or use the id\\."
        did, name = matches[0]
        if sub in ("grant", "add", "on"):
            r = database.feature_flag_grant(NUTQ_FLAG, did, updated_by="telegram_ops")
            if r == "everyone":
                return f"ℹ️ It's already ON for everyone, so *{em(name)}* already has it\\."
            if r == "already":
                return f"✅ *{em(name)}* already has it\\."
            return f"🟢 Granted the pronunciation feature to *{em(name)}*\\."
        else:
            r = database.feature_flag_revoke(NUTQ_FLAG, did, updated_by="telegram_ops")
            if r == "everyone":
                return ("⚠️ It's ON for *everyone* right now, so I can't remove just one\\. "
                        "Use `/nutq off`, or grant specific students to switch to an allowlist\\.")
            if r == "not_present":
                return f"ℹ️ *{em(name)}* wasn't on the list\\."
            if r == "revoked_now_off":
                return f"🔴 Removed *{em(name)}* — they were the last one, so the feature is now *OFF*\\."
            return f"🟠 Removed *{em(name)}* from the pronunciation feature\\."

    # ── cap ─────────────────────────────────────────────────────────────
    if sub in ("cap", "limit"):
        if len(parts) < 3:
            return "Usage: `/nutq cap <name or id> <number>` \\(or `default`\\)\\."
        value = parts[-1].lower()
        matches = _nutq_resolve(" ".join(parts[1:-1]))
        if not matches:
            return "❓ No student matched\\. Try their exact name or discord id\\."
        if len(matches) > 1:
            names = ", ".join(em(n) for _, n in matches[:8])
            return f"⚠️ That matched *{len(matches)}* students \\({names}\\)\\. Be more specific or use the id\\."
        did, name = matches[0]
        if value in ("default", "reset", "clear"):
            database.clear_nutq_daily_cap_override(did)
            return (f"✅ *{em(name)}* now uses the default "
                    f"*{config.NUTQ_AZURE_MAX_CALLS_PER_DAY}*/day\\.")
        if not value.isdigit():
            return "❓ Give a number \\(e\\.g\\. `3`\\) or `default`\\."
        n = int(value)
        if n > 20:
            return "⚠️ That's a lot — cap it at 20/day to protect the free tier\\."
        database.set_nutq_daily_cap_override(did, n)
        return f"✅ *{em(name)}* can now earn *{n}* official grade\\(s\\)/day\\."

    return ("❓ Unknown `/nutq` action\\. Try: `status`, `grant`, `revoke`, "
            "`everyone`, `off`, `cap`\\.")


# ============================================================
#  /announce — post to Discord #announcements
# ============================================================

@command("/announce")
async def handle_announce(args: str, bot) -> str:
    """Post an announcement to Discord #announcements channel."""
    if not args.strip():
        return "Usage: `/announce Your message here`"

    message = args.strip()
    if len(message) > 1950:
        return f"❌ Too long \\({len(message)} chars\\)\\. Keep under 1950\\."

    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return "❌ Discord guild not found\\."

    channel = discord.utils.get(guild.text_channels, name="announcements")
    if not channel:
        return "❌ `#announcements` channel not found\\."

    try:
        await channel.send(f"📢 **Announcement**\n\n{message}")
        return f"✅ Posted to \\#announcements \\({len(message)} chars\\)"
    except Exception as e:
        logger.error(f"ops_commands /announce: {e}")
        return f"❌ Failed to post: {ops_hub.escape_markdown(str(e)[:150])}"


# ============================================================
#  /approve, /deny — owner gate for student-initiated resets
# ============================================================

@command("/approve")
async def handle_approve(args: str, bot) -> str:
    """Approve a student's pending history-reset request (performs the reset)."""
    try:
        rid = int(args.strip())
    except (ValueError, TypeError):
        return ops_hub.escape_markdown("Usage: /approve <request number>")
    res = database.approve_pending_reset(rid, decided_by="telegram-ops")
    if res is None:
        return ops_hub.escape_markdown(f"No pending reset request #{rid}.")
    if res.get("error"):
        return ops_hub.escape_markdown(f"Request #{rid} is already {res['status']} — no action taken.")
    try:
        user = bot.get_user(int(res["discord_id"]))
        if user is None:
            user = await bot.fetch_user(int(res["discord_id"]))
        if user:
            await user.send(
                f"🧾 Your history reset was approved and completed (record #{res['consent_id']}). "
                f"Fresh start — good luck! 🌱"
            )
    except Exception:
        pass
    return ops_hub.escape_markdown(
        f"✅ Approved reset #{rid} for {res['discord_name']} (record #{res['consent_id']}). "
        f"Undo in Discord: !restore-student {res['consent_id']}"
    )


@command("/deny")
async def handle_deny(args: str, bot) -> str:
    """Deny a student's pending history-reset request (nothing is deleted)."""
    try:
        rid = int(args.strip())
    except (ValueError, TypeError):
        return ops_hub.escape_markdown("Usage: /deny <request number>")
    res = database.deny_pending_reset(rid, decided_by="telegram-ops")
    if res is None:
        return ops_hub.escape_markdown(f"No pending reset request #{rid}.")
    if res.get("error"):
        return ops_hub.escape_markdown(f"Request #{rid} is already {res['status']} — no action taken.")
    try:
        user = bot.get_user(int(res["discord_id"]))
        if user is None:
            user = await bot.fetch_user(int(res["discord_id"]))
        if user:
            await user.send(
                "Your history reset request was not approved this time. If you still want it, "
                "please contact the team."
            )
    except Exception:
        pass
    return ops_hub.escape_markdown(f"🚫 Denied reset #{rid} for {res['discord_name']}. Nothing was deleted.")


# ============================================================
#  /help — list available commands
# ============================================================
#  /maintenance — toggle maintenance mode (student-facing)
# ============================================================

@command("/maintenance")
async def handle_maintenance(args: str, bot) -> str:
    """Toggle maintenance mode + auto-announce to students.

    /maintenance                     — show status
    /maintenance status              — show status
    /maintenance start [soft|hard] [minutes] [reason...]
    /maintenance end [what's new...]
    """
    esc = ops_hub.escape_markdown
    parts = args.split()
    sub = parts[0].lower() if parts else "status"

    if sub == "status":
        s = maintenance.get_status()
        if s.get("state") != "maintenance":
            return "🟢 System is *LIVE* — no maintenance active\\."
        return (
            f"🔧 Maintenance: *{esc(s.get('level', 'soft').upper())}*\n"
            f"Reason: {esc(s.get('reason') or '—')}\n"
            f"ETA: {esc(s.get('eta') or '—')}\n"
            f"Since: {esc((s.get('started_at') or '')[:16])}"
        )

    if sub == "start":
        rest = parts[1:]
        level = "soft"
        if rest and rest[0].lower() in ("soft", "hard"):
            level = rest[0].lower()
            rest = rest[1:]
        eta = ""
        window = maintenance.DEFAULT_WINDOW_MINUTES
        if rest and rest[0].isdigit():
            mins = int(rest[0])
            rest = rest[1:]
            eta = f"~{mins} min"
            window = max(mins + 15, 15)
        reason = " ".join(rest).strip()
        maintenance.start(level=level, reason=reason, eta=eta, window_minutes=window)
        result = await maintenance.broadcast_start(bot, maintenance.get_status())
        surface = "overlay" if level == "hard" else "banner"
        d_ok = "✅" if result.get("discord") else "❌"
        return (
            f"🔧 Maintenance *STARTED* \\({esc(level)}\\)\\.\n"
            f"Students now see the {surface}\\.\n"
            f"Announced → Discord {d_ok} · Telegram groups: {result.get('telegram_groups', 0)}\n"
            f"Auto\\-resumes in {window} min if you forget `/maintenance end`\\."
        )

    if sub == "end":
        note = " ".join(parts[1:]).strip()
        if note:
            changelog.add_entry(note)   # publish to "What's New"
        maintenance.end()
        result = await maintenance.broadcast_end(bot, note)
        d_ok = "✅" if result.get("discord") else "❌"
        return (
            f"✅ Maintenance *ENDED* — system is LIVE\\.\n"
            f"Announced → Discord {d_ok} · Telegram groups: {result.get('telegram_groups', 0)}"
        )

    return ("❓ Use `/maintenance status`, "
            "`/maintenance start [soft|hard] [min] [reason]`, "
            "or `/maintenance end [what's new]`")


# ============================================================
#  /changelog — publish / list "What's New" entries
# ============================================================

@command("/changelog")
async def handle_changelog(args: str, bot) -> str:
    """Publish or list student-facing 'What's New' entries.

    /changelog                 — list the latest entries
    /changelog add <text>      — publish a new entry (shows on the page +
                                 guide; also broadcast the next time you end
                                 maintenance with a note)
    """
    esc = ops_hub.escape_markdown
    parts = args.split(maxsplit=1)
    sub = parts[0].lower() if parts else "list"

    if sub == "add":
        text = parts[1].strip() if len(parts) > 1 else ""
        if not text:
            return "Usage: `/changelog add <what changed>`"
        entry = changelog.add_entry(text)
        if not entry:
            return "❌ Could not save the entry\\."
        return f"✨ Published to *What's New*:\n{esc(text)}"

    entries = changelog.get_entries(limit=5)
    if not entries:
        return "📝 No changelog entries yet\\. Add one: `/changelog add <text>`"
    lines = ["📝 *Latest 'What's New' entries*", "━━━━━━━━━━━━━━━━━━━━"]
    for e in entries:
        lines.append(f"• {esc(e.get('date', ''))}: {esc(e.get('text', ''))}")
    return "\n".join(lines)


# ============================================================
#  /itqan — weekly-assessment owner report
# ============================================================

@command("/itqan")
async def handle_itqan(args: str, bot) -> str:
    """Weekly-assessment report: per-student result, flagged queue, most-missed.

    Usage: /itqan [L0|L1|L2|L3]
    """
    from . import assessment
    lvl = args.strip().upper() or None
    if lvl and lvl not in ("L0", "L1", "L2", "L3"):
        return "Usage: `/itqan [L0|L1|L2|L3]`"
    data = database.itqan_report_data(lvl)
    text = assessment.format_itqan_report(data).replace("`", "'")
    # A MarkdownV2 fenced code block renders monospace and needs no inner
    # escaping (we've already stripped backticks).
    return f"```\n{text}\n```"


# ============================================================
#  /itqan-review — full breakdown of one flagged attempt
# ============================================================

@command("/itqan-review")
async def handle_itqan_review(args: str, bot) -> str:
    """Full owner-review breakdown of one attempt. Usage: /itqan-review <attempt id>.
    (Audio recordings are attached in Discord via !itqan-review.)"""
    from . import assessment
    try:
        aid = int(args.strip())
    except (ValueError, TypeError):
        return "Usage: `/itqan\\-review <attempt id>`"
    att = database.itqan_get_attempt(aid)
    if not att:
        return f"No attempt \\#{aid}\\."
    items = database.itqan_get_items(aid)
    recs = database.itqan_get_recordings(aid)
    member = database.get_member(att["discord_id"]) or {}
    name = (member.get("discord_name") or str(att["discord_id"])).split("#")[0]
    text = assessment.format_attempt_review(
        att, items, name=name, rec_item_nos=[r["item_no"] for r in recs]).replace("`", "'")
    note = f"\n\n🎧 {len(recs)} recording(s) — listen in Discord: !itqan-review {aid}" if recs else ""
    return f"```\n{text}{note}\n```"


# ============================================================
#  /itqan-due — full status: who has a due assessment
# ============================================================

@command("/itqan-due")
async def handle_itqan_due(args: str, bot) -> str:
    """Full weekly-assessment status for all students. Usage: /itqan-due [L0-L3]."""
    from . import assessment
    lvl = args.strip().upper() or None
    if lvl and lvl not in ("L0", "L1", "L2", "L3"):
        return "Usage: `/itqan\\-due [L0|L1|L2|L3]`"
    data = database.itqan_status_report(lvl)
    text = assessment.format_itqan_due(data).replace("`", "'")
    return f"```\n{text}\n```"


# ============================================================
#  /majlis — Community Lounge status + config (Phase 7)
# ============================================================

@command("/majlis")
async def handle_majlis(args: str, bot) -> str:
    """Community Lounge (Majlis) status and configuration.

    /majlis          — current flag states + config
    /majlis config   — full config table
    """
    from . import community

    # Flag states
    flags = [
        "community_together_credit",
        "community_lounge_beacon",
        "community_dynamic_rooms",
        "community_pings_optin",
        "community_power_hour",
        "community_together_reward",
    ]
    flag_lines = []
    for f in flags:
        st = database.feature_flag_status(f)
        icon = "✅" if st["enabled"] else "❌"
        scope = "everyone" if st["everyone"] else (f"{len(st['allowed_ids'])} students" if st["allowed_ids"] else "off")
        flag_lines.append(f"  {icon} {f}: {scope}")

    # Config
    cfg = community.get_config()

    lines = [
        "*🏛️ Majlis — Community Lounge*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "*Flags:*",
        *flag_lines,
        "",
        "*Config:*",
        f"  together\\_minutes: {cfg.get('community_together_minutes', 5)}",
        f"  lounge\\_capacity: {cfg.get('community_lounge_capacity', 6)}",
        f"  beacon\\_max\\_occ: {cfg.get('community_beacon_max_occupancy', 4)}",
        f"  beacon\\_cooldown: {cfg.get('community_beacon_cooldown_min', 40)} min",
        f"  beacon\\_ttl: {cfg.get('community_beacon_ttl_min', 20)} min",
        f"  reap\\_grace: {cfg.get('community_reap_grace_min', 3)} min",
        f"  hour\\_start: {cfg.get('community_hour_start', '21:00')} ({cfg.get('community_hour_tz', 'Africa/Cairo')})",
        f"  hour\\_minutes: {cfg.get('community_hour_minutes', 60)}",
        f"  reward\\_points: {cfg.get('community_together_reward_points', 0)}",
        "",
        "_Use `/flag <name> on` to enable flags._",
        "_Config: `!flag` in Discord admin channel._",
    ]
    return "\n".join(lines)


# ============================================================
#  /monthly — Monthly Review cohort report (Taqdeem Phase 3)
# ============================================================

@command("/monthly")
async def handle_monthly(args: str, bot) -> str:
    """Monthly Review status for all students. Usage: /monthly [L0-L3]."""
    from . import monthly_outcomes
    lvl = args.strip().upper() or None
    if lvl and lvl not in ("L0", "L1", "L2", "L3"):
        return "Usage: `/monthly [L0|L1|L2|L3]`"
    text = monthly_outcomes.format_monthly_report(lvl)
    return f"```\n{text}\n```"


# ============================================================

@command("/help")
async def handle_help(args: str, bot) -> str:
    """List all available commands."""
    lines = [
        "*📡 Empire Ops — Commands*",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        "`/status` — Bot health, students, AI status",
        "`/students` — Active students with level \\+ streak",
        "`/flag` — List/toggle feature flags",
        "`/flag <name> on/off` — Toggle a specific flag",
        "`/announce <msg>` — Post to \\#announcements",
        "`/maintenance` — Status / `start [soft|hard] [min] [reason]` / `end`",
        "`/changelog` — List / `add <text>` publish a 'What's New' entry",
        "`/itqan` — Weekly assessment report \\[L0\\-L3\\]",
        "`/itqan-review <id>` — Full breakdown of a flagged attempt",
        "`/itqan-due` — Who has a due weekly assessment",
        "`/majlis` — Community lounge status \\+ config",
        "`/monthly` — Monthly review status for all students",
        "`/check` — Detailed status for one student",
        "`/help` — This message",
    ]
    return "\n".join(lines)



# ============================================================
#  /check — full student status report (Rawiya R5)
# ============================================================

@command("/check")
async def handle_check(args: str, bot) -> str:
    """Get a detailed status report for a specific student.

    Usage: /check [name or partial name]
    """
    if not args.strip():
        return "Usage: `/check [student name]`"

    name = args.strip().lower()
    members = database.all_active_members()
    member = None
    for m in members:
        display_name = (m.get("discord_name", "") or "").split("#")[0].lower()
        if name in display_name:
            member = m
            break

    if not member:
        return f"❌ Student '{ops_hub.escape_markdown(args.strip())}' not found\\."

    discord_id = member["discord_id"]
    level = member.get("level", "A1")
    streak, longest = database.get_streak(discord_id)
    points = member.get("total_points", 0)
    week = database.member_week_number(discord_id)
    tasks_today = len(database.tasks_completed_today(discord_id))
    safe_name = ops_hub.escape_markdown((member.get("discord_name", "?").split("#")[0]))

    # Days since active — via the shared helper, which compares in UTC. Doing
    # it here against a naive datetime.now() was off by the host's UTC offset,
    # and .days truncation turned that into a whole extra day, so this owner
    # report could show "1d inactive" for a student who worked last evening.
    days_inactive = database.days_since_active(
        {"last_active_at": member.get("last_active_at", "")})

    # (Nour retired 2026-09-03: the Journey status line was removed here.)

    # Pronunciation
    pron_avg = database.get_pronunciation_average(discord_id)

    return (
        f"👤 *{safe_name}*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 Level: {level} \\| Week: {week}\n"
        f"🔥 Streak: {streak} days \\(best: {longest}\\)\n"
        f"💎 Points: {points:,}\n"
        f"✅ Today: {tasks_today}/7 tasks\n"
        f"⏱ Last active: {days_inactive} day\\(s\\) ago\n"
        f"🎙 Pronunciation avg: {pron_avg:.0f}%"
    )


# ============================================================
#  /nudge — send personalized Nour check-in (Rawiya R5)
# ============================================================

@command("/nudge")
async def handle_nudge(args: str, bot) -> str:
    """Send a personalized Nour check-in DM to a student.

    Usage: /nudge [name or partial name]
    """
    if not args.strip():
        return "Usage: `/nudge [student name]`"

    name = args.strip().lower()
    members = database.all_active_members()
    member = None
    for m in members:
        display_name = (m.get("discord_name", "") or "").split("#")[0].lower()
        if name in display_name:
            member = m
            break

    if not member:
        return f"❌ Student '{ops_hub.escape_markdown(args.strip())}' not found\\."

    discord_id = member["discord_id"]
    guild = bot.get_guild(config.GUILD_ID)
    if not guild:
        return "❌ Discord guild not found\\."

    discord_member = guild.get_member(int(discord_id))
    if not discord_member:
        return "❌ Member not in server\\."

    safe_name = (member.get("discord_name", "").split("#")[0]) or "there"
    try:
        await discord_member.send(
            f"👋 مرحبًا {safe_name}!\n\n"
            f"كل شيء على ما يرام؟ لاحظت أنك لم تكن نشطًا مؤخرًا.\n"
            f"إذا احتجت أي مساعدة أو لديك سؤال، أنا هنا دائمًا 😊\n\n"
            f"💡 تذكّر: مهمة واحدة يوميًا تكفي للحفاظ على السلسلة!"
        )
        return f"✅ Nudge sent to *{ops_hub.escape_markdown(safe_name)}*\\."
    except Exception as e:
        return f"❌ Could not DM {ops_hub.escape_markdown(safe_name)}: {ops_hub.escape_markdown(str(e)[:100])}"
