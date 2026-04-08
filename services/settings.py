from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
EXPORTS_DIR = PROJECT_ROOT / "exports"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env", override=False)


def _get_secret_value(name: str, default: str = "") -> str:
    env_value = os.getenv(name)
    if env_value is not None and env_value != "":
        return env_value
    try:
        secret_value = st.secrets.get(name, default)
    except Exception:
        secret_value = default
    if secret_value is None:
        return default
    return str(secret_value).strip()


def project_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)


def get_database_path() -> Path:
    raw_path = _get_secret_value("EXPERIMENT_DB_PATH", "data/experiment.db")
    db_path = Path(raw_path)
    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / raw_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path


def get_admin_password() -> str:
    return _get_secret_value("ADMIN_PASSWORD", "")


def get_llm_mode() -> str:
    return _get_secret_value("LLM_MODE", "mock").lower() or "mock"


def get_openai_api_key() -> str:
    return _get_secret_value("OPENAI_API_KEY", "")


def get_llm_provider() -> str:
    return _get_secret_value("LLM_PROVIDER", "openai").lower() or "openai"


def get_provider_api_key(provider: str) -> str:
    provider_map = {
        "openai": "OPENAI_API_KEY",
        "groq": "GROQ_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "huggingface": "HF_TOKEN",
    }
    env_name = provider_map.get(provider.lower())
    if not env_name:
        return ""
    return _get_secret_value(env_name, "")
