"""merge_credit_into_meta copies the render's credit line into episode-meta.json,
and must never fail the pipeline over a cosmetic credit."""
import importlib.util
import json
import pathlib


def _load():
    p = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "merge_credit_into_meta.py"
    spec = importlib.util.spec_from_file_location("merge_credit", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_merges_credit_into_meta(tmp_path):
    mod = _load()
    meta = tmp_path / "meta.json"
    qa = tmp_path / "qa.json"
    meta.write_text(json.dumps({"episode_number": 2, "title": "t"}))
    qa.write_text(json.dumps({"credit": "Sound effects by William Dyer, CC-BY 2.5",
                              "passed": True}))
    assert mod.merge(str(meta), str(qa)) is True
    out = json.loads(meta.read_text())
    assert out["credit"] == "Sound effects by William Dyer, CC-BY 2.5"
    assert out["title"] == "t"          # untouched


def test_missing_qa_leaves_meta_unchanged(tmp_path):
    mod = _load()
    meta = tmp_path / "meta.json"
    meta.write_text(json.dumps({"title": "t"}))
    assert mod.merge(str(meta), str(tmp_path / "nope.json")) is False
    assert json.loads(meta.read_text()) == {"title": "t"}


def test_empty_credit_leaves_meta_unchanged(tmp_path):
    mod = _load()
    meta = tmp_path / "meta.json"
    qa = tmp_path / "qa.json"
    meta.write_text(json.dumps({"title": "t"}))
    qa.write_text(json.dumps({"credit": ""}))
    assert mod.merge(str(meta), str(qa)) is False
