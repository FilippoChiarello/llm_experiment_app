from __future__ import annotations


def test_session_creation(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    result = experiment_service.enter_code(code)
    session = temp_db.get_session(result["data"]["session_id"])
    assert session is not None
    assert session["code"] == code


def test_consent_required_before_chat(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    experiment_service.enter_code(code)
    blocked = experiment_service.submit_user_message(code, "First message")
    assert blocked["ok"] is False
    assert blocked["reason"] == "consent_required"


def test_message_saved_and_turn_index_incremented(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    experiment_service.enter_code(code)
    experiment_service.record_consent(code)
    experiment_service.submit_user_message(code, "First message")
    experiment_service.submit_user_message(code, "Second message")
    session_id = temp_db.get_access_code(code)["session_id"]
    messages = temp_db.list_messages(session_id)
    assert len(messages) == 2
    assert messages[0]["turn_index"] == 1
    assert messages[1]["turn_index"] == 2


def test_max_turns_respected(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    experiment_service.enter_code(code)
    experiment_service.record_consent(code)
    experiment_service.submit_user_message(code, "Turn 1")
    final_turn = experiment_service.submit_user_message(code, "Turn 2")
    assert final_turn["ok"] is True
    assert final_turn["data"]["needs_survey"] is True
    blocked = experiment_service.submit_user_message(code, "Turn 3")
    assert blocked["ok"] is False
    assert blocked["reason"] == "survey_required"


def test_unlimited_turns_do_not_force_survey(experiment_service, temp_db) -> None:
    experiment_service.app_config["max_turns"] = 0
    code = temp_db.create_access_codes(1)[0]
    started = experiment_service.enter_code(code)
    experiment_service.record_consent(code)
    for index in range(5):
        result = experiment_service.submit_user_message(code, f"Turn {index}")
        assert result["ok"] is True
        assert result["data"]["needs_survey"] is False
    assert started["data"]["session_id"] == temp_db.get_access_code(code)["session_id"]
