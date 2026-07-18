#!/usr/bin/env python3
"""
Aql (العقل) Phase A1.3 / A2.5 — one-time knowledge embedding script.

Chunks + embeds every `.md` file in `data/nour_knowledge/` (student +
shared domains) AND `data/nour_knowledge_owner/` (owner-only domains,
Phase A2) into the `knowledge_chunks` table, one row per chunk.
`domain` = the file's stem (e.g. "daily_tasks.md" -> "daily_tasks",
"architecture.md" -> "architecture"), matching the existing
`_KB_CATEGORIES` naming in nour_concierge.py and the domain strings
enumerated in src/nour/permissions.py's KNOWLEDGE_DOMAINS mapping. The
two source directories are just a filing convenience for humans
editing these files — the actual role boundary is enforced entirely
by `domain` string matching in permissions.py / database.py, not by
which directory a file happens to live in.

This is an OFFLINE indexing step, not something that runs per-request
(design.md Section 4.2) — re-run it manually whenever a knowledge file
changes. Safe to re-run: each domain's existing chunks are cleared
before its new chunks are inserted, so re-running never leaves stale
duplicates alongside fresh ones (see database.clear_knowledge_chunks's
own docstring).

Usage:
    python3 scripts/embed_knowledge.py                # embed all files (both dirs)
    python3 scripts/embed_knowledge.py daily_tasks.md  # embed one file, by name
    python3 scripts/embed_knowledge.py --owner-only    # embed only data/nour_knowledge_owner/
    python3 scripts/embed_knowledge.py --student-only  # embed only data/nour_knowledge/
    python3 scripts/embed_knowledge.py --dry-run       # chunk only, no
                                                        # embedding calls,
                                                        # no DB writes —
                                                        # useful to sanity
                                                        # check chunk counts
                                                        # before spending
                                                        # any API quota

Requires GEMINI_API_KEY to be set (reuses the existing bot config —
zero new signup, per the $0 budget constraint). Exits with an error
(not a silent partial run) if the key is missing and --dry-run was not
passed.

Exit codes:
    0 = success
    1 = GEMINI_API_KEY missing (and not --dry-run)
    2 = one or more files failed to embed
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, database  # noqa: E402
from src.nour.knowledge.chunker import chunk_markdown_file  # noqa: E402
from src.nour.knowledge.embedder import embed_text, pack_embedding  # noqa: E402

_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = _ROOT / "data" / "nour_knowledge"
KB_OWNER_DIR = _ROOT / "data" / "nour_knowledge_owner"


async def embed_file(filepath: Path, dry_run: bool) -> int:
    """Chunk + embed one knowledge file. Returns the number of chunks
    written (or that WOULD be written, for --dry-run)."""
    domain = filepath.stem
    chunks = chunk_markdown_file(filepath, domain)

    if dry_run:
        print(f"  [dry-run] {filepath.name}: {len(chunks)} chunk(s), domain='{domain}'")
        for c in chunks:
            print(f"      - {c.heading!r} ({len(c.content)} chars)")
        return len(chunks)

    database.clear_knowledge_chunks(domain)

    written = 0
    for c in chunks:
        vec = await embed_text(c.content, task_type="RETRIEVAL_DOCUMENT")
        if vec is None:
            print(f"      ! embedding FAILED for chunk '{c.heading}' in {filepath.name} — skipped")
            continue
        database.insert_knowledge_chunk(
            domain=c.domain, source_file=c.source_file, heading=c.heading,
            content=c.content, embedding=pack_embedding(vec),
            embedding_model=config.GEMINI_EMBEDDING_MODEL,
        )
        written += 1

    print(f"  {filepath.name}: {written}/{len(chunks)} chunk(s) embedded, domain='{domain}'")
    return written


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filename", nargs="?", default=None,
                        help="Embed only this one file (e.g. daily_tasks.md or architecture.md). "
                             "Searches both directories. Default: all files in both directories.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Chunk only — no embedding calls, no DB writes.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--owner-only", action="store_true",
                       help="Only embed data/nour_knowledge_owner/*.md (Phase A2 owner-only domains).")
    group.add_argument("--student-only", action="store_true",
                       help="Only embed data/nour_knowledge/*.md (student + shared domains).")
    args = parser.parse_args()

    if not args.dry_run and not config.GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY is not set. Set it in .env, or pass --dry-run "
              "to sanity-check chunking without making any API calls.", file=sys.stderr)
        return 1

    if args.filename:
        candidates = [KB_DIR / args.filename, KB_OWNER_DIR / args.filename]
        targets = [c for c in candidates if c.exists()]
        if not targets:
            print(f"ERROR: file not found in {KB_DIR} or {KB_OWNER_DIR}: {args.filename}", file=sys.stderr)
            return 1
    elif args.owner_only:
        targets = sorted(KB_OWNER_DIR.glob("*.md"))
    elif args.student_only:
        targets = sorted(KB_DIR.glob("*.md"))
    else:
        targets = sorted(KB_DIR.glob("*.md")) + sorted(KB_OWNER_DIR.glob("*.md"))

    if not targets:
        print(f"ERROR: no .md files found for the requested scope.", file=sys.stderr)
        return 1

    print(f"Aql knowledge embed{' (DRY RUN)' if args.dry_run else ''} — {len(targets)} file(s)")
    total_written = 0
    failures = 0
    for filepath in targets:
        try:
            total_written += await embed_file(filepath, args.dry_run)
        except Exception as e:
            print(f"  ! {filepath.name}: FAILED ({e})", file=sys.stderr)
            failures += 1

    print(f"\nDone. {total_written} chunk(s) {'would be ' if args.dry_run else ''}written across {len(targets)} file(s).")
    if not args.dry_run:
        print(f"Total rows now in knowledge_chunks: {database.count_knowledge_chunks()}")

    return 2 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
