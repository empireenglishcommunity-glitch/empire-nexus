"""Hissar P1.2 — Role-Gate System (replaces removed Discord Rules Screening).

Discord removed the built-in "Rules Screening" / "Membership Screening"
feature. This module replicates that behavior through bot-managed roles:

Flow:
1. New member joins → sees ONLY #rules and #welcome (via Discord
   channel permission overwrites on @everyone vs the "Student" role)
2. Member reacts ✅ to the pinned rules message in #rules, OR types
   !agree / !أوافق in #rules
3. Bot assigns the "✅ Student | طالب" role → all other channels unlock

The "✅ Student | طالب" role is the gateway role. Channel permissions:
- @everyone: denied Send Messages + View Channel on all channels EXCEPT
  #rules and #welcome
- "✅ Student | طالب" role: allowed View Channel + Send Messages on
  all student channels

Setup (owner must do ONCE):
1. Create a role named "✅ Student | طالب" (bot will auto-create if missing)
2. Set @everyone to DENY view on all channels except #rules and #welcome
3. Set "✅ Student | طالب" to ALLOW view on all student channels
4. Bot posts the agreement message in #rules (via !postgate command)

The bot handles steps 1 and 4 automatically. Steps 2-3 require the owner
to adjust channel permissions manually (bot can't override higher roles).

Gated behind 'hissar_role_gate' feature flag.
"""
import logging
from typing import Optional

import discord

from . import config, database

logger = logging.getLogger("empire-bot.role-gate")

# ============================================================
#  CONSTANTS
# ============================================================

STUDENT_ROLE_NAME = "\u2705 Student | \u0637\u0627\u0644\u0628"
GATE_EMOJI = "\u2705"  # ✅

# Channels that stay visible to @everyone (even before the rules gate).
PUBLIC_CHANNELS = {"rules", "welcome"}

# ADMIN / hidden channels the STUDENT gateway role must NEVER be able to see.
# These are staff-only (set up by scripts/setup_server.py to deny @everyone and
# all level roles, allow only Admin/Moderator/bot). !setupgate used to loop EVERY
# non-rules/welcome channel and grant the Student role view+send — which silently
# unhid these admin channels to every student once the role was granted. The
# detection is deliberately belt-and-suspenders:
#   * by CATEGORY name — the two hidden categories from setup_server.py, and
#   * by CHANNEL name — the exact admin/ghost channels, in case a channel is
#     ever moved out of its category or the category is renamed.
# Matching is accent/emoji-insensitive on a normalised lower-case name.
ADMIN_CATEGORY_HINTS = ("admin", "\u0627\u0644\u0625\u062f\u0627\u0631\u0629", "ghost", "\u063a\u0648\u0633\u062a", "staff", "mod")
ADMIN_CHANNEL_NAMES = {
    "admin-chat", "mod-actions", "member-notes", "bot-logs", "dev-log",
    "ghost-commands", "ghost-showcase", "ghost-writing",
}

# Archived material that must NOT be visible to students. Two flavours:
#  * the legacy "Level 0" category/channels (pre-CEFR). The server was migrated
#    from L0–L3 to CEFR (A1–C2); the old "Level 0" category and its channels were
#    kept only as an ARCHIVE for staff. The CEFR detector (level_zone_of) knows
#    only a1–c2 — and config.level_slug("L0") maps to "a1" — so a legacy Level-0
#    category/channel matched no zone and fell through to the SHARED branch,
#    which granted the student gateway role.
#  * any ARCHIVE category (named "archive" / "أرشيف"), which is where the owner
#    parks retired categories/channels. These are staff-only by definition.
# All matched on the normalised (lower, no separators, ASCII-lower) name, so
# emoji + Arabic + English wrappers like "🌱 Level 0 | مبتدئ" or "📦 Archive |
# الأرشيف" all hit. The CEFR codes "a1"…"c2" never contain "level0"/"l0"/"archive".
LEGACY_ARCHIVE_NAME_HINTS = ("level0", "levelzero", "l0")
# Category-name hints for a generic archive (checked on the CATEGORY only, so a
# real archive category is caught even if it doesn't mention "Level 0").
ARCHIVE_CATEGORY_HINTS = ("archive", "archived", "\u0623\u0631\u0634\u064a\u0641", "\u0627\u0644\u0623\u0631\u0634\u064a\u0641")

# Categories that are built but NOT ready for students yet, so they must stay
# hidden (owner decision — showing half-finished sections looks unprofessional).
# Matched on the CATEGORY name only (normalised: lower, no separators/spaces),
# emoji/Arabic-insensitive, so "📚 المصادر | RESOURCES" and "💬 التقييم | FEEDBACK"
# both hit via their English words. TO UN-HIDE a category once it's ready: remove
# its hint from this tuple and re-run /setupgate — that restores student access.
HIDDEN_CATEGORY_HINTS = (
    "resources", "\u0627\u0644\u0645\u0635\u0627\u062f\u0631",   # RESOURCES / المصادر
    "feedback", "\u0627\u0644\u062a\u0642\u064a\u064a\u0645",     # FEEDBACK / التقييم
)


def _norm_name(name: str) -> str:
    return (name or "").lower().replace("-", "").replace("_", "").replace(" ", "")


def _is_voice(channel) -> bool:
    """True for a voice/stage channel (where 'connect' is the gate to JOIN)."""
    try:
        vt = (discord.VoiceChannel, getattr(discord, "StageChannel", discord.VoiceChannel))
        return isinstance(channel, vt)
    except Exception:
        return False


def _access_kwargs(channel, *, allow: bool) -> dict:
    """Permission kwargs to grant (allow=True) or deny (allow=False) a student
    access to `channel`. For TEXT channels this is view + send. For VOICE/stage
    channels, `send_messages` is meaningless — the gate to actually JOIN is
    `connect` (and `speak`), so we set those instead. Missing this is exactly
    why students could SEE community/level voice channels but got 'no access'
    when trying to join."""
    if _is_voice(channel):
        # use_voice_activation lets a student talk hands-free. Without granting
        # it, Discord forces Push-to-Talk ("Push to Talk Required") — students
        # could join and hear but not speak normally. setup_server grants it;
        # setupgate must too, or a re-apply strands students on PTT.
        return {"view_channel": allow, "connect": allow, "speak": allow,
                "use_voice_activation": allow}
    return {"view_channel": allow, "send_messages": allow}


