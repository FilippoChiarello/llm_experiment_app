from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from services.config_loader import ConfigError, get_active_conditions
from services.db import Database, utc_now_iso
from services.llm import LLMConfigurationError, LLMService
from services.randomization import choose_balanced_condition


class ExperimentService:
    def __init__(
        self,
        database: Database,
        app_config: Dict[str, Any],
        prompts_config: Dict[str, Any],
        survey_config: Dict[str, Any],
        llm_service: Optional[LLMService] = None,
    ):
        self.database = database
        self.app_config = app_config
        self.prompts_config = prompts_config
        self.survey_config = survey_config
        self.llm_service = llm_service or LLMService(
            app_config.get("llm_mode"),
            app_config.get("llm_provider"),
        )

    def _normalize_code(self, code: str) -> str:
        return code.strip().upper()

    def _session_payload(self, session: Dict[str, Any], code_record: Dict[str, Any]) -> Dict[str, Any]:
        messages = self.database.list_messages(session["session_id"])
        turn_count = len(messages)
        needs_survey = session["status"] == "survey_pending" or turn_count >= int(session["max_turns"])
        consent_complete = bool(session.get("consent_given_at"))
        can_chat = code_record["status"] == "in_progress" and not needs_survey and consent_complete
        return {
            "code": code_record["code"],
            "code_status": code_record["status"],
            "assigned_condition": session["assigned_condition"],
            "session_id": session["session_id"],
            "session_status": session["status"],
            "messages": messages,
            "turn_count": turn_count,
            "max_turns": int(session["max_turns"]),
            "needs_survey": needs_survey,
            "can_chat": can_chat,
            "consent_complete": consent_complete,
            "consent_version": session.get("consent_version") or self.app_config.get("privacy_version", "v1"),
            "consent_text_snapshot": session.get("consent_text_snapshot") or self.app_config.get(
                "privacy_notice_text",
                "",
            ),
            "prompt_snapshot": json.loads(session["prompt_snapshot"]),
            "survey_snapshot": json.loads(session["survey_snapshot"]),
            "model_name": session["model_name"],
        }

    def enter_code(self, code: str) -> Dict[str, Any]:
        normalized_code = self._normalize_code(code)
        code_record = self.database.get_access_code(normalized_code)
        if not code_record:
            return {"ok": False, "reason": "invalid_code", "message": "Invalid code."}
        if code_record["status"] == "completed":
            return {
                "ok": False,
                "reason": "completed",
                "message": "This code has already completed the experiment.",
            }
        if code_record["status"] == "disabled":
            return {"ok": False, "reason": "disabled", "message": "This code is disabled."}

        if code_record["status"] == "new":
            if not self.app_config["experiment_open"]:
                return {
                    "ok": False,
                    "reason": "closed",
                    "message": "The experiment is closed and does not accept new participants.",
                }
            try:
                active_conditions = get_active_conditions(self.prompts_config)
            except ConfigError as exc:
                return {
                    "ok": False,
                    "reason": "config_error",
                    "message": f"Configurazione non valida: {exc}",
                }
            counts = self.database.count_sessions_by_condition()
            chosen_condition = choose_balanced_condition(active_conditions, counts)
            session_id = str(uuid.uuid4())
            session = self.database.create_session(
                session_id=session_id,
                code=normalized_code,
                assigned_condition=str(chosen_condition["id"]),
                model_name=str(chosen_condition["model"]),
                prompt_snapshot=json.dumps(chosen_condition, ensure_ascii=True),
                survey_snapshot=json.dumps(self.survey_config, ensure_ascii=True),
                max_turns=int(self.app_config["max_turns"]),
                consent_version=self.app_config.get("privacy_version", "v1"),
                consent_text_snapshot=self.app_config.get("privacy_notice_text", ""),
            )
            self.database.update_access_code(
                normalized_code,
                status="in_progress",
                assigned_condition=str(chosen_condition["id"]),
                session_id=session_id,
                started_at=utc_now_iso(),
            )
            refreshed_code = self.database.get_access_code(normalized_code) or {}
            return {"ok": True, "reason": "started", "data": self._session_payload(session, refreshed_code)}

        session = self.database.get_session(str(code_record["session_id"]))
        if not session:
            return {
                "ok": False,
                "reason": "missing_session",
                "message": "No session was found for this code.",
            }
        return {"ok": True, "reason": "resumed", "data": self._session_payload(session, code_record)}

    def submit_user_message(self, code: str, user_text: str) -> Dict[str, Any]:
        state = self.enter_code(code)
        if not state["ok"]:
            return state
        payload = state["data"]
        if not payload["consent_complete"]:
            return {
                "ok": False,
                "reason": "consent_required",
                "message": "Consent is required before the chat can begin.",
            }
        if not payload["can_chat"]:
            return {
                "ok": False,
                "reason": "survey_required",
                "message": "You have reached the message limit. Please complete the survey.",
            }
        condition = payload["prompt_snapshot"]
        conversation_history: List[Dict[str, str]] = []
        for message in payload["messages"]:
            conversation_history.append({"role": "user", "content": message["user_text"]})
            conversation_history.append({"role": "assistant", "content": message["assistant_text"]})
        try:
            assistant_text, latency_ms = self.llm_service.generate_reply(
                condition=condition,
                history=conversation_history,
                user_message=user_text,
            )
        except LLMConfigurationError as exc:
            return {"ok": False, "reason": "llm_config", "message": str(exc)}

        turn_index = self.database.get_next_turn_index(payload["session_id"])
        self.database.add_message(
            session_id=payload["session_id"],
            turn_index=turn_index,
            user_text=user_text,
            assistant_text=assistant_text,
            latency_ms=latency_ms,
        )
        if turn_index >= payload["max_turns"]:
            self.database.update_session(payload["session_id"], status="survey_pending")
        code_state = self.enter_code(code)
        if not code_state["ok"]:
            return code_state
        return {
            "ok": True,
            "reason": "message_saved",
            "assistant_text": assistant_text,
            "data": code_state["data"],
        }

    def record_consent(self, code: str) -> Dict[str, Any]:
        state = self.enter_code(code)
        if not state["ok"]:
            return state
        payload = state["data"]
        if payload["consent_complete"]:
            return {"ok": True, "reason": "already_consented", "data": payload}
        self.database.update_session(
            payload["session_id"],
            consent_version=self.app_config.get("privacy_version", "v1"),
            consent_text_snapshot=self.app_config.get("privacy_notice_text", ""),
            consent_given_at=utc_now_iso(),
        )
        refreshed = self.enter_code(code)
        if not refreshed["ok"]:
            return refreshed
        return {"ok": True, "reason": "consent_recorded", "data": refreshed["data"]}

    def submit_survey(self, code: str, answers: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        state = self.enter_code(code)
        if not state["ok"]:
            return state
        payload = state["data"]
        session_id = payload["session_id"]
        survey_snapshot = payload["survey_snapshot"]
        question_map = {
            question["id"]: question
            for section in survey_snapshot["sections"]
            for question in section["questions"]
        }
        for question_id, answer in answers.items():
            question = question_map[question_id]
            self.database.add_survey_response(
                session_id=session_id,
                question_id=question_id,
                question_text_snapshot=question["text"],
                answer_value=answer.get("value"),
                answer_label=answer.get("label"),
            )
        self.database.update_session(session_id, status="completed", ended_at=utc_now_iso())
        self.database.update_access_code(code.strip().upper(), status="completed", completed_at=utc_now_iso())
        return {"ok": True, "reason": "completed"}
