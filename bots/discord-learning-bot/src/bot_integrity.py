"""Hissar — bot-profile tamper detection.

WHY THIS EXISTS
---------------
On 2026-08-29 the Empire Ops Telegram bot's token was stolen and used to rewrite
its public description with spam (a "probiv" data-lookup service). A stolen token
lets an attacker change the bot's name/description/bio and post as the bot — all
via token-only API calls, with no server access. The damage in that incident was
limited only because the attacker chose to spam rather than disrupt.

The worst part was **it went unnoticed for ~4 days.** Nothing watched the bot's
public identity, so the compromise was discovered by a human noticing spam, not by
any alarm.

This module closes that gap. It compares each bot's *current* public identity
against its known-good baseline and scans for spam signatures, so any future
tampering is caught within hours and alerted to the owner over the existing Empire
Ops channel — the moment a profile drifts, not days later by accident.

It is deliberately simple and dependency-free (aiohttp only), never raises, and is
gated behind the `hissar_bot_integrity` flag.

KNOWN-GOOD BASELINES
--------------------
These are the canonical, verified-clean values (captured 2026-08-29 after the
spam was removed). **If the owner ever legitimately changes a bot's name or bio,
update the matching constant here in the same change** — otherwise this monitor
will (correctly) flag the change as tampering.
"""
import logging
from typing import Optional

import aiohttp

from . import config

logger = logging.getLogger("empire-bot.bot_integrity")

# --- Empire Ops (Telegram) canonical profile -------------------------------
OPS_EXPECTED_NAME = "Empire Ops"
OPS_EXPECTED_DESCRIPTION = (
    "Empire English Community — owner operations bot. "
    "Digests, alerts and admin commands. Private use only."
)
OPS_EXPECTED_SHORT_DESCRIPTION = (
    "Empire English Community operations bot. Owner use only."
)

# --- Empire English Bot (Discord) canonical identity -----------------------
DISCORD_EXPECTED_USERNAME = "Empire English Bot"

# --- Spam signatures (defense in depth) ------------------------------------
# THIS family of bots' legitimate profiles contain NO URLs at all, so the mere
# presence of a link is itself a strong tamper signal. Plus the specific strings
# from the 2026-08-29 incident, and generic promo/lookup-spam markers.
_SPAM_SIGNATURES = (
    "http://", "https://", "t.me/", "www.",
    "vibeapps", "vibebuild", "c3966075e4",
    "chatgpt", "free ai", "пробив", "probiv", "бот",
)

_TG_API = "https://api.telegram.org"
_DISCORD_API = "https://discord.com/api/v10"


def _scan_for_spam(field_name: str, value: str) -> list[str]:
    """Return findings if `value` contains any spam signature. Case-insensitive."""
    if not value:
        return []
    low = value.lower()
    hits = [sig for sig in _SPAM_SIGNATURES if sig in low]
    if hits:
        return [f"{field_name} contains spam signature(s): {', '.join(hits)}"]
    return []


# --- PURE evaluation (no I/O — the security logic, unit-tested directly) ----

def evaluate_ops_profile(name: Optional[str], description: Optional[str],
                         short_description: Optional[str]) -> list[str]:
    """Compare a fetched Ops (Telegram) profile against baseline + scan for spam.
    A None field means 'could not read this field' and is skipped (not a finding),
    so a partial API failure never masquerades as tampering. Pure/testable."""
    findings: list[str] = []
    if name is not None:
        if name != OPS_EXPECTED_NAME:
            findings.append(f"Ops bot NAME changed: {name!r} (expected {OPS_EXPECTED_NAME!r})")
        findings += _scan_for_spam("Ops bot name", name)
    if description is not None:
        if description != OPS_EXPECTED_DESCRIPTION:
            findings.append("Ops bot DESCRIPTION changed from the approved text")
        findings += _scan_for_spam("Ops bot description", description)
    if short_description is not None:
        if short_description != OPS_EXPECTED_SHORT_DESCRIPTION:
            findings.append("Ops bot SHORT DESCRIPTION changed from the approved text")
        findings += _scan_for_spam("Ops bot short description", short_description)
    return findings


