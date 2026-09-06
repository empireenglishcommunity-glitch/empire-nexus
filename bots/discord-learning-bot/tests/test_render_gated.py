"""Tests for the GATED render orchestrator (spec Phase 2).

The orchestrator is the mechanism that ends "sometimes good, sometimes bad": it
renders, measures against the standard, retries on failure, and — critically —
**refuses to emit an episode that has not passed**. These tests prove that
fail-closed behaviour without doing any real (slow) synthesis, by injecting fakes
for the renderer and the gate. That is exactly the seam the orchestrator was
designed with.
"""
import importlib.util
import json
import pathlib
import tempfile

import pytest

BOT_DIR = pathlib.Path(__file__).resolve().parent.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, BOT_DIR / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rg = _load("render_episode_gated", "scripts/render_episode_gated.py")


class _Harness:
    """Installs fake render/gate/line-report functions on the orchestrator and
    restores them afterwards, so the retry/fail-closed logic is tested in
    isolation (no audio engines, milliseconds not minutes)."""

    def __init__(self, gate_results, stems=None):
        # gate_results: list of bool — pass/fail for each successive attempt.
        self.gate_results = list(gate_results)
        self.stems = stems or [{"index": 1, "character": "narrator",
                                "file": "/dev/null", "seconds": 2.0, "text": "hi"}]
        self.render_calls = 0
        self.gate_calls = 0
        self._orig = {}

    def __enter__(self):
        self._orig = {"render": rg.rv2.render, "gate": rg._gate,
                      "lines": rg._line_stems_report}

        def fake_render(script_text, out, level, music, sound_design, stems_dir,
                        seed=0, **kwargs):
            self.render_calls += 1
            pathlib.Path(out).write_bytes(b"FAKEAUDIO")
            return {"ok": True, "out_path": str(out), "duration_seconds": 330,
                    "line_count": len(self.stems), "stems": self.stems,
                    "music": music, "used_assets": [], "credit": ""}

        def fake_gate(audio, script, level, transcriber=None):
            i = self.gate_calls
            self.gate_calls += 1
            passed = self.gate_results[min(i, len(self.gate_results) - 1)]
            return {"passed": passed,
                    "failures": [] if passed else ["wer"],
                    "unmeasured_critical": [], "metrics": {}, "attempt": i + 1}

        def fake_lines(stems, level, transcriber=None):
            return ([] if self.gate_results[min(self.gate_calls - 1,
                    len(self.gate_results) - 1)] else [1]), []

        rg.rv2.render = fake_render
        rg._gate = fake_gate
        rg._line_stems_report = fake_lines
        return self

    def __exit__(self, *a):
        rg.rv2.render = self._orig["render"]
        rg._gate = self._orig["gate"]
        rg._line_stems_report = self._orig["lines"]


def _script(tmp):
    p = pathlib.Path(tmp) / "ep.txt"
    p.write_text("Narrator: hello there.\nMaya: hi.\n", encoding="utf-8")
    return p


def test_passes_first_time_emits_and_reports():
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "ep.mp3"
        with _Harness([True]) as h:
            r = rg.render_gated(_script(d), out, level="A2", max_attempts=3)
        assert r["passed"] is True
        assert r["attempts"] == 1
        assert h.render_calls == 1
        assert out.exists(), "a passing episode must be emitted"
        assert pathlib.Path(r["report_path"]).exists(), "a report is always written"


def test_retries_then_passes():
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "ep.mp3"
        with _Harness([False, False, True]) as h:
            r = rg.render_gated(_script(d), out, level="A2", max_attempts=3)
        assert r["passed"] is True
        assert r["attempts"] == 3
        assert h.render_calls == 3
        assert out.exists()


def test_fail_closed_never_emits_a_bad_episode():
    """THE core guarantee: if every attempt fails, NO episode is written and the
    exit is a failure so the caller keeps yesterday's state and alerts (R4.3)."""
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "ep.mp3"
        with _Harness([False, False, False]) as h:
            r = rg.render_gated(_script(d), out, level="A2", max_attempts=3)
        assert r["passed"] is False
        assert r["attempts"] == 3
        assert h.render_calls == 3
        assert r["out_path"] is None
        assert not out.exists(), "a FAILING episode must NOT be written"
        # but a diagnostic report still exists
        assert pathlib.Path(r["report_path"]).exists()


def test_failure_never_overwrites_a_previous_good_episode():
    """If yesterday's good episode is already at the output path, a failing render
    today must leave it untouched (fail-closed, R4.3)."""
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "ep.mp3"
        out.write_bytes(b"YESTERDAYS_GOOD_EPISODE")
        with _Harness([False, False, False]):
            r = rg.render_gated(_script(d), out, level="A2", max_attempts=3)
        assert r["passed"] is False
        assert out.read_bytes() == b"YESTERDAYS_GOOD_EPISODE", \
            "a failing render overwrote the previous good episode"


def test_report_is_serialisable_and_records_every_attempt():
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "ep.mp3"
        with _Harness([False, True]):
            r = rg.render_gated(_script(d), out, level="A2", max_attempts=3)
        json.dumps(r)                              # must not raise
        assert len(r["attempts_log"]) == 2
        assert r["attempts_log"][0]["passed"] is False
        assert r["attempts_log"][1]["passed"] is True


def test_respects_max_attempts_bound():
    """An automatic system must never run away; attempts are bounded (R9.6)."""
    with tempfile.TemporaryDirectory() as d:
        out = pathlib.Path(d) / "ep.mp3"
        with _Harness([False] * 10) as h:
            r = rg.render_gated(_script(d), out, level="A2", max_attempts=2)
        assert h.render_calls == 2, "must not exceed max_attempts"
        assert r["passed"] is False
