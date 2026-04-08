from __future__ import annotations

from typing import Dict

import streamlit as st

from services.config_loader import (
    ConfigError,
    load_app_config,
    load_prompts_config,
    load_survey_config,
)
from services.db import Database
from services.experiment import ExperimentService
from services.settings import get_database_path


def apply_user_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(182, 223, 255, 0.88), transparent 22%),
                radial-gradient(circle at 85% 15%, rgba(255, 224, 196, 0.82), transparent 24%),
                radial-gradient(circle at bottom right, rgba(214, 246, 229, 0.8), transparent 30%),
                linear-gradient(180deg, #f7fbff 0%, #eef5f8 55%, #f7fafb 100%);
        }
        .study-hero {
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 28px;
            padding: 1.5rem 1.6rem;
            box-shadow: 0 22px 44px rgba(15, 23, 42, 0.07);
            margin-bottom: 1rem;
        }
        .study-kicker {
            display: inline-block;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: #edf4fb;
            color: #2c526f;
            font-size: 0.85rem;
            margin-bottom: 0.75rem;
        }
        .panel-card {
            background: rgba(255,255,255,0.92);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 24px;
            padding: 1.3rem 1.4rem;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.06);
            margin-bottom: 1rem;
        }
        .completion-card {
            background: linear-gradient(135deg, rgba(237,248,255,0.96), rgba(255,246,231,0.96));
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 28px;
            padding: 2rem;
            box-shadow: 0 20px 45px rgba(15, 23, 42, 0.08);
        }
        .consent-card {
            background: rgba(255,255,255,0.93);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 26px;
            padding: 1.5rem;
            box-shadow: 0 18px 40px rgba(15, 23, 42, 0.07);
        }
        .consent-box {
            background: #f8fbfd;
            border: 1px solid #dde8ef;
            border-radius: 18px;
            padding: 1rem;
            color: #405162;
            line-height: 1.55;
        }
        div[data-testid="stTabs"] button[role="tab"] {
            border-radius: 16px;
            border: 1px solid rgba(15, 23, 42, 0.08);
            background: rgba(255,255,255,0.78);
            padding: 0.7rem 1rem;
            min-height: 56px;
            transition: all 0.2s ease;
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
        .chat-shell {
            background: rgba(255,255,255,0.64);
            border: 1px solid rgba(15, 23, 42, 0.06);
            border-radius: 24px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .soft-note {
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 18px;
            padding: 0.9rem 1rem;
            color: #4f6070;
            margin-top: 0.8rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_service() -> ExperimentService:
    app_config = load_app_config()
    prompts_config = load_prompts_config()
    survey_config = load_survey_config()
    database = Database(get_database_path())
    database.init_schema()
    for code in app_config.get("demo_access_codes", []):
        if isinstance(code, str) and code.strip():
            database.ensure_access_code(code.strip().upper())
    return ExperimentService(database, app_config, prompts_config, survey_config)


def reset_user_flow() -> None:
    for key in ["user_code", "user_state", "completed_message"]:
        st.session_state.pop(key, None)


def render_code_gate(service: ExperimentService) -> None:
    with st.container(border=True):
        st.subheader("Participant Access")
        st.write("Please enter your one-time access code to begin or resume your session.")
        with st.form("user_code_form", clear_on_submit=False):
            code_value = st.text_input("Enter your one-time code").strip().upper()
            submitted = st.form_submit_button("Continue")
        if submitted:
            result = service.enter_code(code_value)
            if not result["ok"]:
                st.error(result["message"])
                return
            st.session_state["user_code"] = code_value
            st.session_state["user_state"] = result["data"]
            st.success("Access granted.")
            st.rerun()


def render_consent(service: ExperimentService, code: str, state: Dict[str, object]) -> None:
    with st.container(border=True):
        st.subheader("Privacy Notice and Consent")
        st.write("Please review the information below before starting the study chat.")
        st.markdown(
            f"""
            <div class="consent-box">
                <strong>Consent version:</strong> {state['consent_version']}<br><br>
                {state['consent_text_snapshot']}
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("consent_form"):
            confirmed = st.checkbox(
                "I have read the privacy notice and I consent to participate in this study."
            )
            no_sensitive_data = st.checkbox(
                "I understand that I should avoid sharing unnecessary personal or sensitive information."
            )
            submitted = st.form_submit_button("Accept and continue")
        if submitted:
            if not confirmed or not no_sensitive_data:
                st.error("Please confirm both statements before continuing.")
                return
            result = service.record_consent(code)
            if result["ok"]:
                st.session_state["user_state"] = result["data"]
                st.rerun()
            st.error(result["message"])


def render_chat(service: ExperimentService, code: str, state: Dict[str, object]) -> None:
    with st.container(border=True):
        st.subheader("Experiment Chat")
        if state["unlimited_turns"]:
            st.caption("There is no fixed turn limit for this session.")
        else:
            st.caption(f"Messages used: {state['turn_count']} / {state['max_turns']}")
        for message in state["messages"]:
            with st.chat_message("user"):
                st.write(message["user_text"])
            with st.chat_message("assistant"):
                st.write(message["assistant_text"])

        if not state["can_chat"]:
            st.info("You have reached the maximum number of chat turns. Please continue to the survey.")
            return

        user_input = st.chat_input("Write your message")
        if user_input:
            result = service.submit_user_message(code, user_input)
            if result["ok"]:
                st.session_state["user_state"] = result["data"]
                st.rerun()
            else:
                st.error(result["message"])


def render_survey(service: ExperimentService, code: str, state: Dict[str, object]) -> None:
    with st.container(border=True):
        st.subheader("Final Survey")
        st.write("Please answer the final questions below to complete your participation.")
        survey_snapshot = state["survey_snapshot"]
        answers = {}
        with st.form("survey_form"):
            for section in survey_snapshot["sections"]:
                st.markdown(f"### {section['title']}")
                if section.get("description"):
                    st.write(section["description"])
                for question in section["questions"]:
                    key = f"survey_{question['id']}"
                    if question["type"] == "likert":
                        labels = [option["label"] for option in question["options"]]
                        selected_label = st.radio(question["text"], labels, key=key, index=None)
                        selected_option = next(
                            (option for option in question["options"] if option["label"] == selected_label),
                            None,
                        )
                        answers[question["id"]] = {
                            "value": selected_option["value"] if selected_option else "",
                            "label": selected_option["label"] if selected_option else "",
                        }
                    else:
                        free_text = st.text_area(question["text"], key=key)
                        answers[question["id"]] = {"value": free_text, "label": free_text}
            submitted = st.form_submit_button("Submit survey")
        if submitted:
            missing_likert = [
                question["id"]
                for section in survey_snapshot["sections"]
                for question in section["questions"]
                if question["type"] == "likert" and not answers[question["id"]]["value"]
            ]
            if missing_likert:
                st.error("Please answer all Likert questions before submitting the survey.")
                return
            result = service.submit_survey(code, answers)
            if result["ok"]:
                st.success("Survey submitted. Thank you for participating.")
                st.session_state["user_state"] = None
                st.session_state["user_code"] = code
                st.session_state["completed_message"] = True
                st.rerun()
            st.error(result["message"])


def render_completion_page() -> None:
    st.markdown(
        """
        <div class="completion-card">
            <h2 style="margin-bottom:0.4rem;">Participation complete</h2>
            <p style="font-size:1.05rem; color:#3d4c5c;">
                Your chat session and survey responses have been saved successfully.
                This one-time code is now closed and cannot be used again.
            </p>
            <hr style="border:none; border-top:1px solid rgba(15,23,42,0.08); margin:1.2rem 0;">
            <p style="margin-bottom:0.4rem;"><strong>What happens next?</strong></p>
            <p style="color:#485769; margin-bottom:0;">
                You can safely close this page. If you were asked to report completion to the researcher,
                you may now do so.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="User", page_icon="🧪", layout="wide")
    apply_user_theme()
    st.markdown(
        """
        <div class="study-hero">
            <div class="study-kicker">Participant Session</div>
            <h1 style="margin:0 0 0.45rem 0;">Participant Mode</h1>
            <p style="margin:0; color:#536475; font-size:1rem;">
                Use your one-time access code to enter the study, review the consent notice,
                complete the chat task, and finish with the final survey.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    try:
        service = get_service()
    except ConfigError as exc:
        st.error(f"Configuration error: {exc}")
        st.stop()

    if st.session_state.get("completed_message"):
        render_completion_page()
        if st.button("Use a different code"):
            st.session_state.pop("completed_message", None)
            reset_user_flow()
            st.rerun()
        st.stop()

    code = st.session_state.get("user_code")
    state = st.session_state.get("user_state")
    if not code or not state:
        render_code_gate(service)
        st.stop()

    latest_state = service.enter_code(code)
    if not latest_state["ok"]:
        st.error(latest_state["message"])
        if st.button("Back to start"):
            reset_user_flow()
            st.rerun()
        st.stop()

    state = latest_state["data"]
    st.session_state["user_state"] = state

    if st.button("Leave this session"):
        reset_user_flow()
        st.rerun()

    if state["needs_survey"]:
        render_survey(service, code, state)
    else:
        consent_tab, chat_tab = st.tabs(["Consent", "Chat"])
        with consent_tab:
            render_consent(service, code, state)
        with chat_tab:
            if not state["consent_complete"]:
                with st.container(border=True):
                    st.subheader("Experiment Chat")
                    st.info("Please complete the consent step first. The chat will unlock immediately after consent.")
            else:
                render_chat(service, code, state)
        st.markdown(
            '<div class="soft-note">You can return to the Consent tab at any time during this session to review the privacy notice again.</div>',
            unsafe_allow_html=True,
        )
        if state["unlimited_turns"]:
            st.info("This session has no fixed turn limit. You can continue the chat until you decide to stop the session.")
        else:
            st.info("The survey will appear automatically when you reach the maximum number of chat turns.")


if __name__ == "__main__":
    main()
