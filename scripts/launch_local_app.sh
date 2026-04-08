#!/bin/zsh
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p "$PROJECT_ROOT/tmp"

if [ ! -d "$PROJECT_ROOT/.venv" ]; then
  python3 -m venv "$PROJECT_ROOT/.venv"
fi

"$PROJECT_ROOT/.venv/bin/python" "$PROJECT_ROOT/scripts/bootstrap_demo.py" >/dev/null

if ! "$PROJECT_ROOT/.venv/bin/python" -c "import streamlit, yaml, openai, dotenv" >/dev/null 2>&1; then
  "$PROJECT_ROOT/.venv/bin/pip" install -r "$PROJECT_ROOT/requirements.txt"
fi

if ! lsof -iTCP:8501 -sTCP:LISTEN >/dev/null 2>&1; then
  nohup "$PROJECT_ROOT/.venv/bin/streamlit" run "$PROJECT_ROOT/app.py" --server.port 8501 --server.headless true >"$PROJECT_ROOT/tmp/streamlit.log" 2>&1 &
  echo $! > "$PROJECT_ROOT/tmp/streamlit.pid"
fi

for _ in {1..20}; do
  if curl -s "http://localhost:8501" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

open "http://localhost:8501" || true