def evaluate_discord_identity(username: Optional[str],
                             global_name: Optional[str]) -> list[str]:
    """Compare a fetched Discord identity against baseline + scan for spam. Pure."""
    findings: list[str] = []
    if username is not None:
        if username != DISCORD_EXPECTED_USERNAME:
            findings.append(
                f"Discord bot USERNAME changed: {username!r} "
                f"(expected {DISCORD_EXPECTED_USERNAME!r})")
        findings += _scan_for_spam("Discord bot username", username)
    findings += _scan_for_spam("Discord bot global_name", global_name or "")
    return findings


async def _tg_get(session: aiohttp.ClientSession, token: str, method: str) -> Optional[dict]:
    """Call a Telegram Bot API method, return its 'result' dict or None."""
    url = f"{_TG_API}/bot{token}/{method}"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
        if resp.status != 200:
            body = await resp.text()
            logger.warning("bot_integrity: %s -> HTTP %s (%s)", method, resp.status, body[:120])
            return None
        data = await resp.json()
        return data.get("result") if data.get("ok") else None


async def check_ops_bot_profile() -> tuple[bool, list[str]]:
    """Check the Empire Ops (Telegram) bot's public profile against baseline.

    Returns (ok, findings). ok is False if the name/description/short-description
    has drifted from the expected values OR contains a spam signature. Never
    raises — on a transient API/network error it returns (True, []) with a log
    line, because a failed *check* must not masquerade as a *tamper alert* (that
    would train the owner to ignore it). Genuine, repeated inability to read the
    profile shows up as the daily digest line going quiet, not as a false alarm.
    """
    if not config.OPS_BOT_TOKEN:
        return True, []
    findings: list[str] = []
    try:
        async with aiohttp.ClientSession() as session:
            name = await _tg_get(session, config.OPS_BOT_TOKEN, "getMyName")
            desc = await _tg_get(session, config.OPS_BOT_TOKEN, "getMyDescription")
            short = await _tg_get(session, config.OPS_BOT_TOKEN, "getMyShortDescription")

        if name is None and desc is None and short is None:
            logger.warning("bot_integrity: could not read Ops bot profile (all calls failed)")
            return True, []  # transient — not a tamper signal

        findings = evaluate_ops_profile(
            (name or {}).get("name") if name is not None else None,
            (desc or {}).get("description") if desc is not None else None,
            (short or {}).get("short_description") if short is not None else None,
        )
    except Exception as e:  # noqa: BLE001 — a monitor must never crash its caller
        logger.warning("bot_integrity: Ops profile check errored: %r", e)
        return True, []

    return (len(findings) == 0), findings


async def check_discord_identity() -> tuple[bool, list[str]]:
    """Check the Discord bot's own username against baseline (token-only tamper:
    an attacker with the Discord token can rename the bot). Returns (ok, findings);
    same never-false-alarm-on-transient-error contract as above."""
    if not config.DISCORD_TOKEN:
        return True, []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{_DISCORD_API}/users/@me",
                headers={"Authorization": f"Bot {config.DISCORD_TOKEN}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logger.warning("bot_integrity: Discord users/@me -> HTTP %s", resp.status)
                    return True, []
                me = await resp.json()
    except Exception as e:  # noqa: BLE001
        logger.warning("bot_integrity: Discord identity check errored: %r", e)
        return True, []

    findings = evaluate_discord_identity(me.get("username"), me.get("global_name"))
    return (len(findings) == 0), findings


async def run_integrity_check() -> tuple[bool, list[str]]:
    """Run every bot-identity check. Returns (all_ok, combined_findings)."""
    ops_ok, ops_f = await check_ops_bot_profile()
    dis_ok, dis_f = await check_discord_identity()
    return (ops_ok and dis_ok), (ops_f + dis_f)
