"""Nutq — Azure Pronunciation Assessment client tests.

Uses Azure's REAL (flat) short-audio REST response shape, verified live:
scores sit directly on NBest[0] and on each Word/Phoneme (not nested under
'PronunciationAssessment'). Headline score = AccuracyScore (fair for L0).
No network, no ffmpeg, no key required.
"""
from src import pronunciation_azure as az


def _resp(accuracy, pron, fluency, completeness, words):
    return {
        "RecognitionStatus": "Success",
        "NBest": [{
            "AccuracyScore": accuracy, "PronScore": pron,
            "FluencyScore": fluency, "CompletenessScore": completeness,
            "Words": words,
        }],
    }


def _word(word, acc, error="None", phonemes=None):
    w = {"Word": word, "AccuracyScore": acc, "ErrorType": error}
    if phonemes:
        w["Phonemes"] = [{"Phoneme": p, "AccuracyScore": a} for p, a in phonemes]
    return w


def test_good_read_headline_is_accuracy_no_missed():
    data = _resp(96.0, 97.4, 99.0, 100.0, [_word("pat", 94.0), _word("bob", 92.0)])
    r = az.parse_azure_response(data)
    assert r["score"] == 96.0           # headline = AccuracyScore, NOT PronScore
    assert r["pron_score"] == 97.4 and r["fluency"] == 99.0
    assert r["missed_words"] == []


def test_accented_read_not_punished_for_fluency():
    # Verified-live pattern: accent-correct → Accuracy high even if PronScore low.
    data = _resp(89.0, 50.2, 23.0, 93.0, [_word("please", 88.0), _word("stella", 90.0)])
    r = az.parse_azure_response(data)
    assert r["score"] == 89.0           # fair headline (would be 50 if we used PronScore)


def test_wrong_word_flagged_with_worst_phoneme():
    data = _resp(61.0, 60.0, 80.0, 100.0, [
        _word("i", 95.0),
        _word("walk", 90.0),
        _word("through", 38.0, error="Mispronunciation",
              phonemes=[("th", 22.0), ("r", 70.0), ("uw", 80.0)]),
    ])
    r = az.parse_azure_response(data)
    assert r["score"] == 61.0
    assert "through" in r["missed_words"]
    assert r["worst_phoneme"] == "th"


def test_low_accuracy_word_flagged_even_without_error_type():
    data = _resp(70.0, 70.0, 90.0, 100.0,
                 [_word("prizes", 45.0, error="None", phonemes=[("p", 80.0), ("r", 30.0)])])
    r = az.parse_azure_response(data)
    assert "prizes" in r["missed_words"]
    assert r["worst_phoneme"] == "r"


def test_omission_flagged_insertion_not_added():
    data = _resp(80.0, 78.0, 60.0, 70.0, [
        _word("please", 20.0, error="Omission"),
        _word("umm", 10.0, error="Insertion"),
    ])
    r = az.parse_azure_response(data)
    assert "please" in r["missed_words"]      # omitted target word → flag
    assert "umm" not in r["missed_words"]     # inserted filler → not a target word


def test_nested_shape_fallback_still_parsed():
    # Robustness: if a future/SDK response nests under PronunciationAssessment.
    data = {"RecognitionStatus": "Success", "NBest": [{
        "PronunciationAssessment": {"AccuracyScore": 88.0, "PronScore": 90.0},
        "Words": [{"Word": "hi", "PronunciationAssessment": {"AccuracyScore": 88.0, "ErrorType": "None"}}],
    }]}
    r = az.parse_azure_response(data)
    assert r["score"] == 88.0


def test_non_success_status_returns_none():
    assert az.parse_azure_response({"RecognitionStatus": "InitialSilenceTimeout", "NBest": []}) is None


def test_empty_nbest_returns_none():
    assert az.parse_azure_response({"RecognitionStatus": "Success", "NBest": []}) is None


def test_garbage_returns_none():
    assert az.parse_azure_response(None) is None
    assert az.parse_azure_response({}) is None


def test_pa_header_is_base64_json_with_reference():
    import base64, json
    cfg = json.loads(base64.b64decode(az._pa_header("Hello world")))
    assert cfg["ReferenceText"] == "Hello world"
    assert cfg["Granularity"] == "Phoneme"
    assert cfg["GradingSystem"] == "HundredMark"


def test_wav_duration_estimate():
    fake = b"H" * 44 + b"\x00" * (16000 * 2)  # header + 1s of 16k 16-bit mono
    assert abs(az.wav_duration_seconds(fake) - 1.0) < 0.01
