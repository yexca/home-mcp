from __future__ import annotations

import json
import sqlite3
from time import perf_counter
from typing import Any

from app.config import Settings
from core.ids import new_audit_id
from core.time import utc_now_iso

SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "access_token",
    "b64_data",
    "b64_json",
    "base64",
    "token",
    "base_url",
    "password",
    "secret",
}
SUMMARY_TEXT_KEYS = {"prompt", "text", "caption"}


class AuditLogger:
    def __init__(self, conn: sqlite3.Connection, settings: Settings):
        self.conn = conn
        self.settings = settings
        self._started_perf: dict[str, float] = {}

    def start(
        self,
        *,
        request_id: str,
        job_id: str | None,
        caller_id: str,
        tool_name: str,
        risk_level: str,
        arguments: dict[str, Any],
    ) -> str:
        audit_id = new_audit_id()
        self._started_perf[audit_id] = perf_counter()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO audit_events
                (id, request_id, job_id, caller_id, tool_name, risk_level,
                 input_summary_json, status, started_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'started', ?)
                """,
                (
                    audit_id,
                    request_id,
                    job_id,
                    caller_id,
                    tool_name,
                    risk_level,
                    json.dumps(self.summarize_input(arguments), ensure_ascii=True, sort_keys=True),
                    utc_now_iso(),
                ),
            )
        return audit_id

    def finish(
        self,
        *,
        audit_id: str,
        policy_decision: str,
        status: str,
        artifact_ids: list[str] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        started = self._started_perf.pop(audit_id, perf_counter())
        duration_ms = int((perf_counter() - started) * 1000)
        with self.conn:
            self.conn.execute(
                """
                UPDATE audit_events
                SET policy_decision = ?, status = ?, artifact_ids_json = ?,
                    error_code = ?, error_message = ?, finished_at = ?, duration_ms = ?
                WHERE id = ?
                """,
                (
                    policy_decision,
                    status,
                    json.dumps(artifact_ids or [], ensure_ascii=True),
                    error_code,
                    error_message,
                    utc_now_iso(),
                    duration_ms,
                    audit_id,
                ),
            )

    def summarize_input(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit = int(self.settings.audit.get("prompt_summary_chars", 200))
        return _summarize(arguments, limit)


def _summarize(value: Any, text_limit: int) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            lowered = key.lower()
            if lowered in SENSITIVE_KEYS or any(part in lowered for part in SENSITIVE_KEYS):
                result[key] = "[redacted]"
            elif lowered in SUMMARY_TEXT_KEYS and isinstance(item, str):
                result[key] = {"prefix": item[:text_limit], "length": len(item)}
            else:
                result[key] = _summarize(item, text_limit)
        return result
    if isinstance(value, list):
        return [_summarize(item, text_limit) for item in value]
    return value
