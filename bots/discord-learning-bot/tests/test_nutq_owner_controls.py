"""Nutq owner controls (PR3): WHO (feature-flag allowlist) + HOW MANY
(per-student daily cap), driven from Telegram /nutq and Discord /nutq.

Unit-tests the generic feature-flag grant/revoke/status helpers, the Telegram
command flows, and that the Discord /nutq slash group is registered.
"""
import pytest

from src import database, config, ops_commands

FLAG = "tatawwur_pronunciation"


@pytest.fixture
def clean_flag():
    database.set_feature_flag(FLAG, enabled=False, updated_by="test")
    yield
    database.set_feature_flag(FLAG, enabled=False, updated_by="test")


# ── feature-flag allowlist helpers (WHO) ───────────────────────────────────
def test_flag_status_default(clean_flag):
    st = database.feature_flag_status(FLAG)
    assert st["enabled"] is False and st["everyone"] is False and st["allowed_ids"] == set()


def test_grant_revoke_flow(clean_flag):
    assert database.feature_flag_grant(FLAG, "111", "t") == "granted"
    assert database.is_feature_enabled(FLAG, "111") is True
    assert database.is_feature_enabled(FLAG, "222") is False        # allowlist restricts
    assert database.feature_flag_grant(FLAG, "111", "t") == "already"
    assert database.feature_flag_grant(FLAG, "222", "t") == "granted"
    assert database.feature_flag_status(FLAG)["allowed_ids"] == {"111", "222"}
    assert database.feature_flag_revoke(FLAG, "111", "t") == "revoked"
    assert database.is_feature_enabled(FLAG, "111") is False
    assert database.is_feature_enabled(FLAG, "222") is True
    # removing the LAST student turns the flag off (never silently opens to all)
    assert database.feature_flag_revoke(FLAG, "222", "t") == "revoked_now_off"
    assert database.feature_flag_status(FLAG)["enabled"] is False


def test_everyone_semantics(clean_flag):
    database.set_feature_flag(FLAG, enabled=True, allowed_ids="", updated_by="t")
    assert database.feature_flag_status(FLAG)["everyone"] is True
    assert database.is_feature_enabled(FLAG, "999") is True         # anyone
    assert database.feature_flag_grant(FLAG, "333", "t") == "everyone"   # no-op
    assert database.feature_flag_revoke(FLAG, "333", "t") == "everyone"  # can't remove one


def test_revoke_not_present(clean_flag):
    database.feature_flag_grant(FLAG, "111", "t")
    assert database.feature_flag_revoke(FLAG, "222", "t") == "not_present"


# ── Telegram /nutq flows (WHO + HOW MANY) ──────────────────────────────────
class _FakeBot:
    def is_ready(self):
        return True

    guilds = []


@pytest.mark.asyncio
async def test_telegram_nutq_grant_cap_revoke(clean_flag):
    database.register_member("770001", "Telegram Nutq Test")
    bot = _FakeBot()

    out = await ops_commands.handle_nutq("grant 770001", bot)
    assert "Granted" in out
    assert database.is_feature_enabled(FLAG, "770001") is True

    out = await ops_commands.handle_nutq("cap 770001 3", bot)
    assert "3" in out
    assert database.nutq_daily_cap_override("770001") == 3

    out = await ops_commands.handle_nutq("cap 770001 default", bot)
    assert database.nutq_daily_cap_override("770001") is None

    out = await ops_commands.handle_nutq("revoke 770001", bot)
    assert database.is_feature_enabled(FLAG, "770001") is False

    status = await ops_commands.handle_nutq("", bot)
    assert "Nutq" in status


@pytest.mark.asyncio
async def test_telegram_nutq_everyone_off(clean_flag):
    bot = _FakeBot()
    await ops_commands.handle_nutq("everyone", bot)
    assert database.feature_flag_status(FLAG)["everyone"] is True
    await ops_commands.handle_nutq("off", bot)
    assert database.feature_flag_status(FLAG)["enabled"] is False


@pytest.mark.asyncio
async def test_telegram_nutq_cap_rejects_huge(clean_flag):
    database.register_member("770002", "Cap Guard Test")
    bot = _FakeBot()
    out = await ops_commands.handle_nutq("cap 770002 999", bot)
    assert "20" in out                                # guarded
    assert database.nutq_daily_cap_override("770002") is None  # not set


# ── Discord /nutq slash group is registered ────────────────────────────────
def test_discord_nutq_slash_group_registered():
    from src import bot as botmod
    grp = botmod.bot.tree.get_command("nutq")
    assert grp is not None
    subs = {c.name for c in grp.commands}
    assert {"status", "grant", "revoke", "everyone", "off", "cap", "capreset"} <= subs
