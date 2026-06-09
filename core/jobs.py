from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any

from core.errors import ARTIFACT_FORBIDDEN, ARTIFACT_NOT_FOUND, GatewayError, INVALID_ARGUMENT
from core.ids import new_job_id
from core.policy import CallerIdentity
from core.time import utc_now_iso

TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}


@dataclass(frozen=True, slots=True)
class Job:
    id: str
    request_id: str
    caller_id: str
    tool_name: str
    status: str
    progress: float
    input_summary: dict[str, Any]
    result_summary: dict[str, Any] | None
    error_code: str | None
    error_message: str | None
    artifact_ids: list[str]
    created_at: str
    started_at: str | None
    updated_at: str
    finished_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "request_id": self.request_id,
            "caller_id": self.caller_id,
            "tool_name": self.tool_name,
            "status": self.status,
            "progress": self.progress,
            "input_summary": self.input_summary,
            "result_summary": self.result_summary,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "artifact_ids": self.artifact_ids,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
        }


class JobManager:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, *, request_id: str, caller_id: str, tool_name: str, input_summary: dict[str, Any]) -> Job:
        now = utc_now_iso()
        job_id = new_job_id()
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO jobs
                (id, request_id, caller_id, tool_name, status, progress, input_summary_json,
                 artifact_ids_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending', 0, ?, '[]', ?, ?)
                """,
                (job_id, request_id, caller_id, tool_name, json.dumps(input_summary, ensure_ascii=True), now, now),
            )
        return self.get(job_id, CallerIdentity(caller_id, role="admin", shared_artifact_read=True))

    def mark_running(self, job_id: str) -> None:
        job = self._get_unchecked(job_id)
        self._ensure_not_terminal(job)
        now = utc_now_iso()
        with self.conn:
            self.conn.execute(
                "UPDATE jobs SET status = 'running', started_at = COALESCE(started_at, ?), updated_at = ? WHERE id = ?",
                (now, now, job_id),
            )

    def update_progress(self, job_id: str, progress: float, result_summary: dict[str, Any] | None = None) -> None:
        if progress < 0 or progress > 1:
            raise GatewayError(INVALID_ARGUMENT, "job progress must be between 0 and 1")
        job = self._get_unchecked(job_id)
        self._ensure_not_terminal(job)
        with self.conn:
            self.conn.execute(
                "UPDATE jobs SET progress = ?, result_summary_json = COALESCE(?, result_summary_json), updated_at = ? WHERE id = ?",
                (
                    progress,
                    json.dumps(result_summary, ensure_ascii=True) if result_summary is not None else None,
                    utc_now_iso(),
                    job_id,
                ),
            )

    def mark_succeeded(self, job_id: str, result_summary: dict[str, Any], artifact_ids: list[str] | None = None) -> None:
        job = self._get_unchecked(job_id)
        self._ensure_not_terminal(job)
        now = utc_now_iso()
        with self.conn:
            self.conn.execute(
                """
                UPDATE jobs
                SET status = 'succeeded', progress = 1, result_summary_json = ?,
                    artifact_ids_json = ?, updated_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(result_summary, ensure_ascii=True, sort_keys=True),
                    json.dumps(artifact_ids or [], ensure_ascii=True),
                    now,
                    now,
                    job_id,
                ),
            )

    def mark_failed(self, job_id: str, error_code: str, error_message: str) -> None:
        job = self._get_unchecked(job_id)
        self._ensure_not_terminal(job)
        now = utc_now_iso()
        with self.conn:
            self.conn.execute(
                """
                UPDATE jobs
                SET status = 'failed', error_code = ?, error_message = ?, updated_at = ?, finished_at = ?
                WHERE id = ?
                """,
                (error_code, error_message, now, now, job_id),
            )

    def get(self, job_id: str, caller: CallerIdentity) -> Job:
        job = self._get_unchecked(job_id)
        if job.caller_id != caller.caller_id and not caller.is_admin:
            raise GatewayError(ARTIFACT_FORBIDDEN, "job access denied")
        return job

    def _get_unchecked(self, job_id: str) -> Job:
        row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise GatewayError(ARTIFACT_NOT_FOUND, "job not found")
        return Job(
            id=row["id"],
            request_id=row["request_id"],
            caller_id=row["caller_id"],
            tool_name=row["tool_name"],
            status=row["status"],
            progress=float(row["progress"]),
            input_summary=json.loads(row["input_summary_json"] or "{}"),
            result_summary=json.loads(row["result_summary_json"]) if row["result_summary_json"] else None,
            error_code=row["error_code"],
            error_message=row["error_message"],
            artifact_ids=json.loads(row["artifact_ids_json"] or "[]"),
            created_at=row["created_at"],
            started_at=row["started_at"],
            updated_at=row["updated_at"],
            finished_at=row["finished_at"],
        )

    def _ensure_not_terminal(self, job: Job) -> None:
        if job.status in TERMINAL_STATUSES:
            raise GatewayError(INVALID_ARGUMENT, "terminal job cannot be updated")