def _is_legacy_level0(channel: "discord.abc.GuildChannel") -> bool:
    """True if `channel` is archived material that must stay staff-only: the
    legacy 'Level 0' category/channels (l0-/level0-/level-0- slug), OR any
    channel sitting inside an ARCHIVE category ('archive'/'أرشيف'). Kept separate
    so the intent — 'archived, staff-only' — is explicit and testable.

    Guard against false positives: a bare 'l0' substring is risky (it could sit
    inside an unrelated word), so a channel name only counts when it has a
    legacy Level-0 slug PREFIX; the category match is the primary, reliable
    signal (the archived category is literally named 'Level 0' or 'Archive').
    This never matches community-live or any CEFR a1–c2 channel."""
    cat = getattr(channel, "category", None)
    cat_norm = _norm_name(cat.name) if cat else ""
    if cat_norm and any(h in cat_norm for h in ARCHIVE_CATEGORY_HINTS):
        return True
    if cat_norm and any(h in cat_norm for h in LEGACY_ARCHIVE_NAME_HINTS):
        return True
    chan_lower = (channel.name or "").lower()
    # Slug prefixes only (real archived channel names), not loose substrings.
    return (chan_lower.startswith("l0-") or chan_lower.startswith("l0_")
            or chan_lower.startswith("level0-") or chan_lower.startswith("level0_")
            or chan_lower.startswith("level-0-") or chan_lower.startswith("level-0_")
            or chan_lower.startswith("level0"))


def _is_hidden_category(channel: "discord.abc.GuildChannel") -> bool:
    """True if `channel` sits in a category that is built but not ready for
    students yet (HIDDEN_CATEGORY_HINTS — e.g. RESOURCES, FEEDBACK). Keyed on
    the CATEGORY name only, so it hides the whole section regardless of the
    individual channel names, and never matches a channel that merely mentions
    'feedback'/'resources' in its own name outside those categories."""
    cat = getattr(channel, "category", None)
    cat_norm = _norm_name(cat.name) if cat else ""
    return bool(cat_norm) and any(h in cat_norm for h in HIDDEN_CATEGORY_HINTS)


def is_admin_only_channel(channel: "discord.abc.GuildChannel") -> bool:
    """True if `channel` is a staff-only channel the Student gateway role must
    never be granted access to. Checks the channel's own name AND its category
    name, so moving a channel between categories cannot silently expose it."""
    if channel.name in ADMIN_CHANNEL_NAMES:
        return True
    cat = getattr(channel, "category", None)
    cat_norm = _norm_name(cat.name) if cat else ""
    if cat_norm and any(h.replace(" ", "") in cat_norm for h in ADMIN_CATEGORY_HINTS):
        return True
    # Archived legacy "Level 0" material is staff-only — never expose to students.
    if _is_legacy_level0(channel):
        return True
    # Categories built but not ready for students yet (RESOURCES, FEEDBACK) stay
    # hidden until the owner un-hides them (remove from HIDDEN_CATEGORY_HINTS).
    if _is_hidden_category(channel):
        return True
    # Also treat the channel's own name as a hint (e.g. a stray "admin-..." chan).
    chan_norm = _norm_name(channel.name)
    return any(h.replace(" ", "") in chan_norm for h in ("admin", "modactions", "botlogs", "devlog", "ghost"))


def level_zone_of(channel: "discord.abc.GuildChannel"):
    """Which CEFR level a channel belongs to, or None if it is not a level zone.

    Level zones are per-level and MUST stay isolated — only that level's role
    (plus staff) may see them. Detected two ways (belt-and-suspenders):
      * the channel's CATEGORY name contains the level code + "ZONE"
        (setup_server names them e.g. "🌱 A1 ZONE | مبتدئ"), and
      * the channel's own name is slug-prefixed a1-/a2-/…/c2- (a1-daily-tasks…).
    Returns the upper-case level code (e.g. "A1") or None.

    This is what !setupgate uses to STOP granting the shared gateway role access
    to level zones — the bug that let every student see every level.
    """
    cat = getattr(channel, "category", None)
    cat_norm = _norm_name(cat.name) if cat else ""
    chan_lower = (channel.name or "").lower()
    for lvl in config.CEFR_ORDER:
        code = lvl.lower()                       # 'a1'
        slug = config.level_slug(lvl).lower()    # 'a1'
        # (a) category named like "🌱 A1 ZONE | مبتدئ" -> normalised has "a1zone"
        if cat_norm and (code + "zone") in cat_norm:
            return lvl
        # (b) channel slug-prefixed: a1-daily-tasks, a1_voice, ... (real prefix
        #     only, so 'a1' never matches the middle of another word)
        if chan_lower.startswith(f"{slug}-") or chan_lower.startswith(f"{slug}_"):
            return lvl
    return None


def protected_channel_reason(channel: "discord.abc.GuildChannel"):
    """Why a channel must NOT be deleted, or None if it is safe to delete.

    The delete command (bot.cmd_deletechannel) refuses any channel this flags.
    Protects everything the bot/onboarding/security depend on, so an admin can
    never accidentally destroy a load-bearing channel:
      * #rules / #welcome  — role-gate PUBLIC_CHANNELS + the ✅ onboarding gate
      * #announcements     — /announce and /ijtihad-announce post here by name
      * the #bot-commands / #admin-commands channels (by configured id)
      * admin/ghost channels (is_admin_only_channel)
      * per-level zones (level_zone_of) — deleting one strands that level
    Returns a short human reason string, or None.
    """
    name = (channel.name or "").lower()
    if name in PUBLIC_CHANNELS:
        return f"#{channel.name} is required by the onboarding role-gate"
    if name == "announcements":
        return "#announcements is used by /announce and /ijtihad-announce"
    cid = getattr(channel, "id", 0)
    if cid and cid == getattr(config, "ADMIN_COMMANDS_CHANNEL_ID", 0):
        return "this is the #admin-commands channel (admin commands run here)"
    if cid and cid == getattr(config, "BOT_COMMANDS_CHANNEL_ID", 0):
        return "this is the #bot-commands channel (students run commands here)"
    if is_admin_only_channel(channel):
        return f"#{channel.name} is a staff/admin channel"
    lvl = level_zone_of(channel)
    if lvl is not None:
        return f"#{channel.name} belongs to the {lvl} level zone"
    return None


# The agreement message posted in #rules. MSA, bidi-safe.
# Students react ✅ to this message to get the Student role.
GATE_MESSAGE_AR = (
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
    "\U0001f512 **\u0644\u0644\u062f\u062e\u0648\u0644 \u0625\u0644\u0649 \u0627\u0644\u0645\u062c\u062a\u0645\u0639**\n\n"
    "\u0628\u0639\u062f \u0642\u0631\u0627\u0621\u0629 \u0627\u0644\u0642\u0648\u0627\u0646\u064a\u0646 \u0623\u0639\u0644\u0627\u0647\u060c "
    "\u0627\u0636\u063a\u0637 \u0639\u0644\u0649 \u2705 \u0623\u0633\u0641\u0644 \u0647\u0630\u0647 \u0627\u0644\u0631\u0633\u0627\u0644\u0629 "
    "\u0644\u0644\u0645\u0648\u0627\u0641\u0642\u0629 \u0639\u0644\u0649 \u0627\u0644\u0634\u0631\u0648\u0637 \u0648\u0641\u062a\u062d \u0627\u0644\u0642\u0646\u0648\u0627\u062a.\n\n"
    "\u0623\u0648 \u0627\u0643\u062a\u0628 `!\u0623\u0648\u0627\u0641\u0642` \u0623\u0648 `!agree` \u0641\u064a \u0647\u0630\u0647 \u0627\u0644\u0642\u0646\u0627\u0629.\n"
    "\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501"
)


