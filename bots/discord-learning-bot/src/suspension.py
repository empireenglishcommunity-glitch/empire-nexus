"""Suspension lifecycle — end-of-month access withdrawal, restore, retention.

Built for a MONTHLY cycle, not a one-off: memberships are monthly, so every
month the owner needs the same three actions with the same guardrails. Doing it
by hand is how someone eventually gets cut off who shouldn't be.

Three commands (registered in bot.py):
  !announce-renewal  -- notice to students: DMs + #announcements + Telegram
  !suspend           -- withdraw access from one, several, or all students
  !restore           -- give it back, continuing from the exact same point

WHAT "SUSPEND" ACTUALLY DOES, and why each part is needed:

  1. members.suspended_at  -> starts the 60-day retention clock. Nothing else in
     the schema records when access was withdrawn.
  2. members.status         -> drops them out of `all_active_members()`, which is
     what stops the nightly DM loops and leaderboards. NOT an access control:
     no auth path reads `status`.
  3. Darb device sessions   -> revoked, so every practice-site API call 401s.
  4. Legacy link tokens     -> deleted, killing the older `?token=` endpoints.
  5. Student gateway role   -> removed, which is what makes the Discord channels
     disappear. `role_gate.py` only ever GRANTED this role; nothing removed it
     before this module.

DELETES NOTHING. Points, streaks, submissions, mastery, assessments and the SRS
queue are all untouched (owner condition, 2026-08-30) so `!restore` genuinely
resumes rather than restarts.

STREAKS: revoking access does not break a streak on its own -- `current_streak`
is only ever written by `tasks.process_submission`, and no nightly job decays it.
But the stored value WOULD collapse on the student's first submission back,
because `_recompute_streak` walks backwards and stops at the first day with no
activity. So `restore` bridges exactly the no-access days via the existing
`maintenance_days` mechanism. Bridging only days the student provably could not
work is what keeps that global setting honest.

EDGE CAVEAT: revoking sessions blocks the API immediately, but the Cloudflare
edge gate serves static lesson pages from the signed cookie alone. The
companion change to `empire-dojo/functions/_middleware.js` adds the revocation
check that makes logout real; without it a suspended student keeps rendering
pages until their 60-day token expires.
"""
import asyncio
import datetime
import json
import logging
import os

from . import config, database

logger = logging.getLogger(__name__)

FLAG = "suspension_lifecycle"

# Where pre-purge JSON archives are written. Inside data_persist so the archive
# survives a container rebuild -- an archive on ephemeral storage would defeat
# its entire purpose.
ARCHIVE_DIR = os.path.join(os.path.dirname(str(config.DB_PATH)), "purged")

DM_THROTTLE_SECONDS = 1.5   # matches the streak_at_risk loop's pacing


# ============================================================
#  SELECTORS
# ============================================================

def resolve_selection(raw: str) -> tuple[list[dict], str]:
    """Turn a command argument into a concrete member list.

    Accepts:
      "all"        every non-suspended member
      "expired"    same as all -- named for how the owner thinks about it
      "suspended"  every currently suspended member (for !restore)
      ""           empty -> caller should show usage

    Mentions are handled by discord.py before this is called; this only covers
    the bulk selectors. Returns (members, description).
    """
    key = (raw or "").strip().lower()
    if key in ("all", "expired"):
        rows = [m for m in database.all_members() if not m.get("suspended_at")]
        return rows, f"all active members ({len(rows)})"
    if key == "suspended":
        rows = database.suspended_members()
        return rows, f"all suspended members ({len(rows)})"
    return [], ""


# ============================================================
#  SUSPEND
# ============================================================

