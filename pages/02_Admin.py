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
from services.settings import EXPORTS_DIR, get_admin_password, get_database_path


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
            border-radius: 26px;
            background: rgba(255,255,255,0.88);
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.07);
            margin-bottom: 1rem;
        }
        .analytics-card {
            padding: 1rem 1.1rem;
            border-radius: 20px;
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 14px 30px rgba(15, 23, 42, 0.05);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login() -> None:
    configured_password = get_admin_password()
    st.subheader("Admin Sign In")
    if not configured_password:
        st.warning(
            "Admin password not configured. First create a local `.env` file with `ADMIN_PASSWORD=...`."
        )
        st.stop()
    with st.form("admin_login"):
        password = st.text_input("Admin password", type="password")
        submitted = st.form_submit_button("Sign in")
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
            "model": condition["model"],
            "temperature": condition["temperature"],
            "top_p": condition.get("top_p", 1.0),
            "max_output_tokens": condition.get("max_output_tokens", 400),
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


def render_app_settings() -> None:
    app_config = load_app_config()
    st.markdown("### General Settings")
    with st.form("app_settings_form"):
        title = st.text_input("App title", value=app_config["title"])
        experiment_open = st.checkbox("Experiment open to new participants", value=app_config["experiment_open"])
        max_turns = st.number_input("Maximum chat turns", min_value=1, value=app_config["max_turns"])
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
        submitted = st.form_submit_button("Save settings")
    if submitted:
        updated = dict(app_config)
        updated["title"] = title
        updated["experiment_open"] = experiment_open
        updated["max_turns"] = int(max_turns)
        updated["llm_mode"] = llm_mode
        updated["llm_provider"] = llm_provider
        updated["privacy_version"] = privacy_version.strip()
        updated["privacy_notice_text"] = privacy_notice_text.strip()
        save_app_config(updated)
        st.success("app.yaml updated.")
        st.rerun()


def render_conditions_manager() -> None:
    prompts_config = load_prompts_config()
    conditions = prompts_config["conditions"]
    st.markdown("### Experimental Conditions")
    st.write("Manage experimental conditions here without changing the application code.")
    st.dataframe(_summarize_conditions(conditions), use_container_width=True)

    selected_condition_id = st.selectbox(
        "Choose a condition to edit",
        options=[condition["id"] for condition in conditions],
        key="condition_select",
    )
    selected_condition = next(condition for condition in conditions if condition["id"] == selected_condition_id)
    with st.form("edit_condition_form"):
        condition_id = st.text_input("Condition ID", value=selected_condition["id"])
        active = st.checkbox("Condition active", value=selected_condition["active"])
        model = st.text_input("Model name", value=selected_condition["model"])
        temperature = st.number_input(
            "Temperature",
            min_value=0.0,
            max_value=2.0,
            value=float(selected_condition["temperature"]),
            step=0.1,
        )
        top_p = st.number_input(
            "Top p",
            min_value=0.0,
            max_value=1.0,
            value=float(selected_condition.get("top_p", 1.0)),
            step=0.05,
        )
        max_output_tokens = st.number_input(
            "Max output tokens",
            min_value=1,
            value=int(selected_condition.get("max_output_tokens", 400)),
        )
        system_prompt = st.text_area("System prompt", value=selected_condition["system_prompt"], height=220)
        submitted = st.form_submit_button("Save condition")
    if submitted:
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
                        "model": model.strip(),
                        "temperature": float(temperature),
                        "top_p": float(top_p),
                        "max_output_tokens": int(max_output_tokens),
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
            new_model = st.text_input("Model name", value="gpt-4.1-mini")
            new_temperature = st.number_input("New condition temperature", min_value=0.0, max_value=2.0, value=0.7, step=0.1)
            new_top_p = st.number_input("New condition top p", min_value=0.0, max_value=1.0, value=1.0, step=0.05)
            new_max_tokens = st.number_input("New condition max output tokens", min_value=1, value=400)
            new_system_prompt = st.text_area("New condition system prompt", height=180)
            add_submitted = st.form_submit_button("Add condition")
        if add_submitted:
            if not new_id.strip():
                st.error("Please enter an ID for the new condition.")
                return
            if any(condition["id"] == new_id.strip() for condition in conditions):
                st.error("This ID already exists.")
                return
            updated_conditions = conditions + [
                {
                    "id": new_id.strip(),
                    "active": new_active,
                    "model": new_model.strip(),
                    "temperature": float(new_temperature),
                    "top_p": float(new_top_p),
                    "max_output_tokens": int(new_max_tokens),
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
            updated_conditions = [condition for condition in conditions if condition["id"] != selected_condition_id]
            save_prompts_config({"conditions": updated_conditions})
            st.success("Condition removed.")
            st.rerun()

    st.divider()
    st.caption("Advanced YAML editor for more complex cases.")
    render_yaml_editor("Advanced prompts.yaml editor", PROMPTS_CONFIG_PATH, save_prompts_config)


def render_survey_manager() -> None:
    survey_config = load_survey_config()
    sections = survey_config["sections"]
    st.markdown("### Survey")
    st.write("Edit survey sections and questions directly here.")

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

    st.divider()
    st.caption("Advanced YAML editor for the full survey.")
    render_yaml_editor("Advanced survey.yaml editor", SURVEY_CONFIG_PATH, save_survey_config)


def render_yaml_editor(title: str, path: Path, save_fn) -> None:
    st.markdown(f"### {title}")
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
        st.markdown('<div class="analytics-card">', unsafe_allow_html=True)
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
        st.markdown("</div>", unsafe_allow_html=True)
    with chart_col2:
        st.markdown('<div class="analytics-card">', unsafe_allow_html=True)
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
        st.markdown("</div>", unsafe_allow_html=True)

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


def render_codes(database: Database) -> None:
    st.markdown("### Generate One-Time Codes")
    with st.form("generate_codes_form"):
        how_many = st.number_input("Number of codes to generate", min_value=1, max_value=500, value=5)
        submitted = st.form_submit_button("Generate")
    if submitted:
        created = database.create_access_codes(int(how_many))
        st.success(f"Created {len(created)} codes.")
        st.code("\n".join(created))
    st.markdown("### Recent Codes")
    recent_codes = database.list_recent_access_codes(limit=50)
    if recent_codes:
        st.dataframe(recent_codes, use_container_width=True)
    else:
        st.info("No codes available.")


def render_export(database: Database) -> None:
    st.markdown("### CSV Export")
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

    if st.button("Sign out"):
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

    tab_dashboard, tab_app, tab_conditions, tab_survey, tab_codes, tab_export = st.tabs(
        ["Dashboard", "Settings", "Conditions", "Survey", "Codes", "Export"]
    )

    with tab_dashboard:
        render_dashboard(database)
    with tab_app:
        render_app_settings()
    with tab_conditions:
        render_conditions_manager()
    with tab_survey:
        render_survey_manager()
    with tab_codes:
        render_codes(database)
    with tab_export:
        render_export(database)


if __name__ == "__main__":
    main()
