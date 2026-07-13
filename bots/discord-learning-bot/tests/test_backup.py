"""Tests for scripts/backup.py — SQLite database backup + rotation.

Imports the script as a module (sys.path already includes the project
root via conftest.py) rather than shelling out to it, so these tests
run fast and don't depend on the `python3` binary being on PATH inside
the test environment.
"""
import glob
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts import backup as backup_module


@pytest.fixture(autouse=True)
def isolate_backup_paths(tmp_path, monkeypatch):
    """Point the backup script at a temp DB and temp backup dir for every
    test, so nothing here ever touches a real database or a real
    backups/ directory."""
    fake_db = tmp_path / "empire_english.db"
    fake_backup_dir = tmp_path / "backups"
    monkeypatch.setattr(backup_module, "DB_PATH", str(fake_db))
    monkeypatch.setattr(backup_module, "DEFAULT_BACKUP_DIR", str(fake_backup_dir))
    return fake_db, fake_backup_dir


def _make_fake_db(path):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE members (discord_id TEXT)")
    conn.execute("INSERT INTO members VALUES ('123')")
    conn.commit()
    conn.close()


def test_backup_missing_database_exits_1(isolate_backup_paths, capsys):
    with pytest.raises(SystemExit) as exc_info:
        backup_module.backup()
    assert exc_info.value.code == 1
    assert "not found" in capsys.readouterr().out


def test_backup_creates_timestamped_copy(isolate_backup_paths):
    fake_db, fake_backup_dir = isolate_backup_paths
    _make_fake_db(fake_db)

    result_path = backup_module.backup()

    assert os.path.exists(result_path)
    assert os.path.dirname(result_path) == str(fake_backup_dir)
    assert os.path.basename(result_path).startswith("empire_english_")
    assert result_path.endswith(".db")


def test_backup_copy_is_a_valid_readable_database(isolate_backup_paths):
    fake_db, _ = isolate_backup_paths
    _make_fake_db(fake_db)

    result_path = backup_module.backup()

    conn = sqlite3.connect(result_path)
    rows = conn.execute("SELECT discord_id FROM members").fetchall()
    conn.close()
    assert rows == [("123",)]


def test_backup_creates_backup_dir_if_missing(isolate_backup_paths):
    _, fake_backup_dir = isolate_backup_paths
    assert not fake_backup_dir.exists()
    fake_db = isolate_backup_paths[0]
    _make_fake_db(fake_db)

    backup_module.backup()

    assert fake_backup_dir.is_dir()


def test_backup_respects_custom_directory_argument(isolate_backup_paths, tmp_path):
    fake_db, _ = isolate_backup_paths
    _make_fake_db(fake_db)
    custom_dir = tmp_path / "custom-backups"

    result_path = backup_module.backup(str(custom_dir))

    assert os.path.dirname(result_path) == str(custom_dir)


def test_backup_rotation_keeps_only_max_backups(isolate_backup_paths):
    """Regression-style test for the exact rotation logic: creating more
    than MAX_BACKUPS backups must delete the oldest ones (by filename
    sort order, which is timestamp order since the format is
    YYYYMMDD_HHMMSS), keeping exactly MAX_BACKUPS afterward."""
    fake_db, fake_backup_dir = isolate_backup_paths
    _make_fake_db(fake_db)
    os.makedirs(fake_backup_dir, exist_ok=True)

    # Pre-seed more than MAX_BACKUPS fake backups with distinct,
    # deliberately out-of-order-of-creation but sortable timestamps.
    extra = backup_module.MAX_BACKUPS + 3
    for i in range(extra):
        ts = f"202601{(i % 28) + 1:02d}_{i:02d}0000"
        fake_backup_path = os.path.join(fake_backup_dir, f"empire_english_{ts}.db")
        with open(fake_backup_path, "wb") as f:
            f.write(b"fake db content")

    backup_module.backup()  # triggers rotation on top of the pre-seeded files

    remaining = glob.glob(os.path.join(str(fake_backup_dir), "empire_english_*.db"))
    assert len(remaining) == backup_module.MAX_BACKUPS


def test_backup_rotation_deletes_oldest_first(isolate_backup_paths):
    fake_db, fake_backup_dir = isolate_backup_paths
    _make_fake_db(fake_db)
    os.makedirs(fake_backup_dir, exist_ok=True)

    oldest = os.path.join(fake_backup_dir, "empire_english_20200101_000000.db")
    newest_seed = os.path.join(fake_backup_dir, "empire_english_20991231_235959.db")
    for path in (oldest, newest_seed):
        with open(path, "wb") as f:
            f.write(b"x")

    for i in range(backup_module.MAX_BACKUPS):
        ts = f"202602{(i % 28) + 1:02d}_{i:02d}0000"
        with open(os.path.join(fake_backup_dir, f"empire_english_{ts}.db"), "wb") as f:
            f.write(b"x")

    backup_module.backup()

    remaining = {os.path.basename(p) for p in glob.glob(
        os.path.join(str(fake_backup_dir), "empire_english_*.db")
    )}
    assert os.path.basename(oldest) not in remaining
    assert os.path.basename(newest_seed) in remaining


def test_backup_uses_config_db_path_not_a_hardcoded_path(monkeypatch):
    """Regression guard: this script must derive its database path from
    src/config.py's DB_PATH (the bot's own, tested path-resolution
    logic), never a separately hardcoded path that could silently drift
    out of sync with where the bot actually reads/writes its database.

    Reloads the module with the autouse isolation fixture's monkeypatch
    NOT applied (this test doesn't take the isolate_backup_paths
    fixture), so DB_PATH here reflects what the module actually
    computed at import time, straight from config.DB_PATH.
    """
    import importlib
    from src import config
    reloaded = importlib.reload(backup_module)
    assert reloaded.DB_PATH == str(config.DB_PATH)