# ============================================================
#  ROLE HELPERS
# ============================================================

async def get_or_create_student_role(guild: discord.Guild) -> discord.Role:
    """Get the Student gateway role, creating it if it doesn't exist."""
    role = discord.utils.get(guild.roles, name=STUDENT_ROLE_NAME)
    if not role:
        role = await guild.create_role(
            name=STUDENT_ROLE_NAME,
            colour=discord.Colour.green(),
            reason="Hissar P1.2: role-gate system — gateway role for verified members",
        )
        logger.info(f"Created gateway role: {STUDENT_ROLE_NAME}")
    return role


def has_student_role(member: discord.Member) -> bool:
    """Check if a member already has the Student gateway role."""
    return any(r.name == STUDENT_ROLE_NAME for r in member.roles)


async def grant_student_role(member: discord.Member, start_journey: bool = True) -> bool:
    """Assign the Student gateway role to a member (the key that unlocks
    channels). Returns True if newly assigned, False if already had it.

    start_journey: retained for backward compatibility only. It used to kick
    off the automated Nour onboarding journey DMs, but Nour was retired
    (2026-09-03), so this parameter is now inert — no journey is ever started.
    Onboarding is team-run via /onboard.
    """
    if has_student_role(member):
        return False

    role = await get_or_create_student_role(member.guild)
    try:
        await member.add_roles(role, reason="role-gate: gateway role granted (unlocks channels)")
        logger.info(f"Role-gate: granted Student role to {member.display_name} ({member.id})")
        # Nour retired 2026-09-03: no onboarding journey is started here anymore.
        return True
    except discord.Forbidden:
        logger.error(f"Role-gate: cannot assign role to {member.display_name} — missing permissions")
        return False


# ============================================================
#  REACTION HANDLER (called from bot.py on_raw_reaction_add)
# ============================================================

async def handle_reaction_gate(
    payload: discord.RawReactionActionEvent,
    guild: discord.Guild,
) -> bool:
    """Handle ✅ reaction in #rules channel for role-gate.

    Returns True if this reaction was handled (consumed) by role-gate,
    False if it should fall through to other handlers.
    """
    if not database.is_feature_enabled("hissar_role_gate"):
        return False

    # Manual-onboarding mode: the team onboards each student in person via
    # !onboard, so the self-serve ✅-react path is disabled. Channel security
    # (the gateway role + overwrites) is unchanged — only the SELF-grant is off.
    if database.is_feature_enabled("manual_onboarding"):
        return False

    # Only handle ✅ emoji
    if str(payload.emoji) != GATE_EMOJI:
        return False

    # Only handle reactions in #rules channel
    channel = guild.get_channel(payload.channel_id)
    if not channel or not hasattr(channel, 'name'):
        return False
    if channel.name != "rules":
        return False

    member = guild.get_member(payload.user_id)
    if not member or member.bot:
        return False

    # Already has role — no-op
    if has_student_role(member):
        return True  # consumed, don't pass to other handlers

    # Grant the role
    granted = await grant_student_role(member)
    if granted:
        # Rawiya R8: Don't send a separate confirmation DM here.
        # Nour's journey (started by grant_student_role) already sends
        # the welcome message which implicitly confirms access is granted.
        # Sending two DMs ("access granted!" + "welcome to Empire!") is
        # confusing — one unified message from Nour is better.
        pass

    return True


# ============================================================
#  !agree / !أوافق COMMAND HANDLER
# ============================================================

async def cmd_agree(ctx) -> bool:
    """Handle !agree / !أوافق command in #rules channel.

    Returns True if handled, False if not applicable (wrong channel, etc.)
    """
    if not database.is_feature_enabled("hissar_role_gate"):
        return False

    # Manual-onboarding mode: self-serve !agree is disabled; the team onboards
    # each student via !onboard. Silent no-op so nothing prompts the student.
    if database.is_feature_enabled("manual_onboarding"):
        return False

    # Only works in #rules channel
    if not hasattr(ctx.channel, 'name') or ctx.channel.name != "rules":
        await ctx.send(
            "\u26a0\ufe0f \u0647\u0630\u0627 \u0627\u0644\u0623\u0645\u0631 \u064a\u0639\u0645\u0644 \u0641\u0642\u0637 \u0641\u064a \u0642\u0646\u0627\u0629 `#rules`.\n"
            "\u26a0\ufe0f This command only works in `#rules`.",
            delete_after=15,
        )
        return True

    member = ctx.author
    if not isinstance(member, discord.Member):
        return False

    if has_student_role(member):
        await ctx.send(
            f"\u2705 {member.mention} \u0623\u0646\u062a \u0645\u0648\u0627\u0641\u0642 \u0628\u0627\u0644\u0641\u0639\u0644! \u0627\u0644\u0642\u0646\u0648\u0627\u062a \u0645\u0641\u062a\u0648\u062d\u0629.\n"
            f"\u2705 You already agreed! Channels are unlocked.",
            delete_after=15,
        )
        return True

    granted = await grant_student_role(member)
    if granted:
        # Rawiya R8: don't send a separate "approved" DM here — Nour's
        # journey (started inside grant_student_role) already sends the
        # welcome DM which itself confirms access was granted. A short
        # confirmation in the channel itself is still useful (visible
        # to the student without needing to check DMs).
        await ctx.send(
            f"\u2705 {member.mention} \u0627\u0644\u0642\u0646\u0648\u0627\u062a \u0645\u0641\u062a\u0648\u062d\u0629 \u0627\u0644\u0622\u0646. \u062a\u062d\u0642\u0651\u0642 \u0645\u0646 \u0631\u0633\u0627\u0644\u062a\u0643 \u0627\u0644\u062e\u0627\u0635\u0651\u0629 \u0645\u0646 \u0646\u0648\u0631.\n"
            f"\u2705 Channels unlocked. Check your DMs from Nour.",
            delete_after=30,
        )
    else:
        await ctx.send(
            "\u274c \u062d\u062f\u062b \u062e\u0637\u0623. \u062a\u0648\u0627\u0635\u0644 \u0645\u0639 \u0627\u0644\u0625\u062f\u0627\u0631\u0629.\n"
            "\u274c Error assigning role. Contact an admin.",
            delete_after=15,
        )

    return True


