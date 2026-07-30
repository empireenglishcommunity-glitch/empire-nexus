"""Nutq 2 scorer — scoring-math unit tests.

These test the PURE scoring pipeline (canon, alignment, per-word/overall score,
Arabic partial credit, feedback) using hand-crafted phoneme sequences — NO model,
NO torch, NO g2p/nltk required. Model + audio are covered by live validation.
"""
import scorer


# ref: "pat bob" → pat=[p,a,t], bob=[b,a,b]
REF_FLAT = ["p", "a", "t", "b", "a", "b"]
REF_WIDX = [0, 0, 0, 1, 1, 1]
REF_WORDS = ["pat", "bob"]


def _score(hyp, level="L0"):
    return scorer.score_from_phonemes(REF_FLAT, REF_WIDX, REF_WORDS, hyp, level)


def test_identical_read_scores_100_no_missed():
    r = _score(["p", "a", "t", "b", "a", "b"])
    assert r["score"] == 100.0
    assert r["missed_words"] == []
    assert all(w["accuracy"] == 1.0 for w in r["per_word"])


def test_totally_wrong_read_scores_low_and_flags_words():
    r = _score(["z", "z", "z", "z", "z", "z"])
    assert r["score"] < 30
    assert set(r["missed_words"]) == {"pat", "bob"}


def test_empty_hyp_is_graceful_and_low():
    r = _score([])
    assert r["score"] <= 20
    assert "pat" in r["missed_words"] and "bob" in r["missed_words"]


def test_arabic_substitution_gets_partial_credit():
    # p→b is a known Arabic substitution: "pat" read as "bat"
    arabic = _score(["b", "a", "t", "b", "a", "b"])
    # unrelated substitution of the same slot: "pat" read as "zat"
    unrelated = _score(["z", "a", "t", "b", "a", "b"])
    # partial credit → arabic scores higher than an unrelated error…
    assert arabic["score"] > unrelated["score"]
    # …and higher than a totally wrong read, but below a perfect one
    assert 0 < unrelated["score"] < arabic["score"] < 100


def test_arabic_substitution_may_not_flag_the_word():
    # "pat"→"bat" : accuracy = (0.6 + 1 + 1)/3 ≈ 0.87 → above missed threshold
    r = _score(["b", "a", "t", "b", "a", "b"])
    pat = next(w for w in r["per_word"] if w["word"] == "pat")
    assert pat["accuracy"] > scorer.MISSED_WORD_THRESHOLD
    assert "pat" not in r["missed_words"]


def test_one_bad_word_only_flags_that_word():
    # pat correct, bob totally wrong
    r = _score(["p", "a", "t", "z", "z", "z"])
    assert "bob" in r["missed_words"]
    assert "pat" not in r["missed_words"]


def test_insertions_reduce_score_but_do_not_crash():
    # correct phones + spurious extra sounds
    r = _score(["p", "a", "t", "b", "a", "b", "z", "z", "z"])
    assert 0 <= r["score"] <= 100
    assert r["score"] < 100  # extra sounds cost something


def test_empty_reference_returns_zero():
    r = scorer.score_from_phonemes([], [], [], ["p", "a", "t"])
    assert r["score"] == 0.0
    assert r["missed_words"] == []


def test_calibrate_clamps_range():
    assert scorer.calibrate(150) == 100.0
    assert scorer.calibrate(-20) == 0.0
    assert 0 <= scorer.calibrate(63.4) <= 100


def test_feedback_is_bilingual_and_nonempty():
    for sc in (95, 80, 60, 30):
        en, ar = scorer.make_feedback(sc, ["through"])
        assert en and ar
        assert en != ar


def test_canon_collapses_notation_equivalents():
    # ɹ→r, ɡ→g, schwa-ish vowels→a, length marks stripped
    assert scorer.canon_seq(["ɹ"]) == ["r"]
    assert scorer.canon_seq(["ɡ"]) == ["g"]
    assert scorer.canon_seq(["ə", "ʌ", "æ"]) == ["a", "a", "a"]
    assert scorer.canon_seq(["iː"]) == ["i"]


def test_sub_cost_matrix():
    assert scorer._sub_cost("p", "p") == 0.0
    assert scorer._sub_cost("p", "b") == scorer.COST_PARTIAL   # Arabic pair
    assert scorer._sub_cost("p", "z") == scorer.COST_SUB       # unrelated


# ── Phase 3: calibration (fitted on real Arabic-accented samples) ────────
def test_calibrate_endpoints_and_monotonic():
    assert scorer.calibrate(0) == 0.0
    assert scorer.calibrate(100) == 100.0
    # monotonic non-decreasing
    prev = -1
    for x in range(0, 101, 5):
        y = scorer.calibrate(x)
        assert y >= prev
        prev = y


def test_calibrate_lifts_midrange_but_keeps_wrong_low():
    # a genuine accented correct read (~66 raw) should feel encouraging…
    assert 72 <= scorer.calibrate(66) <= 85
    # …while a wrong read stays low
    assert scorer.calibrate(10) < 25
    assert scorer.calibrate(0) == 0.0


# ── Phase 3: sound-specific feedback ─────────────────────────────────────
def test_score_from_phonemes_reports_weak_phonemes():
    # ref "think" ~ [θ,i,n,k]; hyp says [s,i,n,k] (θ→s, a classic Arabic error)
    r = scorer.score_from_phonemes(["θ", "i", "n", "k"], [0, 0, 0, 0], ["think"],
                                   ["s", "i", "n", "k"])
    pw = r["per_word"][0]
    assert "weak_phonemes" in pw


def test_weak_phoneme_picks_a_tipped_sound():
    per_word = [{"word": "think", "accuracy": 0.5, "weak_phonemes": ["θ", "θ"]},
                {"word": "cat", "accuracy": 1.0, "weak_phonemes": []}]
    assert scorer.weak_phoneme(per_word) == "θ"


def test_feedback_uses_sound_specific_tip():
    en, ar = scorer.make_feedback(60, ["think"], weak="θ")
    assert "th" in en.lower()          # names the 'th' sound
    assert en and ar and en != ar
