#!/usr/bin/env python3.12
"""Empire English Chronicles — source the Podcast Lab from Wikimedia Commons.

Fetches licence-cleared audio (CC0 / public-domain / CC-BY) from Wikimedia Commons,
verifying EACH file's licence from its own metadata (never assumed), and ingests it
into the library via podcast_lab_tool. Re-runnable and rate-limited, so it can also
be run on a bigger machine (e.g. Kaggle) to expand the library later.

WHY WIKIMEDIA: it exposes per-file licence + author metadata through an API, so every
asset's licence can be VERIFIED programmatically rather than trusted from a page. Files
whose licence is not in the allowed set are skipped, not guessed.

Usage
-----
    python3.12 scripts/source_podcast_lab.py            # source the default plan
    python3.12 scripts/source_podcast_lab.py --dry-run  # show what WOULD be fetched
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
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src import podcast_lab as lab                               # noqa: E402

UA = {"User-Agent": "empire-eec-podcast-lab/1.0 (educational; contact EEC)"}
API = "https://commons.wikimedia.org/w/api.php"

# Wikimedia licence templates → our allowed licence tags. Anything not here is
# treated as unusable and skipped.
LICENCE_MAP = {
    "cc0": "CC0", "pd": "Public Domain", "publicdomain": "Public Domain",
    "cc-by-4.0": "CC-BY-4.0", "cc-by-3.0": "CC-BY-3.0",
    "cc-by-sa-4.0": None,   # share-alike is avoided for simplicity of attribution
    "cc-by-sa-3.0": None,
}

# The sourcing plan: for each story SITUATION, a search phrase + which library
# category/tags it feeds. Kept to sounds a learner-story actually uses.
SFX_PLAN = [
    ("door knock", "sfx", ["knock", "door"]),
    ("door creak", "sfx", ["creak", "door"]),
    ("footsteps walking", "sfx", ["footsteps"]),
    ("clock ticking", "sfx", ["clock", "ticking"]),
    ("thunder", "sfx", ["thunder", "storm"]),
    ("water drip", "sfx", ["water", "drip"]),
    ("paper rustle", "sfx", ["paper"]),
    ("bell ring", "sfx", ["bell"]),
    ("glass break", "sfx", ["glass", "break"]),
    ("wind blowing", "ambience", ["wind"]),
    ("rain", "ambience", ["rain"]),
    ("forest birds", "ambience", ["forest", "nature"]),
    ("crowd talking", "ambience", ["crowd", "market"]),
    ("night crickets", "ambience", ["night", "eerie"]),
]


def _api(params):
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        try:
            return json.load(urllib.request.urlopen(
                urllib.request.Request(url, headers=UA), timeout=30))
        except Exception as e:                                   # noqa: BLE001
            if "429" in str(e) and attempt < 4:
                time.sleep(15 * (attempt + 1))
                continue
            raise


def _file_info(title):
    """Return (download_url, licence_tag, attribution) for a Commons file, or
    (None, None, None) if its licence isn't usable."""
    d = _api({"action": "query", "prop": "imageinfo",
              "iiprop": "url|extmetadata|mediatype", "titles": title})
    pages = d.get("query", {}).get("pages", {})
    for _pid, pg in pages.items():
        ii = (pg.get("imageinfo") or [{}])[0]
        if ii.get("mediatype") != "AUDIO":
            return None, None, None
        em = ii.get("extmetadata", {})
        lic_raw = (em.get("License", {}).get("value", "") or "").lower().strip()
        licence = LICENCE_MAP.get(lic_raw, None)
        # Some PD files use "LicenseShortName" like "Public domain".
        if licence is None:
            short = (em.get("LicenseShortName", {}).get("value", "") or "").lower()
            if "cc0" in short:
                licence = "CC0"
            elif "public domain" in short:
                licence = "Public Domain"
            elif "cc by 4" in short:
                licence = "CC-BY-4.0"
            elif "cc by 3" in short:
                licence = "CC-BY-3.0"
        if not licence:
            return None, None, None
        author = (em.get("Artist", {}).get("value", "") or "").strip()
        # Strip any HTML from the author field crudely.
        import re
        author = re.sub(r"<[^>]+>", "", author).strip() or "Wikimedia Commons"
        attribution = ""
        if licence.startswith("CC-BY"):
            attribution = (f"{title.replace('File:','')} by {author} "
                           f"(Wikimedia Commons, {licence})")
        return ii.get("url"), licence, attribution
    return None, None, None


