# LLM Experiment App

A simple **Python + Streamlit + SQLite** web prototype for browser-based LLM experiments.

The app has two modes:

- **Participant**: enters with a one-time code, chats with the assigned assistant, then completes a survey.
- **Admin**: signs in with a password, manages settings, prompts, survey items, access codes, statistics, and CSV exports.

The app also works **without any real API key** in **mock** mode, which is ideal for development, automated tests, and local smoke tests.

## Public Deployment

This project is now prepared for public deployment through **Streamlit Community Cloud**.

Deployment notes are in:

[`DEPLOYMENT.md`](/Users/filippochiarello/Desktop/llm_experiment_app/DEPLOYMENT.md)

Important preparation already included:

- support for `.env` locally
- support for `st.secrets` in deployed environments
- example secrets file at [`.streamlit/secrets.toml.example`](/Users/filippochiarello/Desktop/llm_experiment_app/.streamlit/secrets.toml.example)
- repository-safe `.gitignore` rule for `.streamlit/secrets.toml`

## Quick Demo Access

For immediate local testing, the project includes a demo bootstrap flow.

- Demo admin password: `studyadmin`
- Demo participant code 1: `DEMO1001`
- Demo participant code 2: `DEMO1002`

The launcher resets those two participant codes back to `new` each time it starts the app, so you can test repeatedly.
On deployed environments, the app now also auto-creates the configured demo participant codes if they do not exist yet.

## Struttura del progetto

```text
llm_experiment_app/
  app.py
  pages/
    01_User.py
    02_Admin.py
  services/
    config_loader.py
    db.py
    experiment.py
    export.py
    llm.py
    randomization.py
    settings.py
  config/
    app.yaml
    prompts.yaml
    survey.yaml
  tests/
  scripts/
    smoke_test.py
  data/
  exports/
  requirements.txt
  .env.example
  .gitignore
  README.md
```

## What each YAML file does

### `config/app.yaml`

Contains general app settings, for example:

- app title
- whether the experiment is open or closed
- maximum chat turns
- randomization mode
- LLM mode (`mock` or `openai`)
- live provider (`openai`, `groq`, `openrouter`, `huggingface`)

### `config/prompts.yaml`

Contains experimental conditions. Each condition includes at least:

- `id`
- `active`
- `model`
- `temperature`
- `system_prompt`

You can activate or deactivate conditions without changing the code.

### `config/survey.yaml`

Contains the final survey, organized into sections with:

- `likert`
- `open_text`

## Requirements

- Python 3.9 or higher
- local terminal

## Installation

1. Open a terminal in the project folder:

```bash
cd /Users/filippochiarello/Desktop/llm_experiment_app
```

2. Create a virtual environment:

```bash
python3 -m venv .venv
```

3. Activate it:

