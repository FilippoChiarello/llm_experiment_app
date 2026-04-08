from __future__ import annotations

import pytest

from services.llm import LLMConfigurationError, LLMService


def test_mock_mode_returns_reply() -> None:
    service = LLMService("mock")
    reply, latency = service.generate_reply(
        condition={"id": "c1", "model": "mock-model", "system_prompt": "Prompt"},
        history=[],
        user_message="hello",
    )
    assert "[MOCK::c1]" in reply
    assert latency >= 0


def test_openai_mode_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    service = LLMService("openai")
    with pytest.raises(LLMConfigurationError):
        service.generate_reply(
            condition={"id": "c1", "model": "gpt-4.1-mini", "system_prompt": "Prompt"},
            history=[],
            user_message="hello",
        )


def test_groq_mode_requires_groq_api_key(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    service = LLMService("openai", "groq")
    with pytest.raises(LLMConfigurationError, match="GROQ_API_KEY"):
        service.generate_reply(
            condition={"id": "c1", "model": "openai/gpt-oss-20b", "system_prompt": "Prompt"},
            history=[],
            user_message="hello",
        )


def test_unsupported_provider_raises_clear_error() -> None:
    service = LLMService("openai", "unknown-provider")
    with pytest.raises(LLMConfigurationError, match="Unsupported provider"):
        service.generate_reply(
            condition={"id": "c1", "model": "model", "system_prompt": "Prompt"},
            history=[],
            user_message="hello",
        )
