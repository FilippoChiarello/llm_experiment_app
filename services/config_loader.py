from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml

from services.settings import CONFIG_DIR


class ConfigError(ValueError):
    """Raised when a config file is invalid."""


APP_CONFIG_PATH = CONFIG_DIR / "app.yaml"
PROMPTS_CONFIG_PATH = CONFIG_DIR / "prompts.yaml"
SURVEY_CONFIG_PATH = CONFIG_DIR / "survey.yaml"


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Config file must contain a YAML object: {path}")
    return data


def _write_yaml(path: Path, data: Dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)


def _require_fields(data: Dict[str, Any], required: List[str], file_label: str) -> None:
    for field_name in required:
        if field_name not in data:
            raise ConfigError(f"Missing required field '{field_name}' in {file_label}")


def load_app_config(path: Path = APP_CONFIG_PATH) -> Dict[str, Any]:
    data = _read_yaml(path)
    _require_fields(
        data,
        ["title", "experiment_open", "max_turns", "randomization_mode"],
        path.name,
    )
    if not isinstance(data["title"], str) or not data["title"].strip():
        raise ConfigError("app.yaml: 'title' must be a non-empty string")
    if not isinstance(data["experiment_open"], bool):
        raise ConfigError("app.yaml: 'experiment_open' must be true or false")
    if not isinstance(data["max_turns"], int) or data["max_turns"] < 0:
        raise ConfigError("app.yaml: 'max_turns' must be a non-negative integer")
    if data["randomization_mode"] != "balanced":
        raise ConfigError("app.yaml: only 'balanced' randomization_mode is supported")
    data.setdefault("llm_mode", "mock")
    data.setdefault("llm_provider", "openai")
    data.setdefault("allow_resume", True)
    data.setdefault("demo_access_codes", [])
    data.setdefault("privacy_version", "v1")
    data.setdefault(
        "privacy_notice_text",
        "By continuing, you confirm that you are participating voluntarily, that your messages and survey responses "
        "will be stored for research purposes, and that you understand you should not share unnecessary personal or "
        "sensitive information in the chat.",
    )
    return data


def save_app_config(data: Dict[str, Any], path: Path = APP_CONFIG_PATH) -> None:
    validated = dict(data)
    load_app_config_from_data(validated)
    _write_yaml(path, validated)


def load_app_config_from_data(data: Dict[str, Any]) -> Dict[str, Any]:
    _require_fields(data, ["title", "experiment_open", "max_turns", "randomization_mode"], "app data")
    return load_app_config_dict(data)


def load_app_config_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data["title"], str) or not data["title"].strip():
        raise ConfigError("app config: 'title' must be a non-empty string")
    if not isinstance(data["experiment_open"], bool):
        raise ConfigError("app config: 'experiment_open' must be true or false")
    if not isinstance(data["max_turns"], int) or data["max_turns"] < 0:
        raise ConfigError("app config: 'max_turns' must be a non-negative integer")
    if data["randomization_mode"] != "balanced":
        raise ConfigError("app config: only 'balanced' randomization_mode is supported")
    data.setdefault("llm_mode", "mock")
    data.setdefault("llm_provider", "openai")
    data.setdefault("allow_resume", True)
    data.setdefault("demo_access_codes", [])
    data.setdefault("privacy_version", "v1")
    data.setdefault(
        "privacy_notice_text",
        "By continuing, you confirm that you are participating voluntarily, that your messages and survey responses "
        "will be stored for research purposes, and that you understand you should not share unnecessary personal or "
        "sensitive information in the chat.",
    )
    return data


def load_prompts_config(path: Path = PROMPTS_CONFIG_PATH) -> Dict[str, Any]:
    data = _read_yaml(path)
    validate_prompts_config(data, path.name)
    return data


