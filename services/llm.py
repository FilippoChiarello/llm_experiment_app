from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from openai import OpenAI

from services.settings import get_llm_mode, get_llm_provider, get_provider_api_key


class LLMConfigurationError(RuntimeError):
    """Raised when live mode is requested without a valid config."""


class LLMService:
    def __init__(self, mode: str | None = None, provider: str | None = None):
        self.mode = (mode or get_llm_mode()).lower()
        self.provider = (provider or get_llm_provider()).lower()

    def generate_reply(
        self,
        condition: Dict[str, Any],
        history: List[Dict[str, str]],
        user_message: str,
    ) -> Tuple[str, float]:
        if self.mode == "mock":
            return self._generate_mock_reply(condition, history, user_message)
        if self.mode == "openai":
            return self._generate_openai_reply(condition, history, user_message)
        raise LLMConfigurationError(f"Unsupported LLM mode: {self.mode}")

    def _generate_mock_reply(
        self,
        condition: Dict[str, Any],
        history: List[Dict[str, str]],
        user_message: str,
    ) -> Tuple[str, float]:
        started = time.perf_counter()
        turn_number = len([item for item in history if item["role"] == "user"]) + 1
        reply = (
            f"[MOCK::{condition['id']}] Turn {turn_number}. "
            f"You wrote: '{user_message}'. "
            f"This simulated reply uses the configured prompt for condition "
            f"'{condition['id']}' without making any external call."
        )
        latency_ms = (time.perf_counter() - started) * 1000
        return reply, latency_ms

    def _generate_openai_reply(
        self,
        condition: Dict[str, Any],
        history: List[Dict[str, str]],
        user_message: str,
    ) -> Tuple[str, float]:
        provider_settings = {
            "openai": {
                "base_url": None,
                "api_key_env": "OPENAI_API_KEY",
            },
            "groq": {
                "base_url": "https://api.groq.com/openai/v1",
                "api_key_env": "GROQ_API_KEY",
            },
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
            },
            "huggingface": {
                "base_url": "https://router.huggingface.co/v1",
                "api_key_env": "HF_TOKEN",
            },
        }
        provider_config = provider_settings.get(self.provider)
        if not provider_config:
            raise LLMConfigurationError(f"Unsupported provider: {self.provider}")

        api_key = get_provider_api_key(self.provider)
        if not api_key:
            raise LLMConfigurationError(
                f"{provider_config['api_key_env']} is missing. Use mock mode or configure a local secret."
            )
        client_kwargs: Dict[str, Any] = {"api_key": api_key}
        if provider_config["base_url"]:
            client_kwargs["base_url"] = provider_config["base_url"]
        client = OpenAI(**client_kwargs)
        messages = [{"role": "system", "content": condition["system_prompt"]}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        extra_headers: Dict[str, str] = {}
        if self.provider == "openrouter":
            extra_headers["HTTP-Referer"] = "http://localhost:8501"
            extra_headers["X-Title"] = "LLM Experiment App"
        started = time.perf_counter()
        response = client.chat.completions.create(
            model=condition["model"],
            temperature=condition.get("temperature", 0.7),
            top_p=condition.get("top_p", 1.0),
            messages=messages,
            max_tokens=condition.get("max_output_tokens", 400),
            extra_headers=extra_headers or None,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        reply = response.choices[0].message.content or ""
        return reply, latency_ms