async def suspend_one(guild, member_row: dict, dry_run: bool = False) -> dict:
    """Withdraw all access from one student. Returns a per-step result so the
    caller can report exactly what did and did not happen -- a partial failure
    (e.g. missing Manage Roles) must be visible, never silent."""
    discord_id = str(member_row["discord_id"])
    name = member_row.get("discord_name", discord_id)
    result = {"name": name, "discord_id": discord_id, "dry_run": dry_run,
              "flagged": False, "sessions": 0, "tokens": False,
              "role_removed": None, "already": False, "errors": []}

    if member_row.get("suspended_at"):
        result["already"] = True
        return result

    if dry_run:
        result["sessions"] = len(database.active_device_sessions(discord_id))
        result["tokens"] = bool(database.get_token_for_member(discord_id))
        result["role_removed"] = _has_student_role(guild, discord_id)
        return result

    # 1+2. clock + status
    result["flagged"] = database.suspend_member(discord_id)

    # 3+4. web access
    try:
        result["sessions"] = database.revoke_all_device_sessions(discord_id)
    except Exception as e:
        result["errors"].append(f"sessions: {e}")
    try:
        result["tokens"] = database.revoke_member_token(discord_id)
    except Exception as e:
        result["errors"].append(f"tokens: {e}")

    # 5. Discord visibility
    ok, err = await _remove_student_role(guild, discord_id)
    result["role_removed"] = ok
    if err:
        result["errors"].append(f"role: {err}")

    logger.info("suspension: suspended %s (%s) sessions=%s tokens=%s role=%s",
                name, discord_id, result["sessions"], result["tokens"], ok)
    return result


def _has_student_role(guild, discord_id: str):
    """True/False if we can see the member, None if they've left the server."""
    if guild is None:
        return None
    try:
        from . import role_gate
        m = guild.get_member(int(discord_id))
        if m is None:
            return None
        return role_gate.has_student_role(m)
    except Exception:
        return None


async def _remove_student_role(guild, discord_id: str) -> tuple:
    """Remove the gateway role that grants channel visibility.

    Nothing in the codebase did this before -- `role_gate.grant_student_role`
    has no counterpart -- so this is the piece that actually makes the channels
    disappear. A member who has left the server is reported as such rather than
    as a failure: two students had already left by 2026-08-30.
    """
    if guild is None:
        return False, "no guild"
    try:
        import discord as dlib
        from . import role_gate
        m = guild.get_member(int(discord_id))
        if m is None:
            return False, "not in server"
        role = dlib.utils.get(guild.roles, name=role_gate.STUDENT_ROLE_NAME)
        if role is None:
            return False, "student role not found"
        if role not in m.roles:
            return False, "did not have the role"
        await m.remove_roles(role, reason="Suspension: membership lapsed")
        return True, ""
    except Exception as e:  # includes discord.Forbidden -> missing Manage Roles
        return False, str(e)[:120]


# ============================================================
#  RESTORE
# ============================================================

async def restore_one(guild, member_row: dict, dry_run: bool = False) -> dict:
    """Give access back and bridge the gap so the streak survives."""
    discord_id = str(member_row["discord_id"])
    name = member_row.get("discord_name", discord_id)
    result = {"name": name, "discord_id": discord_id, "dry_run": dry_run,
              "was_suspended_at": member_row.get("suspended_at"),
              "cleared": False, "bridged_days": 0, "role_added": False,
              "not_suspended": False, "errors": []}

    if not member_row.get("suspended_at"):
        result["not_suspended"] = True
        return result

    if dry_run:
        gap = _gap_days(member_row["suspended_at"])
        result["bridged_days"] = len(gap)
        return result

    was = database.restore_member(discord_id)
    result["cleared"] = bool(was)

    # Bridge exactly the no-access window, nothing more. See module docstring:
    # maintenance_days is global, so only genuinely inaccessible days may go in.
    if was:
        gap = _gap_days(was)
        if gap:
            try:
                result["bridged_days"] = database.add_maintenance_days(gap)
            except Exception as e:
                result["errors"].append(f"bridge: {e}")

    ok, err = await _add_student_role(guild, discord_id)
    result["role_added"] = ok
    if err:
        result["errors"].append(f"role: {err}")

    logger.info("suspension: restored %s (%s) bridged=%s role=%s",
                name, discord_id, result["bridged_days"], ok)
    return result


def _gap_days(suspended_at: str) -> list:
    """The ISO dates from the suspension date up to YESTERDAY.

    Today is excluded on purpose: the student has access again from now on, so
    today is a day they genuinely can work. Bridging it would hand them a free
    day they did not earn.
    """
    try:
        start = datetime.date.fromisoformat(str(suspended_at)[:10])
    except (TypeError, ValueError):
        return []
    yesterday = database._today_local() - datetime.timedelta(days=1)
    if start > yesterday:
        return []
    return database.date_range_iso(start.isoformat(), yesterday.isoformat())


