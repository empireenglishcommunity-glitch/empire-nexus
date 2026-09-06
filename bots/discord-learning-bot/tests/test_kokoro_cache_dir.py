"""The Kokoro model cache directory must be configurable (groundwork for running
the v2 renderer off-server, e.g. on a non-root CI runner where /root is not
writable). Default stays backward-compatible with the server (~/.cache/kokoro,
which for root is /root/.cache/kokoro)."""
import importlib.util
import os
import pathlib


def _load_render_v2():
    p = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "render_story_v2.py"
    spec = importlib.util.spec_from_file_location("rsv_cachetest", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_cache_dir_honours_env_override(monkeypatch):
    monkeypatch.setenv("KOKORO_CACHE_DIR", "/tmp/eec-kokoro-test")
    mod = _load_render_v2()
    assert str(mod._KOKORO_DIR) == "/tmp/eec-kokoro-test"


def test_cache_dir_defaults_to_home_cache(monkeypatch):
    monkeypatch.delenv("KOKORO_CACHE_DIR", raising=False)
    mod = _load_render_v2()
    assert mod._KOKORO_DIR == pathlib.Path.home() / ".cache" / "kokoro"