# ============================================================
#  RAWIYA R8: SELF-HEAL FOR PERSISTENT REACTIONS ON REJOIN
# ============================================================

async def check_existing_reaction_on_join(member: discord.Member) -> None:
    """Discord does not clear a member's past reactions from a message
    when they leave and rejoin a server — a ✅ they left on the rules
    message during a PREVIOUS visit is still physically there. Since
    the normal flow only reacts to the on_raw_reaction_add EVENT (a NEW
    reaction), a returning member whose old reaction still shows on the
    message gets no event at all, and stays locked out of every channel
    until they manually un-react and react again (confirmed live during
    Rawiya R8 testing).

    Called from on_member_join: checks the gate message for this
    member's reaction and grants the role immediately if found, exactly
    as if a fresh reaction event had just arrived.
    """
    if not database.is_feature_enabled("hissar_role_gate"):
        return
    if has_student_role(member):
        return  # already has it, nothing to heal

    gate_msg_id = database.get_setting("role_gate_message_id", "")
    if not gate_msg_id:
        return

    guild = member.guild
    rules_channel = discord.utils.get(guild.text_channels, name="rules")
    if not rules_channel:
        return

    try:
        gate_msg = await rules_channel.fetch_message(int(gate_msg_id))
    except (discord.NotFound, discord.HTTPException, ValueError):
        return

    for reaction in gate_msg.reactions:
        if str(reaction.emoji) != GATE_EMOJI:
            continue
        async for user in reaction.users():
            if user.id == member.id:
                logger.info(f"Role-gate: self-heal — {member.display_name} already had ✅ from a previous visit, granting role now")
                await grant_student_role(member)
                return


# ============================================================
#  ADMIN: !postgate — post the agreement message in #rules
# ============================================================

async def cmd_postgate(ctx) -> bool:
    """Admin command: post the role-gate agreement message in #rules.

    Usage: !postgate
    Must be run by an admin in the #rules channel.
    The bot posts the agreement message and reacts ✅ to it as a prompt.
    """
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("\U0001f512 Admin only.", delete_after=10)
        return True

    # Find #rules channel (post there regardless of where command is run)
    rules_channel = discord.utils.get(ctx.guild.text_channels, name="rules")
    if not rules_channel:
        await ctx.send("\u274c Cannot find `#rules` channel.", delete_after=10)
        return True

    # Post the gate message
    gate_msg = await rules_channel.send(GATE_MESSAGE_AR)
    # React with ✅ so students see it as a prompt
    await gate_msg.add_reaction(GATE_EMOJI)

    # Store the message ID so we can reference it later (optional)
    database.set_setting("role_gate_message_id", str(gate_msg.id))

    await ctx.send(
        f"\u2705 \u062a\u0645 \u0646\u0634\u0631 \u0631\u0633\u0627\u0644\u0629 \u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629 \u0641\u064a {rules_channel.mention}. "
        f"\u0627\u0644\u0637\u0644\u0627\u0628 \u064a\u0636\u063a\u0637\u0648\u0646 \u2705 \u0644\u0641\u062a\u062d \u0627\u0644\u0642\u0646\u0648\u0627\u062a.\n\n"
        f"\u2705 Gate message posted in {rules_channel.mention}. Students react \u2705 to unlock.",
        delete_after=30,
    )
    return True


# ============================================================
#  ADMIN: !cleanrules — tidy up the #rules channel safely
# ============================================================

async def cmd_cleanrules(ctx, confirm: bool = False) -> bool:
    """Admin command: clean up a messy #rules channel.

    Deletes messages in #rules EXCEPT the ones worth keeping — pinned messages
    and the stored role-gate ✅ message — so the onboarding gate and reactions
    survive. This is deliberately non-destructive to the gate: we do NOT delete
    and recreate the channel (that would break the reaction gate, drop the pin,
    and un-react everyone). Requires confirm=True to actually delete; otherwise
    it's a dry run that just reports what it would remove.

    Usage:
      !cleanrules          — dry run (counts what would be deleted)
      !cleanrules confirm  — actually delete the non-kept messages
    """
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("\U0001f512 Admin only.", delete_after=10)
        return True

    rules_channel = discord.utils.get(ctx.guild.text_channels, name="rules")
    if not rules_channel:
        await ctx.send("\u274c Cannot find `#rules` channel.", delete_after=10)
        return True

    # Messages to KEEP: anything pinned, plus the stored gate message id (belt
    # and suspenders in case the gate message was never pinned).
    try:
        pinned = await rules_channel.pins()
        keep_ids = {m.id for m in pinned}
    except Exception:
        keep_ids = set()
    stored_gate = database.get_setting("role_gate_message_id", "")
    if stored_gate.isdigit():
        keep_ids.add(int(stored_gate))

    # Count / collect deletable messages (everything not in keep_ids).
    to_delete = []
    try:
        async for msg in rules_channel.history(limit=None):
            if msg.id not in keep_ids:
                to_delete.append(msg)
    except Exception as e:
        await ctx.send(f"\u274c Couldn't read #rules history: {type(e).__name__}.",
                       delete_after=15)
        return True

    if not to_delete:
        await ctx.send("\u2705 #rules is already clean \u2014 nothing to remove "
                       f"(keeping {len(keep_ids)} pinned/gate message(s)).")
        return True

    if not confirm:
        await ctx.send(
            f"\U0001f9f9 **DRY RUN.** Would delete **{len(to_delete)}** message(s) in "
            f"{rules_channel.mention}, keeping **{len(keep_ids)}** pinned/gate message(s).\n"
            f"Run `!cleanrules confirm` (or `/admin command:cleanrules args:confirm`) "
            f"to actually clean it.")
        return True

    # Delete. Prefer bulk purge (fast, but Discord only bulk-deletes messages
    # < 14 days old); fall back to per-message delete for anything older.
    deleted = 0
    errors = 0
    try:
        purged = await rules_channel.purge(
            limit=None,
            check=lambda m: m.id not in keep_ids,
            reason="cleanrules: tidy up #rules (admin)")
        deleted = len(purged)
    except Exception:
        # Fallback: delete one by one (handles >14-day-old messages too).
        for msg in to_delete:
            try:
                await msg.delete()
                deleted += 1
            except Exception:
                errors += 1

    msg = [f"\u2705 **#rules cleaned.** Deleted **{deleted}** message(s); "
           f"kept **{len(keep_ids)}** pinned/gate message(s)."]
    if errors:
        msg.append(f"\u26a0\ufe0f {errors} message(s) couldn't be deleted "
                   f"(likely older than 14 days \u2014 delete those manually if needed).")
    msg.append("\U0001f4dd #rules is now read-only for students (run `!setupgate` "
               "if you haven't since this update).")
    await ctx.send("\n".join(msg))
    return True


