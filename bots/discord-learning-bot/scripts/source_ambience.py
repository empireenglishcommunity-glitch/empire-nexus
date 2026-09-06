#!/usr/bin/env python3.12
"""Source room-tone / environment ambiences for the Podcast Lab.

Pulls from the CC0 "SSE Library: AMBIENCE" item on archive.org (verified
publicdomain/zero dedication — commercial use OK, no attribution required) and trims
each to a ~30s lo-able bed. Environments are curated for a learner story podcast
(markets, schools, seaside, farm, café…), skipping warfare/riot/prison tones.

Resumable via --limit N (downloads are slow); re-run to continue.
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

ITEM = "SSE_Library_AMBIENCE"
LICENCE = "CC0"

# (exact file path on item, ingest name, tags/moods)
PICKS = [
    ("FARM/AMBFarm_Barnyard bg_CS_USC.mp3", "amb_farmyard", ["farm", "rural", "warm"]),
    ("HISTORICAL/AMBHist_Western street background with horses; wagons;_CS_USC.mp3",
     "amb_old_town_street", ["historical", "town", "adventure"]),
    ("MARKET/AMBMrkt_Street market in Marrakesh_CS_USC.mp3",
     "amb_market", ["market", "busy", "adventure", "mystery"]),
    ("OFFICE/AMBOffc_Movement in indoor space; office or waiting_CS_USC.mp3",
     "amb_indoor_room", ["indoor", "room", "calm"]),
    ("RESTAURANT & BAR/AMBRest_Banquet crowd walla; outdoors or large quiet_CS_USC.mp3",
     "amb_cafe_walla", ["cafe", "crowd", "warm"]),
    ("SCHOOL/AMBSchl_High school students walla in hallway 2_CS_USC.mp3",
     "amb_school_hallway", ["school", "crowd", "busy"]),
    ("SEASIDE/AMBSea_Water background; urban noise in background_CS_USC.mp3",
     "amb_seaside", ["seaside", "water", "calm"]),
    ("TROPICAL/AMBTrop_Jungle background 1_CS_USC.mp3",
     "amb_jungle", ["jungle", "nature", "wonder"]),
    ("PUBLIC PLACE/AMBPubl_Courtroom murmur and mild surprise; multiple_CS_USC.mp3",
     "amb_hall_murmur", ["hall", "crowd", "tension"]),
    ("CELEBRATION/AMBCele_New Year?s Eve party crowd; much laughter_CS_USC.mp3",
     "amb_party", ["party", "crowd", "hopeful", "playful"]),
    ("RELIGIOUS/AMBRlgn_Church reactions 1_CS_USC.mp3",
     "amb_church_hall", ["hall", "quiet", "wonder"]),
    ("NAUTICAL/AMBNaut_Water background; multiple ships? whistles_CS_USC.mp3",
     "amb_harbour", ["harbour", "water", "adventure"]),
]
BED_SECONDS = 30.0
START_SECONDS = 5.0


def _metadata():
    m = urllib.request.urlopen(urllib.request.Request(
        f"https://archive.org/metadata/{ITEM}", headers=UA), timeout=60)
    return json.loads(m.read())


def _download(fname, servers, dir_, dest):
    last = ""
    for srv in servers:
        url = f"https://{srv}{dir_}/" + urllib.parse.quote(fname)
        for _ in range(2):
            try:
                data = urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=240).read()
                if len(data) < 4096:
                    last = f"too small ({len(data)}b)"; continue
                dest.write_bytes(data)
                return True
            except Exception as e:                              # noqa: BLE001
                last = str(e)[:80]
                time.sleep(1.5)
    print(f"    download failed: {last}")
    return False


def run(dry_run=False, limit=None):
    d = _metadata()
    lic = d.get("metadata", {}).get("licenseurl", "")
    servers = d.get("workable_servers") or [d.get("server")]
    dir_ = d.get("dir", "")
    have = {f["name"] for f in d.get("files", [])}
    print(f"archive.org item {ITEM}\n  licence: {lic}\n  servers: {servers}")
    if "publicdomain/zero" not in lic:
        print("  ❌ not CC0 — refusing"); return 0

    import numpy as np
    import librosa
    import soundfile as sf
    amb_dir = BOT_DIR / "content" / "podcast-lab" / "ambience"
    got = 0
    for fpath, name, tags in PICKS:
        if (amb_dir / f"{name}.ogg").exists() and not dry_run:
            continue
        if limit is not None and got >= limit:
            print(f"  (limit {limit} reached — resume by re-running)"); break
        if fpath not in have:
            print(f"  (skip: not on item: {fpath})"); continue
        print(f"  ✓ ambience [{','.join(tags)}] <- {fpath.split('/')[-1][:45]}")
        if dry_run:
            got += 1; continue
        raw = BOT_DIR / f"_amb_{got}.mp3"
        if not _download(fpath, servers, dir_, raw):
            continue
        try:
            y, sr = librosa.load(str(raw), sr=24000, mono=True)
            a = int(START_SECONDS * sr)
            b = a + int(BED_SECONDS * sr)
            if b > len(y):
                a, b = 0, min(len(y), int(BED_SECONDS * sr))
            y = y[a:b].astype("float32")
            trimmed = BOT_DIR / f"_ambcut_{got}.ogg"
            sf.write(str(trimmed), y, sr, format="OGG", subtype="VORBIS")
        except Exception as e:                                  # noqa: BLE001
            print(f"    trim failed: {e!r}"); raw.unlink(missing_ok=True); continue
        cmd = [sys.executable, str(BOT_DIR / "scripts" / "podcast_lab_tool.py"),
               "ingest", "--src", str(trimmed), "--category", "ambience",
               "--name", name,
               "--description", f"Environment ambience: {tags[0]}",
               "--tags", ",".join(tags),
               "--source", f"archive.org — {ITEM} — {fpath}", "--licence", LICENCE]
        r = subprocess.run(cmd, capture_output=True, text=True)
        raw.unlink(missing_ok=True)
        trimmed.unlink(missing_ok=True)
        if r.returncode == 0:
            got += 1; print(f"    {r.stdout.strip()}")
        else:
            print(f"    ingest failed: {r.stderr.strip()[:160]}")
        time.sleep(1)
    print(f"\n  sourced {got} ambience(s){' (dry run)' if dry_run else ''}")
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    run(dry_run=a.dry_run, limit=a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
