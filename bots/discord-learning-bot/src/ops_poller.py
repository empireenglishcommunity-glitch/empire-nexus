"""Markaz (مركز) Phase M2 — Telegram reply-forwarding poller.

Background asyncio task that long-polls Telegram's getUpdates for the
Empire Ops bot, watching for the owner replying to an escalation
message. When a match is found, forwards the reply to the student as
a Discord DM "from Nour" and confirms delivery back to the owner.

Design notes:
- Uses getUpdates long-polling (timeout=25s), NOT a webhook — no public
  HTTPS endpoint is exposed for this bot, matching the "same container,
  no new services" design goal in design.md.
- The Telegram `offset` (last-processed update_id + 1) is persisted in
  the settings table so a restart doesn't re-process old updates or
  miss ones that arrived while the bot was down.
- Runs as a single asyncio.create_task() background loop started from
  on_ready(), NOT a discord.ext.tasks.loop — long-polling blocks for up
  to 25s per call, which doesn't fit tasks.loop's fixed-interval model
  well. The loop below is itself resilient: any single iteration
  failing (network blip, Telegram hiccup) is caught and logged, and the
  loop keeps going.
"""
import asyncio
import logging

import aiohttp

from . import config, database, ops_hub

logger = logging.getLogger("empire-bot.ops_poller")

_OFFSET_SETTING_KEY = "ops_poller_telegram_offset"
_POLL_TIMEOUT = 25  # seconds, Telegram long-poll timeout
_running = False


async def poll_for_replies(bot):
    """Long-polling loop for the Empire Ops bot's getUpdates.

    Call once, e.g. `asyncio.create_task(ops_poller.poll_for_replies(bot))`
    from on_ready(). Runs forever (or until the process exits); designed
    to survive individual request failures without dying.
    """
    global _running
    if _running:
        logger.warning("ops_poller: poll_for_replies() already running, refusing duplicate start")
        return
    _running = True
    logger.info("ops_poller: starting Telegram reply-forwarding poller")

    while True:
        try:
            if not config.OPS_BOT_TOKEN:
                # Ops bot not configured — nothing to poll. Sleep and
                # recheck periodically rather than busy-looping or
                # exiting outright (config could be added later without
                # a restart... well, it can't without a restart, but
                # this keeps the loop harmless either way).
                await asyncio.sleep(60)
                continue

            offset = int(database.get_setting(_OFFSET_SETTING_KEY, "0") or "0")
            updates = await _get_updates(offset)

            for update in updates:
                await _handle_update(update, bot)
                # Advance the offset past this update regardless of
                # whether handling succeeded — a getUpdates offset is
                # an acknowledgement mechanism, not a retry queue.
                # Failures inside _handle_update are already logged;
                # retrying the same update forever on a persistent
                # error (e.g. a malformed payload) would wedge the
                # whole poller.
                new_offset = update["update_id"] + 1
                database.set_setting(_OFFSET_SETTING_KEY, str(new_offset))

        except asyncio.CancelledError:
            logger.info("ops_poller: poll loop cancelled, shutting down")
            _running = False
            raise
        except Exception as e:
            logger.error(f"ops_poller: unexpected error in poll loop: {e}")
            await asyncio.sleep(5)


async def _get_updates(offset: int) -> list[dict]:
    """Call Telegram's getUpdates with long-polling. Returns [] on any
    failure (network error, bad token, etc.) rather than raising —
    the caller's loop handles retry timing."""
    url = f"https://api.telegram.org/bot{config.OPS_BOT_TOKEN}/getUpdates"
    params = {
        "offset": offset,
        "timeout": _POLL_TIMEOUT,
        "allowed_updates": '["message"]',
    }
    try:
        async with aiohttp.ClientSession() as session:
            # Client-side timeout must exceed Telegram's own long-poll
            # timeout, or we'll cancel the request right as Telegram is
            # about to respond with an empty result.
            async with session.get(
                url, params=params,
                timeout=aiohttp.ClientTimeout(total=_POLL_TIMEOUT + 10),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"ops_poller: getUpdates failed: {resp.status} — {body[:200]}")
                    return []
                data = await resp.json()
                return data.get("result", [])
    except asyncio.TimeoutError:
        # Normal — happens whenever nothing arrives within the poll
        # window. Not an error worth logging every time.
        return []
    except Exception as e:
        logger.error(f"ops_poller: getUpdates request error: {e}")
        return []


async def _handle_update(update: dict, bot) -> None:
    """Process a single Telegram update. Only cares about text message
    replies from the owner's chat; everything else is ignored (Phase
    M3 will extend this same dispatcher for /commands)."""
    message = update.get("message")
    if not message:
        return

    chat_id = str(message.get("chat", {}).get("id", ""))
    if chat_id != str(config.OPS_CHAT_ID):
        # Ignore messages from anyone/anywhere other than the owner's
        # configured chat — this bot is single-owner by design (see
        # design.md "Privacy" note).
        return

    text = message.get("text", "")
    if not text:
        return

    reply_to = message.get("reply_to_message")
    if not reply_to:
        # Not a reply to anything — Phase M3 will handle standalone
        # /commands here. For M2, only replies matter.
        return

    replied_msg_id = reply_to.get("message_id")
    await _handle_escalation_reply(replied_msg_id, text, bot)


async def _handle_escalation_reply(replied_msg_id: int, reply_text: str, bot) -> None:
    """Markaz M2.2-M2.4 — match a reply to a pending escalation, forward
    it to the student, and confirm success/failure back to the owner."""
    pending = database.get_pending_escalation(replied_msg_id)
    if not pending:
        # Reply to a message that isn't a tracked escalation (could be
        # an old/already-resolved one, or just an unrelated reply).
        # Silently ignore — don't confuse the owner with a notice for
        # every reply that isn't escalation-related.
        return

    discord_id = pending["discord_id"]
    student_name = pending.get("student_name") or discord_id

    from . import nour_escalation
    delivered = await nour_escalation.forward_reply_to_student(discord_id, reply_text, bot)

    if delivered:
        database.resolve_pending_escalation(replied_msg_id)
        await ops_hub.send_ops_alert(
            "Delivered",
            f"Your reply was delivered to {student_name}.",
            severity="success",
        )
        logger.info(f"ops_poller: forwarded owner reply to {student_name} ({discord_id})")
    else:
        # M2.4: do NOT resolve the escalation on failure — leave it
        # pending so the owner can see it's still outstanding in the
        # next daily digest, and so they know to try another channel.
        await ops_hub.send_ops_alert(
            "Delivery failed",
            f"Couldn't deliver to {student_name} — they may have DMs "
            f"off, left the server, or something else went wrong. "
            f"Check Discord directly if this is urgent.",
            severity="warning",
        )
        logger.warning(f"ops_poller: failed to forward owner reply to {student_name} ({discord_id})")