# ============================================================
#  ADMIN: !repost-rules — refresh the pinned #rules content
# ============================================================

# The first line of the rules message — used to recognise (and remove) an
# EXISTING rules post by this bot, so re-posting replaces it rather than stacking.
_RULES_HEADER = config.RULES_MESSAGE.splitlines()[0].strip()


async def cmd_repost_rules(ctx, confirm: bool = False) -> bool:
    """Admin command: (re)post the canonical #rules content, pinned.

    Replaces any existing bot-posted rules message with the current
    config.RULES_MESSAGE, split into Discord-safe chunks (the bilingual rules
    exceed the 2000-char limit). The FIRST chunk is pinned. The onboarding ✅
    gate message is NEVER touched. Dry run by default; posts only with confirm.

    Usage:
      !repost-rules          — dry run (shows what it will do)
      !repost-rules confirm  — actually repost + pin
    """
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("\U0001f512 Admin only.", delete_after=10)
        return True

    rules_channel = discord.utils.get(ctx.guild.text_channels, name="rules")
    if not rules_channel:
        await ctx.send("\u274c Cannot find `#rules` channel.", delete_after=10)
        return True

    chunks = config.chunk_message(config.RULES_MESSAGE)
    gate_id = database.get_setting("role_gate_message_id", "")
    gate_id = int(gate_id) if gate_id.isdigit() else 0

    # Find existing bot-posted rules messages to replace: any message by this bot
    # whose content starts with the rules header (covers the current + previous
    # versions). The ✅ gate message is explicitly excluded.
    old_rules = []
    try:
        async for m in rules_channel.history(limit=50):
            if m.author == ctx.bot.user and m.id != gate_id \
                    and (m.content or "").lstrip().startswith(_RULES_HEADER):
                old_rules.append(m)
    except Exception:
        pass

    if not confirm:
        await ctx.send(
            f"\U0001f9f9 **DRY RUN.** Would post the rules as **{len(chunks)}** "
            f"message(s) in {rules_channel.mention} (pinning the first) and remove "
            f"**{len(old_rules)}** old rules post(s). The \u2705 gate message is "
            f"kept.\nRun `!repost-rules confirm` "
            f"(or `/admin command:repost-rules args:confirm`) to do it.")
        return True

    # Remove the old rules posts (never the gate message).
    removed = 0
    for m in old_rules:
        try:
            await m.delete()
            removed += 1
        except Exception:
            pass

    # Post the fresh rules; pin the FIRST chunk.
    first = None
    posted = 0
    for i, chunk in enumerate(chunks):
        try:
            sent = await rules_channel.send(chunk)
            posted += 1
            if i == 0:
                first = sent
        except Exception as e:
            await ctx.send(f"\u26a0\ufe0f Failed to post rules chunk {i+1}: "
                           f"{type(e).__name__}.", delete_after=15)
    if first is not None:
        try:
            await first.pin()
        except discord.HTTPException:
            pass

    await ctx.send(
        f"\u2705 **Rules reposted.** Posted **{posted}** message(s) in "
        f"{rules_channel.mention} (pinned the first), removed **{removed}** old "
        f"post(s). The \u2705 gate message was left untouched.\n"
        f"\U0001f4dd Tip: run `!setupgate` if you haven't, so #rules stays "
        f"read-only for students.")
    return True


# ============================================================
#  ADMIN: !setupgate — auto-configure channel permissions
# ============================================================

