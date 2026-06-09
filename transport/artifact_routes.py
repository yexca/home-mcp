from __future__ import annotations

import json
from http import HTTPStatus
from urllib.parse import unquote

from core.errors import GatewayError
from transport.request_context import CoreServices


def serve_artifact(handler, services: CoreServices, artifact_id: str) -> None:
    authorization = handler.headers.get("Authorization")
    caller = services.policy.resolve_caller(authorization, remote_addr=handler.client_address[0])
    try:
        artifact = services.artifacts.get(unquote(artifact_id), caller)
        path = services.artifacts.safe_path(artifact)
        handler.send_response(HTTPStatus.OK)
        handler.send_header("Content-Type", artifact.mime_type)
        handler.send_header("Content-Length", str(artifact.size_bytes))
        handler.send_header("Content-Disposition", f'inline; filename="{artifact.filename}"')
        handler.send_header("X-Artifact-Id", artifact.id)
        handler.send_header("Cache-Control", "private, max-age=300")
        handler.end_headers()
        with path.open("rb") as fh:
            while chunk := fh.read(1024 * 1024):
                handler.wfile.write(chunk)
    except GatewayError as exc:
        payload = {
            "ok": False,
            "status": "failed",
            "error": {"code": exc.code, "message": exc.message, "retryable": exc.retryable},
        }
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        handler.send_response(HTTPStatus.FORBIDDEN if exc.code.endswith("FORBIDDEN") else HTTPStatus.NOT_FOUND)
        handler.send_header("Content-Type", "application/json")
        handler.send_header("Content-Length", str(len(body)))
        handler.end_headers()
        handler.wfile.write(body)