def _search_audio(phrase, limit=6):
    d = _api({"action": "query", "list": "search",
              "srsearch": f"filetype:audio {phrase}", "srnamespace": "6",
              "srlimit": str(limit)})
    return [r["title"] for r in d.get("query", {}).get("search", [])]


def run(dry_run=False, per_situation=1):
    got, skipped = 0, 0
    for phrase, category, tags in SFX_PLAN:
        print(f"\n[{category}] {phrase!r} (tags {tags})")
        try:
            titles = _search_audio(phrase)
        except Exception as e:                                   # noqa: BLE001
            print(f"  search failed: {e}")
            continue
        taken = 0
        for title in titles:
            if taken >= per_situation:
                break
            time.sleep(2)   # be polite to the API
            try:
                url, licence, attribution = _file_info(title)
            except Exception as e:                               # noqa: BLE001
                print(f"  {title}: info error {e}")
                continue
            if not url:
                continue     # unusable licence or not audio
            import re as _re
            # Clean, predictable name: the situation slug + a short index. No colons,
            # spaces, or source-title cruft (which produced ugly filenames).
            slug = _re.sub(r"[^a-z0-9]+", "_", phrase.lower()).strip("_")
            name = f"{slug}_{taken + 1}"
            print(f"  ✓ {title}  [{licence}]")
            if dry_run:
                taken += 1
                got += 1
                continue
            # download to a temp file, then ingest (normalises + registers)
            raw = BOT_DIR / f"_src_{name}{pathlib.Path(url).suffix}"
            # Wikimedia's media host (upload.wikimedia.org) rate-limits hard and
            # wants a Referer; retry with backoff on 429 so an automated run
            # completes rather than dropping assets.
            dl_headers = {**UA, "Referer": "https://commons.wikimedia.org/"}
            ok = False
            for da in range(4):
                try:
                    data = urllib.request.urlopen(
                        urllib.request.Request(url, headers=dl_headers),
                        timeout=90).read()
                    raw.write_bytes(data)
                    ok = True
                    break
                except Exception as e:                           # noqa: BLE001
                    if "429" in str(e) and da < 3:
                        time.sleep(20 * (da + 1))
                        continue
                    print(f"    download failed: {e}")
                    break
            if not ok:
                continue
            cmd = [sys.executable, str(BOT_DIR / "scripts" / "podcast_lab_tool.py"),
                   "ingest", "--src", str(raw), "--category", category,
                   "--name", name, "--description", phrase.capitalize(),
                   "--tags", ",".join(tags),
                   "--source", f"Wikimedia Commons — {title}",
                   "--licence", licence]
            if attribution:
                cmd += ["--attribution", attribution]
            r = subprocess.run(cmd, capture_output=True, text=True)
            raw.unlink(missing_ok=True)
            if r.returncode == 0:
                taken += 1
                got += 1
                print(f"    {r.stdout.strip()}")
            else:
                print(f"    ingest failed: {r.stderr.strip()[:120]}")
                skipped += 1
    print(f"\n  sourced {got} asset(s){' (dry run)' if dry_run else ''}, "
          f"{skipped} skipped")
    return got


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--per-situation", type=int, default=1)
    args = ap.parse_args()
    run(dry_run=args.dry_run, per_situation=args.per_situation)
    return 0


if __name__ == "__main__":
    sys.exit(main())
