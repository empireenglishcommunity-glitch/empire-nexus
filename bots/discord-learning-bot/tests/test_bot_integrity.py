"""Hissar — tests for bot-profile tamper detection (src/bot_integrity.py).

This is a security monitor born from the 2026-08-29 Ops-token theft, so it is
tested for both directions of failure that matter:
  - it MUST fire on the exact tampering that happened (spam bio, renamed bot);
  - it MUST NOT fire on a clean profile or on a transient API error (a monitor
    that cries wolf gets muted, and then the next real incident runs for days).
"""
import asyncio

import pytest

from src import bot_integrity as bi
from src import flag_registry


def _run(coro):
    return asyncio.run(coro)


# ============================================================
#  PURE evaluation — the security logic
# ============================================================

def test_clean_ops_profile_has_no_findings():
    findings = bi.evaluate_ops_profile(
        bi.OPS_EXPECTED_NAME, bi.OPS_EXPECTED_DESCRIPTION, bi.OPS_EXPECTED_SHORT_DESCRIPTION)
    assert findings == []


def test_the_actual_2026_08_29_spam_bio_is_caught():
    """The real incident: description rewritten to a vibeapps spam link."""
    spam = ("🤖 Free ChatGPT, Claude, Gemini: "
            "👉 https://t.me/vibeapps_bot?start=ref_c3966075e4")
    findings = bi.evaluate_ops_profile(bi.OPS_EXPECTED_NAME, spam,
                                       bi.OPS_EXPECTED_SHORT_DESCRIPTION)
    assert findings, "the spam description that actually happened must be flagged"
    # both the drift AND the spam signature should register
    assert any("DESCRIPTION changed" in f for f in findings)
    assert any("spam signature" in f for f in findings)


def test_renamed_ops_bot_is_caught():
    findings = bi.evaluate_ops_profile("Free AI Bot", bi.OPS_EXPECTED_DESCRIPTION,
                                       bi.OPS_EXPECTED_SHORT_DESCRIPTION)
    assert any("NAME changed" in f for f in findings)


def test_any_url_in_ops_bio_is_suspicious():
    """This bot's legitimate bio contains no links, so a bare URL is a signal."""
    findings = bi.evaluate_ops_profile(
        bi.OPS_EXPECTED_NAME, bi.OPS_EXPECTED_DESCRIPTION, "visit https://example.com now")
    assert any("spam signature" in f for f in findings)


def test_none_fields_are_skipped_not_flagged():
    """A partial API read (field=None) must never look like tampering."""
    assert bi.evaluate_ops_profile(None, None, None) == []
    assert bi.evaluate_ops_profile(bi.OPS_EXPECTED_NAME, None, None) == []


def test_clean_discord_identity_has_no_findings():
    assert bi.evaluate_discord_identity(bi.DISCORD_EXPECTED_USERNAME, None) == []


def test_renamed_discord_bot_is_caught():
    findings = bi.evaluate_discord_identity("Hacked Bot", None)
    assert any("USERNAME changed" in f for f in findings)


def test_spam_scan_is_case_insensitive():
    assert bi._scan_for_spam("x", "VIBEBUILD.PRO") != []
    assert bi._scan_for_spam("x", "") == []


# ============================================================
#  ASYNC wrappers — fail SAFE on transient errors
# ============================================================

def test_ops_check_returns_ok_when_token_absent(monkeypatch):
    monkeypatch.setattr(bi.config, "OPS_BOT_TOKEN", "")
    ok, findings = _run(bi.check_ops_bot_profile())
    assert ok is True and findings == []


def test_ops_check_ok_when_all_api_calls_fail(monkeypatch):
    """All three fetches failing = transient outage, NOT a tamper alert."""
    monkeypatch.setattr(bi.config, "OPS_BOT_TOKEN", "x:y")

    async def _all_fail(session, token, method):
        return None
    monkeypatch.setattr(bi, "_tg_get", _all_fail)
    ok, findings = _run(bi.check_ops_bot_profile())
    assert ok is True and findings == []


def test_ops_check_flags_tampering_via_fetch(monkeypatch):
    monkeypatch.setattr(bi.config, "OPS_BOT_TOKEN", "x:y")

    async def _fake(session, token, method):
        return {
            "getMyName": {"name": "Empire Ops"},
            "getMyDescription": {"description": "buy now http://t.me/vibeapps_bot"},
            "getMyShortDescription": {"short_description": bi.OPS_EXPECTED_SHORT_DESCRIPTION},
        }[method]
    monkeypatch.setattr(bi, "_tg_get", _fake)
    ok, findings = _run(bi.check_ops_bot_profile())
    assert ok is False
    assert any("spam signature" in f for f in findings)


def test_ops_check_ok_on_clean_fetch(monkeypatch):
    monkeypatch.setattr(bi.config, "OPS_BOT_TOKEN", "x:y")

    async def _clean(session, token, method):
        return {
            "getMyName": {"name": bi.OPS_EXPECTED_NAME},
            "getMyDescription": {"description": bi.OPS_EXPECTED_DESCRIPTION},
            "getMyShortDescription": {"short_description": bi.OPS_EXPECTED_SHORT_DESCRIPTION},
        }[method]
    monkeypatch.setattr(bi, "_tg_get", _clean)
    ok, findings = _run(bi.check_ops_bot_profile())
    assert ok is True and findings == []


# ============================================================
#  Flag registration (steering §6: a feature = a registered flag)
# ============================================================

def test_flag_registered_and_defaults_off():
    entry = next((e for e in flag_registry.REGISTRY if e[0] == "hissar_bot_integrity"), None)
    assert entry is not None, "hissar_bot_integrity must be in the registry"
    assert entry[2] == "hissar"
    assert entry[3] is False, "must ship default-OFF (fail-closed); enabled live + recorded"
