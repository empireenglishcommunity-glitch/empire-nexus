#!/usr/bin/env python3.12
"""Empire English Chronicles — Podcast Lab tooling (spec Phase 3).

Three jobs, one tool:
  ingest   — normalise a source audio file into the library (format, sample rate,
             loudness per category, trim) and add its manifest entry (R5.5).
  check    — fail if the library is unhealthy: any unlisted file, missing licence
             or attribution, disallowed licence, or over the size budget (R5.4/R5.7).
  credits  — (re)generate CREDITS.md from the manifest, so attribution can never
             drift from what actually ships (R5.4).

The manifest schema (content/podcast-lab/LIBRARY.json) per asset:
    file, category, description, tags[], duration, source, licence, attribution

Usage
-----
    python3.12 scripts/podcast_lab_tool.py ingest --src bed.mp3 --category music \
        --tags mystery,tension --description "Dark ambient bed" \
        --source "freepd.com (Rafael Krux)" --licence CC-BY-4.0 \
        --attribution 'Music: "Lights" by Rafael Krux (freepd.com), CC-BY 4.0'
    python3.12 scripts/podcast_lab_tool.py check
    python3.12 scripts/podcast_lab_tool.py credits
"""
import argparse
import json
import pathlib
import sys

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))

from src import podcast_lab as lab                               # noqa: E402

# Per-category loudness on ingest, so the mixer never has to compensate for an
# inconsistent source (R5.5). Beds/ambience sit well BELOW speech; foley a little
# below; stings near speech level. Speech itself is mastered to -16 LUFS.
CATEGORY_LUFS = {
    "music": -30.0,       # bed: well under narration
    "ambience": -34.0,    # even quieter — presence, not content
    "sfx": -20.0,         # foley: noticeable but not louder than speech
    "sting": -18.0,       # transitions: near speech level
    "voice": -23.0,       # reference clips: consistent for cloning
}
SIZE_BUDGET_MB = 60.0     # the whole library; OGG-compressed. Reported by `check`.


def _norm_loudness(y, sr, target_lufs):
    import numpy as np
    try:
        import pyloudnorm as pyln
        meter = pyln.Meter(sr)
        cur = meter.integrated_loudness(y.astype("float64"))
        if np.isfinite(cur):
            y = (y * (10 ** ((target_lufs - cur) / 20.0))).astype("float32")
    except Exception:                                            # noqa: BLE001
        pass
    peak = float(np.max(np.abs(y))) or 1.0
    if peak > 0.97:
        y = (y * (0.97 / peak)).astype("float32")
    return y


def ingest(args):
    import numpy as np
    import librosa
    import soundfile as sf

    if args.category not in lab.CATEGORIES:
        print(f"unknown category {args.category!r}", file=sys.stderr)
        return 2
    if args.licence not in lab.ALLOWED_LICENCES:
        print(f"licence {args.licence!r} not allowed {sorted(lab.ALLOWED_LICENCES)}",
              file=sys.stderr)
        return 2
    if args.licence in lab.ATTRIBUTION_REQUIRED and not args.attribution:
        print(f"{args.licence} requires --attribution", file=sys.stderr)
        return 2

    src = pathlib.Path(args.src)
    if not src.exists():
        print(f"source not found: {src}", file=sys.stderr)
        return 2

    y, sr = librosa.load(str(src), sr=24000, mono=True)
    if y is None or not len(y):
        print(f"{src}: decoded to no audio", file=sys.stderr)
        return 2
    y = y.astype("float32")
    # Trim leading/trailing silence (keep a little tail on beds so loops breathe).
    try:
        yt, _ = librosa.effects.trim(y, top_db=40)
        if len(yt) > sr * 0.3:
            y = yt
    except Exception:                                            # noqa: BLE001
        pass
    y = _norm_loudness(y, sr, CATEGORY_LUFS.get(args.category, -23.0))

    sub = lab.LAB_DIR / lab.CATEGORIES[args.category]
    sub.mkdir(parents=True, exist_ok=True)
    out_name = args.name or (src.stem.lower().replace(" ", "_") + ".ogg")
    if not out_name.endswith(".ogg"):
        out_name += ".ogg"
    out = sub / out_name
    sf.write(str(out), y, sr, format="OGG", subtype="VORBIS")

    entry = {
        "file": out_name,
        "category": args.category,
        "description": args.description,
        "tags": [t.strip().lower() for t in (args.tags or "").split(",") if t.strip()],
        "duration": round(len(y) / sr, 2),
        "source": args.source,
        "licence": args.licence,
        "attribution": args.attribution or "",
    }
    data = lab._load()
    # Replace an existing entry for the same file, else append.
    data.setdefault("assets", [])
    data["assets"] = [a for a in data["assets"]
                      if not (a["category"] == args.category
                              and a["file"] == out_name)]
    data["assets"].append(entry)
    data["assets"].sort(key=lambda a: (a["category"], a["file"]))
    lab.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    lab.MANIFEST.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
    print(f"  ingested {out} ({entry['duration']}s, {args.category}, {args.licence})")
    return 0


