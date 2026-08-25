"""Phase 8 (8d) — exam-based CEFR certificate.

Passing a level exit exam yields a "demonstrated proficiency at CEFR Level X"
certificate (the stronger credential); with no passed exam it falls back to the
completion certificate. Truth-in-labelling: never "CEFR-certified".
"""
from src import database


def _seed_passed_exam(discord_id, level, part_b_score, attempt_id):
    conn = database._connect()
    conn.execute(
        "INSERT INTO advancement_exams "
        "(discord_id, level, attempt_num, attempt_id, part_a_score, part_b_score, "
        " overall_score, passed) VALUES (?,?,?,?,?,?,?,1)",
        (discord_id, level, 1, attempt_id, 80, part_b_score, 85))
    conn.commit()
    conn.close()


def test_highest_passed_exit_exam_picks_top_level():
    database.register_member("c1", "Cert Student")
    _seed_passed_exam("c1", "A1", 70, 9001)
    _seed_passed_exam("c1", "A2", 88, 9002)
    top = database.highest_passed_exit_exam("c1")
    assert top["level"] == "A2" and top["part_b_score"] == 88


def test_exam_based_certificate_wording_and_eligibility():
    database.register_member("c2", "Amina")
    database.set_level("c2", "A2")                 # promoted after passing A1
    _seed_passed_exam("c2", "A1", 92, 9003)        # ≥90 → distinction
    data = database.itqan_certificate_data("c2", "A2")
    assert data["basis"] == "exam"
    assert data["eligible"] is True
    assert data["level"] == "A1"                   # certified at the level they passed
    assert data["distinction"] is True
    assert "demonstrated proficiency at CEFR Level A1" in data["statement_en"]
    assert "CEFR" in data["statement_ar"]
    assert "certified" not in data["statement_en"].lower()  # never "CEFR-certified"
    assert data["can_do"] and data["can_do"][0]["code"].startswith("A1.")
    assert data["cefr_aligned"] is True


def test_no_distinction_when_part_b_below_90():
    database.register_member("c3", "Sami")
    _seed_passed_exam("c3", "A1", 74, 9004)
    data = database.itqan_certificate_data("c3", "A1")
    assert data["basis"] == "exam" and data["distinction"] is False


def test_falls_back_to_mastery_basis_without_a_passed_exam():
    database.register_member("c4", "No Exam")
    database.set_level("c4", "A1")
    data = database.itqan_certificate_data("c4", "A1")
    assert data["basis"] == "mastery"
    assert "completed CEFR Level A1" in data["statement_en"]
    # not eligible until all weeks mastered (fresh student)
    assert data["eligible"] is False
