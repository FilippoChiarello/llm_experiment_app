from __future__ import annotations

import streamlit as st

from services.config_loader import ConfigError, load_app_config


st.set_page_config(page_title="Info", page_icon="🧪", layout="wide")


def apply_app_theme() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(199, 230, 255, 0.85), transparent 30%),
                radial-gradient(circle at top right, rgba(255, 230, 199, 0.8), transparent 28%),
                linear-gradient(180deg, #f7fbff 0%, #eef5f9 100%);
        }
        .hero-card {
            padding: 1.6rem 1.8rem;
            border-radius: 24px;
            background: rgba(255,255,255,0.82);
            border: 1px solid rgba(17, 24, 39, 0.08);
            box-shadow: 0 18px 45px rgba(31, 41, 55, 0.08);
            backdrop-filter: blur(8px);
            margin-bottom: 1rem;
        }
        .small-muted {
            color: #526071;
            font-size: 0.95rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    apply_app_theme()
    try:
        app_config = load_app_config()
    except ConfigError as exc:
        st.error(f"Configuration error: {exc}")
        st.stop()

    st.markdown(
        f"""
        <div class="hero-card">
            <div style="display:inline-block; padding:0.35rem 0.7rem; border-radius:999px; background:#edf4fb; color:#2c526f; font-size:0.85rem; margin-bottom:0.75rem;">
                Info
            </div>
            <h1 style="margin-bottom:0.4rem;">Study Access Hub</h1>
            <p class="small-muted" style="margin-bottom:0;">
                Choose how you want to enter the study platform. Participants can begin or resume a session with a
                one-time code, while researchers can open the admin area to manage the study setup and exports.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("Participant Mode")
            st.write("Enter a one-time code, review the consent information, complete the chat task, and finish the survey.")
            st.page_link("pages/01_User.py", label="Open Participant Mode")
    with col2:
        with st.container(border=True):
            st.subheader("Admin Mode")
            st.write("Sign in with the admin password to manage settings, prompts, survey items, participant codes, analytics, and exports.")
            st.page_link("pages/02_Admin.py", label="Open Admin Mode")


if __name__ == "__main__":
    main()
