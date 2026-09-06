"""Tests for the story bible (spec Phase 4.1).

The bible is the narrative source of truth: recurring characters keyed to real
voices, and a small genre palette whose moods must exist in the owned library.
These tests pin the guarantees Phase 4 depends on:
  * every genre's mood is a REAL, canonical podcast_lab mood with an asset behind
    it (so mood-aware scoring can never point at a missing bed);
  * every bible character maps to a real cast entry (so the writer can only name
    people the renderer can voice);
  * genre rotation never repeats back-to-back (arc variety, task 4.3).
"""
from src import sawt_bible as bible
from src import sawt_cast as cast
from src import podcast_lab as lab


def test_every_character_is_keyed_to_a_real_cast_entry():
    for key, ch in bible.CHARACTERS.items():
        assert ch["cast_key"] in cast.CAST, f"{key} -> unknown cast key {ch['cast_key']}"
        # each carries a story spine
        assert ch["want"] and ch["archetype"] and ch["traits"]


def test_speaking_names_match_the_cast_registry():
    assert bible.speaking_names() == cast.speaking_names()


def test_character_brief_names_only_real_characters():
    brief = bible.character_brief()
    assert brief.strip()
    # every display name mentioned is a real cast display name
    for key, ch in bible.CHARACTERS.items():
        assert cast.CAST[ch["cast_key"]]["display"] in brief


def test_every_genre_mood_is_canonical_and_available_on_disk():
    available = set(lab.available_moods())
    for genre, meta in bible.GENRES.items():
        mood = meta["mood"]
        assert mood in lab.MOODS, f"{genre} mood {mood!r} is not a canonical mood"
        assert mood in available, f"{genre} mood {mood!r} has no bed/ambience on disk"


def test_genre_rotation_never_repeats_back_to_back():
    prev = None
    for _ in range(len(bible.GENRE_ROTATION) * 3):
        nxt = bible.next_genre(prev)
        assert nxt in bible.GENRES
        if prev is not None:
            assert nxt != prev
        prev = nxt


def test_new_arc_seed_is_complete_and_differs_from_previous_genre():
    seed = bible.new_arc_seed(None, 0)
    for k in ("genre", "setting", "premise", "mood", "curiosity", "leads",
              "planned_episodes"):
        assert k in seed and seed[k] != "" and seed[k] is not None
    assert bible.ARC_MIN_EPISODES <= seed["planned_episodes"] <= bible.ARC_MAX_EPISODES
    # a follow-on arc gets a different genre
    seed2 = bible.new_arc_seed(seed["genre"], 1)
    assert seed2["genre"] != seed["genre"]


def test_leads_always_include_the_core_leads():
    for genre in bible.GENRES:
        leads = bible.leads_for_arc(genre)
        assert cast.CAST["maya"]["display"] in leads
        assert cast.CAST["leo"]["display"] in leads


def test_arc_window_is_five_to_seven():
    assert bible.ARC_MIN_EPISODES == 5
    assert bible.ARC_MAX_EPISODES == 7
    assert bible.ARC_MIN_EPISODES <= bible.ARC_DEFAULT_EPISODES <= bible.ARC_MAX_EPISODES
