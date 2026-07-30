"""Nutq — Azure Pronunciation Assessment client tests (Phase A1).

Tests the pure parser (parse_azure_response) against representative Azure payloads.
No network, no ffmpeg, no key required.
"""
from src import pronunciation_azure as az


def _resp(pron_score, words):
    return {
        "RecognitionStatus": "Success",
        "NBest": [{
            "PronunciationAssessment": {
                "AccuracyScore": pron_score, "FluencyScore": 95.0,
                "CompletenessScore": 100.0, "PronScore": pron_score,
            },
            "Words": words,
        }],
    }


def _word(word, acc, error="None", phonemes=None):
    w = {"Word": word, "PronunciationAssessment": {"AccuracyScore": acc, "ErrorType": error}}
    if phonemes:
        w["Phonemes"] = [
            {"Phoneme": p, "PronunciationAssessment": {"AccuracyScore": a}} for p, a in phonemes
        ]
    return w


def test_good_read_high_score_no_missed():
    data = _resp(94.0, [_word("good", 96.0), _word("job", 92.0)])
    r = az.parse_azure_response(data)
    assert r["score"] == 94.0
    assert r["missed_words"] == []
    assert r["fluency"] == 95.0 and r["completeness"] == 100.0


def test_wrong_word_flagged_with_worst_phoneme():
    data = _resp(61.0, [
        _word("i", 95.0),
        _word("walk", 90.0),
        _word("through", 38.0, error="Mispronunciation",
              phonemes=[("th", 22.0), ("r", 70.0), ("uw", 80.0)]),
    ])
    r = az.parse_azure_response(data)
    assert r["score"] == 61.0
    assert "through" in r["missed_words"]
    assert r["worst_phoneme"] == "th"   # lowest-scoring phoneme in the bad word


def test_low_accuracy_word_flagged_even_without_error_type():
    data = _resp(70.0, [_word("prizes", 45.0, error="None",
                              phonemes=[("p", 80.0), ("r", 30.0)])])
    r = az.parse_azure_response(data)
    assert "prizes" in r["missed_words"]
    assert r["worst_phoneme"] == "r"


def test_omission_flagged_insertion_not_added():
    data = _resp(80.0, [
        _word("please", 20.0, error="Omission"),
        _word("umm", 10.0, error="Insertion"),
    ])
    r = az.parse_azure_response(data)
    assert "please" in r["missed_words"]      # omitted target word → flag
    assert "umm" not in r["missed_words"]     # inserted filler → not a target word


def test_non_success_status_returns_none():
    assert az.parse_azure_response({"RecognitionStatus": "InitialSilenceTimeout", "NBest": []}) is None


def test_empty_nbest_returns_none():
    assert az.parse_azure_response({"RecognitionStatus": "Success", "NBest": []}) is None


def test_garbage_returns_none():
    assert az.parse_azure_response(None) is None
    assert az.parse_azure_response({}) is None


def test_pa_header_is_base64_json_with_reference():
    import base64, json
    h = az._pa_header("Hello world")
    cfg = json.loads(base64.b64decode(h))
    assert cfg["ReferenceText"] == "Hello world"
    assert cfg["Granularity"] == "Phoneme"
    assert cfg["GradingSystem"] == "HundredMark"


def test_wav_duration_estimate():
    # 44-byte header + 16000 samples * 2 bytes = 1 second
    fake = b"H" * 44 + b"\x00" * (16000 * 2)
    assert abs(az.wav_duration_seconds(fake) - 1.0) < 0.01