async def _add_student_role(guild, discord_id: str) -> tuple:
    if guild is None:
        return False, "no guild"
    try:
        from . import role_gate
        m = guild.get_member(int(discord_id))
        if m is None:
            return False, "not in server"
        await role_gate.get_or_create_student_role(guild)
        import discord as dlib
        role = dlib.utils.get(guild.roles, name=role_gate.STUDENT_ROLE_NAME)
        if role is None:
            return False, "student role not found"
        if role in m.roles:
            return True, ""
        await m.add_roles(role, reason="Restore: membership renewed")
        return True, ""
    except Exception as e:
        return False, str(e)[:120]


async def dm_restored(guild, discord_id: str, name: str) -> bool:
    """Tell a restored student they're back, and how to re-open the practice
    page (their old session was revoked, so they must re-claim a code)."""
    try:
        m = guild.get_member(int(discord_id)) if guild else None
        if m is None:
            return False
        first = (name or "").split()[0] or name
        await m.send(
            f"🏛️ **أهلاً بيك تاني {first}!**\n\n"
            "اشتراكك اتجدد، وكل حاجة رجعت زي ما كانت:\n"
            "• القنوات ظهرت تاني\n"
            "• نقاطك وأسابيعك وامتحاناتك كلها في مكانها\n"
            "• وسلسلة أيامك محفوظة — أيام التوقف مش محسوبة عليك\n\n"
            "🔑 **حاجة واحدة بس:** اكتب `!link` عشان تاخد كود جديد "
            "لمنصة التمرين (الكود القديم اتلغى).\n\n"
            "يلا نكمّل من حيث ما وقفنا. 💪"
        )
        return True
    except Exception:
        return False


# ============================================================
#  60-DAY PURGE
# ============================================================

def archive_path(discord_id: str, name: str) -> str:
    safe = "".join(ch for ch in (name or "") if ch.isalnum() or ch in "-_")[:40]
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    return os.path.join(ARCHIVE_DIR, f"{stamp}_{safe or 'student'}_{discord_id}.json")


def write_archive(member_row: dict) -> tuple:
    """Snapshot a member to JSON on disk BEFORE anything is deleted.

    This is the safeguard that makes the purge survivable. Payments happen on
    WhatsApp, entirely outside this system -- there is no payment table -- so the
    purge is driven only by a flag the owner maintains by hand. If a paying
    student was never restored, an unarchived purge would destroy their history
    with no way back. Returns (path, rows) or (None, 0) on failure.
    """
    discord_id = str(member_row["discord_id"])
    name = member_row.get("discord_name", "")
    try:
        os.makedirs(ARCHIVE_DIR, exist_ok=True)
        snap = database.member_snapshot(discord_id)
        snap["discord_name"] = name
        snap["suspended_at"] = member_row.get("suspended_at")
        path = archive_path(discord_id, name)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, ensure_ascii=False, indent=1, default=str)
        return path, snap.get("total_rows", 0)
    except Exception as e:
        logger.error("suspension: archive FAILED for %s (%s): %s", name, discord_id, e)
        return None, 0


def purge_one(member_row: dict) -> dict:
    """Archive, then permanently delete. Refuses to delete if the archive
    could not be written -- an un-archived purge is not an acceptable outcome,
    and leaving the data in place is always the safer failure."""
    discord_id = str(member_row["discord_id"])
    name = member_row.get("discord_name", discord_id)
    out = {"name": name, "discord_id": discord_id, "archived": None,
           "rows_archived": 0, "deleted": {}, "skipped": None}

    path, rows = write_archive(member_row)
    if not path:
        out["skipped"] = "archive failed — data left intact"
        logger.error("suspension: refusing to purge %s, archive failed", name)
        return out
    out["archived"] = path
    out["rows_archived"] = rows

    out["deleted"] = database.purge_member(discord_id)
    logger.warning("suspension: PURGED %s (%s) rows=%s archive=%s",
                   name, discord_id, out["deleted"].get("_total"), path)
    return out