async def cmd_setupgate(ctx) -> bool:
    """Admin command: automatically configure channel permissions for role-gate.

    Sets @everyone to DENY view on all channels except #rules and #welcome,
    and sets the Student role to ALLOW view on student channels.

    WARNING: This modifies ALL channel permissions in the server.
    Only run this once during initial setup.
    """
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("\U0001f512 Admin only.", delete_after=10)
        return True

    guild = ctx.guild
    student_role = await get_or_create_student_role(guild)

    # Immediate acknowledgement BEFORE the heavy loop. setupgate makes many
    # sequential, rate-limited set_permissions calls (a level zone alone is ~9
    # calls, and there can be dozens of channels), so the full run takes a while.
    # Without this the channel — and the /admin slash bridge that awaits it —
    # just shows "thinking…" for minutes and can hit Discord's interaction
    # timeout. This early message makes it clear the work has started; the final
    # summary is posted when it finishes.
    channel_count = sum(
        1 for c in guild.channels
        if isinstance(c, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel))
    )
    try:
        await ctx.send(
            f"⏳ **إعداد البوابة بدأ…** بأمّن {channel_count} قناة "
            f"(ممكن ياخد دقيقة أو اتنين بسبب حدود ديسكورد). هبعت الملخص لما أخلص.\n"
            f"⏳ **Setting up the gate…** securing {channel_count} channels "
            f"(this can take a minute or two due to Discord rate limits). "
            f"I'll post a summary when done."
        )
    except discord.HTTPException:
        pass

    modified = 0
    errors = 0
    admin_locked = 0        # admin channels the Student role was DENIED on
    zones_locked = 0        # level zones re-isolated to their own level role

    for channel in guild.channels:
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)):
            continue

        # SECURITY: never grant the Student gateway role access to a staff-only
        # channel. The old loop granted Student view+send on EVERY non-public
        # channel, which unhid the admin/ghost channels to every student. Now we
        # actively DENY the Student role there and also re-assert the @everyone
        # deny, so re-running !setupgate REPAIRS a server that was already exposed.
        if is_admin_only_channel(channel):
            try:
                await channel.set_permissions(
                    student_role,
                    overwrite=None,        # drop any prior (erroneous) allow first
                    reason="Hissar: role-gate — remove any Student access to admin channel",
                )
                await channel.set_permissions(
                    student_role,
                    view_channel=False,
                    send_messages=False,
                    reason="Hissar: role-gate — Student role must never see admin channels",
                )
                await channel.set_permissions(
                    guild.default_role,
                    view_channel=False,
                    reason="Hissar: role-gate — admin channel hidden from @everyone",
                )
                admin_locked += 1
            except discord.Forbidden:
                errors += 1
            continue

        # LEVEL ZONES are per-level, NOT shared. The gateway role must NOT open
        # them — only the channel's OWN level role may see it. The old loop
        # granted the shared Student role view on every non-admin channel, which
        # let every student see every level's zone. Re-assert isolation here so
        # re-running !setupgate REPAIRS the leak.
        zone_level = level_zone_of(channel)
        if zone_level is not None:
            try:
                own_role_name = config.level_role_name(zone_level)
                # gateway role must NOT grant access to a level zone
                await channel.set_permissions(
                    student_role, overwrite=None,
                    reason="isolation: drop stale Student overwrite on level zone")
                await channel.set_permissions(
                    student_role, view_channel=False,
                    reason="isolation: gateway role does not open per-level zones")
                await channel.set_permissions(
                    guild.default_role, view_channel=False,
                    reason="isolation: level zone hidden from @everyone")
                # own level sees it; every other level denied
                for lvl in config.CEFR_ORDER:
                    role = discord.utils.get(guild.roles, name=config.level_role_name(lvl))
                    if role is None:
                        continue
                    if lvl == zone_level:
                        await channel.set_permissions(
                            role, **_access_kwargs(channel, allow=True),
                            reason=f"isolation: {zone_level} zone visible to its own level")
                    else:
                        await channel.set_permissions(
                            role, **_access_kwargs(channel, allow=False),
                            reason=f"isolation: {zone_level} zone hidden from other levels")
                zones_locked += 1
            except discord.Forbidden:
                errors += 1
            continue

        if channel.name in PUBLIC_CHANNELS:
            # These stay VISIBLE to @everyone (even before the rules gate).
            # #rules is READ-ONLY: @everyone can view but NOT write. Onboarding
            # is by REACTION (✅ on the pinned message), never by typing, so
            # nobody needs send access — this is what stops students messing up
            # #rules. (It used to grant send=True, which is why #rules got messy.)
            # NOTE: add_reactions is intentionally NOT denied — the gate needs
            # students to be able to react ✅.
            try:
                await channel.set_permissions(
                    guild.default_role,
                    view_channel=True,
                    send_messages=False if channel.name == "rules" else None,
                    reason="Hissar P1.2: public channel (visible pre-gate; #rules read-only)",
                )
                # Student role doesn't need overwrite here (inherits)
                modified += 1
            except discord.Forbidden:
                errors += 1
        else:
            # SHARED student channels (community, resources, accountability, …):
            # deny @everyone, allow the gateway role. These are the same for all
            # levels, so the gateway role is the right key here.
            try:
                await channel.set_permissions(
                    guild.default_role,
                    view_channel=False,
                    reason="Hissar P1.2: role-gate — hidden until rules accepted",
                )
                await channel.set_permissions(
                    student_role,
                    **_access_kwargs(channel, allow=True),
                    reason="Hissar P1.2: role-gate — visible after rules accepted",
                )
                modified += 1
            except discord.Forbidden:
                errors += 1

    # Also grant existing members the Student role (retroactive)
    retroactive = 0
    for member in guild.members:
        if member.bot:
            continue
        if not has_student_role(member):
            try:
                await member.add_roles(student_role, reason="Hissar P1.2: retroactive grant for existing members")
                retroactive += 1
            except discord.Forbidden:
                pass

    result = (
        f"\u2705 **\u062a\u0645 \u0625\u0639\u062f\u0627\u062f \u0646\u0638\u0627\u0645 \u0627\u0644\u0628\u0648\u0627\u0628\u0629!**\n\n"
        f"\U0001f4dd \u0627\u0644\u0642\u0646\u0648\u0627\u062a \u0627\u0644\u0645\u0639\u062f\u0644\u0629: {modified}\n"
        f"\U0001f512 \u0642\u0646\u0648\u0627\u062a \u0627\u0644\u0625\u062f\u0627\u0631\u0629 \u0627\u0644\u0645\u064f\u0642\u0641\u0644\u0629 \u0623\u0645\u0627\u0645 \u0627\u0644\u0637\u0644\u0627\u0628: {admin_locked}\n"
        f"\U0001f3af \u0642\u0646\u0648\u0627\u062a \u0627\u0644\u0645\u0633\u062a\u0648\u064a\u0627\u062a \u0627\u0644\u0645\u0639\u0632\u0648\u0644\u0629 (\u0643\u0644 \u0645\u0633\u062a\u0648\u0649 \u0644\u0637\u0644\u0627\u0628\u0647 \u0641\u0642\u0637): {zones_locked}\n"
        f"\u2705 \u0627\u0644\u0623\u0639\u0636\u0627\u0621 \u0627\u0644\u062d\u0627\u0644\u064a\u0648\u0646 (\u0645\u0646\u062d \u0627\u0644\u062f\u0648\u0631): {retroactive}\n"
    )
    if errors:
        result += f"\u26a0\ufe0f \u0623\u062e\u0637\u0627\u0621 (\u0635\u0644\u0627\u062d\u064a\u0627\u062a \u0646\u0627\u0642\u0635\u0629): {errors}\n"
    result += (
        f"\n**\u0627\u0644\u062e\u0637\u0648\u0629 \u0627\u0644\u062a\u0627\u0644\u064a\u0629:** \u0627\u0643\u062a\u0628 `!postgate` \u0644\u0646\u0634\u0631 \u0631\u0633\u0627\u0644\u0629 \u0627\u0644\u0645\u0648\u0627\u0641\u0642\u0629 \u0641\u064a #rules."
    )

    await ctx.send(result)
    logger.info(f"Role-gate setup: {modified} channels modified, {retroactive} existing members granted, {errors} errors")
    return True



# ============================================================
#  ONBOARDING SAFETY NET — read-only reconciliation
# ============================================================
#
#  Session-33 hardening. The role-gate + guided journey can only be
#  *skipped* if (a) a member ends up in the server without the gateway
#  role, or (b) they hold the role but no journey ever started. This
#  audit detects both, so a regression like the session-23 gap (14/15
#  students with NO_JOURNEY) would be caught automatically instead of
#  by chance. It ONLY reads + alerts the owner — it never DMs students
#  or changes any state.


def audit_onboarding(guild: discord.Guild) -> dict:
    """Classify every ACTIVE student against the two onboarding signals:
    the Discord gateway role (passed the #rules gate) and a
    student_journey row (the guided journey started).

    Read-only. Returns a dict of member-dict lists:
      - ok                : has the role AND a journey (fully onboarded)
      - gated_no_journey  : has the role but NO journey (legacy/grandfathered)
      - no_gate           : in the guild but WITHOUT the role (a real bypass)
      - not_in_guild      : active in the DB but not currently in the guild
    """
    active = database.all_active_members()
    conn = database._connect()
    journeyed = {
        str(r["discord_id"])
        for r in conn.execute("SELECT discord_id FROM student_journey").fetchall()
    }
    conn.close()

    ok, gated_no_journey, no_gate, not_in_guild = [], [], [], []
    for m in active:
        did = str(m.get("discord_id", ""))
        member = guild.get_member(int(did)) if did.isdigit() else None
        if member is None:
            not_in_guild.append(m)
            continue
        if not has_student_role(member):
            no_gate.append(m)
        elif did not in journeyed:
            gated_no_journey.append(m)
        else:
            ok.append(m)

    return {
        "total": len(active),
        "ok": ok,
        "gated_no_journey": gated_no_journey,
        "no_gate": no_gate,
        "not_in_guild": not_in_guild,
    }


