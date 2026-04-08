from __future__ import annotations

from typing import Any, Dict, List


DEFAULT_MODEL_CATALOG: Dict[str, List[Dict[str, Any]]] = {
    "openai": [
        {
            "id": "gpt-5.4",
            "label": "GPT-5.4",
            "family": "reasoning",
            "recommended": True,
            "supports_reasoning_effort": True,
            "supports_sampling": False,
            "supports_verbosity": False,
        },
        {
            "id": "gpt-5.4-mini",
            "label": "GPT-5.4 mini",
            "family": "reasoning",
            "recommended": True,
            "supports_reasoning_effort": True,
            "supports_sampling": False,
            "supports_verbosity": False,
        },
        {
            "id": "gpt-5.4-nano",
            "label": "GPT-5.4 nano",
            "family": "reasoning",
            "recommended": True,
            "supports_reasoning_effort": True,
            "supports_sampling": False,
            "supports_verbosity": False,
        },
        {
            "id": "gpt-4.1",
            "label": "GPT-4.1",
            "family": "general",
            "recommended": True,
            "supports_reasoning_effort": False,
            "supports_sampling": False,
            "supports_verbosity": False,
        },
        {
            "id": "gpt-4.1-mini",
            "label": "GPT-4.1 mini",
            "family": "general",
            "recommended": True,
            "supports_reasoning_effort": False,
            "supports_sampling": False,
            "supports_verbosity": False,
        },
        {
            "id": "gpt-4.1-nano",
            "label": "GPT-4.1 nano",
            "family": "general",
            "recommended": True,
            "supports_reasoning_effort": False,
            "supports_sampling": False,
            "supports_verbosity": False,
        },
    ],
    "groq": [
        {
            "id": "openai/gpt-oss-20b",
            "label": "gpt-oss-20b via Groq",
            "family": "open_weight",
            "supports_reasoning_effort": False,
            "supports_sampling": True,
        }
    ],
    "openrouter": [
        {
            "id": "openrouter/free",
            "label": "OpenRouter free router",
            "family": "router",
            "supports_reasoning_effort": False,
            "supports_sampling": True,
        },
        {
            "id": "openai/gpt-oss-20b:free",
            "label": "gpt-oss-20b free",
            "family": "open_weight",
            "supports_reasoning_effort": False,
            "supports_sampling": True,
        },
    ],
    "huggingface": [
        {
            "id": "openai/gpt-oss-20b",
            "label": "gpt-oss-20b via Hugging Face router",
            "family": "open_weight",
            "supports_reasoning_effort": False,
            "supports_sampling": True,
        }
    ],
}


def get_model_catalog(app_config: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    configured_catalog = app_config.get("llm_model_catalog")
    if isinstance(configured_catalog, dict):
        return configured_catalog
    return DEFAULT_MODEL_CATALOG


def get_provider_model_options(provider: str, app_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    catalog = get_model_catalog(app_config)
    return list(catalog.get(provider, []))


def get_model_metadata(provider: str, model_id: str, app_config: Dict[str, Any]) -> Dict[str, Any]:
    options = get_provider_model_options(provider, app_config)
    for option in options:
        if option.get("id") == model_id:
            return option
    return {}