async def run_retention_cycle(dry_run: bool = False) -> dict:
    """The scheduled half of the policy: warn at day 53, purge at day 60.

    Deliberately warns BEFORE it deletes and reports AFTER, because the system
    cannot know who renewed (see write_archive).
    """
    warn = database.members_due_for_purge_warning()
    due = database.members_due_for_purge()
    summary = {"warned": [m["discord_name"] for m in warn],
               "purged": [], "dry_run": dry_run, "vacuum": None}

    if warn and not dry_run:
        await _alert_owner(
            "Retention warning — students purge soon",
            "\n".join(
                f"- {m['discord_name']}: suspended {m['days_suspended']}d, "
                f"purges in {m['days_until_purge']}d"
                for m in warn
            ) + "\n\nRestore anyone who has renewed with !restore before then.",
        )

    for m in due:
        if dry_run:
            summary["purged"].append({"name": m["discord_name"], "dry_run": True})
            continue
        summary["purged"].append(purge_one(m))

    if summary["purged"] and not dry_run:
        try:
            summary["vacuum"] = database.vacuum()
        except Exception as e:
            logger.warning("suspension: vacuum failed: %s", e)
        lines = []
        for p in summary["purged"]:
            if p.get("skipped"):
                lines.append(f"- {p['name']}: SKIPPED — {p['skipped']}")
            else:
                lines.append(f"- {p['name']}: {p['deleted'].get('_total', 0)} rows deleted, "
                             f"archive {os.path.basename(p.get('archived') or '?')}")
        await _alert_owner("Retention purge complete", "\n".join(lines))

    return summary


async def _alert_owner(title: str, body: str) -> None:
    try:
        from . import ops_hub
        await ops_hub.send_ops_alert(title, body, severity="warning")
    except Exception as e:
        logger.warning("suspension: owner alert failed: %s", e)


# ============================================================
#  RENEWAL NOTICE BROADCAST
# ============================================================

def renewal_dm(name: str, cutoff: str, gender: str = "",
               stats: str = "") -> str:
    """The per-student notice.

    Egyptian Arabic is gendered, so an ungendered template addresses roughly
    half the students incorrectly. `members.gender` is '' for everyone today,
    so the neutral variant is what actually ships unless the owner sets it --
    and the neutral variant avoids second-person verb inflection entirely
    rather than silently guessing.
    """
    first = (name or "").split()[0] or name
    block = f"\n📊 شهرك في سطرين:\n   {stats}\n" if stats else ""
    if gender == "f":
        ask, cont, back = ("لو عايزة تكمّلي", "كلّميني", "لو رجعتي، هتكمّلي")
    elif gender == "m":
        ask, cont, back = ("لو عايز تكمّل", "كلّمني", "لو رجعت، هتكمّل")
    else:
        ask, cont, back = ("للاستمرار", "كلّمني", "لو رجعت، هتكمّل")
    return (
        f"مرحب {first} 🏛️\n\n"
        "أول حاجة وأهم حاجة: شكراً على الشهر اللي فات.\n"
        f"{block}\n"
        "📌 **اشتراكك الشهري خلص.**\n\n"
        f"**عندك لحد يوم {cutoff}.**\n"
        "لحد اليوم ده كل حاجة شغالة زي ما هي — القنوات، المهام، ومنصة التمرين.\n\n"
        "بعد التاريخ ده، لو الاشتراك مااتجددش، الوصول للقنوات ولمنصة التمرين هيتوقف.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**{ask}:**\n\n"
        f"{cont} أنا شخصياً — محمود عشري:\n\n"
        f"📱 واتساب: {config.OWNER_WHATSAPP_URL}\n"
        f"✈️ تليجرام: {config.OWNER_TELEGRAM}\n\n"
        "مش هنتكلم في فلوس على الرسائل. هنعمل **مقابلة قصيرة** نراجع فيها "
        "مستواك وشغلك، ونحدد سوا الخطة الجايّة وكل التفاصيل.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "كل تقدمك محفوظ — نقاطك، أسابيعك، امتحاناتك، وسلسلة أيامك. "
        f"{back} من مكانك بالظبط، مش من الأول.\n\n"
        f"⏳ بنحتفظ ببياناتك **{database.RETENTION_DAYS} يوم** من تاريخ التوقف. "
        "بعد كده بتتشال نهائي، وساعتها الرجوع يبقى من الصفر.\n\n"
        "الباب مفتوح، وأنا مستني رسالتك. 🏛️"
    )