def validate_prompts_config(data: Dict[str, Any], file_label: str = "prompts.yaml") -> None:
    _require_fields(data, ["conditions"], file_label)
    conditions = data["conditions"]
    if not isinstance(conditions, list) or not conditions:
        raise ConfigError(f"{file_label}: 'conditions' must be a non-empty list")
    for index, condition in enumerate(conditions):
        if not isinstance(condition, dict):
            raise ConfigError(f"{file_label}: condition #{index + 1} must be an object")
        for field_name in ["id", "active", "model", "system_prompt"]:
            if field_name not in condition:
                raise ConfigError(
                    f"{file_label}: missing required field '{field_name}' in condition #{index + 1}"
                )
        if not isinstance(condition["id"], str) or not condition["id"].strip():
            raise ConfigError(f"{file_label}: condition #{index + 1} id must be a non-empty string")
        if not isinstance(condition["active"], bool):
            raise ConfigError(f"{file_label}: condition '{condition['id']}' active must be true or false")
        if not isinstance(condition["model"], str) or not condition["model"].strip():
            raise ConfigError(f"{file_label}: condition '{condition['id']}' model must be a non-empty string")
        if condition.get("temperature") is not None and not isinstance(condition["temperature"], (int, float)):
            raise ConfigError(f"{file_label}: condition '{condition['id']}' temperature must be numeric")
        if condition.get("max_output_tokens") is not None and (
            not isinstance(condition["max_output_tokens"], int) or condition["max_output_tokens"] <= 0
        ):
            raise ConfigError(
                f"{file_label}: condition '{condition['id']}' max_output_tokens must be a positive integer or null"
            )
        if not isinstance(condition["system_prompt"], str) or not condition["system_prompt"].strip():
            raise ConfigError(
                f"{file_label}: condition '{condition['id']}' system_prompt must be a non-empty string"
            )
        condition.setdefault("provider", "openai")
        condition.setdefault("temperature", 0.7)
        condition.setdefault("max_output_tokens", 400)
        condition.setdefault("top_p", 1.0)
        condition.setdefault("reasoning_effort", "none")


def save_prompts_config(data: Dict[str, Any], path: Path = PROMPTS_CONFIG_PATH) -> None:
    validate_prompts_config(data)
    _write_yaml(path, data)


def get_active_conditions(prompts_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    active = [condition for condition in prompts_config["conditions"] if condition.get("active")]
    if not active:
        raise ConfigError("At least one active condition is required")
    return active


def load_survey_config(path: Path = SURVEY_CONFIG_PATH) -> Dict[str, Any]:
    data = _read_yaml(path)
    validate_survey_config(data, path.name)
    return data


def validate_survey_config(data: Dict[str, Any], file_label: str = "survey.yaml") -> None:
    _require_fields(data, ["sections"], file_label)
    sections = data["sections"]
    if not isinstance(sections, list) or not sections:
        raise ConfigError(f"{file_label}: 'sections' must be a non-empty list")
    for section_index, section in enumerate(sections):
        if not isinstance(section, dict):
            raise ConfigError(f"{file_label}: section #{section_index + 1} must be an object")
        for field_name in ["id", "title", "questions"]:
            if field_name not in section:
                raise ConfigError(
                    f"{file_label}: missing required field '{field_name}' in section #{section_index + 1}"
                )
        questions = section["questions"]
        if not isinstance(questions, list) or not questions:
            raise ConfigError(f"{file_label}: section '{section['id']}' must contain questions")
        for question_index, question in enumerate(questions):
            if not isinstance(question, dict):
                raise ConfigError(
                    f"{file_label}: question #{question_index + 1} in section '{section['id']}' must be an object"
                )
            for field_name in ["id", "type", "text"]:
                if field_name not in question:
                    raise ConfigError(
                        f"{file_label}: missing required field '{field_name}' in question #{question_index + 1}"
                    )
            question_type = question["type"]
            if question_type not in {"likert", "open_text"}:
                raise ConfigError(
                    f"{file_label}: question '{question['id']}' type must be 'likert' or 'open_text'"
                )
            if question_type == "likert" and not isinstance(question.get("options"), list):
                raise ConfigError(
                    f"{file_label}: likert question '{question['id']}' must contain an 'options' list"
                )


def save_survey_config(data: Dict[str, Any], path: Path = SURVEY_CONFIG_PATH) -> None:
    validate_survey_config(data)
    _write_yaml(path, data)
