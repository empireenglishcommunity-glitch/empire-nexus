"""Empire English Chronicles — THE PODCAST LAB (owned audio library).

An in-house, licence-cleared audio library so the automatic pipeline ALWAYS has the
right sound available — no runtime dependency on an external fetch, no expiring URL.
This is the "exclusive production" asset base the owner asked for.

This module is the single source of truth for what the library contains and how the
rest of the system reads it (spec R5). The audio files live under content/podcast-lab/;
their metadata lives in content/podcast-lab/LIBRARY.json.

WHY A MANIFEST (not just files on disk)
---------------------------------------
* The story generator may only request sounds that EXIST (R5.6) — the legal
  vocabulary is derived from here, and the script validator rejects anything else.
  This structurally ends the old bug where the LLM invented [SFX:wind] that rendered
  as silence.
* Every asset must carry its licence + attribution (R5.4). A build check fails if any
  file is unlisted or any entry lacks a licence, and CREDITS is generated from here so
  attribution can never drift from reality.

LICENCE POLICY (R5.4)
---------------------
Only CC0 / public-domain / CC-BY are permitted. CC-BY requires visible attribution
wherever an episode using the asset is published; the bot emits it automatically.
"""
import json
import pathlib

LAB_DIR = pathlib.Path(__file__).resolve().parent.parent / "content" / "podcast-lab"
MANIFEST = LAB_DIR / "LIBRARY.json"

# Categories and their on-disk sub-folders (R5.1).
CATEGORIES = {
    "music": "music",         # background beds, by mood
    "ambience": "ambience",   # room tones / environments under narration
    "sfx": "sfx",             # foley / one-shot sound effects
    "sting": "stings",        # short intro / outro / transition marks
    "voice": "voices",        # voice references (Mai's clone source, fixtures)
}

# Licences we accept. Anything else fails the build (R5.4).
ALLOWED_LICENCES = {"CC0", "Public Domain", "CC-BY", "CC-BY-3.0", "CC-BY-4.0"}
# Which of those REQUIRE visible attribution when used.
ATTRIBUTION_REQUIRED = {"CC-BY", "CC-BY-3.0", "CC-BY-4.0"}

# Standard moods a story can call for. The generator picks from these; the mixer maps
# a mood to an actual bed/ambience. Kept small and human — a learner-story palette.
MOODS = ["mystery", "warm", "tension", "wonder", "playful", "sad", "triumph",
         "calm", "eerie", "hopeful"]


def _load() -> dict:
    if not MANIFEST.exists():
        return {"version": 1, "assets": []}
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:                                            # noqa: BLE001
        return {"version": 1, "assets": []}


def all_assets() -> list:
    """Every asset entry in the manifest."""
    return _load().get("assets", [])


def assets_in(category: str) -> list:
    return [a for a in all_assets() if a.get("category") == category]


def by_tag(category: str, tag: str) -> list:
    """Assets in a category carrying `tag` (a mood or a situation), best-effort so
    the mixer/generator can find 'a mystery bed' or 'a door sfx'."""
    tag = (tag or "").lower()
    return [a for a in assets_in(category)
            if tag in [t.lower() for t in a.get("tags", [])]]


def sfx_names() -> list:
    """The legal [SFX:...] names the generator may use — derived from the manifest
    (R5.6), so the writer can never request an effect that does not exist."""
    names = set()
    for a in assets_in("sfx"):
        for t in a.get("tags", []):
            names.add(t.lower())
        # the primary name is the filename stem
        names.add(pathlib.Path(a["file"]).stem.lower())
    return sorted(names)


def sfx_vocab() -> list:
    """A CLEAN, human [SFX:...] vocabulary for the generation prompt: the tag words
    only (e.g. 'knock', 'door', 'wind'), NOT the internal filename stems like
    'sfx_car_1'. `sfx_names()` stays the permissive superset the validator accepts
    (a script may legally reference either a tag or a stem); this is the shorter,
    readable menu we actually SUGGEST to the writer."""
    words = set()
    for a in assets_in("sfx"):
        for t in a.get("tags", []):
            t = t.lower().strip()
            # skip internal-looking tokens; keep real words
            if t and not t.startswith("sfx_") and "_" not in t:
                words.add(t)
    return sorted(words)


def available_moods() -> list:
    """Moods that actually have at least one music bed OR ambience behind them."""
    have = set()
    for a in assets_in("music") + assets_in("ambience"):
        for t in a.get("tags", []):
            if t.lower() in MOODS:
                have.add(t.lower())
    return [m for m in MOODS if m in have]


def resolve_path(asset: dict) -> pathlib.Path:
    return LAB_DIR / CATEGORIES.get(asset["category"], "") / asset["file"]


def required_attributions(used_assets: list) -> list:
    """Attribution lines for the CC-BY assets an episode actually used (R5.4)."""
    out = []
    for a in used_assets:
        if a.get("licence") in ATTRIBUTION_REQUIRED and a.get("attribution"):
            out.append(a["attribution"])
    return sorted(set(out))


