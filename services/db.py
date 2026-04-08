from __future__ import annotations

import csv
import secrets
import sqlite3
import string
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def init_schema(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS access_codes (
                    code TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    assigned_condition TEXT,
                    session_id TEXT,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    code TEXT NOT NULL,
                    assigned_condition TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_snapshot TEXT NOT NULL,
                    survey_snapshot TEXT NOT NULL,
                    consent_version TEXT,
                    consent_text_snapshot TEXT,
                    consent_given_at TEXT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    max_turns INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(code) REFERENCES access_codes(code)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    turn_index INTEGER NOT NULL,
                    user_text TEXT NOT NULL,
                    assistant_text TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    latency_ms REAL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );

                CREATE TABLE IF NOT EXISTS survey_responses (
                    response_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    question_id TEXT NOT NULL,
                    question_text_snapshot TEXT NOT NULL,
                    answer_value TEXT,
                    answer_label TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id)
                );
                """
            )
            self._ensure_column(connection, "sessions", "consent_version", "TEXT")
            self._ensure_column(connection, "sessions", "consent_text_snapshot", "TEXT")
            self._ensure_column(connection, "sessions", "consent_given_at", "TEXT")

    def _ensure_column(self, connection: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
        existing_columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")

    def fetch_one(self, query: str, params: Iterable[Any] = ()) -> Optional[Dict[str, Any]]:
        with self.connect() as connection:
            row = connection.execute(query, tuple(params)).fetchone()
        return dict(row) if row else None

    def fetch_all(self, query: str, params: Iterable[Any] = ()) -> List[Dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    def ensure_access_code(self, code: str, status: str = "new") -> Dict[str, Any]:
        existing = self.get_access_code(code)
        if existing:
            return existing
        now = utc_now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO access_codes (code, status, created_at)
                VALUES (?, ?, ?)
                """,
                (code, status, now),
            )
        return self.get_access_code(code) or {}

    def create_access_codes(self, count: int, code_length: int = 8) -> List[str]:
        alphabet = string.ascii_uppercase + string.digits
        created_codes: List[str] = []
        for _ in range(count):
            while True:
                candidate = "".join(secrets.choice(alphabet) for _ in range(code_length))
                if not self.get_access_code(candidate):
                    self.ensure_access_code(candidate)
                    created_codes.append(candidate)
                    break
        return created_codes

    def get_access_code(self, code: str) -> Optional[Dict[str, Any]]:
        return self.fetch_one("SELECT * FROM access_codes WHERE code = ?", (code,))

    def update_access_code(
        self,
        code: str,
        *,
        status: Optional[str] = None,
        assigned_condition: Optional[str] = None,
        session_id: Optional[str] = None,
        started_at: Optional[str] = None,
        completed_at: Optional[str] = None,
    ) -> None:
        fields = []
        params: List[Any] = []
        for field_name, value in {
            "status": status,
            "assigned_condition": assigned_condition,
            "session_id": session_id,
            "started_at": started_at,
            "completed_at": completed_at,
        }.items():
            if value is not None:
                fields.append(f"{field_name} = ?")
                params.append(value)
        if not fields:
            return
        params.append(code)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE access_codes SET {', '.join(fields)} WHERE code = ?",
                params,
            )

    def create_session(
        self,
        session_id: str,
        code: str,
        assigned_condition: str,
        model_name: str,
        prompt_snapshot: str,
        survey_snapshot: str,
        max_turns: int,
        status: str = "in_progress",
        consent_version: Optional[str] = None,
        consent_text_snapshot: Optional[str] = None,
    ) -> Dict[str, Any]:
        started_at = utc_now_iso()
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, code, assigned_condition, model_name, prompt_snapshot,
                    survey_snapshot, consent_version, consent_text_snapshot, started_at, max_turns, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    code,
                    assigned_condition,
                    model_name,
                    prompt_snapshot,
                    survey_snapshot,
                    consent_version,
                    consent_text_snapshot,
                    started_at,
                    max_turns,
                    status,
                ),
            )
        return self.get_session(session_id) or {}

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.fetch_one("SELECT * FROM sessions WHERE session_id = ?", (session_id,))

    def update_session(
        self,
        session_id: str,
        *,
        status: Optional[str] = None,
        ended_at: Optional[str] = None,
        model_name: Optional[str] = None,
        consent_version: Optional[str] = None,
        consent_text_snapshot: Optional[str] = None,
        consent_given_at: Optional[str] = None,
    ) -> None:
        fields = []
        params: List[Any] = []
        for field_name, value in {
            "status": status,
            "ended_at": ended_at,
            "model_name": model_name,
            "consent_version": consent_version,
            "consent_text_snapshot": consent_text_snapshot,
            "consent_given_at": consent_given_at,
        }.items():
            if value is not None:
                fields.append(f"{field_name} = ?")
                params.append(value)
        if not fields:
            return
        params.append(session_id)
        with self.connect() as connection:
            connection.execute(
                f"UPDATE sessions SET {', '.join(fields)} WHERE session_id = ?",
                params,
            )

    def add_message(
        self,
        session_id: str,
        turn_index: int,
        user_text: str,
        assistant_text: str,
        latency_ms: Optional[float] = None,
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO messages (
                    session_id, turn_index, user_text, assistant_text, timestamp, latency_ms
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (session_id, turn_index, user_text, assistant_text, utc_now_iso(), latency_ms),
            )

    def list_messages(self, session_id: str) -> List[Dict[str, Any]]:
        return self.fetch_all(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY turn_index ASC",
            (session_id,),
        )

    def get_next_turn_index(self, session_id: str) -> int:
        row = self.fetch_one(
            "SELECT COALESCE(MAX(turn_index), 0) AS max_turn_index FROM messages WHERE session_id = ?",
            (session_id,),
        )
        return int(row["max_turn_index"]) + 1 if row else 1

    def add_survey_response(
        self,
        session_id: str,
        question_id: str,
        question_text_snapshot: str,
        answer_value: Optional[str],
        answer_label: Optional[str],
    ) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO survey_responses (
                    session_id, question_id, question_text_snapshot,
                    answer_value, answer_label, timestamp
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    question_id,
                    question_text_snapshot,
                    answer_value,
                    answer_label,
                    utc_now_iso(),
                ),
            )

    def count_access_codes_by_status(self) -> Dict[str, int]:
        rows = self.fetch_all(
            "SELECT status, COUNT(*) AS count FROM access_codes GROUP BY status"
        )
        summary = {"new": 0, "in_progress": 0, "completed": 0, "disabled": 0}
        for row in rows:
            summary[row["status"]] = int(row["count"])
        return summary

    def count_sessions_by_condition(self) -> Dict[str, int]:
        rows = self.fetch_all(
            "SELECT assigned_condition, COUNT(*) AS count FROM sessions GROUP BY assigned_condition"
        )
        return {str(row["assigned_condition"]): int(row["count"]) for row in rows}

    def list_recent_access_codes(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.fetch_all(
            "SELECT * FROM access_codes ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )

    def get_session_metrics(self) -> Dict[str, float]:
        row = self.fetch_one(
            """
            SELECT
                COUNT(*) AS total_sessions,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions,
                AVG(max_turns) AS average_max_turns,
                AVG(message_count) AS average_turns_used,
                AVG(avg_latency) AS average_latency_ms
            FROM (
                SELECT
                    sessions.session_id,
                    sessions.status,
                    sessions.max_turns,
                    COUNT(messages.message_id) AS message_count,
                    AVG(messages.latency_ms) AS avg_latency
                FROM sessions
                LEFT JOIN messages ON sessions.session_id = messages.session_id
                GROUP BY sessions.session_id
            ) AS session_rollup
            """
        )
        return {
            "total_sessions": float(row["total_sessions"] or 0),
            "completed_sessions": float(row["completed_sessions"] or 0),
            "average_max_turns": float(row["average_max_turns"] or 0),
            "average_turns_used": float(row["average_turns_used"] or 0),
            "average_latency_ms": float(row["average_latency_ms"] or 0),
        }

    def get_condition_analytics(self) -> List[Dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT
                sessions.assigned_condition,
                COUNT(DISTINCT sessions.session_id) AS sessions,
                SUM(CASE WHEN sessions.status = 'completed' THEN 1 ELSE 0 END) AS completed_sessions,
                ROUND(AVG(message_rollup.message_count), 2) AS avg_turns_used
            FROM sessions
            LEFT JOIN (
                SELECT session_id, COUNT(*) AS message_count
                FROM messages
                GROUP BY session_id
            ) AS message_rollup ON sessions.session_id = message_rollup.session_id
            GROUP BY sessions.assigned_condition
            ORDER BY sessions DESC, sessions.assigned_condition ASC
            """
        )

    def get_daily_session_counts(self) -> List[Dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT substr(started_at, 1, 10) AS day, COUNT(*) AS sessions
            FROM sessions
            GROUP BY substr(started_at, 1, 10)
            ORDER BY day ASC
            """
        )

    def get_turn_distribution(self) -> List[Dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT
                turn_count,
                COUNT(*) AS sessions
            FROM (
                SELECT sessions.session_id, COUNT(messages.message_id) AS turn_count
                FROM sessions
                LEFT JOIN messages ON sessions.session_id = messages.session_id
                GROUP BY sessions.session_id
            ) AS turn_rollup
            GROUP BY turn_count
            ORDER BY turn_count ASC
            """
        )

    def get_likert_summaries(self) -> List[Dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT
                question_id,
                question_text_snapshot,
                COUNT(*) AS responses,
                ROUND(AVG(CAST(answer_value AS REAL)), 2) AS average_score
            FROM survey_responses
            WHERE answer_value GLOB '[0-9]*'
            GROUP BY question_id, question_text_snapshot
            ORDER BY question_id ASC
            """
        )

    def get_likert_breakdown(self, question_id: str) -> List[Dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT answer_label, COUNT(*) AS responses
            FROM survey_responses
            WHERE question_id = ?
            GROUP BY answer_label
            ORDER BY answer_label ASC
            """,
            (question_id,),
        )

    def get_open_text_responses(self) -> List[Dict[str, Any]]:
        return self.fetch_all(
            """
            SELECT
                survey_responses.session_id,
                sessions.assigned_condition,
                survey_responses.question_id,
                survey_responses.question_text_snapshot,
                survey_responses.answer_value,
                survey_responses.timestamp
            FROM survey_responses
            LEFT JOIN sessions ON survey_responses.session_id = sessions.session_id
            WHERE survey_responses.answer_value IS NOT NULL
              AND survey_responses.answer_value != ''
              AND survey_responses.answer_value NOT GLOB '[0-9]*'
            ORDER BY survey_responses.timestamp ASC
            """
        )

    def reset_access_code_for_demo(self, code: str) -> None:
        code_record = self.get_access_code(code)
        if not code_record:
            self.ensure_access_code(code, status="new")
            return
        session_id = code_record.get("session_id")
        with self.connect() as connection:
            if session_id:
                connection.execute("DELETE FROM survey_responses WHERE session_id = ?", (session_id,))
                connection.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                connection.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            connection.execute(
                """
                UPDATE access_codes
                SET status = 'new',
                    assigned_condition = NULL,
                    session_id = NULL,
                    started_at = NULL,
                    completed_at = NULL
                WHERE code = ?
                """,
                (code,),
            )

    def export_table_to_csv(self, table_name: str, output_path: Path) -> None:
        rows = self.fetch_all(f"SELECT * FROM {table_name}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            if rows:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            else:
                handle.write("")
