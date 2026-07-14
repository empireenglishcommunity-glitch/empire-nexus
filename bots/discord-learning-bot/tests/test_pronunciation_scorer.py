"""Unit tests for pronunciation_scorer.compare_words() algorithm.

Tests the word-level comparison that underpins all pronunciation scoring.
"""
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pronunciation_scorer import compare_words, _normalize


class TestNormalize:
    def test_basic(self):
        assert _normalize("Hello World") == ["hello", "world"]

    def test_punctuation_stripped(self):
        assert _normalize("Hello, world!") == ["hello", "world"]

    def test_apostrophe_kept(self):
        assert _normalize("don't it's") == ["don't", "it's"]

    def test_extra_spaces(self):
        assert _normalize("  hello   world  ") == ["hello", "world"]

    def test_empty(self):
        assert _normalize("") == []


class TestCompareWords:
    def test_exact_match(self):
        score, missed = compare_words(
            "Pat put the pen in the paper bag",
            "Pat put the pen in the paper bag"
        )
        assert score == 100.0
        assert missed == []

    def test_case_insensitive(self):
        score, missed = compare_words(
            "pat put the pen in the paper bag",
            "Pat Put The Pen In The Paper Bag"
        )
        assert score == 100.0
        assert missed == []

    def test_punctuation_insensitive(self):
        score, missed = compare_words(
            "pat put the pen in the paper bag",
            "Pat put the pen in the paper bag."
        )
        assert score == 100.0

    def test_completely_wrong(self):
        score, missed = compare_words(
            "something entirely different here now",
            "Pat put the pen in the paper bag"
        )
        assert score < 30
        assert len(missed) > 0

    def test_partial_match(self):
        score, missed = compare_words(
            "Pat put the pen in bag",  # missing "the paper"
            "Pat put the pen in the paper bag"
        )
        # 6 out of 8 words matched
        assert 70 <= score <= 80
        assert "paper" in missed

    def test_empty_transcript(self):
        score, missed = compare_words("", "Hello world")
        assert score == 0.0
        assert len(missed) > 0

    def test_empty_expected(self):
        score, missed = compare_words("Hello world", "")
        assert score == 100.0
        assert missed == []

    def test_extra_words_in_transcript(self):
        score, missed = compare_words(
            "Pat uh put the uh pen in the paper um bag",
            "Pat put the pen in the paper bag"
        )
        # All expected words are present, just with fillers
        assert score == 100.0
        assert missed == []

    def test_swapped_words(self):
        score, missed = compare_words(
            "put Pat the pen in the bag paper",
            "Pat put the pen in the paper bag"
        )
        # LCS handles some reordering — most words still match
        assert score >= 60

    def test_single_word_match(self):
        score, missed = compare_words("hello", "hello")
        assert score == 100.0
        assert missed == []

    def test_single_word_miss(self):
        score, missed = compare_words("helo", "hello")
        assert score == 0.0
        assert "hello" in missed

    def test_real_accent_drill(self):
        """Real example from L0 week 1 day 1."""
        score, missed = compare_words(
            "Bob bought a big blue ball",
            "Bob bought a big blue ball"
        )
        assert score == 100.0

    def test_arabic_speaker_common_errors(self):
        """Common Arabic-speaker pronunciation errors detected."""
        # 'p' → 'b' substitution (common for Arabic speakers)
        score, missed = compare_words(
            "bat but the ben in the baber bag",
            "Pat put the pen in the paper bag"
        )
        # Several word mismatches
        assert score < 60
        assert len(missed) >= 3

    def test_max_five_missed_words(self):
        """Missed words list is capped at 5."""
        score, missed = compare_words(
            "completely different text altogether now",
            "one two three four five six seven eight nine ten"
        )
        assert len(missed) <= 5


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