def format_onboarding_audit(audit: dict) -> str:
    """Plain-text (bilingual-labelled) summary of audit_onboarding().
    Suitable for both the Empire Ops alert body and an in-channel report.
    Kept free of Markdown — ops_hub.send_ops_alert escapes it for us."""

    def _names(lst, n=15):
        rows = [
            f"- {(m.get('discord_name') or m.get('discord_id'))} ({m.get('level', '?')})"
            for m in lst[:n]
        ]
        if len(lst) > n:
            rows.append(f"... +{len(lst) - n} more")
        return "\n".join(rows) if rows else "-"

    lines = [
        f"Active students: {audit['total']}",
        f"Fully onboarded (gate + journey): {len(audit['ok'])}",
        "",
    ]
    if audit["no_gate"]:
        lines += [
            f"[!] In the server WITHOUT the gate role ({len(audit['no_gate'])}) "
            f"| بدون دور البوابة — investigate:",
            _names(audit["no_gate"]),
            "",
        ]
    if audit["gated_no_journey"]:
        lines += [
            f"Gated but no guided journey ({len(audit['gated_no_journey'])}) "
            f"| legacy/grandfathered:",
            _names(audit["gated_no_journey"]),
            "",
        ]
    if audit["not_in_guild"]:
        lines += [
            f"Active in DB but not currently in the server "
            f"({len(audit['not_in_guild'])}):",
            _names(audit["not_in_guild"]),
            "",
        ]
    if not audit["no_gate"] and not audit["gated_no_journey"]:
        lines.append(
            "OK: every active student passed the gate and has a guided journey."
        )
    return "\n".join(lines).strip()


async def run_onboarding_reconciliation(
    guild: discord.Guild, force: bool = False
) -> Optional[dict]:
    """Run the onboarding audit and alert the owner via Empire Ops ONLY
    when the set of flagged students changes (so a daily loop doesn't spam
    the same known-legacy members every day). `force=True` sends a report
    regardless (used by the on-demand !checkgate command).

    Returns the audit dict (or None if the role-gate feature is off).
    Never raises for an alert failure and never DMs a student.
    """
    if not database.is_feature_enabled("hissar_role_gate"):
        return None

    audit = audit_onboarding(guild)

    problem_ids = sorted(
        [str(m.get("discord_id")) for m in audit["no_gate"]]
        + [str(m.get("discord_id")) for m in audit["gated_no_journey"]]
    )
    fingerprint = ",".join(problem_ids)
    last = database.get_setting("onboarding_recon_fingerprint", "")
    changed = fingerprint != last

    if force or (problem_ids and changed):
        try:
            from . import ops_hub
            severity = "critical" if audit["no_gate"] else "warning"
            await ops_hub.send_ops_alert(
                "Onboarding gate check",
                format_onboarding_audit(audit),
                severity=severity,
            )
        except Exception as e:  # never let an alert failure crash the loop
            logger.error(f"run_onboarding_reconciliation: ops alert failed: {e}")

    # Record the fingerprint even when we didn't alert, so a later change
    # (someone entering/leaving a flagged state) is what triggers the next one.
    database.set_setting("onboarding_recon_fingerprint", fingerprint)
    return audit


async def cmd_checkgate(ctx) -> bool:
    """Admin command: on-demand onboarding audit, reported in-channel.

    Usage: !checkgate  (admin-only, admin-channel-gated via bot.py)
    Also refreshes the reconciliation fingerprint so the next scheduled
    run only alerts on genuinely new changes.
    """
    guild = getattr(ctx, "guild", None)
    if guild is None:
        await ctx.send("Run `!checkgate` inside the server.", delete_after=15)
        return True

    audit = audit_onboarding(guild)
    report = format_onboarding_audit(audit)
    # Keep the stored fingerprint in sync with what the owner just saw.
    problem_ids = sorted(
        [str(m.get("discord_id")) for m in audit["no_gate"]]
        + [str(m.get("discord_id")) for m in audit["gated_no_journey"]]
    )
    database.set_setting("onboarding_recon_fingerprint", ",".join(problem_ids))

    await ctx.send(f"**Onboarding gate check | فحص البوابة**\n```\n{report}\n```")
    return True



# ============================================================
#  ADMIN-CHANNEL EXPOSURE AUDIT — the guardrail for THIS bug
# ============================================================
#
#  The onboarding audit above checks MEMBERS. This one checks CHANNEL
#  PERMISSIONS: it reads the live overwrites on every admin/hidden channel
#  and reports any that a student could see — either because @everyone is
#  allowed view, or because the Student gateway role (or a CEFR level role)
#  is allowed view. This is exactly the failure !setupgate used to cause.
#  Read-only: it reports, never changes permissions. Fix with !setupgate.

def audit_admin_exposure(guild: discord.Guild) -> dict:
    """Return {'exposed': [...], 'ok_count': int, 'checked': int} where each
    exposed entry is {'channel', 'reasons': [...]}. A channel is 'exposed' if a
    student-reachable role/@everyone is granted view_channel on it."""
    student_role = discord.utils.get(guild.roles, name=STUDENT_ROLE_NAME)
    level_role_names = set(config.all_managed_level_role_names())
    exposed, ok_count, checked = [], 0, 0

    for channel in guild.channels:
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)):
            continue
        if not is_admin_only_channel(channel):
            continue
        checked += 1
        reasons = []
        for target, ow in channel.overwrites.items():
            # ow.view_channel is True (allow), False (deny), or None (neutral).
            if ow.view_channel is not True:
                continue
            if target == guild.default_role:
                reasons.append("@everyone is allowed to view")
            elif student_role is not None and target == student_role:
                reasons.append(f"the '{STUDENT_ROLE_NAME}' role is allowed to view")
            elif getattr(target, "name", None) in level_role_names:
                reasons.append(f"the student level role '{target.name}' is allowed to view")
        if reasons:
            exposed.append({"channel": channel.name, "reasons": reasons})
        else:
            ok_count += 1

    return {"exposed": exposed, "ok_count": ok_count, "checked": checked}


