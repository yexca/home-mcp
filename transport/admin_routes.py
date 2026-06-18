from __future__ import annotations

import json
import os
import shutil
import subprocess
from http import HTTPStatus
from pathlib import Path
from typing import Any

from app.webui_config import mask_secret_fields, public_status, read_current_config, write_snapshot
from core.errors import GatewayError
from transport.request_context import CoreServices


WEBUI_ROOT = Path("webui")
WEBUI_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}


def serve_webui(handler, path: str) -> None:
    relative = path.removeprefix("/webui").strip("/")
    if not relative:
        relative = "index.html"
    target = (WEBUI_ROOT / relative).resolve()
    try:
        target.relative_to(WEBUI_ROOT.resolve())
    except ValueError:
        _json(handler, {"ok": False, "error": "invalid path"}, status=HTTPStatus.BAD_REQUEST)
        return
    if not target.is_file():
        _json(handler, {"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
        return
    body = target.read_bytes()
    handler.send_response(HTTPStatus.OK)
    handler.send_header("Content-Type", WEBUI_MIME_TYPES.get(target.suffix.lower(), "application/octet-stream"))
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store" if target.name == "index.html" else "private, max-age=60")
    handler.end_headers()
    handler.wfile.write(body)


def handle_admin_get(handler, services: CoreServices, path: str) -> None:
    if not _authorize(handler, services):
        return
    if path == "/admin/api/status":
        webui_config = read_current_config()
        _json(
            handler,
            {
                "ok": True,
                "server": {
                    "name": services.config.server.get("name"),
                    "version": services.config.server.get("version"),
                    "host": services.config.server.get("host"),
                    "port": services.config.server.get("port"),
                },
                "modules": services.config.enabled_modules(),
                "webui": public_status(webui_config),
                "local_env": mask_secret_fields(_current_user_env_values()),
                "environment": _environment_status(),
            },
        )
        return
    _json(handler, {"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)


def handle_admin_post(handler, services: CoreServices, path: str) -> None:
    if not _authorize(handler, services):
        return
    if path == "/admin/api/config":
        try:
            payload = _read_json_body(handler)
            result = write_snapshot(payload.get("owned_fields", {}))
        except ValueError as exc:
            _json(handler, {"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        _json(handler, {"ok": True, "webui": result})
        return
    _json(handler, {"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)


def _authorize(handler, services: CoreServices) -> bool:
    authorization = handler.headers.get("Authorization")
    if not authorization:
        _json(handler, {"ok": False, "error": "admin token required"}, status=HTTPStatus.UNAUTHORIZED)
        return False
    try:
        caller = services.policy.resolve_caller(authorization, remote_addr=handler.client_address[0])
    except GatewayError:
        _json(handler, {"ok": False, "error": "invalid admin token"}, status=HTTPStatus.FORBIDDEN)
        return False
    if caller.role != "admin":
        _json(handler, {"ok": False, "error": "admin role required"}, status=HTTPStatus.FORBIDDEN)
        return False
    return True


def _read_json_body(handler) -> dict[str, Any]:
    body = handler.rfile.read(int(handler.headers.get("Content-Length", "0") or "0"))
    loaded = json.loads(body.decode("utf-8") or "{}")
    if not isinstance(loaded, dict):
        raise ValueError("request body must be a JSON object")
    return loaded


def _json(handler, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _current_user_env_values() -> dict[str, str]:
    values: dict[str, str] = {}
    values.update(_read_dotenv_values(Path(".env.example")))
    for env_path in (Path(".env"), Path(os.getenv("AGENT_ENV_DIR", "")) / ".env"):
        values.update(_read_dotenv_values(env_path))
    for key in list(values):
        if key in os.environ:
            values[key] = os.environ[key]
    return values


def _read_dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def _environment_status() -> dict[str, Any]:
    return {
        "inside_container": Path("/.dockerenv").exists(),
        "docker_cli": _command_status("docker", "--version"),
        "docker_compose": _command_status("docker", "compose", "version"),
        "powershell": _command_status("pwsh", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()")
        or _command_status("powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"),
    }


def _command_status(*args: str) -> dict[str, Any] | None:
    if shutil.which(args[0]) is None:
        return None
    try:
        completed = subprocess.run(args, check=False, capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}
    output = (completed.stdout or completed.stderr).strip()
    return {
        "available": completed.returncode == 0,
        "output": output[:300],
    }
