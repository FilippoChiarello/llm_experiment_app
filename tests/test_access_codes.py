from __future__ import annotations


def test_generate_unique_codes(temp_db) -> None:
    created = temp_db.create_access_codes(20)
    assert len(created) == len(set(created))


def test_validate_existing_code(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    result = experiment_service.enter_code(code)
    assert result["ok"] is True
    assert result["data"]["code"] == code


def test_block_completed_code(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    temp_db.update_access_code(code, status="completed")
    result = experiment_service.enter_code(code)
    assert result["ok"] is False
    assert result["reason"] == "completed"


def test_resume_in_progress_code(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    started = experiment_service.enter_code(code)
    resumed = experiment_service.enter_code(code)
    assert started["ok"] and resumed["ok"]
    assert started["data"]["session_id"] == resumed["data"]["session_id"]


def test_closed_experiment_blocks_new_code(experiment_service, temp_db) -> None:
    code = temp_db.create_access_codes(1)[0]
    experiment_service.app_config["experiment_open"] = False
    result = experiment_service.enter_code(code)
    assert result["ok"] is False
    assert result["reason"] == "closed"
