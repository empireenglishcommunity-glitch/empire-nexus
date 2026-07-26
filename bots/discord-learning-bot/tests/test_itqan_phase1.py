"""Itqan Phase 1 — generation engine (spiral). Pure logic, curriculum mocked."""
import pytest

from src import assessment, curriculum, database


@pytest.fixture(autouse=True)
def fake_curriculum(monkeypatch):
    # Deterministic fake vocab: 20 distinct words per week, tagged by week.
    def _vocab(week, level="L0"):
        return [
            {"word": f"w{week}_{i}", "arabic": f"ع{week}_{i}",
             "pronunciation": f"p{week}_{i}", "pos": "noun"}
            for i in range(20)
        ]
    monkeypatch.setattr(curriculum, "get_vocabulary_for_week", _vocab)
    monkeypatch.setattr(curriculum, "get_theme", lambda week, level="L0": f"theme{week}")
    # No SRS due words unless a test overrides.
    monkeypatch.setattr(database, "get_due_reviews", lambda did, limit=100: [])


def _skills(bp):
    return {it["skill"] for it in bp["items"]}


def test_all_five_skills_present():
    bp = assessment.generate_blueprint("u1", "L0", 3, seed="s", total_items=10)
    assert _skills(bp) == {"listening", "vocab", "pronunciation", "speaking", "writing"}


def test_total_items_bounded():
    bp = assessment.generate_blueprint("u1", "L0", 6, seed="s", total_items=10)
    assert len(bp["items"]) == 10
    # item numbers are 1..10 in order
    assert [it["item_no"] for it in bp["items"]] == list(range(1, 11))


def test_spiral_split_recent_vs_prior():
    bp = assessment.generate_blueprint("u1", "L0", 3, seed="s", total_items=10)
    # Production (speaking+writing) are current week; objective split 65/35.
    objective = [it for it in bp["items"] if it["skill"] in ("vocab", "listening", "pronunciation")]
    prior = [it for it in objective if it["source_week"] < 3]
    recent = [it for it in objective if it["source_week"] == 3]
    assert len(objective) == 8
    assert len(recent) == 5 and len(prior) == 3  # round(8*0.65)=5, remainder 3


def test_week1_has_no_prior():
    bp = assessment.generate_blueprint("u1", "L0", 1, seed="s", total_items=10)
    assert all(it["source_week"] == 1 for it in bp["items"])


def test_deterministic_same_seed():
    a = assessment.generate_blueprint("u1", "L0", 4, seed="same", total_items=10)
    b = assessment.generate_blueprint("u1", "L0", 4, seed="same", total_items=10)
    assert a == b


def test_differs_by_seed():
    a = assessment.generate_blueprint("u1", "L0", 4, seed="seedA", total_items=10)
    b = assessment.generate_blueprint("u1", "L0", 4, seed="seedB", total_items=10)
    # The chosen words should differ between attempts (anti-memorization).
    aw = [it["payload"].get("expected") or it["payload"].get("word") for it in a["items"]]
    bw = [it["payload"].get("expected") or it["payload"].get("word") for it in b["items"]]
    assert aw != bw


def test_prior_favors_weak_srs_words(monkeypatch):
    # Mark specific earlier-week words as "due" (weak) — they must be chosen first.
    weak = [{"word": "w1_7"}, {"word": "w2_3"}, {"word": "w1_11"}]
    monkeypatch.setattr(database, "get_due_reviews", lambda did, limit=100: weak)
    bp = assessment.generate_blueprint("u1", "L0", 3, seed="s", total_items=10)
    prior_words = [
        (it["payload"].get("expected") or it["payload"].get("word"))
        for it in bp["items"]
        if it["skill"] in ("vocab", "listening", "pronunciation") and it["source_week"] < 3
    ]
    # For vocab items expected=English word; for listening expected=arabic.
    # Normalize: prior items should be drawn from the weak set first.
    weak_words = {"w1_7", "w2_3", "w1_11"}
    # every prior item's word (english) should be in the weak set (3 prior slots, 3 weak words)
    prior_en = [
        it["payload"]["word"] if it["skill"] == "pronunciation"
        else (it["payload"]["expected"] if it["skill"] == "vocab"
              else it["payload"]["say_en"])
        for it in bp["items"]
        if it["skill"] in ("vocab", "listening", "pronunciation") and it["source_week"] < 3
    ]
    assert set(prior_en).issubset(weak_words)
