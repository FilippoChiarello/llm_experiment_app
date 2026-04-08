from __future__ import annotations

import time
from typing import Any, Dict, List, Tuple

from openai import OpenAI

from services.model_catalog import get_model_metadata
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
            provider = str(condition.get("provider", self.provider)).lower()
            if provider == "openai":
                return self._generate_openai_responses_reply(condition, history, user_message)
            return self._generate_compatible_chat_reply(condition, history, user_message)
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

    def _get_provider_client(self, provider: str) -> tuple[OpenAI, Dict[str, Any]]:
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
        provider_config = provider_settings.get(provider)
        if not provider_config:
            raise LLMConfigurationError(f"Unsupported provider: {provider}")

        api_key = get_provider_api_key(provider)
        if not api_key:
            raise LLMConfigurationError(
                f"{provider_config['api_key_env']} is missing. Use mock mode or configure a local secret."
            )
        client_kwargs: Dict[str, Any] = {"api_key": api_key}
        if provider_config["base_url"]:
            client_kwargs["base_url"] = provider_config["base_url"]
        return OpenAI(**client_kwargs), provider_config

    def _generate_openai_responses_reply(
        self,
        condition: Dict[str, Any],
        history: List[Dict[str, str]],
        user_message: str,
    ) -> Tuple[str, float]:
        client, _provider_config = self._get_provider_client("openai")
        conversation_input: List[Dict[str, str]] = list(history)
        conversation_input.append({"role": "user", "content": user_message})
        request_kwargs: Dict[str, Any] = {
            "model": condition["model"],
            "instructions": condition["system_prompt"],
            "input": conversation_input,
        }
        max_output_tokens = condition.get("max_output_tokens")
        if max_output_tokens is not None:
            request_kwargs["max_output_tokens"] = int(max_output_tokens)
        reasoning_effort = str(condition.get("reasoning_effort", "none")).strip().lower()
        if reasoning_effort and reasoning_effort != "none":
            request_kwargs["reasoning"] = {"effort": reasoning_effort}
        started = time.perf_counter()
        response = client.responses.create(**request_kwargs)
        latency_ms = (time.perf_counter() - started) * 1000
        reply = getattr(response, "output_text", "") or self._extract_output_text(response)
        return reply, latency_ms

    def _generate_compatible_chat_reply(
        self,
        condition: Dict[str, Any],
        history: List[Dict[str, str]],
        user_message: str,
    ) -> Tuple[str, float]:
        provider = str(condition.get("provider", self.provider)).lower()
        client, _provider_config = self._get_provider_client(provider)
        messages = [{"role": "system", "content": condition["system_prompt"]}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        extra_headers: Dict[str, str] = {}
        if provider == "openrouter":
            extra_headers["HTTP-Referer"] = "http://localhost:8501"
            extra_headers["X-Title"] = "LLM Experiment App"
        request_kwargs: Dict[str, Any] = {
            "model": condition["model"],
            "messages": messages,
        }
        max_output_tokens = condition.get("max_output_tokens")
        if max_output_tokens is not None:
            request_kwargs["max_tokens"] = int(max_output_tokens)
        temperature = condition.get("temperature")
        top_p = condition.get("top_p")
        if temperature is not None:
            request_kwargs["temperature"] = float(temperature)
        if top_p is not None:
            request_kwargs["top_p"] = float(top_p)
        started = time.perf_counter()
        response = client.chat.completions.create(
            **request_kwargs,
            extra_headers=extra_headers or None,
        )
        latency_ms = (time.perf_counter() - started) * 1000
        reply = response.choices[0].message.content or ""
        return reply, latency_ms

    def _extract_output_text(self, response: Any) -> str:
        output_items = getattr(response, "output", None) or []
        extracted_parts: List[str] = []
        for item in output_items:
            if getattr(item, "type", "") != "message":
                continue
            for content_item in getattr(item, "content", []) or []:
                text = getattr(content_item, "text", None)
                if text:
                    extracted_parts.append(text)
        return "\n".join(extracted_parts).strip()