def renewal_announcement(cutoff: str) -> str:
    return (
        "🏛️ **إعلان مهم — نهاية الشهر**\n\n"
        "الشهر خلص، وعايز أشكر كل واحد فيكم على المجهود.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 **اشتراكات الشهر خلصت لكل الطلبة الحاليين.**\n\n"
        f"**آخر ميعاد: يوم {cutoff}.**\n\n"
        f"• لحد {cutoff}: كل حاجة شغالة عادي.\n"
        "• بعد كده: الوصول للقنوات ولمنصة التمرين هيتوقف لأي حد مااتجددش اشتراكه.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ **عايز تكمّل؟**\n\n"
        "كلّمني شخصياً — محمود عشري:\n\n"
        f"📱 واتساب: {config.OWNER_WHATSAPP_URL}\n"
        f"✈️ تليجرام: {config.OWNER_TELEGRAM}\n\n"
        "مش بنحدد أي حاجة بالرسائل. هنعمل **مقابلة قصيرة** نراجع فيها مستواك "
        "وشغلك، ونحدد الخطة الجايّة سوا.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💾 **تقدمكم محفوظ بالكامل** — النقاط، الأسابيع، الامتحانات، والسلاسل. "
        "اللي هيرجع هيكمّل من مكانه بالظبط.\n\n"
        f"⏳ **بنحتفظ بالبيانات {database.RETENTION_DAYS} يوم** من تاريخ التوقف. "
        "بعد كده بتتشال نهائي، والرجوع بعدها يبقى من الصفر.\n\n"
        "شكراً لكل واحد فيكم. الباب مفتوح. 🏛️"
    )


def renewal_telegram(cutoff: str) -> str:
    """Plain text — `maintenance._send_telegram_groups` posts with no
    parse_mode, so any ** would render as literal asterisks."""
    return (
        "🏛️ إعلان مهم — نهاية الشهر\n\n"
        "الشهر خلص، وعايز أشكر كل واحد فيكم على المجهود.\n\n"
        "📌 اشتراكات الشهر خلصت لكل الطلبة الحاليين.\n\n"
        f"آخر ميعاد: يوم {cutoff}.\n\n"
        f"• لحد {cutoff} — كل حاجة شغالة عادي.\n"
        "• بعد كده — الوصول لقنوات الديسكورد ولمنصة التمرين هيتوقف "
        "لأي حد مااتجددش اشتراكه.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ عايز تكمّل؟\n\n"
        "كلّمني شخصياً — محمود عشري:\n\n"
        f"واتساب: {config.OWNER_WHATSAPP_URL}\n"
        f"تليجرام: {config.OWNER_TELEGRAM}\n\n"
        "مش بنحدد حاجة بالرسائل. هنعمل مقابلة قصيرة نراجع فيها مستواك وشغلك، "
        "ونحدد الخطة الجايّة سوا.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💾 تقدمكم محفوظ بالكامل — النقاط، الأسابيع، الامتحانات، والسلاسل.\n\n"
        f"⏳ بنحتفظ بالبيانات {database.RETENTION_DAYS} يوم من تاريخ التوقف. "
        "بعد كده بتتشال نهائي.\n\n"
        "شكراً لكل واحد فيكم. الباب مفتوح 🏛️"
    )


async def broadcast_renewal(bot, cutoff: str, dry_run: bool = False) -> dict:
    """DM every active student + post to #announcements + Telegram groups.

    Reports DM failures by name and reason. A student who has LEFT the server
    surfaces as a distinct outcome rather than a generic error -- Discord
    returns "no mutual guilds" for that case, which is not the same problem as
    closed DMs and needs a different response from the owner.
    """
    from . import maintenance

    guild = bot.get_guild(config.GUILD_ID) if config.GUILD_ID else None
    members = [m for m in database.all_members() if not m.get("suspended_at")]
    out = {"dry_run": dry_run, "targets": len(members), "sent": [],
           "failed": [], "left_server": [], "announcement": False,
           "telegram_groups": 0}

    for m in members:
        did, name = str(m["discord_id"]), m.get("discord_name", "")
        if dry_run:
            out["sent"].append(name)
            continue
        dm = guild.get_member(int(did)) if guild else None
        if dm is None:
            out["left_server"].append(name)
            continue
        try:
            await dm.send(renewal_dm(name, cutoff, m.get("gender", "")))
            out["sent"].append(name)
        except Exception as e:
            out["failed"].append((name, str(e)[:100]))
        await asyncio.sleep(DM_THROTTLE_SECONDS)

    if not dry_run:
        out["announcement"] = await maintenance._send_discord_announcement(
            bot, renewal_announcement(cutoff))
        out["telegram_groups"] = await maintenance._send_telegram_groups(
            renewal_telegram(cutoff))
    return out
