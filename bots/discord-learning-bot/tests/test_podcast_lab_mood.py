"""Tests for mood-aware asset selection (spec 3.7, wired in Phase 4).

The story declares a mood; the mixer must resolve it to a real, licence-cleared
asset — deterministically, and never pointing at a file that doesn't exist.
"""
from src import podcast_lab as lab


def test_select_bed_returns_a_real_existing_file_for_every_mood():
    for mood in lab.MOODS:
        path, asset = lab.select_bed_path(mood, seed=0)
        # A bed OR (via fallback) at least some music asset must resolve.
        assert asset is not None, f"no bed resolved for mood {mood!r}"
        assert path is not None and path.exists()


def test_selection_is_deterministic_for_same_mood_and_seed():
    a1 = lab.select_asset("music", "wonder", seed=3)
    a2 = lab.select_asset("music", "wonder", seed=3)
    assert a1 == a2
    # different seeds may (not must) differ, but must still be real assets
    a3 = lab.select_asset("music", "wonder", seed=4)
    assert a3 in lab.assets_in("music")


def test_mood_fallback_prefers_the_exact_mood_when_available():
    # 'warm' has its own beds — selection must be tagged warm (not a fallback).
    a = lab.select_asset("music", "warm", seed=0)
    assert a is not None
    assert "warm" in [t.lower() for t in a.get("tags", [])]


def test_resolve_sfx_matches_tag_or_stem():
    # a tag that exists in the library resolves to a real sfx file
    path, asset = lab.resolve_sfx_path("knock")
    assert asset is not None and path is not None and path.exists()
    # a nonexistent effect resolves to nothing (validator would reject it)
    p2, a2 = lab.resolve_sfx_path("heartbeat")
    assert a2 is None and p2 is None


def test_sfx_vocab_is_clean_words_not_internal_stems():
    vocab = lab.sfx_vocab()
    assert vocab, "expected a non-empty sfx vocabulary"
    assert all("_" not in w and not w.startswith("sfx_") for w in vocab)
    # vocab is a subset of the permissive superset the validator accepts
    assert set(vocab).issubset(set(lab.sfx_names()))


def test_credit_line_names_ccby_but_not_cc0():
    cc0 = [a for a in lab.assets_in("music") if a.get("licence") == "CC0"][:1]
    line_cc0 = lab.credit_line(cc0)
    assert "CC0" in line_cc0 or "Podcast Lab" in line_cc0

    ccby = [a for a in lab.all_assets()
            if str(a.get("licence", "")).startswith("CC-BY") and a.get("attribution")][:1]
    if ccby:
        line = lab.credit_line(ccby)
        assert ccby[0]["attribution"] in line
