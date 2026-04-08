from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.db import Database
from services.settings import PROJECT_ROOT, get_database_path


DEMO_ADMIN_PASSWORD = "studyadmin"
DEMO_CODES = ["DEMO1001", "DEMO1002"]


def ensure_env_file() -> Path:
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        return env_path
    env_path.write_text(
        "\n".join(
            [
                f"ADMIN_PASSWORD={DEMO_ADMIN_PASSWORD}",
                "LLM_MODE=mock",
                "LLM_PROVIDER=openai",
                "EXPERIMENT_DB_PATH=data/experiment.db",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return env_path


def seed_demo_data() -> None:
    database = Database(get_database_path())
    database.init_schema()
    for code in DEMO_CODES:
        database.reset_access_code_for_demo(code)


def main() -> None:
    env_path = ensure_env_file()
    seed_demo_data()
    print(f"Demo environment ready: {env_path}")
    print(f"Demo admin password: {DEMO_ADMIN_PASSWORD}")
    print("Demo participant codes:")
    for code in DEMO_CODES:
        print(f"- {code}")


if __name__ == "__main__":
    main()
