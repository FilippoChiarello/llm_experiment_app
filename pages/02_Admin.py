from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import altair as alt
import pandas as pd
import streamlit as st
import yaml

from services.config_loader import (
    APP_CONFIG_PATH,
    PROMPTS_CONFIG_PATH,
    SURVEY_CONFIG_PATH,
    ConfigError,
    load_app_config,
    load_prompts_config,
    load_survey_config,
    save_app_config,
    save_prompts_config,
    save_survey_config,
)
from services.db import Database
from services.export import create_publication_export, export_all_tables
from services.model_catalog import get_provider_model_options
from services.settings import EXPORTS_DIR, get_admin_password, get_database_path, get_provider_api_key


def get_database() -> Database:
    database = Database(get_database_path())
    database.init_schema()
    app_config = load_app_config()
    for code in app_config.get("demo_access_codes", []):
        if isinstance(code, str) and code.strip():
            database.ensure_access_code(code.strip().upper())
    return database


def apply_admin_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(208, 232, 255, 0.8), transparent 22%),
                radial-gradient(circle at top right, rgba(255, 232, 202, 0.75), transparent 24%),
                linear-gradient(180deg, #f8fbfd 0%, #eef4f8 100%);
        }
        .admin-hero {
            padding: 1.6rem 1.8rem;
            border-radius: 28px;
            background: rgba(255,255,255,0.88);
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.07);
            margin-bottom: 1rem;
        }
        .admin-kicker {
            display: inline-block;
            padding: 0.35rem 0.72rem;
            border-radius: 999px;
            background: #edf4fb;
            color: #2c526f;
            font-size: 0.85rem;
            margin-bottom: 0.8rem;
        }
        .analytics-card {
            padding: 1rem 1.1rem;
            border-radius: 22px;
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.05);
        }
        .workflow-card {
            padding: 1rem 1.1rem;
            border-radius: 22px;
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.05);
            margin-bottom: 1rem;
        }
        .pill-row {
            margin-bottom: 0.9rem;
        }
        .status-pill {
            display: inline-block;
            padding: 0.4rem 0.75rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.84);
            border: 1px solid rgba(15, 23, 42, 0.08);
            color: #405162;
            font-size: 0.9rem;
            margin: 0 0.45rem 0.45rem 0;
        }
        .admin-soft-note {
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            color: #506171;
            margin-top: 0.8rem;
        }
        div[data-testid="stTabs"] button[role="tab"] {
            border-radius: 16px;
            border: 1px solid rgba(15, 23, 42, 0.08);
            background: rgba(255,255,255,0.78);
            padding: 0.7rem 1rem;
            min-height: 56px;
        }
        div[data-testid="stTabs"] button[aria-selected="true"] {
            background: linear-gradient(135deg, #e6f3ff, #fff2e6);
            border-color: #cfe0ef;
            box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stTabs"] button[role="tab"] p {
            font-size: 0.96rem;
            font-weight: 600;
        }
        div[data-testid="stTabs"] [data-baseweb="tab-border"] {
            display: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login() -> None:
    configured_password = get_admin_password()
    st.subheader("Admin Sign In")
    st.write("Use the admin password to open the study control area for setup, participant management, analytics, and exports.")
    if not configured_password:
        st.warning(
            "Admin password not configured. First create a local `.env` file with `ADMIN_PASSWORD=...`."
        )
        st.stop()
    with st.container(border=True):
        st.caption("Only researchers or study operators should use this page.")
        with st.form("admin_login"):
            password = st.text_input("Admin password", type="password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)
    if submitted:
        if password == configured_password:
            st.session_state["admin_authenticated"] = True
            st.success("Admin login successful.")
            st.rerun()
        st.error("Incorrect password.")


def _load_configs() -> tuple[dict, dict, dict]:
    return load_app_config(), load_prompts_config(), load_survey_config()


def _summarize_conditions(conditions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": condition["id"],
            "active": condition["active"],
            "provider": condition.get("provider", "openai"),
            "model": condition["model"],
            "temperature": condition["temperature"],
            "top_p": condition.get("top_p", 1.0),
            "max_output_tokens": condition.get("max_output_tokens", 400),
            "reasoning_effort": condition.get("reasoning_effort", "none"),
        }
        for condition in conditions
    ]


def _parse_likert_options(raw_text: str) -> List[Dict[str, str]]:
    options = []
    for line in raw_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if "|" in cleaned:
            label, value = cleaned.split("|", 1)
            options.append({"label": label.strip(), "value": value.strip()})
        else:
            options.append({"label": cleaned, "value": cleaned})
    return options


def _format_likert_options(question: Dict[str, Any]) -> str:
    return "\n".join(f"{option['label']}|{option['value']}" for option in question.get("options", []))


def get_operations_context(database: Database) -> Dict[str, Any]:
    stats = database.count_access_codes_by_status()
    metrics = database.get_session_metrics()
    return {
        "new_codes": int(stats["new"]),
        "in_progress_codes": int(stats["in_progress"]),
        "completed_codes": int(stats["completed"]),
        "disabled_codes": int(stats["disabled"]),
        "total_sessions": int(metrics["total_sessions"]),
        "completed_sessions": int(metrics["completed_sessions"]),
        "study_live": int(stats["in_progress"]) > 0,
    }


def render_operations_banner(database: Database) -> None:
    app_config = load_app_config()
    context = get_operations_context(database)
    provider = app_config.get("llm_provider", "openai")
    llm_mode = app_config.get("llm_mode", "mock")
    provider_key_present = bool(get_provider_api_key(provider)) if llm_mode == "openai" else False

    if llm_mode == "mock":
        st.info("Mock mode is active. Participants will receive simulated responses, which is useful for testing and rehearsal.")
    else:
        if provider_key_present:
            st.success(f"Live mode is active with provider `{provider}`. The required API secret is available on the server.")
        else:
            st.error(
                f"Live mode is selected with provider `{provider}`, but the server secret for that provider is missing. Participant chats may fail until the secret is configured."
            )

    if app_config["experiment_open"] and not context["study_live"] and context["new_codes"] == 0:
        st.warning("The experiment is open, but there are no unused participant codes ready to distribute.")
    if context["study_live"]:
        st.warning(
            f"There are currently {context['in_progress_codes']} in-progress participant session(s). Be careful with study settings changes while data collection is underway."
        )


def render_app_settings(database: Database) -> None:
    app_config = load_app_config()
    operations = get_operations_context(database)
    st.markdown("### General Settings")
    st.write("Start here when you want to change the overall study behavior, provider defaults, or the participant consent text.")
    with st.form("app_settings_form"):
        title = st.text_input("App title", value=app_config["title"])
        experiment_open = st.checkbox("Experiment open to new participants", value=app_config["experiment_open"])
        unlimited_turns = st.checkbox("Unlimited participant turns", value=app_config["max_turns"] == 0)
        max_turns = st.number_input(
            "Maximum chat turns",
            min_value=1,
            value=max(1, int(app_config["max_turns"] or 1)),
            disabled=unlimited_turns,
            help="Ignored when unlimited turns is enabled.",
        )
        llm_mode = st.selectbox(
            "LLM mode",
            options=["mock", "openai"],
            index=["mock", "openai"].index(app_config.get("llm_mode", "mock")),
        )
        llm_provider = st.selectbox(
            "Live provider",
            options=["openai", "groq", "openrouter", "huggingface"],
            index=["openai", "groq", "openrouter", "huggingface"].index(
                app_config.get("llm_provider", "openai")
            ),
            help="Used only when LLM mode is set to openai.",
        )
        privacy_version = st.text_input("Privacy notice version", value=app_config.get("privacy_version", "v1"))
        privacy_notice_text = st.text_area(
            "Privacy / consent text",
            value=app_config.get("privacy_notice_text", ""),
            height=180,
        )
        risky_change_requested = any(
            [
                title != app_config["title"],
                experiment_open != app_config["experiment_open"],
                (0 if unlimited_turns else int(max_turns)) != int(app_config["max_turns"]),
                llm_mode != app_config.get("llm_mode", "mock"),
                llm_provider != app_config.get("llm_provider", "openai"),
                privacy_version.strip() != app_config.get("privacy_version", "v1"),
                privacy_notice_text.strip() != app_config.get("privacy_notice_text", ""),
            ]
        )
        confirm_risky_change = st.checkbox(
            "I understand that these changes affect new participants and can change study operations.",
            value=False,
            disabled=not (operations["study_live"] and risky_change_requested),
            help="Required only when there are active in-progress participants and you are changing study-level settings.",
        )
        submitted = st.form_submit_button("Save settings")
    if submitted:
        if operations["study_live"] and risky_change_requested and not confirm_risky_change:
            st.error("Active participant sessions are in progress. Please confirm that you want to change study-level settings during live data collection.")
            return
        updated = dict(app_config)
        updated["title"] = title
        updated["experiment_open"] = experiment_open
        updated["max_turns"] = 0 if unlimited_turns else int(max_turns)
        updated["llm_mode"] = llm_mode
        updated["llm_provider"] = llm_provider
        updated["privacy_version"] = privacy_version.strip()
        updated["privacy_notice_text"] = privacy_notice_text.strip()
        save_app_config(updated)
        st.success("app.yaml updated.")
        st.rerun()
    st.markdown(
        '<div class="admin-soft-note">Recommended workflow: keep the experiment closed while you edit settings, then open it only when participant codes are ready to distribute.</div>',
        unsafe_allow_html=True,
    )
    if operations["study_live"]:
        st.warning("Live participants are currently in progress. If possible, wait until active sessions finish before changing global study settings.")


def render_conditions_manager(database: Database) -> None:
    app_config = load_app_config()
    prompts_config = load_prompts_config()
    operations = get_operations_context(database)
    conditions = prompts_config["conditions"]
    st.markdown("### Experimental Conditions")
    st.write("Manage the experimental arms here without changing application code.")
    active_count = len([condition for condition in conditions if condition["active"]])
    provider_count = len({condition.get("provider", "openai") for condition in conditions})
    summary_col1, summary_col2, summary_col3 = st.columns(3)
    summary_col1.metric("Total conditions", len(conditions))
    summary_col2.metric("Active conditions", active_count)
    summary_col3.metric("Providers in use", provider_count)
    with st.expander("View condition summary", expanded=False):
        st.dataframe(_summarize_conditions(conditions), use_container_width=True, hide_index=True)

    selected_condition_id = st.selectbox(
        "Choose a condition to edit",
        options=[condition["id"] for condition in conditions],
        key="condition_select",
    )
    selected_condition = next(condition for condition in conditions if condition["id"] == selected_condition_id)
    current_provider = selected_condition.get("provider", app_config.get("llm_provider", "openai"))
    provider_options = list(app_config.get("llm_model_catalog", {}).keys()) or ["openai", "groq", "openrouter", "huggingface"]
    provider_index = provider_options.index(current_provider) if current_provider in provider_options else 0
    current_model_options = get_provider_model_options(current_provider, app_config)
    current_model_ids = [item["id"] for item in current_model_options]
    current_model_is_custom = selected_condition["model"] not in current_model_ids
    current_model_selector = selected_condition["model"] if not current_model_is_custom else "__custom__"
    with st.form("edit_condition_form"):
        condition_id = st.text_input("Condition ID", value=selected_condition["id"])
        active = st.checkbox("Condition active", value=selected_condition["active"])
        provider = st.selectbox("Provider", options=provider_options, index=provider_index)
        provider_model_options = get_provider_model_options(provider, app_config)
        provider_model_ids = [item["id"] for item in provider_model_options]
        model_selector_options = provider_model_ids + ["__custom__"]
        model_selector_labels = {
            item["id"]: f"{item['label']} ({item['id']})"
            for item in provider_model_options
        }
        model_selector_labels["__custom__"] = "Custom model id"
        selected_model_option = st.selectbox(
            "Model catalog",
            options=model_selector_options,
            format_func=lambda value: model_selector_labels.get(value, value),
            index=model_selector_options.index(current_model_selector)
            if current_model_selector in model_selector_options
            else 0,
        )
        model = st.text_input(
            "Model name",
            value=selected_condition["model"],
            disabled=selected_model_option != "__custom__",
        )
        effective_model = model.strip() if selected_model_option == "__custom__" else selected_model_option
        selected_model_metadata = next(
            (item for item in provider_model_options if item["id"] == effective_model),
            {},
        )
        temperature = st.number_input(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=float(selected_condition.get("temperature", 0.7) or 0.7),
            step=0.1,
            disabled=provider == "openai",
            help="Used for OpenAI-compatible chat-completions providers. OpenAI official models use the Responses API path.",
        )
        top_p = st.number_input(
            "Top p",
            min_value=0.0,
            max_value=1.0,
            value=float(selected_condition.get("top_p", 1.0)),
            step=0.05,
            disabled=provider == "openai",
            help="Used for OpenAI-compatible chat-completions providers. OpenAI official models use the Responses API path.",
        )
        use_provider_default_max_output = st.checkbox(
            "Let the model/provider decide max output length",
            value=selected_condition.get("max_output_tokens") is None,
        )
        max_output_tokens = st.number_input(
            "Max output tokens",
            min_value=1,
            value=int(selected_condition.get("max_output_tokens") or 400),
            disabled=use_provider_default_max_output,
            help="When enabled, the request will omit the max output token limit and let the provider use its default behavior.",
        )
        reasoning_effort = st.selectbox(
            "Reasoning effort",
            options=["none", "low", "medium", "high", "xhigh"],
            index=["none", "low", "medium", "high", "xhigh"].index(
                selected_condition.get("reasoning_effort", "none")
            )
            if selected_condition.get("reasoning_effort", "none") in ["none", "low", "medium", "high", "xhigh"]
            else 0,
            disabled=not selected_model_metadata.get("supports_reasoning_effort", False),
            help="Best used with current OpenAI reasoning models such as GPT-5.x variants.",
        )
        system_prompt = st.text_area("System prompt", value=selected_condition["system_prompt"], height=220)
        risky_condition_change = any(
            [
                condition_id.strip() != selected_condition["id"],
                active != selected_condition["active"],
                provider != selected_condition.get("provider", app_config.get("llm_provider", "openai")),
                effective_model != selected_condition["model"],
                float(temperature) != float(selected_condition.get("temperature", 0.7) or 0.7),
                float(top_p) != float(selected_condition.get("top_p", 1.0)),
                (None if use_provider_default_max_output else int(max_output_tokens))
                != selected_condition.get("max_output_tokens"),
                reasoning_effort != selected_condition.get("reasoning_effort", "none"),
                system_prompt != selected_condition["system_prompt"],
            ]
        )
        confirm_condition_change = st.checkbox(
            "I understand that condition changes will affect future participant assignments.",
            value=False,
            disabled=not (operations["study_live"] and risky_condition_change),
            help="Required only when there are active participants and you are changing a condition.",
        )
        submitted = st.form_submit_button("Save condition")
    if submitted:
        if operations["study_live"] and risky_condition_change and not confirm_condition_change:
            st.error("Active participant sessions are in progress. Please confirm the condition change before saving.")
            return
        if condition_id != selected_condition["id"] and any(
            condition["id"] == condition_id for condition in conditions
        ):
            st.error("A condition with this ID already exists.")
            return
        updated_conditions = []
        for condition in conditions:
            if condition["id"] == selected_condition["id"]:
                updated_conditions.append(
                    {
                        "id": condition_id.strip(),
                        "active": active,
                        "provider": provider,
                        "model": effective_model,
                        "temperature": float(temperature),
                        "top_p": float(top_p),
                        "max_output_tokens": None if use_provider_default_max_output else int(max_output_tokens),
                        "reasoning_effort": reasoning_effort,
                        "system_prompt": system_prompt,
                    }
                )
            else:
                updated_conditions.append(condition)
        save_prompts_config({"conditions": updated_conditions})
        st.success("Condition updated.")
        st.rerun()

    col_add, col_remove = st.columns(2)
    with col_add:
        with st.form("add_condition_form"):
            st.markdown("#### Add New Condition")
            new_id = st.text_input("New ID")
            new_active = st.checkbox("Activate immediately", value=True)
            new_provider = st.selectbox("Provider", options=provider_options, key="new_condition_provider")
            new_provider_model_options = get_provider_model_options(new_provider, app_config)
            new_provider_model_ids = [item["id"] for item in new_provider_model_options]
            new_model_selector = st.selectbox(
                "Model catalog",
                options=new_provider_model_ids + ["__custom__"],
                format_func=lambda value: (
                    next((f"{item['label']} ({item['id']})" for item in new_provider_model_options if item["id"] == value), None)
                    or ("Custom model id" if value == "__custom__" else value)
                ),
                key="new_condition_model_selector",
            )
            new_model = st.text_input("Model name", value="gpt-4.1-mini", disabled=new_model_selector != "__custom__")
            new_temperature = st.number_input("New condition temperature", min_value=0.0, max_value=2.0, value=0.7, step=0.1)
            new_top_p = st.number_input("New condition top p", min_value=0.0, max_value=1.0, value=1.0, step=0.05)
            new_use_provider_default_max_output = st.checkbox(
                "Let the model/provider decide max output length",
                value=False,
                key="new_use_provider_default_max_output",
            )
            new_max_tokens = st.number_input(
                "New condition max output tokens",
                min_value=1,
                value=400,
                disabled=new_use_provider_default_max_output,
            )
            new_reasoning_effort = st.selectbox(
                "Reasoning effort",
                options=["none", "low", "medium", "high", "xhigh"],
                index=0,
                key="new_condition_reasoning_effort",
            )
            new_system_prompt = st.text_area("New condition system prompt", height=180)
            confirm_add_condition = st.checkbox(
                "I understand that a new condition changes future random assignment.",
                value=False,
                disabled=not operations["study_live"],
            )
            add_submitted = st.form_submit_button("Add condition")
        if add_submitted:
            if operations["study_live"] and not confirm_add_condition:
                st.error("Active participant sessions are in progress. Please confirm that you want to add a new condition during live data collection.")
                return
            if not new_id.strip():
                st.error("Please enter an ID for the new condition.")
                return
            if any(condition["id"] == new_id.strip() for condition in conditions):
                st.error("This ID already exists.")
                return
            new_effective_model = new_model.strip() if new_model_selector == "__custom__" else new_model_selector
            updated_conditions = conditions + [
                {
                    "id": new_id.strip(),
                    "active": new_active,
                    "provider": new_provider,
                    "model": new_effective_model,
                    "temperature": float(new_temperature),
                    "top_p": float(new_top_p),
                    "max_output_tokens": None if new_use_provider_default_max_output else int(new_max_tokens),
                    "reasoning_effort": new_reasoning_effort,
                    "system_prompt": new_system_prompt,
                }
            ]
            save_prompts_config({"conditions": updated_conditions})
            st.success("New condition added.")
            st.rerun()

    with col_remove:
        st.markdown("#### Remove Condition")
        if len(conditions) == 1:
            st.info("You cannot remove the last available condition.")
        elif st.button("Remove selected condition"):
            if operations["study_live"]:
                st.error("Removing a condition is blocked while participant sessions are in progress. Wait until the live study is clear, then try again.")
                return
            updated_conditions = [condition for condition in conditions if condition["id"] != selected_condition_id]
            save_prompts_config({"conditions": updated_conditions})
            st.success("Condition removed.")
            st.rerun()

    st.markdown(
        '<div class="admin-soft-note">Tip: keep at least two active conditions only if you really need random assignment. For simpler pilots, one active condition is usually easier to manage.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Advanced prompts.yaml editor", expanded=False):
        render_yaml_editor("Advanced prompts.yaml editor", PROMPTS_CONFIG_PATH, save_prompts_config)


def render_survey_manager() -> None:
    survey_config = load_survey_config()
    sections = survey_config["sections"]
    st.markdown("### Survey")
    st.write("Edit the participant survey here. The basic workflow is: choose a section, edit its questions, then add new items only if needed.")
    section_col1, section_col2 = st.columns(2)
    section_col1.metric("Sections", len(sections))
    section_col2.metric("Questions", sum(len(section["questions"]) for section in sections))

    selected_section_id = st.selectbox(
        "Choose a section",
        options=[section["id"] for section in sections],
        key="survey_section_select",
    )
    selected_section = next(section for section in sections if section["id"] == selected_section_id)

    with st.form("edit_section_form"):
        section_id = st.text_input("Section ID", value=selected_section["id"])
        section_title = st.text_input("Section title", value=selected_section["title"])
        section_description = st.text_area("Section description", value=selected_section.get("description", ""), height=100)
        save_section = st.form_submit_button("Save section")
    if save_section:
        if section_id != selected_section["id"] and any(section["id"] == section_id for section in sections):
            st.error("A section with this ID already exists.")
            return
        updated_sections = []
        for section in sections:
            if section["id"] == selected_section["id"]:
                updated_sections.append(
                    {
                        "id": section_id.strip(),
                        "title": section_title.strip(),
                        "description": section_description,
                        "questions": section["questions"],
                    }
                )
            else:
                updated_sections.append(section)
        save_survey_config({"sections": updated_sections})
        st.success("Section updated.")
        st.rerun()

    question_options = [question["id"] for question in selected_section["questions"]]
    selected_question_id = st.selectbox(
        "Choose a question to edit",
        options=question_options,
        key="survey_question_select",
    )
    selected_question = next(
        question for question in selected_section["questions"] if question["id"] == selected_question_id
    )
    with st.form("edit_question_form"):
        question_id = st.text_input("Question ID", value=selected_question["id"])
        question_type = st.selectbox(
            "Question type",
            options=["likert", "open_text"],
            index=["likert", "open_text"].index(selected_question["type"]),
        )
        question_text = st.text_area("Question text", value=selected_question["text"], height=120)
        options_text = st.text_area(
            "Likert options (one per line as label|value)",
            value=_format_likert_options(selected_question),
            height=120,
            disabled=question_type != "likert",
        )
        save_question = st.form_submit_button("Save question")
    if save_question:
        if question_id != selected_question["id"] and any(
            question["id"] == question_id for question in selected_section["questions"]
        ):
            st.error("A question with this ID already exists in this section.")
            return
        updated_sections = []
        for section in sections:
            if section["id"] != selected_section["id"]:
                updated_sections.append(section)
                continue
            updated_questions = []
            for question in section["questions"]:
                if question["id"] == selected_question["id"]:
                    updated_question = {
                        "id": question_id.strip(),
                        "type": question_type,
                        "text": question_text,
                    }
                    if question_type == "likert":
                        parsed_options = _parse_likert_options(options_text)
                        if not parsed_options:
                            st.error("Likert questions must include at least one option.")
                            return
                        updated_question["options"] = parsed_options
                    updated_questions.append(updated_question)
                else:
                    updated_questions.append(question)
            updated_sections.append(
                {
                    "id": section_id.strip(),
                    "title": section_title.strip(),
                    "description": section_description,
                    "questions": updated_questions,
                }
            )
        save_survey_config({"sections": updated_sections})
        st.success("Question updated.")
        st.rerun()

    col_add_question, col_add_section = st.columns(2)
    with col_add_question:
        with st.form("add_question_form"):
            st.markdown("#### Add Question")
            new_question_id = st.text_input("New question ID")
            new_question_type = st.selectbox("New question type", options=["likert", "open_text"])
            new_question_text = st.text_area("New question text", height=100)
            new_question_options = st.text_area(
                "New Likert options (label|value)",
                height=100,
                help="Ignored for open_text questions.",
            )
            add_question = st.form_submit_button("Add question")
        if add_question:
            if not new_question_id.strip():
                st.error("Please enter an ID for the new question.")
                return
            if any(question["id"] == new_question_id.strip() for question in selected_section["questions"]):
                st.error("This question already exists in the selected section.")
                return
            question_payload: Dict[str, Any] = {
                "id": new_question_id.strip(),
                "type": new_question_type,
                "text": new_question_text,
            }
            if new_question_type == "likert":
                parsed_options = _parse_likert_options(new_question_options)
                if not parsed_options:
                    st.error("A Likert question needs at least one option.")
                    return
                question_payload["options"] = parsed_options
            updated_sections = []
            for section in sections:
                if section["id"] == selected_section["id"]:
                    updated_sections.append(
                        {
                            "id": section_id.strip(),
                            "title": section_title.strip(),
                            "description": section_description,
                            "questions": section["questions"] + [question_payload],
                        }
                    )
                else:
                    updated_sections.append(section)
            save_survey_config({"sections": updated_sections})
            st.success("Question added.")
            st.rerun()

    with col_add_section:
        with st.form("add_section_form"):
            st.markdown("#### Add Section")
            new_section_id = st.text_input("New section ID")
            new_section_title = st.text_input("New section title")
            new_section_description = st.text_area("New section description", height=100)
            add_section = st.form_submit_button("Add section")
        if add_section:
            if not new_section_id.strip() or not new_section_title.strip():
                st.error("Please enter at least the new section ID and title.")
                return
            if any(section["id"] == new_section_id.strip() for section in sections):
                st.error("This section ID already exists.")
                return
            updated_sections = sections + [
                {
                    "id": new_section_id.strip(),
                    "title": new_section_title.strip(),
                    "description": new_section_description,
                    "questions": [
                        {
                            "id": f"{new_section_id.strip()}_q1",
                            "type": "open_text",
                            "text": "New question",
                        }
                    ],
                }
            ]
            save_survey_config({"sections": updated_sections})
            st.success("Section added.")
            st.rerun()

    st.markdown(
        '<div class="admin-soft-note">Tip: keep the survey short unless the research design truly requires more. Shorter surveys usually improve completion quality.</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Advanced survey.yaml editor", expanded=False):
        render_yaml_editor("Advanced survey.yaml editor", SURVEY_CONFIG_PATH, save_survey_config)


def render_yaml_editor(title: str, path: Path, save_fn) -> None:
    content = path.read_text(encoding="utf-8")
    edited = st.text_area(f"Edit {path.name}", value=content, height=420)
    if st.button(f"Save {path.name}", key=f"save_{path.name}"):
        try:
            parsed = yaml.safe_load(edited) or {}
            save_fn(parsed)
        except (yaml.YAMLError, ConfigError, ValueError) as exc:
            st.error(f"Save failed: {exc}")
            return
        st.success(f"{path.name} updated.")
        st.rerun()


def render_study_readiness(app_config: Dict[str, Any], prompts_config: Dict[str, Any], survey_config: Dict[str, Any], database: Database) -> None:
    conditions = prompts_config["conditions"]
    active_conditions = [condition for condition in conditions if condition["active"]]
    operations = get_operations_context(database)
    provider = app_config.get("llm_provider", "openai")
    provider_key_present = bool(get_provider_api_key(provider)) if app_config.get("llm_mode", "mock") == "openai" else True
    checks = [
        (
            "Participant entry",
            "Open" if app_config["experiment_open"] else "Closed",
            "New participants can start the study." if app_config["experiment_open"] else "New participants are currently blocked.",
        ),
        (
            "Experimental conditions",
            f"{len(active_conditions)} active",
            "At least one active condition is ready for assignment." if active_conditions else "No active condition is available. New participants cannot be assigned correctly.",
        ),
        (
            "Survey",
            f"{len(survey_config['sections'])} sections",
            "The participant survey is available." if survey_config["sections"] else "No survey sections are configured yet.",
        ),
        (
            "LLM mode",
            str(app_config.get("llm_mode", "mock")).upper(),
            "Participants will use mock responses." if app_config.get("llm_mode", "mock") == "mock" else "Live model calls are enabled.",
        ),
        (
            "Provider secret",
            "Available" if provider_key_present else "Missing",
            "The live provider secret is present on the server." if provider_key_present else "The selected live provider does not currently have a usable server secret configured.",
        ),
        (
            "Live activity",
            f"{operations['in_progress_codes']} in progress",
            "The study is currently collecting live participant data." if operations["study_live"] else "There are no active participant sessions right now.",
        ),
    ]
    st.markdown("### Study Readiness")
    for title, status, detail in checks:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(status)
            st.write(detail)


def render_overview(database: Database) -> None:
    app_config, prompts_config, survey_config = _load_configs()
    render_operations_banner(database)
    pills = [
        f"Experiment {'open' if app_config['experiment_open'] else 'closed'}",
        f"LLM mode: {app_config.get('llm_mode', 'mock')}",
        f"Provider: {app_config.get('llm_provider', 'openai')}",
        f"Active conditions: {len([c for c in prompts_config['conditions'] if c['active']])}",
    ]
    st.markdown(
        '<div class="pill-row">' + "".join(f'<span class="status-pill">{pill}</span>' for pill in pills) + "</div>",
        unsafe_allow_html=True,
    )
    overview_col, checklist_col = st.columns([1.5, 1])
    with overview_col:
        render_dashboard(database)
    with checklist_col:
        render_study_readiness(app_config, prompts_config, survey_config, database)


def render_dashboard(database: Database) -> None:
    stats = database.count_access_codes_by_status()
    sessions_by_condition = database.count_sessions_by_condition()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Codes new", stats["new"])
    col2.metric("Codes in_progress", stats["in_progress"])
    col3.metric("Codes completed", stats["completed"])
    col4.metric("Codes disabled", stats["disabled"])
    st.markdown("### Sessions by Condition")
    if sessions_by_condition:
        st.dataframe(
            [{"condition": key, "sessions": value} for key, value in sessions_by_condition.items()],
            use_container_width=True,
        )
    else:
        st.info("No sessions recorded yet.")
    app_config, prompts_config, survey_config = _load_configs()
    st.markdown("### Current Configuration")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total conditions", len(prompts_config["conditions"]))
    col2.metric("Active conditions", len([c for c in prompts_config["conditions"] if c["active"]]))
    col3.metric("Survey sections", len(survey_config["sections"]))
    st.caption(
        f"Experiment open: {'yes' if app_config['experiment_open'] else 'no'} | "
        f"LLM mode: {app_config.get('llm_mode', 'mock')} | "
        f"Live provider: {app_config.get('llm_provider', 'openai')}"
    )

    st.markdown("### Analytics")
    metrics = database.get_session_metrics()
    total_sessions = int(metrics["total_sessions"])
    completed_sessions = int(metrics["completed_sessions"])
    completion_rate = (completed_sessions / total_sessions * 100) if total_sessions else 0.0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total sessions", total_sessions)
    m2.metric("Completion rate", f"{completion_rate:.1f}%")
    m3.metric("Avg. turns used", f"{metrics['average_turns_used']:.2f}")
    m4.metric("Avg. latency", f"{metrics['average_latency_ms']:.1f} ms")

    condition_df = pd.DataFrame(database.get_condition_analytics())
    turn_df = pd.DataFrame(database.get_turn_distribution())
    daily_df = pd.DataFrame(database.get_daily_session_counts())

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        st.markdown("#### Sessions by Condition")
        if not condition_df.empty:
            chart = (
                alt.Chart(condition_df)
                .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
                .encode(
                    x=alt.X("assigned_condition:N", title="Condition"),
                    y=alt.Y("sessions:Q", title="Sessions"),
                    tooltip=["assigned_condition", "sessions", "completed_sessions", "avg_turns_used"],
                    color=alt.Color("assigned_condition:N", legend=None),
                )
                .properties(height=280)
            )
            st.altair_chart(chart, use_container_width=True)
            st.dataframe(condition_df, use_container_width=True, hide_index=True)
        else:
            st.info("No condition data yet.")
    with chart_col2:
        st.markdown("#### Session Turn Distribution")
        if not turn_df.empty:
            chart = (
                alt.Chart(turn_df)
                .mark_area(line={"color": "#29638a"}, color="#cfe8f6")
                .encode(
                    x=alt.X("turn_count:Q", title="Turns used"),
                    y=alt.Y("sessions:Q", title="Sessions"),
                    tooltip=["turn_count", "sessions"],
                )
                .properties(height=280)
            )
            st.altair_chart(chart, use_container_width=True)
        else:
            st.info("No turn distribution available yet.")

    st.markdown("### Activity Over Time")
    if not daily_df.empty:
        chart = (
            alt.Chart(daily_df)
            .mark_line(point=True, strokeWidth=3, color="#3f7397")
            .encode(
                x=alt.X("day:N", title="Day"),
                y=alt.Y("sessions:Q", title="Started sessions"),
                tooltip=["day", "sessions"],
            )
            .properties(height=260)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No daily activity to display yet.")

    st.markdown("### Survey Response Summary")
    likert_df = pd.DataFrame(database.get_likert_summaries())
    if not likert_df.empty:
        st.dataframe(likert_df, use_container_width=True, hide_index=True)
        selected_question = st.selectbox(
            "Inspect a Likert question",
            options=likert_df["question_id"].tolist(),
            key="likert_breakdown_question",
        )
        breakdown_df = pd.DataFrame(database.get_likert_breakdown(selected_question))
        if not breakdown_df.empty:
            chart = (
                alt.Chart(breakdown_df)
                .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color="#6ea6c6")
                .encode(
                    x=alt.X("answer_label:N", title="Answer"),
                    y=alt.Y("responses:Q", title="Responses"),
                    tooltip=["answer_label", "responses"],
                )
                .properties(height=240)
            )
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No survey responses recorded yet.")
    st.markdown(
        '<div class="admin-soft-note">Tip: use this dashboard as the quick operational view, then use Export when you want formatted outputs for reporting or collaboration.</div>',
        unsafe_allow_html=True,
    )


def render_codes(database: Database) -> None:
    st.markdown("### Generate One-Time Codes")
    operations = get_operations_context(database)
    if operations["study_live"]:
        st.info("A live study session is currently running. Generate new codes only if you want to onboard more participants right now.")
    with st.form("generate_codes_form"):
        how_many = st.number_input("Number of codes to generate", min_value=1, max_value=500, value=5)
        submitted = st.form_submit_button("Generate")
    if submitted:
        created = database.create_access_codes(int(how_many))
        st.success(f"Created {len(created)} codes.")
        st.code("\n".join(created))
        st.download_button(
            label="Download generated codes (.txt)",
            data="\n".join(created).encode("utf-8"),
            file_name="participant_codes.txt",
            mime="text/plain",
            key="download_generated_codes_txt",
        )
    st.markdown("### Recent Codes")
    recent_codes = database.list_recent_access_codes(limit=50)
    if recent_codes:
        recent_df = pd.DataFrame(recent_codes)
        status_filter = st.multiselect(
            "Filter by status",
            options=sorted(recent_df["status"].dropna().unique().tolist()),
            default=sorted(recent_df["status"].dropna().unique().tolist()),
        )
        if status_filter:
            recent_df = recent_df[recent_df["status"].isin(status_filter)]
        st.dataframe(recent_df, use_container_width=True, hide_index=True)
    else:
        st.info("No codes available.")
    st.markdown(
        '<div class="admin-soft-note">For a live study session, generate a small batch of fresh participant codes here and distribute them privately.</div>',
        unsafe_allow_html=True,
    )


def render_export(database: Database) -> None:
    st.markdown("### CSV Export")
    st.write("Choose the export format based on what you need right now: raw tables for analysis pipelines, or a polished package for review and sharing.")
    raw_col, publication_col = st.columns(2)
    with raw_col:
        if st.button("Generate raw CSV export"):
            exported = export_all_tables(database)
            st.success("Raw export created.")
            for table_name, path in exported.items():
                st.write(f"{table_name}: {path}")
                st.download_button(
                    label=f"Download {path.name}",
                    data=path.read_bytes(),
                    file_name=path.name,
                    mime="text/csv",
                    key=f"download_{table_name}_{path.name}",
                )
    with publication_col:
        if st.button("Generate publication-ready export"):
            exported = create_publication_export(database)
            st.success("Publication-ready export created.")
            zip_path = exported["publication_export.zip"]
            report_path = exported["study_report.html"]
            st.download_button(
                label="Download publication export (.zip)",
                data=zip_path.read_bytes(),
                file_name=zip_path.name,
                mime="application/zip",
                key=f"download_zip_{zip_path.name}",
            )
            st.download_button(
                label="Download HTML study report",
                data=report_path.read_bytes(),
                file_name=report_path.name,
                mime="text/html",
                key=f"download_report_{report_path.name}",
            )
            st.caption("The publication-ready package includes raw data, summary CSVs, and a formatted HTML report.")
    if EXPORTS_DIR.exists():
        existing = sorted(EXPORTS_DIR.glob("export_*"))
        if existing:
            st.caption(f"Local export folder: {EXPORTS_DIR}")


def main() -> None:
    st.set_page_config(page_title="Admin", page_icon="🛠️", layout="wide")
    apply_admin_theme()
    st.markdown(
        """
        <div class="admin-hero">
            <div class="admin-kicker">Study Control Panel</div>
            <h1 style="margin-bottom:0.3rem;">Admin Mode</h1>
            <p style="margin:0; color:#516172;">
                Manage the study configuration, monitor participant progress, inspect response patterns,
                and export the collected data.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if not st.session_state.get("admin_authenticated"):
        render_login()
        st.stop()

    action_col1, action_col2 = st.columns([5, 1])
    with action_col2:
        if st.button("Sign out", use_container_width=True):
            st.session_state["admin_authenticated"] = False
            st.rerun()

    try:
        database = get_database()
        load_app_config()
        load_prompts_config()
        load_survey_config()
    except ConfigError as exc:
        st.error(f"Configuration error: {exc}")
        st.stop()

    top_tab_overview, top_tab_setup, top_tab_participants, top_tab_export = st.tabs(
        ["Overview", "Study Setup", "Participants", "Export"]
    )

    with top_tab_overview:
        render_overview(database)
    with top_tab_setup:
        render_operations_banner(database)
        st.markdown(
            '<div class="admin-soft-note">Use this area to configure the study before you distribute participant codes. The usual order is General Settings, then Conditions, then Survey.</div>',
            unsafe_allow_html=True,
        )
        setup_tab_general, setup_tab_conditions, setup_tab_survey = st.tabs(
            ["General Settings", "Conditions", "Survey"]
        )
        with setup_tab_general:
            render_app_settings(database)
        with setup_tab_conditions:
            render_conditions_manager(database)
        with setup_tab_survey:
            render_survey_manager()
    with top_tab_participants:
        render_operations_banner(database)
        st.markdown(
            '<div class="admin-soft-note">Use this area during live data collection to generate codes, check recent participant progress, and monitor operational status.</div>',
            unsafe_allow_html=True,
        )
        render_codes(database)
    with top_tab_export:
        render_operations_banner(database)
        render_export(database)


if __name__ == "__main__":
    main()
