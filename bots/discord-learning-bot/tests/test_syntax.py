"""Syntax and import smoke tests — verify all modules compile and import
cleanly, and that curriculum JSON data files parse without error."""
import glob
import importlib
import json
import os


def test_import_config():
    mod = importlib.import_module("src.config")
    assert hasattr(mod, "DISCORD_TOKEN")
    assert hasattr(mod, "LEVELS")
    assert hasattr(mod, "DAILY_TASKS")


def test_import_database():
    mod = importlib.import_module("src.database")
    assert hasattr(mod, "init_db")
    assert hasattr(mod, "register_member")
    assert hasattr(mod, "log_submission")


def test_import_curriculum():
    mod = importlib.import_module("src.curriculum")
    assert hasattr(mod, "load_all")
    assert hasattr(mod, "get_vocabulary_for_week")
    assert hasattr(mod, "LEVEL_WEEK_COUNTS")


def test_import_tasks():
    mod = importlib.import_module("src.tasks")
    assert hasattr(mod, "generate_daily_tasks")
    assert hasattr(mod, "format_daily_post_chunks")


def test_import_verification():
    mod = importlib.import_module("src.verification")
    assert hasattr(mod, "verify_task")
    assert hasattr(mod, "check_cooldown")


def test_import_features():
    mod = importlib.import_module("src.features")
    assert hasattr(mod, "assign_buddy")
    assert hasattr(mod, "check_english_only")


def test_import_ai_engine():
    mod = importlib.import_module("src.ai_engine")
    assert hasattr(mod, "quick_feedback")
    assert hasattr(mod, "evaluate_writing")


def test_import_bot():
    """bot.py wires everything together with discord.py decorators — just
    confirm the module itself imports without error (no live connection)."""
    mod = importlib.import_module("src.bot")
    assert hasattr(mod, "run")


def test_all_weekly_data_json_files_parse():
    """Every data/{level}_week{N}.json file must be syntactically valid
    JSON — a single malformed file would silently break curriculum.load_all()
    for that one week only (caught, logged, but the week ends up missing),
    which is exactly the kind of partial failure this test exists to catch
    before it reaches production."""
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    files = glob.glob(os.path.join(base, "data", "*_week*.json"))
    assert len(files) == 38  # 8 + 10 + 12 + 8, per LEVEL_WEEK_COUNTS
    for path in files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "vocabulary" in data
        assert "theme" in data


def test_all_accent_and_grammar_json_files_parse():
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    files = glob.glob(os.path.join(base, "content", "*", "accent", "week*.json"))
    files += glob.glob(os.path.join(base, "content", "*", "grammar", "week*.json"))
    assert len(files) > 0
    for path in files:
        with open(path, encoding="utf-8") as f:
            json.load(f)  # must not raise


def test_env_example_documents_all_required_keys():
    """.env.example should at minimum mention the two keys config.py
    treats as required (bot.run() raises SystemExit without them) — if
    a required key is renamed in config.py without updating the example
    file, new setups would fail with a confusing error."""
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_example = os.path.join(base, ".env.example")
    with open(env_example, encoding="utf-8") as f:
        content = f.read()
    assert "DISCORD_TOKEN" in content
    assert "GUILD_ID" in content
