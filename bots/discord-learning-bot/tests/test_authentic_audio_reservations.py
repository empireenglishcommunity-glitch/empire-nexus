"""A film reservation must close itself when the real recordings arrive.

`B2.R.2` and `C1.R.2` both name FILMS. Synthesised audio delivers the words, the
slang and the ellipsis but not what an actor does with a line, so both descriptors
carry a reservation. The debt is paid by recording the drama scenes with real
voices.

Rather than depend on someone remembering to hand-edit `coverage_ledger.py` on the
day that happens, closure is DECLARATIVE: record the scene, list it in
`content/cefr/authentic_audio.json`, and the reservation lifts on the next run.

These tests pin the three properties that make that safe:

  * ALL required scenes must be present — a partial recording must not close it;
  * a reservation with no stated completion condition can never auto-close;
  * the manifest failing to load must leave the reservation OPEN (fail towards
    honesty, never towards a claim we cannot support).
"""
import json

import pytest

from src import coverage_ledger as cl

FILM_RESERVATIONS = ("B2.R.2", "C1.R.2")


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    """Point the ledger at a throwaway manifest so tests never touch the real one."""
    path = tmp_path / "authentic_audio.json"
    path.write_text(json.dumps({"scenes": []}), encoding="utf-8")
    monkeypatch.setattr(cl, "_AUTHENTIC_AUDIO_PATH", path)

    def _set(scenes):
        path.write_text(json.dumps({"scenes": scenes}), encoding="utf-8")
    return _set


# ============================================================
#  The declaration contract
# ============================================================

def test_both_film_reservations_state_how_they_close():
    """A reservation without a completion condition is an excuse, not a debt."""
    for code in FILM_RESERVATIONS:
        entry = cl.TAUGHT_WITH_RESERVATION[code]
        scenes = entry.get("requires_authentic_scenes")
        assert scenes, f"{code} does not say which scenes would close it"
        level = code.split(".")[0].lower()
        for s in scenes:
            assert s.startswith(level + "-w"), f"{code} lists foreign scene {s}"


def test_required_scenes_are_real_drama_scenes(load_curriculum):
    """Guard against a typo'd scene id, which would make a reservation
    permanently uncloseable while looking perfectly fine."""
    from src import curriculum
    for code in FILM_RESERVATIONS:
        for scene in cl.TAUGHT_WITH_RESERVATION[code]["requires_authentic_scenes"]:
            level, wk = scene.split("-w")
            bc = curriculum.get_broadcast_for_week(int(wk), level.upper())
            assert bc, f"{scene} is not a real week"
            assert bc.get("format") == "drama scene", f"{scene} is not a drama scene"
            assert code in (bc.get("can_do") or []), f"{scene} does not target {code}"


# ============================================================
#  Closing behaviour
# ============================================================

def test_reservations_are_open_while_nothing_is_recorded(manifest):
    manifest([])
    for code in FILM_RESERVATIONS:
        assert cl.reservation_is_closed(code) is False
    assert set(cl.open_reservations()) == set(FILM_RESERVATIONS)


def test_a_partial_recording_does_not_close_a_reservation(manifest):
    """The dangerous case: some scenes done, and the ledger quietly stops
    disclosing the shortfall."""
    required = cl.TAUGHT_WITH_RESERVATION["B2.R.2"]["requires_authentic_scenes"]
    manifest(list(required[:-1]))          # all but one
    assert cl.reservation_is_closed("B2.R.2") is False
    manifest(list(required))               # now complete
    assert cl.reservation_is_closed("B2.R.2") is True


def test_each_reservation_closes_independently(manifest):
    manifest(list(cl.TAUGHT_WITH_RESERVATION["B2.R.2"]["requires_authentic_scenes"]))
    assert cl.reservation_is_closed("B2.R.2") is True
    assert cl.reservation_is_closed("C1.R.2") is False
    assert set(cl.open_reservations()) == {"C1.R.2"}


def test_scene_ids_are_matched_case_insensitively(manifest):
    manifest([s.upper() for s in
              cl.TAUGHT_WITH_RESERVATION["C1.R.2"]["requires_authentic_scenes"]])
    assert cl.reservation_is_closed("C1.R.2") is True


def test_all_recorded_removes_the_block_from_the_report(manifest, load_curriculum):
    every = []
    for code in FILM_RESERVATIONS:
        every += cl.TAUGHT_WITH_RESERVATION[code]["requires_authentic_scenes"]
    manifest(every)
    rep = cl.report()
    assert rep["taught_with_reservation"] == {}
    assert sorted(rep["reservations_closed_by_authentic_audio"]) == sorted(FILM_RESERVATIONS)
    assert "TAUGHT, WITH A STATED RESERVATION" not in cl.format_report(rep)


# ============================================================
#  Failing safely
# ============================================================

def test_a_broken_manifest_leaves_reservations_open(tmp_path, monkeypatch):
    """If the manifest cannot be read we must keep disclosing the shortfall.
    Failing the other way would drop an honest caveat because of a syntax error."""
    bad = tmp_path / "authentic_audio.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setattr(cl, "_AUTHENTIC_AUDIO_PATH", bad)
    assert cl.authentic_scenes() == set()
    for code in FILM_RESERVATIONS:
        assert cl.reservation_is_closed(code) is False


def test_a_missing_manifest_leaves_reservations_open(tmp_path, monkeypatch):
    monkeypatch.setattr(cl, "_AUTHENTIC_AUDIO_PATH", tmp_path / "nope.json")
    assert cl.authentic_scenes() == set()
    assert set(cl.open_reservations()) == set(FILM_RESERVATIONS)


def test_a_reservation_with_no_condition_never_auto_closes(manifest, monkeypatch):
    monkeypatch.setitem(cl.TAUGHT_WITH_RESERVATION, "ZZ.R.9",
                        {"descriptor": "d", "taught_by": "t",
                         "reservation": "r", "removed_by": "x"})
    manifest(["anything", "everything"])
    assert cl.reservation_is_closed("ZZ.R.9") is False


def test_the_live_manifest_is_valid_and_starts_empty():
    """The shipped manifest must parse, and must not claim recordings we do not
    have."""
    with open(cl._AUTHENTIC_AUDIO_PATH, encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data.get("scenes"), list)
    for code in FILM_RESERVATIONS:
        assert cl.reservation_is_closed(code) is False, (
            f"{code} is reported closed — only list a scene once it is really "
            f"recorded with human voices")