def check(_args):
    problems = lab.validate()
    st = lab.stats()
    print("=== Podcast Lab ===")
    print(f"  assets: {st['total']}  by category: {st['by_category']}")
    print(f"  size: {st['total_mb']} MB (budget {SIZE_BUDGET_MB} MB)")
    print(f"  moods covered: {st['moods_covered']}")
    print(f"  sfx names: {st['sfx_names']}")
    if st["total_mb"] > SIZE_BUDGET_MB:
        problems.append(f"library {st['total_mb']}MB exceeds budget {SIZE_BUDGET_MB}MB")
    if problems:
        print("\n  PROBLEMS:")
        for p in problems:
            print(f"    ❌ {p}")
        return 1
    print("\n  ✅ library healthy — every asset listed, licensed, and attributed")
    return 0


def credits(_args):
    """Generate CREDITS.md from the manifest (R5.4)."""
    data = lab._load()
    assets = data.get("assets", [])
    lines = ["# Empire English Chronicles — Podcast Lab Credits", "",
             "> Generated from `content/podcast-lab/LIBRARY.json` by "
             "`scripts/podcast_lab_tool.py credits`. Do not edit by hand.", "",
             "All assets are CC0, public domain, or CC-BY. CC-BY assets require the "
             "attribution below wherever an episode using them is published; the bot "
             "emits it automatically.", ""]
    for cat in lab.CATEGORIES:
        cat_assets = [a for a in assets if a["category"] == cat]
        if not cat_assets:
            continue
        lines.append(f"## {cat.capitalize()}")
        lines.append("")
        lines.append("| File | Description | Licence | Attribution |")
        lines.append("|------|-------------|---------|-------------|")
        for a in sorted(cat_assets, key=lambda x: x["file"]):
            attr = a.get("attribution", "") or ("—" if a["licence"] in
                                                ("CC0", "Public Domain") else "**MISSING**")
            lines.append(f"| `{a['file']}` | {a.get('description','')} | "
                         f"{a['licence']} | {attr} |")
        lines.append("")
    out = lab.LAB_DIR / "CREDITS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {out} ({len(assets)} assets)")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ing = sub.add_parser("ingest", help="normalise + register a source asset")
    ing.add_argument("--src", required=True)
    ing.add_argument("--category", required=True, choices=list(lab.CATEGORIES))
    ing.add_argument("--description", required=True)
    ing.add_argument("--tags", default="")
    ing.add_argument("--source", required=True, help="where it came from")
    ing.add_argument("--licence", required=True)
    ing.add_argument("--attribution", default="")
    ing.add_argument("--name", default="", help="output filename (default: from src)")
    ing.set_defaults(func=ingest)

    chk = sub.add_parser("check", help="fail if the library is unhealthy")
    chk.set_defaults(func=check)

    cr = sub.add_parser("credits", help="regenerate CREDITS.md from the manifest")
    cr.set_defaults(func=credits)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
