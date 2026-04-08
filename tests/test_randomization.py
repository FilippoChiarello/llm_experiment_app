from __future__ import annotations

from services.randomization import choose_balanced_condition


def test_assigns_only_active_conditions(prompts_config) -> None:
    active = [condition for condition in prompts_config["conditions"] if condition["active"]]
    chosen = choose_balanced_condition(active, {"c1": 1, "c2": 2})
    assert chosen["id"] in {"c1", "c2"}


def test_balanced_distribution(experiment_service, temp_db) -> None:
    codes = temp_db.create_access_codes(8)
    for code in codes:
        result = experiment_service.enter_code(code)
        assert result["ok"]
    counts = temp_db.count_sessions_by_condition()
    assert counts["c1"] == counts["c2"] or abs(counts["c1"] - counts["c2"]) <= 1
    assert "c3" not in counts


def test_missing_active_conditions_returns_clear_error(experiment_service, temp_db) -> None:
    experiment_service.prompts_config["conditions"] = [
        {
            "id": "c1",
            "active": False,
            "model": "mock-model-1",
            "temperature": 0.1,
            "system_prompt": "Prompt 1",
        }
    ]
    code = temp_db.create_access_codes(1)[0]
    result = experiment_service.enter_code(code)
    assert result["ok"] is False
    assert result["reason"] == "config_error"