```bash
source .venv/bin/activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

## Local `.env` configuration

To use the **Admin** area, create a local `.env` file in the project folder based on `.env.example`.

Minimal example for mock mode:

```env
ADMIN_PASSWORD=your_admin_password
LLM_MODE=mock
LLM_PROVIDER=openai
EXPERIMENT_DB_PATH=data/experiment.db
```

If you are not using a live provider yet, you can leave all API key fields empty.

The `.env` file is already excluded from the repository in `.gitignore`.

## Start the app

Inside the project folder, with the virtual environment active:

```bash
streamlit run app.py
```

By default, Streamlit uses this local link:

[http://localhost:8501](http://localhost:8501)

If port `8501` is busy, Streamlit will use another port and print it in the terminal.

## Click-To-Open Version

If you do not want to start the app from the terminal, use either:

- [`LLM Experiment Launcher.app`](/Users/filippochiarello/Desktop/llm_experiment_app/LLM%20Experiment%20Launcher.app)
- [`Open LLM Experiment.command`](/Users/filippochiarello/Desktop/llm_experiment_app/Open%20LLM%20Experiment.command)

On macOS you can double-click one of them in Finder. The `.app` version is the closest option to a no-terminal launch. They will:

1. make sure the virtual environment exists
2. create a demo `.env` if missing
3. seed demo credentials
4. start Streamlit in the background
5. open [http://localhost:8501](http://localhost:8501)

If macOS warns about opening the file, right-click it and choose **Open** the first time.

## Participant Flow

1. Open the home page.
2. Go to **Participant Mode**.
3. Enter a valid one-time code.
4. If the code is `new`, a session is created.
5. The system assigns one active condition using balanced randomization.
6. The participant can send messages up to `max_turns`.
7. The survey appears at the end.
8. After survey submission, the code becomes `completed`.

Important behavior:

- a `completed` code cannot access again
- an `in_progress` code can resume
- if `experiment_open: false`, no new participant can start

## Admin Flow

1. Open **Admin Mode**.
2. Enter the password defined in `.env`.
3. From the dashboard you can:

- view basic statistics
- edit general settings
- edit conditions, prompts, model names, and main parameters through a guided editor
- add or remove active conditions without touching the code
- edit survey sections and questions through a guided editor
- still use advanced YAML editors when needed
- generate one-time codes
- inspect recent codes
- generate CSV exports

## CSV Export

CSV is not used as the live database.

The live database is **SQLite**. CSV files are generated only when requested by the admin.

Files are saved in:

```text
/Users/filippochiarello/Desktop/llm_experiment_app/exports/
```

## Automated Tests

To run the tests:

```bash
pytest
```

Tests use **mock** mode and do not make standard external LLM calls.

## Local Smoke Test

To run a full smoke test in mock mode:

```bash
python scripts/smoke_test.py
```

The script verifies this flow:

1. initialize database and config
2. generate codes
3. start a participant session
4. assign a condition
5. send messages with the mock LLM
6. complete the survey
7. block a second access attempt for the same code
8. generate CSV exports

## Mock Mode and Live Providers

### Mock

Usa:

```env
LLM_MODE=mock
```

In this mode:

- the app works without any API key
- automated tests stay local
- no external LLM calls are made

### Live mode

Use:

```env
LLM_MODE=openai
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
```

The key must be stored **only** in the local `.env` file or another local secret store, never in the code.

You can also use supported compatible providers:

```env
LLM_MODE=openai
LLM_PROVIDER=groq
GROQ_API_KEY=your_key
```

```env
LLM_MODE=openai
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=your_key
```

```env
LLM_MODE=openai
LLM_PROVIDER=huggingface
HF_TOKEN=your_token
```

## Free API options

The app now supports free-friendly live provider options in addition to `mock`.

- **Groq**: Groq’s official site shows a free plan for getting started, and Groq documents OpenAI-compatible API access via `https://api.groq.com/openai/v1`.
- **OpenRouter**: OpenRouter documents a fully free router called `openrouter/free` plus `:free` model variants.
- **Hugging Face**: Hugging Face documents monthly free credits for Inference Providers, but the free amount is very small. I included support because their router is OpenAI-compatible, but for practical testing Groq or OpenRouter are the simpler choices.

Suggested examples for `config/prompts.yaml` when using free live providers:

```yaml
conditions:
  - id: "baseline"
    active: true
    model: "openrouter/free"
    temperature: 0.3
    top_p: 1.0
    max_output_tokens: 300
    system_prompt: |
      You are a neutral and clear assistant. Respond briefly and helpfully.
```

or:

```yaml
conditions:
  - id: "baseline"
    active: true
    model: "openai/gpt-oss-20b"
    temperature: 0.3
    top_p: 1.0
    max_output_tokens: 300
    system_prompt: |
      You are a neutral and clear assistant. Respond briefly and helpfully.
```

## Stored Data

SQLite stores these tables:

- `access_codes`
- `sessions`
- `messages`
- `survey_responses`

Each session also stores:

- a full snapshot of the condition prompt
- a full snapshot of the survey

This prevents future YAML changes from altering already collected data.

## Practical First Test

For a first local test:

1. set `ADMIN_PASSWORD` in `.env`
2. start the app
3. enter Admin Mode
4. generate a few codes
5. open Participant Mode
6. try one newly generated code
7. complete the mock chat and survey
