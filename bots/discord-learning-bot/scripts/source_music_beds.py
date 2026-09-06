#!/usr/bin/env python3.12
"""Source music beds for the Podcast Lab from archive.org CC0 collections.

Commercial-safe music (CC0 / public-domain / CC-BY, NOT NonCommercial — EEC is a
paid community) is scarce, so this pulls from a verified CC0 ambient collection and
trims each track to a ~45s bed. Curated: a few VARIED tracks mapped to moods, not a
dozen near-identical ones.

Robustness notes:
  * archive.org filenames on this item carry UUID suffixes, so we match by a stable
    stem ("Calm_Pill_<n>_") against the item METADATA rather than guessing names.
  * We download from the item's actual server+dir (metadata) instead of the flaky
    /download/<item>/<file> redirect, which 404s for some derivative files.
  * Each download is retried across the item's workable_servers.
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

# archive.org item "CalmPills" — CC0 (public domain dedication): no attribution
# required, commercial use OK. Verified licenseurl = publicdomain/zero/1.0.
ITEM = "CalmPills"
LICENCE = "CC0"

# (stable stem to match in metadata, moods) — chosen for variety across the palette.
PICKS = [
    ("Calm_Pill_1_", ["calm", "warm"]),
    ("Calm_Pill_11_", ["hopeful", "calm"]),
    ("Calm_Pill_12_", ["wonder", "warm"]),
    ("Calm_Pill_15_", ["sad"]),
    ("Calm_Pill_16_", ["wonder", "eerie"]),
    ("Calm_Pill_18_", ["hopeful"]),
    ("Calm_Pill_21_", ["hopeful", "wonder", "triumph"]),
    ("Calm_Pill_22_", ["sad", "wonder"]),
    ("Calm_Pill_27_", ["mystery", "eerie"]),
    ("Calm_Pill_46_", ["warm", "calm", "playful"]),
    ("Calm_Pill_60_", ["warm", "hopeful", "triumph"]),
    ("Calm_Pill_69_", ["adventure", "wonder"]),
    ("Calm_Pill_78_", ["eerie", "wonder"]),
    ("Calm_Pill_80_", ["calm", "sad"]),
]
BED_SECONDS = 45.0


def _metadata():
    m = urllib.request.urlopen(urllib.request.Request(
        f"https://archive.org/metadata/{ITEM}", headers=UA), timeout=60)
    return json.loads(m.read())


def _download(fname, servers, dir_, dest):
    """Try each workable server's direct path; return True on success."""
    last = ""
    for srv in servers:
        url = f"https://{srv}{dir_}/" + urllib.parse.quote(fname)
        for attempt in range(2):
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
    names = [f["name"] for f in d.get("files", []) if f["name"].endswith(".mp3")]
    print(f"archive.org item {ITEM}\n  licence: {lic}\n  servers: {servers}")
    if "publicdomain/zero" not in lic:
        print("  ❌ not CC0 — refusing"); return 0

    import numpy as np
    import librosa
    import soundfile as sf
    music_dir = BOT_DIR / "content" / "podcast-lab" / "music"
    got = 0
    for i, (stem, moods) in enumerate(PICKS, 1):
        name = f"calm_{'_'.join(moods)}_{i}"
        # resumable: skip picks already ingested to disk
        if (music_dir / f"{name}.ogg").exists() and not dry_run:
            continue
        if limit is not None and got >= limit:
            print(f"  (limit {limit} reached — resume by re-running)"); break
        match = next((n for n in names if stem in n), None)
        if not match:
            print(f"  (skip: no file matching {stem})"); continue
        print(f"  ✓ music [{','.join(moods)}] <- {match[:55]}")
        if dry_run:
            got += 1; continue
        raw = BOT_DIR / f"_music_{i}.mp3"
        if not _download(match, servers, dir_, raw):
            continue
        # Load full file (audioread offset-seeking on mp3 is fragile), then slice a
        # ~45s bed starting ~20s in (skip long intros).
        try:
            y, sr = librosa.load(str(raw), sr=24000, mono=True)
            start = int(20.0 * sr)
            end = start + int(BED_SECONDS * sr)
            if end > len(y):                       # short track: take from start
                start, end = 0, min(len(y), int(BED_SECONDS * sr))
            y = y[start:end]
            trimmed = BOT_DIR / f"_bed_{i}.ogg"
            sf.write(str(trimmed), y.astype("float32"), sr, format="OGG",
                     subtype="VORBIS")
        except Exception as e:                                  # noqa: BLE001
            print(f"    trim failed: {e!r}"); raw.unlink(missing_ok=True); continue
        cmd = [sys.executable, str(BOT_DIR / "scripts" / "podcast_lab_tool.py"),
               "ingest", "--src", str(trimmed), "--category", "music",
               "--name", name, "--description",
               f"Calm ambient bed ({', '.join(moods)})",
               "--tags", ",".join(moods),
               "--source", f"archive.org — {ITEM} — {match}", "--licence", LICENCE]
        r = subprocess.run(cmd, capture_output=True, text=True)
        raw.unlink(missing_ok=True)
        trimmed.unlink(missing_ok=True)
        if r.returncode == 0:
            got += 1; print(f"    {r.stdout.strip()}")
        else:
            print(f"    ingest failed: {r.stderr.strip()[:160]}")
        time.sleep(1)
    print(f"\n  sourced {got} bed(s){' (dry run)' if dry_run else ''}")
    return got


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None,
                    help="max new beds to fetch this run (for chunking)")
    a = ap.parse_args()
    run(dry_run=a.dry_run, limit=a.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
