#!/usr/bin/env python3.12
"""Source Podcast Lab assets from archive.org (spec Phase 3 — task 3.5).

archive.org is reachable + un-throttled from the build sandbox (unlike Wikimedia's
media host), and hosts CC0 / public-domain / CC-BY audio with verifiable licence
metadata. This pulls from HAND-PICKED, licence-verified collections into the library
via podcast_lab_tool (which normalises loudness + registers each asset).

Curation is explicit: each collection lists exactly which files to take, the tags
they get, and their story situation — so nothing violent or off-tone lands in a
learner podcast, and every asset's licence + attribution is recorded.

Usage
-----
    python3.12 scripts/source_archive_org.py            # ingest the curated plan
    python3.12 scripts/source_archive_org.py --dry-run  # list without downloading
"""
import argparse
import json
import pathlib
import subprocess
import sys
import time
import urllib.parse
import urllib.request

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
UA = {"User-Agent": "empire-eec-podcast-lab/1.0 (educational; EEC)"}

# ── Curated, licence-verified collections ────────────────────────────────────
# William Dyer Sound Effects Library — CC-BY 2.5, single author (one clean
# attribution). Story-relevant, learner-appropriate picks only (violent effects
# deliberately excluded). (item file-stem, category, tags, description)
DYER = {
    "item": "WilliamDyerSoundEffectsLibrary",
    "licence": "CC-BY-3.0",   # normalised bucket; actual is CC-BY 2.5 (recorded in attribution)
    "attribution": "Sound effects by William Dyer (archive.org), CC-BY 2.5",
    "picks": [
        ("creeking_door", "sfx", ["creak", "door"], "Door creaking open"),
        ("door_slamming", "sfx", ["slam", "door"], "Door slamming shut"),
        ("stone_door", "sfx", ["door", "stone", "eerie"], "Heavy stone door"),
        ("creaking", "sfx", ["creak", "eerie"], "Wood creaking"),
        ("footsteps_wood", "sfx", ["footsteps", "wood"], "Footsteps on wood"),
        ("footsteps_grass", "sfx", ["footsteps", "grass", "nature"], "Footsteps on grass"),
        ("footsteps_cement", "sfx", ["footsteps", "street"], "Footsteps on pavement"),
        ("ticking_clock", "sfx", ["clock", "ticking", "tension"], "Clock ticking"),
        ("crackling_fire", "sfx", ["fire", "warm"], "Crackling fire"),
        ("rain", "ambience", ["rain", "sad"], "Rain"),
        ("thunder", "sfx", ["thunder", "storm"], "Thunder"),
        ("tornado", "ambience", ["wind", "storm", "tension"], "Strong wind / storm"),
        ("roar", "sfx", ["roar", "monster", "tension"], "A loud roar"),
        ("crash", "sfx", ["crash", "impact"], "A crash"),
        ("small_glass_shattering", "sfx", ["glass", "break"], "Glass shattering"),
        ("window_shattering", "sfx", ["glass", "window", "break"], "Window breaking"),
        ("glasses_hitting", "sfx", ["glass", "clink"], "Glasses clinking"),
        ("horse_hooves", "sfx", ["horse", "hooves"], "Horse hooves"),
        ("metal_scratching", "sfx", ["metal", "scratch", "eerie"], "Metal scratching"),
        ("slap", "sfx", ["slap", "impact"], "A slap"),
        ("scratching", "sfx", ["scratch", "eerie"], "Scratching sound"),
    ],
}


def _get(url, binary=False):
    for a in range(4):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                       timeout=90)
            return r.read() if binary else json.load(r)
        except Exception as e:                                   # noqa: BLE001
            if a < 3:
                time.sleep(4 * (a + 1))
                continue
            raise


def run(dry_run=False):
    item = DYER["item"]
    meta = _get(f"https://archive.org/metadata/{item}")
    have = {f["name"] for f in meta.get("files", [])}
    lic_url = meta.get("metadata", {}).get("licenseurl", "")
    print(f"archive.org item {item}\n  licence: {lic_url}")
    if "creativecommons.org/licenses/by" not in lic_url and \
       "publicdomain" not in lic_url:
        print("  ❌ licence is not CC-BY / public-domain — refusing to source")
        return 0

    got = 0
    for stem, category, tags, desc in DYER["picks"]:
        fname = f"{stem}.ogg"
        if fname not in have:
            print(f"  (skip {stem}: no .ogg in item)")
            continue
        print(f"  ✓ [{category}] {stem}  {tags}")
        if dry_run:
            got += 1
            continue
        url = (f"https://archive.org/download/{item}/"
               + urllib.parse.quote(fname))
        raw = BOT_DIR / f"_arc_{stem}.ogg"
        try:
            raw.write_bytes(_get(url, binary=True))
        except Exception as e:                                   # noqa: BLE001
            print(f"    download failed: {e}")
            continue
        cmd = [sys.executable, str(BOT_DIR / "scripts" / "podcast_lab_tool.py"),
               "ingest", "--src", str(raw), "--category", category,
               "--name", stem, "--description", desc,
               "--tags", ",".join(tags),
               "--source", f"archive.org — {item} — {fname}",
               "--licence", DYER["licence"], "--attribution", DYER["attribution"]]
        r = subprocess.run(cmd, capture_output=True, text=True)
        raw.unlink(missing_ok=True)
        if r.returncode == 0:
            got += 1
            print(f"    {r.stdout.strip()}")
        else:
            print(f"    ingest failed: {r.stderr.strip()[:120]}")
        time.sleep(1)
    print(f"\n  sourced {got} asset(s){' (dry run)' if dry_run else ''}")
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.parse_args()
    run(dry_run=ap.parse_args().dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