def format_admin_exposure(audit: dict) -> str:
    """Plain-text summary of audit_admin_exposure(). Markdown-free (ops_hub
    escapes)."""
    if audit["checked"] == 0:
        return ("No admin/hidden channels found to check. If the server has admin "
                "channels, confirm their names/category match role_gate's detection.")
    if not audit["exposed"]:
        return (f"OK: all {audit['checked']} admin/hidden channel(s) are hidden "
                f"from students (no student-reachable role can view them).")
    lines = [
        f"[!] {len(audit['exposed'])} of {audit['checked']} admin/hidden channel(s) "
        f"are VISIBLE to students — run !setupgate to re-lock:",
        "",
    ]
    for e in audit["exposed"]:
        lines.append(f"- #{e['channel']}: " + "; ".join(e["reasons"]))
    return "\n".join(lines)


async def run_admin_exposure_check(guild: discord.Guild, force: bool = False):
    """Audit admin-channel exposure and alert the owner via Empire Ops when the
    exposed set changes (so a daily loop doesn't spam). force=True always reports.
    Returns the audit dict. Never raises for an alert failure; never changes perms."""
    audit = audit_admin_exposure(guild)
    fingerprint = ",".join(sorted(e["channel"] for e in audit["exposed"]))
    last = database.get_setting("admin_exposure_fingerprint", "")
    changed = fingerprint != last

    if force or (audit["exposed"] and changed):
        try:
            from . import ops_hub
            await ops_hub.send_ops_alert(
                "Admin-channel exposure check",
                format_admin_exposure(audit),
                severity="critical" if audit["exposed"] else "info",
            )
        except Exception as e:  # never let an alert failure crash a loop
            logger.error(f"run_admin_exposure_check: ops alert failed: {e}")

    database.set_setting("admin_exposure_fingerprint", fingerprint)
    return audit


async def cmd_checkadmin(ctx) -> bool:
    """Admin command: on-demand admin-channel exposure audit, reported in-channel.

    Usage: !checkadmin  (admin-only, admin-channel-gated via bot.py)
    Reports whether any admin/hidden channel is visible to students. Read-only —
    to FIX an exposure, run !setupgate (which re-locks admin channels).
    """
    guild = getattr(ctx, "guild", None)
    if guild is None:
        await ctx.send("Run `!checkadmin` inside the server.", delete_after=15)
        return True
    audit = audit_admin_exposure(guild)
    database.set_setting(
        "admin_exposure_fingerprint",
        ",".join(sorted(e["channel"] for e in audit["exposed"])),
    )
    report = format_admin_exposure(audit)
    await ctx.send(f"**Admin-channel exposure | تسريب قنوات الإدارة**\n```\n{report}\n```")
    return True



# ============================================================
#  LEVEL-ISOLATION AUDIT — the guardrail for cross-level leakage
# ============================================================
#
#  Each per-level zone (a1-*, …, c2-*) must be visible ONLY to its own level
#  role (plus staff). This read-only audit flags any zone channel that a
#  student-reachable target that should NOT see it can view: @everyone, the
#  shared gateway role, or ANOTHER level's role. It reports; !setupgate fixes.

def audit_level_isolation(guild: discord.Guild) -> dict:
    """Return {'leaks': [...], 'ok_count': int, 'checked': int}. Each leak is
    {'channel', 'level', 'reasons':[...]} where a wrong target can view the zone."""
    student_role = discord.utils.get(guild.roles, name=STUDENT_ROLE_NAME)
    leaks, ok_count, checked = [], 0, 0

    for channel in guild.channels:
        if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel, discord.ForumChannel)):
            continue
        zone_level = level_zone_of(channel)
        if zone_level is None:
            continue
        checked += 1
        own_role_name = config.level_role_name(zone_level)
        other_level_names = {config.level_role_name(l) for l in config.CEFR_ORDER
                             if l != zone_level}
        reasons = []
        for target, ow in channel.overwrites.items():
            if ow.view_channel is not True:
                continue
            tname = getattr(target, "name", None)
            if target == guild.default_role:
                reasons.append("@everyone can view")
            elif student_role is not None and target == student_role:
                reasons.append(f"the shared '{STUDENT_ROLE_NAME}' gateway role can view")
            elif tname in other_level_names:
                reasons.append(f"another level's role '{tname}' can view")
            # own level role viewing is CORRECT — never flagged
        if reasons:
            leaks.append({"channel": channel.name, "level": zone_level, "reasons": reasons})
        else:
            ok_count += 1

    return {"leaks": leaks, "ok_count": ok_count, "checked": checked}


def format_level_isolation(audit: dict) -> str:
    if audit["checked"] == 0:
        return "No level-zone channels found to check."
    if not audit["leaks"]:
        return (f"OK: all {audit['checked']} level-zone channel(s) are isolated "
                f"(each visible only to its own level).")
    lines = [
        f"[!] {len(audit['leaks'])} of {audit['checked']} level-zone channel(s) "
        f"leak to the wrong students — run !setupgate to re-isolate:",
        "",
    ]
    for e in audit["leaks"]:
        lines.append(f"- #{e['channel']} ({e['level']} zone): " + "; ".join(e["reasons"]))
    return "\n".join(lines)


async def run_level_isolation_check(guild: discord.Guild, force: bool = False):
    """Alert Empire Ops on a change of leak state (no daily spam). Read-only."""
    audit = audit_level_isolation(guild)
    fingerprint = ",".join(sorted(e["channel"] for e in audit["leaks"]))
    last = database.get_setting("level_isolation_fingerprint", "")
    changed = fingerprint != last
    if force or (audit["leaks"] and changed):
        try:
            from . import ops_hub
            await ops_hub.send_ops_alert(
                "Level-isolation check",
                format_level_isolation(audit),
                severity="critical" if audit["leaks"] else "info",
            )
        except Exception as e:
            logger.error(f"run_level_isolation_check: ops alert failed: {e}")
    database.set_setting("level_isolation_fingerprint", fingerprint)
    return audit


async def cmd_checkchannels(ctx) -> bool:
    """Admin command: audit BOTH admin-channel exposure AND per-level isolation.

    Usage: !checkchannels (admin-only). Read-only — fix either finding with
    !setupgate.
    """
    guild = getattr(ctx, "guild", None)
    if guild is None:
        await ctx.send("Run `!checkchannels` inside the server.", delete_after=15)
        return True
    admin_audit = audit_admin_exposure(guild)
    level_audit = audit_level_isolation(guild)
    database.set_setting(
        "admin_exposure_fingerprint",
        ",".join(sorted(e["channel"] for e in admin_audit["exposed"])))
    database.set_setting(
        "level_isolation_fingerprint",
        ",".join(sorted(e["channel"] for e in level_audit["leaks"])))
    report = (format_admin_exposure(admin_audit) + "\n\n"
              + format_level_isolation(level_audit))
    await ctx.send(f"**Channel security check | فحص أمان القنوات**\n```\n{report}\n```")
    return True
