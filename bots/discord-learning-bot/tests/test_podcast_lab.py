"""Tests for the Podcast Lab library (spec Phase 3).

The library is the owned, licence-cleared audio base the automatic pipeline reads.
These tests pin the two guarantees that matter:
  * the manifest and disk never silently diverge, and every asset is licensed +
    (for CC-BY) attributed — the licence gate cannot be bypassed;
  * the generator can ONLY be offered sounds that actually exist.
"""
import json

import pytest

from src import podcast_lab as lab


def test_categories_and_licence_policy_are_defined():
    assert set(lab.CATEGORIES) >= {"music", "ambience", "sfx", "sting", "voice"}
    # Only free licences are allowed, and share-alike is deliberately excluded.
    assert "CC0" in lab.ALLOWED_LICENCES
    assert "Public Domain" in lab.ALLOWED_LICENCES
    assert not any("SA" in x.upper() for x in lab.ALLOWED_LICENCES)
    # CC-BY needs attribution; CC0/PD do not.
    assert "CC-BY-4.0" in lab.ATTRIBUTION_REQUIRED
    assert "CC0" not in lab.ATTRIBUTION_REQUIRED


def test_the_shipped_library_is_healthy():
    """Whatever is committed must pass validation: every file listed, licensed,
    described, and (for CC-BY) attributed; no orphan files on disk."""
    problems = lab.validate()
    assert problems == [], f"library has problems: {problems}"


def test_manifest_parses_and_entries_are_well_formed():
    for a in lab.all_assets():
        assert a["category"] in lab.CATEGORIES
        assert a["licence"] in lab.ALLOWED_LICENCES
        assert a.get("description")
        assert lab.resolve_path(a).exists(), f"{a['file']} missing on disk"
        if a["licence"] in lab.ATTRIBUTION_REQUIRED:
            assert a.get("attribution"), f"{a['file']} is CC-BY but has no attribution"


def test_validate_catches_a_missing_file(tmp_path, monkeypatch):
    """A manifest entry with no file on disk must be reported."""
    fake = {"version": 1, "assets": [
        {"file": "ghost.ogg", "category": "sfx", "description": "x",
         "tags": [], "licence": "CC0", "attribution": ""}]}
    monkeypatch.setattr(lab, "_load", lambda: fake)
    problems = lab.validate()
    assert any("missing on disk" in p for p in problems)


def test_validate_catches_a_disallowed_licence(monkeypatch):
    fake = {"version": 1, "assets": [
        {"file": "x.ogg", "category": "sfx", "description": "x", "tags": [],
         "licence": "All Rights Reserved", "attribution": ""}]}
    monkeypatch.setattr(lab, "_load", lambda: fake)
    assert any("not in allowed set" in p for p in lab.validate())


def test_validate_requires_attribution_for_cc_by(monkeypatch):
    fake = {"version": 1, "assets": [
        {"file": "x.ogg", "category": "music", "description": "x", "tags": [],
         "licence": "CC-BY-4.0", "attribution": ""}]}
    monkeypatch.setattr(lab, "_load", lambda: fake)
    assert any("requires an attribution" in p for p in lab.validate())


def test_sfx_names_are_derived_from_the_manifest():
    """The generator's legal SFX vocabulary comes from the library, so it can never
    request an effect that does not exist (the old invented-[SFX:wind] bug)."""
    names = lab.sfx_names()
    assert isinstance(names, list)
    # Every SFX asset's stem is offered as a legal name.
    for a in lab.assets_in("sfx"):
        import pathlib
        assert pathlib.Path(a["file"]).stem.lower() in names


def test_required_attributions_only_lists_cc_by(monkeypatch):
    fake = {"version": 1, "assets": [
        {"file": "a.ogg", "category": "sfx", "description": "a", "tags": [],
         "licence": "CC0", "attribution": ""},
        {"file": "b.ogg", "category": "music", "description": "b", "tags": [],
         "licence": "CC-BY-4.0", "attribution": "Music by X, CC-BY 4.0"}]}
    monkeypatch.setattr(lab, "_load", lambda: fake)
    attrs = lab.required_attributions(fake["assets"])
    assert attrs == ["Music by X, CC-BY 4.0"]


def test_stats_are_serialisable():
    json.dumps(lab.stats())
