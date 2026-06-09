from __future__ import annotations

from typing import Any

from core.errors import GatewayError


def success(
    *,
    request_id: str,
    status: str = "succeeded",
    job_id: str | None = None,
    **payload: Any,
) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True, "request_id": request_id, "status": status}
    if job_id:
        result["job_id"] = job_id
    result.update(payload)
    return result


def failure(*, request_id: str, error: GatewayError, job_id: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": False,
        "request_id": request_id,
        "status": "failed",
        "error": {
            "code": error.code,
            "message": error.message,
            "retryable": error.retryable,
        },
    }
    if job_id:
        result["job_id"] = job_id
    return result
