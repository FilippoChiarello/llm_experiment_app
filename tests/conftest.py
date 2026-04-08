from __future__ import annotations

from pathlib import Path
import sys

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.db import Database
from services.experiment import ExperimentService
from services.llm import LLMService


@pytest.fixture
def app_config() -> dict:
    return {
        "title": "Test App",
        "experiment_open": True,
        "max_turns": 2,
        "randomization_mode": "balanced",
        "llm_mode": "mock",
        "llm_provider": "openai",
    }


@pytest.fixture
def prompts_config() -> dict:
    return {
        "conditions": [
            {
                "id": "c1",
                "active": True,
                "model": "mock-model-1",
                "temperature": 0.1,
                "system_prompt": "Prompt 1",
            },
            {
                "id": "c2",
                "active": True,
                "model": "mock-model-2",
                "temperature": 0.2,
                "system_prompt": "Prompt 2",
            },
            {
                "id": "c3",
                "active": False,
                "model": "mock-model-3",
                "temperature": 0.3,
                "system_prompt": "Prompt 3",
            },
        ]
    }


@pytest.fixture
def survey_config() -> dict:
    return {
        "sections": [
            {
                "id": "s1",
                "title": "Section 1",
                "questions": [
                    {
                        "id": "q1",
                        "type": "likert",
                        "text": "How clear was it?",
                        "options": [
                            {"value": "1", "label": "Low"},
                            {"value": "2", "label": "High"},
                        ],
                    },
                    {"id": "q2", "type": "open_text", "text": "Comment"},
                ],
            }
        ]
    }


@pytest.fixture
def temp_db(tmp_path: Path) -> Database:
    database = Database(tmp_path / "test.db")
    database.init_schema()
    return database


@pytest.fixture
def experiment_service(
    temp_db: Database,
    app_config: dict,
    prompts_config: dict,
    survey_config: dict,
) -> ExperimentService:
    return ExperimentService(
        database=temp_db,
        app_config=app_config,
        prompts_config=prompts_config,
        survey_config=survey_config,
        llm_service=LLMService("mock"),
    )


@pytest.fixture
def config_files(tmp_path: Path, app_config: dict, prompts_config: dict, survey_config: dict) -> dict:
    app_path = tmp_path / "app.yaml"
    prompts_path = tmp_path / "prompts.yaml"
    survey_path = tmp_path / "survey.yaml"
    app_path.write_text(yaml.safe_dump(app_config, sort_keys=False), encoding="utf-8")
    prompts_path.write_text(yaml.safe_dump(prompts_config, sort_keys=False), encoding="utf-8")
    survey_path.write_text(yaml.safe_dump(survey_config, sort_keys=False), encoding="utf-8")
    return {"app": app_path, "prompts": prompts_path, "survey": survey_path}
