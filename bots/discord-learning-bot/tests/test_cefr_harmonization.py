"""Mi'yar System Harmonization — Step 1 foundation tests.

The whole system is moving from the legacy 4-level model (L0–L3) to the six
CEFR levels (A1–C2). These tests lock the SINGLE source of truth in config —
the resolvers every other module (displays, role assignment, daily-task
routing, practice API, setup script) must go through instead of hardcoding
L0–L3. If these hold, the later steps can safely swap call sites over.
"""
from src import config


# ============================================================
#  level_info — accepts BOTH key styles
# ============================================================

def test_level_info_resolves_all_cefr_levels():
    for lvl in config.CEFR_ORDER:
        info = config.level_info(lvl)
        assert info["cefr"] == lvl
        # Every field the old LEVELS dict exposed must exist on CEFR levels too,
        # so no display call site breaks when it switches to level_info().
        for field in ("name", "name_ar", "emoji", "color",
                      "speaking_target_seconds", "advancement_score", "title"):
            assert field in info, f"{lvl} missing '{field}'"


def test_level_info_resolves_legacy_keys_to_cefr():
    # Legacy keys still resolve (defensive: any un-migrated record won't crash).
    for legacy, cefr in config.LEGACY_LEVEL_MAP.items():
        info = config.level_info(legacy)
        assert info["cefr"] == cefr


def test_level_info_unknown_falls_back_to_a1():
    assert config.level_info("ZZ")["cefr"] == "A1"
    assert config.level_info("")["cefr"] == "A1"


# ============================================================
#  slug / display
# ============================================================

def test_level_slug():
    assert config.level_slug("A1") == "a1"
    assert config.level_slug("C2") == "c2"
    assert config.level_slug("L0") == "l0"  # legacy still lowercases
    assert config.level_slug("") == "a1"    # safe default


def test_level_display_contains_cefr_and_title():
    d = config.level_display("A1")
    assert "A1" in d and "Breakthrough" in d
    d2 = config.level_display("C2")
    assert "C2" in d2 and "Mastery" in d2


# ============================================================
#  role names
# ============================================================

def test_level_role_name_is_cefr_driven():
    # A1 role: emoji + CEFR code + arabic name, bilingual.
    name = config.level_role_name("A1")
    assert "A1" in name
    assert "مبتدئ" in name  # arabic name for A1
    # Legacy key maps to its CEFR role name (NOT the old "Level 0" string).
    assert config.level_role_name("L0") == config.level_role_name("A1")


def test_all_cefr_role_names_are_six_and_ordered():
    names = config.all_cefr_role_names()
    assert len(names) == 6
    # Ordered A1→C2: each CEFR code appears in the matching position.
    for i, lvl in enumerate(config.CEFR_ORDER):
        assert lvl in names[i]


def test_all_managed_role_names_include_legacy_for_cleanup():
    managed = config.all_managed_level_role_names()
    # 6 CEFR + 4 legacy = 10, so a stale legacy role can always be stripped.
    assert len(managed) == 10
    for legacy_name in config.LEGACY_ROLE_NAMES.values():
        assert legacy_name in managed
    # And every CEFR role is present too.
    for cefr_name in config.all_cefr_role_names():
        assert cefr_name in managed


def test_legacy_role_names_exact_strings_preserved():
    # These must match the exact pre-CEFR strings so Discord can find & remove
    # the real old roles during reassignment.
    assert config.LEGACY_ROLE_NAMES["L0"] == "🌱 Level 0 | مبتدئ"
    assert config.LEGACY_ROLE_NAMES["L3"] == "👑 Level 3 | طليق"


# ============================================================
#  progression + xp thresholds
# ============================================================

def test_next_cefr_level_chain():
    assert config.next_cefr_level("A1") == "A2"
    assert config.next_cefr_level("B2") == "C1"
    assert config.next_cefr_level("C2") is None  # top of the ladder
    # Legacy key maps first, then advances: L0->A1 -> next is A2.
    assert config.next_cefr_level("L0") == "A2"


def test_xp_thresholds_monotonic_and_start_at_zero():
    assert config.level_xp_threshold("A1") == 0
    thresholds = [config.level_xp_threshold(lvl) for lvl in config.CEFR_ORDER]
    assert thresholds == sorted(thresholds)  # strictly non-decreasing, ordered
    assert len(set(thresholds)) == 6         # all distinct
    # Legacy key resolves to its CEFR threshold.
    assert config.level_xp_threshold("L1") == config.level_xp_threshold("A2")



# ============================================================
#  Step 3 — practice-dashboard XP-progress contract
#  (locks the CEFR-aware math api_server.get_dashboard now uses, so a
#  migrated student is never measured against the old L0 thresholds again)
# ============================================================

def _dashboard_level_pct(level: str, total_points: int):
    """Replicates api_server.get_dashboard's CEFR level-progress block, so the
    behavior is unit-tested without spinning up the web server."""
    cefr = config.cefr_key(level)
    nxt = config.next_cefr_level(cefr)
    if nxt:
        cur_t = config.level_xp_threshold(cefr)
        nxt_t = config.level_xp_threshold(nxt)
        return min(100, round((total_points - cur_t) / max(nxt_t - cur_t, 1) * 100, 1)), nxt
    return 100, None


def test_dashboard_xp_progress_is_cefr_aware():
    # A1 student with 1000 pts: measured against A1(0)->A2(2000) = 50%.
    pct, nxt = _dashboard_level_pct("A1", 1000)
    assert nxt == "A2" and pct == 50.0
    # A migrated legacy 'L0' record behaves identically to A1 (no L0 thresholds).
    assert _dashboard_level_pct("L0", 1000) == _dashboard_level_pct("A1", 1000)
    # B1 student measured against B1(5000)->B2(10000), NOT treated as L0/index-0.
    pct_b1, nxt_b1 = _dashboard_level_pct("B1", 7500)
    assert nxt_b1 == "B2" and pct_b1 == 50.0


def test_dashboard_xp_progress_tops_out_at_c2():
    # Top of the ladder: no next level -> full bar, never "stuck at L0".
    pct, nxt = _dashboard_level_pct("C2", 40000)
    assert pct == 100 and nxt is None