def validate() -> list:
    """Return a list of problems with the library. Empty list = healthy. Used by the
    build check (R5.4) and tests. Checks:
      * every listed file exists on disk, and every audio file on disk is listed;
      * every entry has a valid category, an allowed licence, and — for CC-BY —
        an attribution string;
      * no duplicate files."""
    problems = []
    data = _load()
    assets = data.get("assets", [])
    listed = {}
    for a in assets:
        f = a.get("file", "")
        cat = a.get("category", "")
        if cat not in CATEGORIES:
            problems.append(f"{f}: unknown category {cat!r}")
            continue
        p = LAB_DIR / CATEGORIES[cat] / f
        if not p.exists():
            problems.append(f"{f}: listed in manifest but missing on disk ({p})")
        lic = a.get("licence", "")
        if lic not in ALLOWED_LICENCES:
            problems.append(f"{f}: licence {lic!r} not in allowed set")
        if lic in ATTRIBUTION_REQUIRED and not a.get("attribution"):
            problems.append(f"{f}: {lic} requires an attribution string")
        if not a.get("description"):
            problems.append(f"{f}: missing description")
        key = (cat, f)
        if key in listed:
            problems.append(f"{f}: duplicate manifest entry in {cat}")
        listed[key] = True
    # Reverse: audio files on disk that aren't in the manifest.
    for cat, sub in CATEGORIES.items():
        d = LAB_DIR / sub
        if not d.exists():
            continue
        for p in d.iterdir():
            if p.suffix.lower() in (".ogg", ".mp3", ".wav", ".flac"):
                if (cat, p.name) not in listed:
                    problems.append(f"{p.name}: on disk in {sub}/ but not in manifest")
    return problems


def stats() -> dict:
    """Counts per category + total size, for the build log and the size budget."""
    assets = all_assets()
    by_cat = {}
    total_bytes = 0
    for a in assets:
        by_cat[a["category"]] = by_cat.get(a["category"], 0) + 1
        p = resolve_path(a)
        if p.exists():
            total_bytes += p.stat().st_size
    return {"total": len(assets), "by_category": by_cat,
            "total_mb": round(total_bytes / 1e6, 2),
            "moods_covered": available_moods(),
            "sfx_names": sfx_names()}



# ── mood-aware selection (spec 3.7 / R5) ────────────────────────────────────────
#
# The story declares a MOOD; the mixer needs a concrete bed/ambience/effect. These
# helpers do that mapping in ONE place, so both renderers pick assets the same way
# and can never reference a file that isn't in the licence-cleared manifest.

# When a mood has no asset of its own, fall back along emotionally-adjacent moods
# before giving up. Keeps a story scored even if the library is thin for one mood.
_MOOD_FALLBACK = {
    "mystery": ["mystery", "eerie", "tension", "wonder"],
    "eerie": ["eerie", "mystery", "tension"],
    "tension": ["tension", "eerie", "mystery"],
    "wonder": ["wonder", "hopeful", "calm", "mystery"],
    "warm": ["warm", "hopeful", "calm", "playful"],
    "hopeful": ["hopeful", "warm", "triumph", "wonder"],
    "triumph": ["triumph", "hopeful", "warm"],
    "playful": ["playful", "warm", "hopeful"],
    "calm": ["calm", "warm", "wonder"],
    "sad": ["sad", "calm", "warm"],
}


def _stable_pick(items: list, seed):
    """Deterministically choose one item from a sorted list, varied by `seed` (e.g.
    an episode number) so repeated moods don't always get the identical bed but the
    same (mood, seed) always resolves the same asset — reproducible renders."""
    if not items:
        return None
    ordered = sorted(items, key=lambda a: a.get("file", ""))
    try:
        idx = int(seed) % len(ordered)
    except Exception:                                            # noqa: BLE001
        idx = 0
    return ordered[idx]


def select_asset(category: str, mood: str, seed=0) -> dict | None:
    """Pick ONE asset in `category` that fits `mood`, following the fallback chain.
    Deterministic for a given (category, mood, seed).

    Returns None for an UNKNOWN mood (not a canonical mood and not in the fallback
    table) — an unrecognised mood must not silently grab a random bed. A KNOWN mood
    that simply has no asset of its own does fall back along adjacent moods, and
    finally to any asset in the category so a real mood is always scored."""
    m0 = (mood or "").lower()
    if m0 not in _MOOD_FALLBACK and m0 not in MOODS:
        return None
    chain = _MOOD_FALLBACK.get(m0, [m0])
    for m in chain:
        hits = by_tag(category, m)
        if hits:
            return _stable_pick(hits, seed)
    # known mood with no adjacent match: any asset, so a real mood never fails
    allc = assets_in(category)
    return _stable_pick(allc, seed) if allc else None


def select_bed_path(mood: str, seed=0):
    """Filesystem path to a music bed for `mood`, or None. (spec 3.7)"""
    a = select_asset("music", mood, seed)
    return (resolve_path(a) if a else None), a


def select_ambience_path(mood: str, seed=0):
    """Filesystem path to an ambience for `mood`, or None."""
    a = select_asset("ambience", mood, seed)
    return (resolve_path(a) if a else None), a


def resolve_sfx_path(name: str):
    """Map a script's [SFX:name] to a real sfx file path, or None. Matches the name
    against each sfx asset's tags AND its filename stem (the permissive superset the
    validator accepts). Prefers a filename-stem hit, then a tag hit; deterministic."""
    want = (name or "").lower().strip()
    if not want:
        return None, None
    stem_hit = None
    tag_hits = []
    for a in assets_in("sfx"):
        stem = pathlib.Path(a["file"]).stem.lower()
        if stem == want and stem_hit is None:
            stem_hit = a
        tags = [t.lower() for t in a.get("tags", [])]
        if want in tags:
            tag_hits.append(a)
    chosen = stem_hit or (sorted(tag_hits, key=lambda a: a["file"])[0]
                          if tag_hits else None)
    return (resolve_path(chosen) if chosen else None), chosen


def credit_line(used_assets: list) -> str:
    """A single human credit line for the assets an episode actually used. CC-BY
    assets are named with their attribution; if only CC0/PD assets were used, a
    short generic line is returned. Feeds episode-meta['credit'] and the post."""
    attribs = required_attributions(used_assets or [])
    if attribs:
        return "Music & sound: " + "; ".join(attribs)
    return ("Music & sound: Empire English Chronicles Podcast Lab "
            "(CC0 — see content/podcast-lab/CREDITS.md).")
