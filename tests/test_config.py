from __future__ import annotations

import pytest
import yaml

from services.config_loader import (
    ConfigError,
    load_app_config,
    load_prompts_config,
    load_survey_config,
)


def test_load_app_config(config_files: dict) -> None:
    config = load_app_config(config_files["app"])
    assert config["title"] == "Test App"


def test_load_app_config_allows_unlimited_turns(tmp_path) -> None:
    path = tmp_path / "app.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "title": "Test App",
                "experiment_open": True,
                "max_turns": 0,
                "randomization_mode": "balanced",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    config = load_app_config(path)
    assert config["max_turns"] == 0


def test_load_prompts_config(config_files: dict) -> None:
    config = load_prompts_config(config_files["prompts"])
    assert len(config["conditions"]) == 3


def test_load_survey_config(config_files: dict) -> None:
    config = load_survey_config(config_files["survey"])
    assert config["sections"][0]["id"] == "s1"


def test_missing_required_field_raises_clear_error(tmp_path) -> None:
    broken_path = tmp_path / "broken.yaml"
    broken_path.write_text(yaml.safe_dump({"experiment_open": True}), encoding="utf-8")
    with pytest.raises(ConfigError, match="Missing required field 'title'"):
        load_app_config(broken_path)
