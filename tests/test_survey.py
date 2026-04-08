from __future__ import annotations


def test_survey_loading(survey_config) -> None:
    assert survey_config["sections"][0]["questions"][0]["type"] == "likert"


def test_save_survey_and_close_session(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    experiment_service.enter_code(code)
    experiment_service.record_consent(code)
    experiment_service.submit_user_message(code, "Turn 1")
    experiment_service.submit_user_message(code, "Turn 2")
    result = experiment_service.submit_survey(
        code,
        {
            "q1": {"value": "2", "label": "High"},
            "q2": {"value": "Comment", "label": "Comment"},
        },
    )
    assert result["ok"] is True
    code_record = temp_db.get_access_code(code)
    session = temp_db.get_session(code_record["session_id"])
    responses = temp_db.fetch_all("SELECT * FROM survey_responses WHERE session_id = ?", (session["session_id"],))
    assert code_record["status"] == "completed"
    assert session["status"] == "completed"
    assert len(responses) == 2
