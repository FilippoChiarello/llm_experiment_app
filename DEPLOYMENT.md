# Public Deployment

This project is prepared for **Streamlit Community Cloud**, which is the simplest way to publish a public shareable link for a Streamlit app.

## Why this option

The official Streamlit docs describe Community Cloud as a one-click deployment flow from a GitHub repository. Streamlit also documents a secure secrets workflow through the app's **Advanced settings** using `st.secrets`.

## What you need

1. A GitHub account
2. A GitHub repository containing this project
3. A Streamlit Community Cloud account

## Recommended deployment path

1. Create a new GitHub repository.
2. Upload the contents of `/Users/filippochiarello/Desktop/llm_experiment_app`.
3. Go to Streamlit Community Cloud.
4. Click **Create app**.
5. Select your GitHub repository.
6. Set the main file to `app.py`.
7. Open **Advanced settings**.
8. Paste your secrets in TOML format.

Example secrets for mock mode:

```toml
ADMIN_PASSWORD = "your-admin-password"
LLM_MODE = "mock"
LLM_PROVIDER = "openai"
EXPERIMENT_DB_PATH = "data/experiment.db"
```

Example secrets for a live provider:

```toml
ADMIN_PASSWORD = "your-admin-password"
LLM_MODE = "openai"
LLM_PROVIDER = "groq"
GROQ_API_KEY = "your-real-key"
EXPERIMENT_DB_PATH = "data/experiment.db"
```

## Important note

Community Cloud instances are not meant to be a permanent production database host for sensitive research data. For a real study, you should plan a more durable deployment architecture for:

- persistent database storage
- backups
- access control
- data retention
- audit and governance

This project is now deployment-ready for a **public demo or pilot**, but for a formal study you should evaluate a more controlled hosting setup.
