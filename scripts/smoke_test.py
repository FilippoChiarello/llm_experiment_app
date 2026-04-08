from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.config_loader import load_app_config, load_prompts_config, load_survey_config
from services.db import Database
from services.experiment import ExperimentService
from services.export import export_all_tables
from services.llm import LLMService
from services.settings import get_database_path


def main() -> None:
    database = Database(get_database_path())
    database.init_schema()
    app_config = load_app_config()
    prompts_config = load_prompts_config()
    survey_config = load_survey_config()
    service = ExperimentService(
        database=database,
        app_config=app_config,
        prompts_config=prompts_config,
        survey_config=survey_config,
        llm_service=LLMService("mock"),
    )

    created_codes = database.create_access_codes(3)
    code = created_codes[0]
    print(f"Generated codes: {created_codes}")

    enter_result = service.enter_code(code)
    assert enter_result["ok"], "The code should start a session"
    print(f"Assigned condition: {enter_result['data']['assigned_condition']}")

    consent_result = service.record_consent(code)
    assert consent_result["ok"], "Consent should be recorded before chat"
    print("Consent recorded.")

    message_result = service.submit_user_message(code, "Hello, this is a smoke test message.")
    assert message_result["ok"], "The mock message should be saved"
    print(f"Mock reply: {message_result['assistant_text']}")

    while message_result["data"]["can_chat"]:
        message_result = service.submit_user_message(code, "Additional message to reach the turn limit.")
        assert message_result["ok"], "Each mock turn should succeed"

    survey_snapshot = message_result["data"]["survey_snapshot"]
    answers = {}
    for section in survey_snapshot["sections"]:
        for question in section["questions"]:
            if question["type"] == "likert":
                option = question["options"][-1]
                answers[question["id"]] = {"value": option["value"], "label": option["label"]}
            else:
                answers[question["id"]] = {"value": "Test comment", "label": "Test comment"}
    survey_result = service.submit_survey(code, answers)
    assert survey_result["ok"], "The survey should complete the session"
    print("Survey completed.")

    blocked_result = service.enter_code(code)
    assert not blocked_result["ok"] and blocked_result["reason"] == "completed"
    print("Second access correctly blocked.")

    exported = export_all_tables(database)
    print("Exported CSV files:")
    for table_name, path in exported.items():
        print(f"- {table_name}: {path}")

    print("Smoke test completed with mock LLM.")


if __name__ == "__main__":
    main()
