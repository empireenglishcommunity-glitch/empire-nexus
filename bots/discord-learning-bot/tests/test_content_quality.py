"""Objective content-quality invariants for reading / broadcast / mediation.

The per-level `test_cefr_*_content.py` files check the WEEK data files
(vocabulary, missions, grammar, can-do library). `test_broadcast.py` checks the
broadcast word bar and channel narrowing. Neither checks the thing that most
directly makes a comprehension ITEM wrong or guessable: the multiple-choice
options and the answer key.

This file does. It was added after a full manual review of all 270
reading/mediation/broadcast files (2026-08-27), at which point every assertion
here passed. Its job is to keep it that way: to fail the build the moment an
authored item acquires a bad answer index, a duplicate option, an empty field,
an invalid descriptor code, or a glossary entry with no Arabic.

What it deliberately does NOT assert:
  * that the KEYED answer is the CORRECT one -- no test can know that; it was
    verified by reading, and stays a human responsibility on new content;
  * length/position balance across options -- those are guessability *smells*,
    reported by scripts/content_qa.py, not correctness errors, and are left to a
    human-reviewed authoring pass rather than mass-edited into currently-correct
    content.
"""
import glob
import json
import os
import re

import pytest

from src import curriculum

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEVELS = ("a1", "a2", "b1", "b2", "c1", "c2")
ARABIC = re.compile(r"[\u0600-\u06FF]")


def _files(kind):
    out = []
    for level in LEVELS:
        out += sorted(glob.glob(os.path.join(HERE, "content", level, kind, "*.json")))
    return out


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _id(path):
    # e.g. .../content/c2/reading/week1_so_be_it.json -> c2/reading/week1_so_be_it
    parts = path.split(os.sep)
    return f"{parts[-3]}/{parts[-2]}/{parts[-1][:-5]}"


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _dmap(level):
    return curriculum.can_do_descriptor_map(level.upper())


def _check_mcq(qs, *, min_options, require_q_ar, where):
    """Assert every MCQ in `qs` is structurally sound. Returns nothing; raises."""
    for i, q in enumerate(qs):
        loc = f"{where} q{i}"
        stem = q.get("q")
        assert stem and stem.strip(), f"{loc}: empty question stem"
        opts = q.get("options")
        assert isinstance(opts, list) and len(opts) >= min_options, (
            f"{loc}: needs >= {min_options} options, has "
            f"{len(opts) if isinstance(opts, list) else 'none'}")
        assert all(isinstance(o, str) and o.strip() for o in opts), (
            f"{loc}: an option is empty or non-string")
        assert len(set(opts)) == len(opts), (
            f"{loc}: duplicate option text: {opts}")
        # near-duplicate (same ignoring case/punctuation) -> likely double-correct
        norms = [_norm(o) for o in opts]
        assert len(set(norms)) == len(norms), (
            f"{loc}: two options are identical ignoring case/punctuation "
            f"(possible double-correct): {opts}")
        ans = q.get("answer")
        assert isinstance(ans, int) and 0 <= ans < len(opts), (
            f"{loc}: answer index {ans!r} out of range for {len(opts)} options")
        if require_q_ar:
            assert q.get("q_ar"), f"{loc}: reading question missing Arabic (q_ar)"


def _check_glossary(gloss, where):
    for i, g in enumerate(gloss or []):
        assert isinstance(g, dict), f"{where} glossary[{i}] not an object"
        assert g.get("word", "").strip(), f"{where} glossary[{i}] has no word"
        ar = g.get("ar", "")
        assert ar and ar.strip(), f"{where} glossary[{i}] ({g.get('word')!r}) has no Arabic"
        assert ARABIC.search(ar), (
            f"{where} glossary[{i}] ({g.get('word')!r}) 'ar' has no Arabic script: {ar!r}")


# --------------------------------------------------------------------------- #
#  READING
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", _files("reading"), ids=_id)
def test_reading_items_are_sound(load_curriculum, path):
    d = _load(path)
    level = d["level"].lower()
    where = _id(path)
    qs = d.get("questions") or []
    assert qs, f"{where}: reading has no questions"
    _check_mcq(qs, min_options=3, require_q_ar=True, where=where)
    _check_glossary(d.get("glossary"), where)
    dmap = _dmap(level)
    for c in d.get("can_do", []):
        assert c in dmap, f"{where}: can_do {c} not in {level.upper()} library"


# --------------------------------------------------------------------------- #
#  BROADCAST
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", _files("broadcast"), ids=_id)
def test_broadcast_items_are_sound(load_curriculum, path):
    d = _load(path)
    level = d["level"].lower()
    where = _id(path)
    qs = ([d["gist_question"]] if d.get("gist_question") else []) + (d.get("questions") or [])
    _check_mcq(qs, min_options=3, require_q_ar=False, where=where)
    assert len(d.get("questions") or []) >= 2, (
        f"{where}: needs >= 2 detail questions to evidence a listening descriptor")
    _check_glossary(d.get("glossary"), where)
    for s in d.get("segments", []):
        assert s.get("text", "").strip(), f"{where}: a segment has empty text"
    dmap = _dmap(level)
    for c in d.get("can_do", []):
        assert c in dmap, f"{where}: can_do {c} not in {level.upper()} library"


# --------------------------------------------------------------------------- #
#  MEDIATION
# --------------------------------------------------------------------------- #
def _text_of(v):
    return (v.get("en", "") if isinstance(v, dict) else v) or ""


@pytest.mark.parametrize("path", _files("mediation"), ids=_id)
def test_mediation_items_are_sound(load_curriculum, path):
    d = _load(path)
    level = d["level"].lower()
    where = _id(path)
    for field in ("scenario", "source", "task", "model_answer"):
        raw = d.get(field)
        assert _text_of(raw).strip(), f"{where}: missing/empty '{field}'"
        if isinstance(raw, dict):
            assert ARABIC.search(raw.get("ar", "") or ""), (
                f"{where}: bilingual field '{field}' has no Arabic side")
    assert len(d.get("key_points") or []) >= 2, f"{where}: needs >= 2 key points"
    dmap = _dmap(level)
    for c in d.get("can_do", []):
        assert c in dmap, f"{where}: can_do {c} not in {level.upper()} library"


# --------------------------------------------------------------------------- #
#  COVERAGE OF THE CHECKER ITSELF
# --------------------------------------------------------------------------- #
def test_the_checker_actually_sees_all_content():
    """Guard against the globs going blind and the file passing vacuously."""
    assert len(_files("reading")) == 90, len(_files("reading"))
    assert len(_files("broadcast")) == 90, len(_files("broadcast"))
    assert len(_files("mediation")) == 90, len(_files("mediation"))
