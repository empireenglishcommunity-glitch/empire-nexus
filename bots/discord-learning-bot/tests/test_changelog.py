"""Tests for changelog / "What's New" (src/changelog.py) — Phase 4."""
from src import changelog, database


def _reset():
    database.set_setting("changelog_entries", "[]")


def test_empty_by_default():
    _reset()
    assert changelog.get_entries() == []
    assert changelog.latest() == {}


def test_add_and_list_newest_first():
    _reset()
    e1 = changelog.add_entry("First update")
    e2 = changelog.add_entry("Second update")
    assert e1 and e2
    entries = changelog.get_entries()
    assert entries[0]["text"] == "Second update"   # newest first
    assert entries[1]["text"] == "First update"
    assert changelog.latest()["text"] == "Second update"


def test_ids_strictly_increase():
    _reset()
    a = changelog.add_entry("a")
    b = changelog.add_entry("b")
    c = changelog.add_entry("c")
    assert a["id"] < b["id"] < c["id"]   # unique + increasing (page shows each once)


def test_empty_text_ignored():
    _reset()
    assert changelog.add_entry("   ") == {}
    assert changelog.get_entries() == []


def test_entry_has_date_and_text():
    _reset()
    e = changelog.add_entry("Vocabulary got faster")
    assert e["text"] == "Vocabulary got faster"
    assert e["date"]  # ISO date string
    assert isinstance(e["id"], int)


def test_capped_to_50():
    _reset()
    for i in range(60):
        changelog.add_entry(f"entry {i}")
    entries = changelog.get_entries(limit=100)
    assert len(entries) == 50
    assert entries[0]["text"] == "entry 59"  # newest kept
