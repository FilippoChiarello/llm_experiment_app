from __future__ import annotations

import streamlit as st

from services.config_loader import ConfigError, load_app_config
from services.settings import get_database_path


st.set_page_config(page_title="LLM Experiment App", page_icon="🧪", layout="wide")


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
        .mode-card {
            padding: 1.4rem;
            border-radius: 20px;
            background: rgba(255,255,255,0.92);
            border: 1px solid rgba(17, 24, 39, 0.08);
            min-height: 210px;
        }
        .small-muted {
            color: #526071;
            font-size: 0.95rem;
        }
        .demo-card {
            padding: 1rem 1.2rem;
            border-radius: 20px;
            background: rgba(255,255,255,0.9);
            border: 1px solid rgba(17, 24, 39, 0.08);
            margin-top: 1rem;
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
            <h1 style="margin-bottom:0.4rem;">{app_config["title"]}</h1>
            <p class="small-muted" style="margin-bottom:0;">
                A browser-based experimental platform with a participant chat flow, balanced condition assignment,
                integrated survey completion, and an admin area for experiment management.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info("Default mode is mock, so you can test the full app locally without any real API key.")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="mode-card">', unsafe_allow_html=True)
        st.subheader("Participant Mode")
        st.write("Enter a one-time code, chat with the assigned assistant, and complete the final survey.")
        st.page_link("pages/01_User.py", label="Open Participant Mode")
        st.markdown("</div>", unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="mode-card">', unsafe_allow_html=True)
        st.subheader("Admin Mode")
        st.write("Sign in with the admin password to manage settings, prompts, survey items, codes, and exports.")
        st.page_link("pages/02_Admin.py", label="Open Admin Mode")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        """
        <div class="demo-card">
            <strong>Quick demo credentials</strong><br>
            Admin password: <code>studyadmin</code><br>
            Participant codes: <code>DEMO1001</code>, <code>DEMO1002</code><br><br>
            If you use the clickable launcher, those demo participant codes are reset automatically so you can test again.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(f"Local database path: {get_database_path()}")


if __name__ == "__main__":
    main()
