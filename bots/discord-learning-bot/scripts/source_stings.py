#!/usr/bin/env python3.12
"""Create short transition stings for the Podcast Lab from CC0 music.

A "sting" is a 2.5–4s musical punctuation used between scenes. Rather than source a
dozen separate files, we take a few VARIED CC0 tracks (from the CalmPills item, same
verified CC0 dedication used for music beds) and extract one short, self-contained
phrase from each, with a gentle fade-in/out so it reads as a deliberate transition.

Resumable via --limit N (downloads are slow); re-run to continue where it stopped.
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

ITEM = "CalmPills"
LICENCE = "CC0"

# (stem, moods, start_seconds) — a distinct short phrase per sting.
PICKS = [
    ("Calm_Pill_21_", ["hopeful", "transition"], 30.0),
    ("Calm_Pill_37_", ["wonder", "transition"], 25.0),
    ("Calm_Pill_54_", ["hopeful", "transition"], 40.0),
    ("Calm_Pill_60_", ["warm", "transition"], 35.0),
    ("Calm_Pill_66_", ["mysterious", "transition"], 20.0),
    ("Calm_Pill_78_", ["eerie", "transition"], 30.0),
]
STING_SECONDS = 3.2
FADE_SECONDS = 0.4


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
    names = [f["name"] for f in d.get("files", []) if f["name"].endswith(".mp3")]
    print(f"archive.org item {ITEM}\n  licence: {lic}")
    if "publicdomain/zero" not in lic:
        print("  ❌ not CC0 — refusing"); return 0

    import numpy as np
    import librosa
    import soundfile as sf
    stings_dir = BOT_DIR / "content" / "podcast-lab" / "stings"
    got = 0
    for i, (stem, moods, start_s) in enumerate(PICKS, 1):
        name = f"sting_{moods[0]}_{i}"
        if (stings_dir / f"{name}.ogg").exists() and not dry_run:
            continue
        if limit is not None and got >= limit:
            print(f"  (limit {limit} reached — resume by re-running)"); break
        match = next((n for n in names if stem in n), None)
        if not match:
            print(f"  (skip: no file matching {stem})"); continue
        print(f"  ✓ sting [{','.join(moods)}] <- {match[:50]}")
        if dry_run:
            got += 1; continue
        raw = BOT_DIR / f"_sting_{i}.mp3"
        if not _download(match, servers, dir_, raw):
            continue
        try:
            y, sr = librosa.load(str(raw), sr=24000, mono=True)
            a = int(start_s * sr)
            b = a + int(STING_SECONDS * sr)
            if b > len(y):
                a, b = 0, min(len(y), int(STING_SECONDS * sr))
            seg = y[a:b].astype("float32").copy()
            # gentle fade-in / fade-out so the phrase reads as a deliberate sting
            f = int(FADE_SECONDS * sr)
            if len(seg) > 2 * f > 0:
                ramp = np.linspace(0.0, 1.0, f, dtype="float32")
                seg[:f] *= ramp
                seg[-f:] *= ramp[::-1]
            trimmed = BOT_DIR / f"_stingcut_{i}.ogg"
            sf.write(str(trimmed), seg, sr, format="OGG", subtype="VORBIS")
        except Exception as e:                                  # noqa: BLE001
            print(f"    cut failed: {e!r}"); raw.unlink(missing_ok=True); continue
        cmd = [sys.executable, str(BOT_DIR / "scripts" / "podcast_lab_tool.py"),
               "ingest", "--src", str(trimmed), "--category", "sting",
               "--name", name,
               "--description", f"Short transition sting ({moods[0]})",
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
    print(f"\n  sourced {got} sting(s){' (dry run)' if dry_run else ''}")
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
