"""Phase 7 — automation & observability tests (spec R9).

Covers the gaps built in Phase 7:
  * R9.5 — a per-episode run is recorded (emitted OR failed) and is queryable,
    keyed on slug (idempotent — a re-run UPSERTs, no duplicate history);
  * R9.6 — a max-spoken-lines ceiling rejects a runaway script;
  * R9.4 — the failure-summary helper produces a clean one-line alert detail.
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture()
def db(monkeypatch):
    os.environ.setdefault("DISCORD_TOKEN", "x")
    os.environ.setdefault("GUILD_ID", "1")
    os.environ.setdefault("TIMEZONE", "UTC")
    from src import config, database
    d = tempfile.mkdtemp()
    monkeypatch.setattr(config, "DB_PATH", pathlib.Path(d) / "t.db")
    database.init_db()
    return database


def test_run_recorded_on_pass_and_fail(db):
    """Both an emitted and a failed run are persisted with their outcome (R9.5)."""
    db.record_podcast_run(
        "chronicles-ep10", episode_number=10, level="A2", passed=True, attempts=1,
        failures=[], metrics={"wer": {"value": 0.03}, "duration_s": {"value": 400}},
        elapsed_seconds=250.0)
    db.record_podcast_run(
        "chronicles-ep11", episode_number=11, level="A2", passed=False, attempts=3,
        failures=["wer", "true_peak_dbtp"], metrics={"wer": {"value": 0.07}},
        elapsed_seconds=800.0)
    runs = db.recent_podcast_runs(5)
    by_slug = {r["slug"]: r for r in runs}
    assert by_slug["chronicles-ep10"]["passed"] == 1
    assert by_slug["chronicles-ep10"]["wer"] == 0.03
    assert by_slug["chronicles-ep11"]["passed"] == 0
    assert by_slug["chronicles-ep11"]["attempts"] == 3
    assert "wer" in by_slug["chronicles-ep11"]["failures"]


def test_run_record_is_idempotent_by_slug(db):
    """Re-recording the same slug UPSERTs — no duplicate history rows (R9.2)."""
    db.record_podcast_run("chronicles-ep12", episode_number=12, passed=False,
                          attempts=1, failures=["duration_s"])
    db.record_podcast_run("chronicles-ep12", episode_number=12, passed=True,
                          attempts=2, failures=[], metrics={"wer": {"value": 0.02}})
    runs = [r for r in db.recent_podcast_runs(20) if r["slug"] == "chronicles-ep12"]
    assert len(runs) == 1, "a re-run must overwrite, not duplicate"
    assert runs[0]["passed"] == 1 and runs[0]["attempts"] == 2


def test_record_episode_run_script_writes_a_row(db, monkeypatch):
    """The record_episode_run.py helper turns a qa.json into a DB row (R9.5)."""
    d = tempfile.mkdtemp()
    report = pathlib.Path(d) / "chronicles-ep13.qa.json"
    report.write_text(json.dumps({
        "passed": True, "attempts": 1, "elapsed_seconds": 240.0,
        "report": {"level": "A2", "failures": [],
                   "metrics": {"wer": {"value": 0.04},
                               "duration_s": {"value": 401.0}}},
    }), encoding="utf-8")
    meta = pathlib.Path(d) / "episode-meta.json"
    meta.write_text(json.dumps({"slug": "chronicles-ep13", "episode_number": 13,
                                "level": "A2"}), encoding="utf-8")
    # Run in-process so it uses the SAME monkeypatched DB_PATH as the fixture.
    sys.path.insert(0, str(BOT_DIR))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "record_episode_run", BOT_DIR / "scripts" / "record_episode_run.py")
    mod = importlib.util.module_from_spec(spec)
    monkeypatch.setattr(sys, "argv",
                        ["record_episode_run.py", "--report", str(report),
                         "--meta", str(meta)])
    spec.loader.exec_module(mod)
    assert mod.main() == 0
    runs = [r for r in db.recent_podcast_runs(20) if r["slug"] == "chronicles-ep13"]
    assert runs and runs[0]["passed"] == 1 and runs[0]["level"] == "A2"


def test_max_spoken_lines_ceiling_rejects_runaway():
    """A script over MAX_SPOKEN_LINES is rejected so synthesis can't run away (R9.6)."""
    from src import sawt_script_validator as V, audio_standards as STD
    lines = ["Narrator: Welcome to Empire English Chronicles."]
    lines += [f"Maya: This is line number {i} of the scene." for i in range(STD.MAX_SPOKEN_LINES + 5)]
    lines.append("Narrator: Vote below. Tomorrow, the story continues the way you choose.")
    ep = {"title": "T", "script": "\n".join(lines), "recap": "r", "facts": [],
          "mood": "mystery", "vote_a": "Go left now", "vote_b": "Go right now",
          "motif_used": False}
    probs = V.validate_episode(ep, level="A2", episode_number=1)
    assert any("Too many spoken lines" in p for p in probs)


def test_normal_length_episode_not_line_capped():
    """A normal episode is well under the ceiling (no false positive)."""
    from src import sawt_script_validator as V
    base = "Narrator: Welcome to Empire English Chronicles.\n"
    body = "\n".join(f"Maya: A short line {i}." for i in range(20))
    close = "\nNarrator: Vote below. Tomorrow, the story continues the way you choose."
    ep = {"title": "T", "script": base + body + close, "recap": "r", "facts": [],
          "mood": "mystery", "vote_a": "Go left now", "vote_b": "Go right now",
          "motif_used": False}
    probs = V.validate_episode(ep, level="A2", episode_number=1)
    assert not any("Too many spoken lines" in p for p in probs)


def test_qa_failure_summary_helper():
    """The alert detail helper prints a clean one-liner from a failed report (R9.4)."""
    d = tempfile.mkdtemp()
    report = pathlib.Path(d) / "f.qa.json"
    report.write_text(json.dumps({
        "passed": False, "attempts": 3,
        "report": {"failures": ["wer", "true_peak_dbtp"],
                   "unmeasured_critical": []},
    }), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, str(BOT_DIR / "scripts" / "qa_failure_summary.py"),
         str(report)],
        capture_output=True, text=True)
    assert out.returncode == 0
    assert "failures=wer,true_peak_dbtp" in out.stdout
    assert "attempts=3" in out.stdout


def test_qa_failure_summary_missing_report_is_safe():
    """A missing report never crashes the alert step (R9.4)."""
    out = subprocess.run(
        [sys.executable, str(BOT_DIR / "scripts" / "qa_failure_summary.py"),
         "/nonexistent/x.qa.json"],
        capture_output=True, text=True)
    assert out.returncode == 0
    assert out.stdout.strip()          # prints a safe fallback, not empty
