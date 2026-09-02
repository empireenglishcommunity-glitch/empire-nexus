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


def _norm_name(name: str) -> str:
    return (name or "").lower().replace("-", "").replace("_", "").replace(" ", "")


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
    # Also treat the channel's own name as a hint (e.g. a stray "admin-..." chan).
    chan_norm = _norm_name(channel.name)
    return any(h.replace(" ", "") in chan_norm for h in ("admin", "modactions", "botlogs", "devlog", "ghost"))

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


async def grant_student_role(member: discord.Member) -> bool:
    """Assign the Student gateway role to a member.

    Returns True if newly assigned, False if already had it.
    """
    if has_student_role(member):
        return False

    role = await get_or_create_student_role(member.guild)
    try:
        await member.add_roles(role, reason="Hissar P1.2: member agreed to rules")
        logger.info(f"Role-gate: granted Student role to {member.display_name} ({member.id})")
        # Rawiya R2: start the onboarding journey when student accepts rules
        from . import nour_journey
        import asyncio
        asyncio.create_task(nour_journey.start_journey(member))
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

    modified = 0
    errors = 0
    admin_locked = 0        # admin channels the Student role was DENIED on

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

        if channel.name in PUBLIC_CHANNELS:
            # These stay visible to @everyone
            try:
                await channel.set_permissions(
                    guild.default_role,
                    view_channel=True,
                    send_messages=True if channel.name == "rules" else None,
                    reason="Hissar P1.2: public channel (visible pre-gate)",
                )
                # Student role doesn't need overwrite here (inherits)
                modified += 1
            except discord.Forbidden:
                errors += 1
        else:
            # Student (non-admin) channels: deny @everyone, allow Student role
            try:
                await channel.set_permissions(
                    guild.default_role,
                    view_channel=False,
                    reason="Hissar P1.2: role-gate — hidden until rules accepted",
                )
                await channel.set_permissions(
                    student_role,
                    view_channel=True,
                    send_messages=True,
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
