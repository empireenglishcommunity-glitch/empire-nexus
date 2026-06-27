"""Tests for src/config.py — configuration loading and rank logic."""
from src import config


def test_rank_thresholds_descending():
    """RANKS must be in descending order of threshold."""
    thresholds = [r[0] for r in config.RANKS]
    assert thresholds == sorted(thresholds, reverse=True)


def test_rank_for_zero():
    name, emoji = config.rank_for(0)
    assert name == "مشارك جديد"
    assert emoji == "🌱"


def test_rank_for_one():
    name, emoji = config.rank_for(1)
    assert name == "بدأ الرحلة"
    assert emoji == "🥉"


def test_rank_for_fifteen():
    name, emoji = config.rank_for(15)
    assert name == "مثابر"
    assert emoji == "🥈"


def test_rank_for_twenty_two():
    name, emoji = config.rank_for(22)
    assert name == "محارب"
    assert emoji == "🥇"


def test_rank_for_thirty():
    name, emoji = config.rank_for(30)
    assert name == "بطل المرونة"
    assert emoji == "👑"


def test_rank_for_exceeds_thirty():
    """Even more than 30 should still return top rank."""
    name, emoji = config.rank_for(50)
    assert name == "بطل المرونة"


def test_total_days():
    assert config.TOTAL_DAYS == 30


def test_paths_are_absolute():
    import os
    assert os.path.isabs(config.BASE_DIR)
    assert os.path.isabs(config.DATA_DIR)
    assert os.path.isabs(config.DB_PATH)
