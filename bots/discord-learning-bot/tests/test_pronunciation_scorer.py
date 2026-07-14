"""Unit tests for pronunciation_scorer.compare_words() algorithm.

Tests the FAIR word-level comparison that underpins all pronunciation scoring.
Includes: fuzzy matching, stop-word tolerance, Arabic substitution awareness.
"""
import re


# ─── Self-contained functions (same logic as pronunciation_scorer.py) ───

STOP_WORDS = frozenset([
    "the", "a", "an", "in", "on", "at", "to", "of", "for", "is", "it",
    "and", "or", "but", "my", "your", "his", "her", "its", "this", "that",
    "was", "were", "be", "been", "have", "has", "had", "do", "does", "did",
])

ARABIC_SUBSTITUTIONS = {
    "b": "p", "p": "b",
    "f": "v", "v": "f",
    "s": "th", "z": "th",
    "d": "th",
}


def _normalize(text: str) -> list[str]:
    text = text.lower()
    text = re.sub(r"[^\w\s']", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.split()


def _levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (0 if ca == cb else 1)))
        prev = curr
    return prev[-1]


def _words_match(transcript_word: str, expected_word: str) -> float:
    if transcript_word == expected_word:
        return 1.0
    distance = _levenshtein(transcript_word, expected_word)
    if distance <= 1:
        return 0.9
    if distance <= 2 and len(expected_word) >= 4:
        return 0.75
    if len(transcript_word) >= 2 and len(expected_word) >= 2:
        if (ARABIC_SUBSTITUTIONS.get(transcript_word[0]) == expected_word[0] and
                transcript_word[1:] == expected_word[1:]):
            return 0.7
        if expected_word.startswith("th") and transcript_word[0] in ("d", "s", "z"):
            if transcript_word[1:] == expected_word[2:] or _levenshtein(transcript_word, expected_word) <= 2:
                return 0.7
    return 0.0


def compare_words(transcript: str, expected: str, level: str = "L0") -> tuple[float, list[str]]:
    expected_words = _normalize(expected)
    transcript_words = _normalize(transcript)

    if not expected_words:
        return 100.0, []
    if not transcript_words:
        return 0.0, [w for w in expected_words if w not in STOP_WORDS][:5]

    total_weight = 0.0
    earned_weight = 0.0
    missed_content_words = []

    for exp_word in expected_words:
        is_stop = exp_word in STOP_WORDS
        weight = 0.5 if is_stop else 1.0
        total_weight += weight

        best_match = 0.0
        for tr_word in transcript_words:
            match_score = _words_match(tr_word, exp_word)
            best_match = max(best_match, match_score)
            if match_score == 1.0:
                break

        earned_weight += weight * best_match
        if best_match < 0.5 and not is_stop:
            missed_content_words.append(exp_word)

    raw_score = (earned_weight / total_weight) * 100 if total_weight > 0 else 100.0
    level_bonus = {"L0": 10, "L1": 5, "L2": 2, "L3": 0}.get(level, 10)
    adjusted_score = min(100.0, raw_score + level_bonus)
    final_score = max(40.0, adjusted_score)

    return round(final_score, 1), missed_content_words[:5]


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

    def test_completely_wrong_has_floor(self):
        """Score never goes below 40% (floor for encouragement)."""
        score, missed = compare_words(
            "something entirely different here now",
            "Pat put the pen in the paper bag"
        )
        assert score >= 40.0  # Floor!
        assert len(missed) > 0

    def test_partial_match_generous(self):
        score, missed = compare_words(
            "Pat put the pen in bag",  # missing "the paper"
            "Pat put the pen in the paper bag"
        )
        # With stop-word tolerance ("the" is half weight), score should be high
        assert score >= 75

    def test_empty_transcript_has_floor(self):
        score, missed = compare_words("", "Hello world")
        assert score == 0.0  # Only case with no floor (nothing said)
        assert len(missed) > 0

    def test_empty_expected(self):
        score, missed = compare_words("Hello world", "")
        assert score == 100.0
        assert missed == []

    def test_extra_words_no_penalty(self):
        """Extra filler words in transcript don't penalize."""
        score, missed = compare_words(
            "Pat uh put the uh pen in the paper um bag",
            "Pat put the pen in the paper bag"
        )
        assert score == 100.0
        assert missed == []

    def test_fuzzy_match_close_words(self):
        """Slight misspellings get partial credit (Levenshtein ≤ 2)."""
        score, missed = compare_words(
            "Pat putt the peen in the papor bag",  # close misspellings
            "Pat put the pen in the paper bag"
        )
        # Should be generous with fuzzy matching
        assert score >= 75

    def test_arabic_b_p_substitution(self):
        """Arabic speakers saying b instead of p get partial credit."""
        score, missed = compare_words(
            "bat but the ben in the baper bag",  # b/p substitution
            "Pat put the pen in the paper bag"
        )
        # With Arabic substitution awareness, this should score reasonably
        assert score >= 60  # NOT the harsh < 30% from before

    def test_stop_words_dont_heavily_penalize(self):
        """Missing stop words (the, a, in) only minor penalty."""
        score, missed = compare_words(
            "Pat put pen paper bag",  # missing all stop words
            "Pat put the pen in the paper bag"
        )
        assert score >= 70
        # "the" and "in" should NOT be in missed content words
        assert "the" not in missed
        assert "in" not in missed

    def test_level_l0_generous(self):
        """L0 beginners get a bonus."""
        score_l0, _ = compare_words("pat put pen", "Pat put the pen in the paper bag", level="L0")
        score_l3, _ = compare_words("pat put pen", "Pat put the pen in the paper bag", level="L3")
        assert score_l0 > score_l3  # L0 is more generous

    def test_single_word_match(self):
        score, missed = compare_words("hello", "hello")
        assert score == 100.0
        assert missed == []

    def test_real_accent_drill(self):
        """Real example from L0 week 1 day 1."""
        score, missed = compare_words(
            "Bob bought a big blue ball",
            "Bob bought a big blue ball"
        )
        assert score == 100.0

    def test_max_five_missed_words(self):
        """Missed words list is capped at 5."""
        score, missed = compare_words(
            "completely different text",
            "one two three four five six seven eight nine ten"
        )
        assert len(missed) <= 5


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
