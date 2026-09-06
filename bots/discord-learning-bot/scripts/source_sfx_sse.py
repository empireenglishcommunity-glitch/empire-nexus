#!/usr/bin/env python3.12
"""Source one-shot SFX for the Podcast Lab from the CC0 SSE_Library_* items.

The SSE libraries on archive.org are all released under CC0 (public-domain
dedication — commercial use OK, no attribution required). This script pulls a
curated, learner-appropriate spread of one-shot effects across many categories,
selecting the first N mp3s under a given folder so we don't hand-transcribe the
long, punctuation-heavy filenames.

Each effect is loudness-normalised + silence-trimmed by the ingest tool, and we cap
each clip to a few seconds so nothing is a long recording.

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
LICENCE = "CC0"
MAX_SECONDS = 5.0

# (item, folder, count, name_prefix, tags[, prefer_substrings])
# The optional 6th element lists case-insensitive substrings; matching files are
# chosen first (used to skip violent/graphic clips a plain alphabetical pick hits).
RULES = [
    # animals
    ("SSE_Library_ANIMALS", "DOG", 2, "sfx_dog", ["dog", "animal"]),
    ("SSE_Library_ANIMALS", "INSECT", 1, "sfx_insect", ["insect", "nature"]),
    ("SSE_Library_ANIMALS", "HORSE", 2, "sfx_horse", ["horse", "animal"]),
    ("SSE_Library_ANIMALS", "FARM", 2, "sfx_farm_animal", ["farm", "animal"]),
    ("SSE_Library_ANIMALS", "WILD", 1, "sfx_wild_animal", ["wild", "animal", "nature"],
     ["elephant running", "camel"]),
    ("SSE_Library_ANIMALS", "PRIMATE", 1, "sfx_monkey", ["monkey", "animal", "jungle"]),
    ("SSE_Library_ANIMALS", "CAT WILD", 1, "sfx_lion", ["lion", "roar", "danger"]),
    # water
    ("SSE_Library_WATER", "FLOW", 2, "sfx_water_flow", ["water", "stream", "nature"]),
    ("SSE_Library_WATER", "SPLASH", 1, "sfx_splash", ["water", "splash"]),
    ("SSE_Library_WATER", "SURF", 2, "sfx_waves", ["water", "waves", "seaside"]),
    # wind
    ("SSE_Library_WIND", "GENERAL", 2, "sfx_wind", ["wind", "weather", "nature"]),
    ("SSE_Library_WIND", "GUST", 1, "sfx_wind_gust", ["wind", "gust", "storm"]),
    # fire
    ("SSE_Library_FIRE", "BURNING", 1, "sfx_fire_burn", ["fire", "warm"]),
    ("SSE_Library_FIRE", "SIZZLE", 1, "sfx_sizzle", ["fire", "cooking"]),
    ("SSE_Library_FIRE", "WHOOSH", 1, "sfx_fire_whoosh", ["fire", "whoosh"]),
    # bells
    ("SSE_Library_BELLS", "DOORBELL", 1, "sfx_doorbell", ["bell", "door", "indoor"]),
    ("SSE_Library_BELLS", "HANDBELL", 1, "sfx_handbell", ["bell", "hand"]),
    ("SSE_Library_BELLS", "MISC", 1, "sfx_bell", ["bell"]),
    # machines
    ("SSE_Library_MACHINES", "MECHANISM", 2, "sfx_mechanism", ["machine", "mechanical"]),
    ("SSE_Library_MACHINES", "APPLIANCE", 1, "sfx_appliance", ["machine", "indoor"]),
    ("SSE_Library_MACHINES", "ANTIQUE", 1, "sfx_old_machine", ["machine", "antique"]),
    # vehicles
    ("SSE_Library_VEHICLES", "CAR", 2, "sfx_car", ["car", "vehicle", "street"],
     ["engine start", "idles in garage", "drives in and stops", "by medium speed"]),
    ("SSE_Library_VEHICLES", "HORN", 1, "sfx_car_horn", ["car", "horn", "street"]),
    ("SSE_Library_VEHICLES", "BICYCLE", 1, "sfx_bicycle", ["bicycle", "street"]),
    # crowds
    ("SSE_Library_CROWDS", "CHEERING", 1, "sfx_cheer", ["crowd", "cheer", "hopeful"],
     ["very happy", "encouraging"]),
    ("SSE_Library_CROWDS", "LAUGHTER", 1, "sfx_laughter", ["crowd", "laughter", "warm"]),
    ("SSE_Library_CROWDS", "CHILDREN", 1, "sfx_children", ["crowd", "children", "school"]),
    ("SSE_Library_CROWDS", "CONVERSATION", 1, "sfx_chatter", ["crowd", "chatter"]),
    ("SSE_Library_CROWDS", "REACTION", 1, "sfx_crowd_react", ["crowd", "reaction"],
     ["oohs", "cheering"]),
    # alarms
    ("SSE_Library_ALARMS", "BUZZER", 1, "sfx_buzzer", ["alarm", "buzzer"]),
    ("SSE_Library_ALARMS", "CLOCK", 1, "sfx_alarm_clock", ["alarm", "clock"]),
    ("SSE_Library_ALARMS", "SIREN", 1, "sfx_siren", ["alarm", "siren", "danger"],
     ["police siren", "distant siren"]),
    # electricity
    ("SSE_Library_ELECTRICITY", "ZAP", 1, "sfx_zap", ["electric", "zap"]),
    ("SSE_Library_ELECTRICITY", "SPARKS", 1, "sfx_sparks", ["electric", "sparks"]),
    # trains
    ("SSE_Library_TRAINS", "STEAM", 1, "sfx_steam_train", ["train", "steam", "adventure"]),
    ("SSE_Library_TRAINS", "CLACK", 1, "sfx_train_track", ["train", "track"]),
]

_META_CACHE: dict = {}


def _metadata(item):
    if item not in _META_CACHE:
        m = urllib.request.urlopen(urllib.request.Request(
            f"https://archive.org/metadata/{item}", headers=UA), timeout=60)
        _META_CACHE[item] = json.loads(m.read())
    return _META_CACHE[item]


def _download(fname, servers, dir_, dest):
    last = ""
    for srv in servers:
        url = f"https://{srv}{dir_}/" + urllib.parse.quote(fname)
        for _ in range(2):
            try:
                data = urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=240).read()
                if len(data) < 2048:
                    last = f"too small ({len(data)}b)"; continue
                dest.write_bytes(data)
                return True
            except Exception as e:                              # noqa: BLE001
                last = str(e)[:80]
                time.sleep(1.5)
    print(f"    download failed: {last}")
    return False


def _expand_rules():
    """Turn (item,folder,count,...) rules into concrete (item,file,name,tags) picks."""
    picks = []
    for rule in RULES:
        item, folder, count, prefix, tags = rule[:5]
        prefer = rule[5] if len(rule) > 5 else []
        d = _metadata(item)
        lic = d.get("metadata", {}).get("licenseurl", "")
        if "publicdomain/zero" not in lic:
            print(f"  ❌ {item} not CC0 ({lic}) — skipping category"); continue
        mp3s = sorted(f["name"] for f in d["files"]
                      if f["name"].lower().endswith(".mp3")
                      and f["name"].split("/")[0] == folder)
        if prefer:
            preferred = [m for m in mp3s
                         if any(s.lower() in m.lower() for s in prefer)]
            rest = [m for m in mp3s if m not in preferred]
            mp3s = preferred + rest
        for i, fname in enumerate(mp3s[:count], 1):
            name = prefix if count == 1 else f"{prefix}_{i}"
            picks.append((item, fname, name, tags))
    return picks


def run(dry_run=False, limit=None):
    picks = _expand_rules()
    print(f"planned {len(picks)} SFX picks")
    import numpy as np
    import librosa
    import soundfile as sf
    sfx_dir = BOT_DIR / "content" / "podcast-lab" / "sfx"
    got = 0
    for item, fname, name, tags in picks:
        if (sfx_dir / f"{name}.ogg").exists() and not dry_run:
            continue
        if limit is not None and got >= limit:
            print(f"  (limit {limit} reached — resume by re-running)"); break
        d = _metadata(item)
        servers = d.get("workable_servers") or [d.get("server")]
        dir_ = d.get("dir", "")
        short = fname.split("/")[-1][:42]
        print(f"  ✓ sfx {name} [{','.join(tags)}] <- {short}")
        if dry_run:
            got += 1; continue
        raw = BOT_DIR / f"_sfx_{got}.mp3"
        if not _download(fname, servers, dir_, raw):
            continue
        try:
            y, sr = librosa.load(str(raw), sr=24000, mono=True)
            if len(y) > int(MAX_SECONDS * sr):
                y = y[:int(MAX_SECONDS * sr)]
            trimmed = BOT_DIR / f"_sfxcut_{got}.ogg"
            sf.write(str(trimmed), y.astype("float32"), sr, format="OGG",
                     subtype="VORBIS")
        except Exception as e:                                  # noqa: BLE001
            print(f"    trim failed: {e!r}"); raw.unlink(missing_ok=True); continue
        cmd = [sys.executable, str(BOT_DIR / "scripts" / "podcast_lab_tool.py"),
               "ingest", "--src", str(trimmed), "--category", "sfx",
               "--name", name,
               "--description", f"{tags[0]} effect",
               "--tags", ",".join(tags),
               "--source", f"archive.org — {item} — {fname}", "--licence", LICENCE]
        r = subprocess.run(cmd, capture_output=True, text=True)
        raw.unlink(missing_ok=True)
        trimmed.unlink(missing_ok=True)
        if r.returncode == 0:
            got += 1; print(f"    {r.stdout.strip()}")
        else:
            print(f"    ingest failed: {r.stderr.strip()[:160]}")
        time.sleep(0.5)
    print(f"\n  sourced {got} sfx{' (dry run)' if dry_run else ''}")
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
