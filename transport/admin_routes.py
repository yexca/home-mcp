from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from http import HTTPStatus
from pathlib import Path
from typing import Any

import yaml

from app.webui_config import mask_secret_fields, public_status, read_current_config, write_snapshot
from core.errors import GatewayError
from transport.request_context import CoreServices


WEBUI_ROOT = Path("webui")
WEBUI_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}
MANAGED_AGENT_MARKER = "# Managed by WebUI"
MATRIX_TOOLS = ("matrix_send_text", "matrix_send_image", "matrix_send_audio")
SECRET_ENV_RE = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD)", re.IGNORECASE)


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
                "agents": _agent_status(_current_user_env_values()),
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
            owned_fields = payload.get("owned_fields", {})
            agents = payload.get("agents")
            if agents is not None:
                agent_result = _write_agent_configs(agents)
                owned_fields = dict(owned_fields)
                owned_fields["ENABLED_AGENTS"] = ",".join(agent["name"] for agent in agent_result["agents"])
                owned_fields.update(agent_result.get("owned_fields", {}))
            else:
                agent_result = None
            owned_fields = _preserve_existing_secrets(owned_fields)
            result = write_snapshot(owned_fields)
        except (OSError, ValueError) as exc:
            _json(handler, {"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        _json(handler, {"ok": True, "webui": result, "agents": agent_result})
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
    artifact_root = Path(os.getenv("ARTIFACT_ROOT", "./artifacts"))
    database_path = Path(os.getenv("DATABASE_PATH", "./artifacts/metadata.sqlite3"))
    webui_dir = Path(os.getenv("WEBUI_CONFIG_DIR", "config_webUI"))
    agent_config_dir = Path(os.getenv("AGENT_CONFIG_DIR", "config/agent"))
    return {
        "powershell": _command_status("pwsh", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()")
        or _command_status("powershell", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"),
        "python": _command_status("python", "--version"),
        "dotenv": _path_status(Path(".env")),
        "dotenv_example": _path_status(Path(".env.example")),
        "webui_config_dir": _path_status(webui_dir),
        "webui_current": _path_status(webui_dir / "current.json"),
        "agent_config_dir": _path_status(agent_config_dir),
        "artifact_root": _path_status(artifact_root),
        "database_path": _path_status(database_path),
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


def _path_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
    }


def _agent_status(root_env: dict[str, str]) -> list[dict[str, Any]]:
    agent_names = set(_parse_agents(root_env.get("ENABLED_AGENTS", "")))
    config_dir = Path(os.getenv("AGENT_CONFIG_DIR", "config/agent"))
    env_dir = Path(os.getenv("AGENT_ENV_DIR", "."))
    if config_dir.is_dir():
        for path in config_dir.glob("config.agent.*.yaml"):
            agent_names.add(path.name.removeprefix("config.agent.").removesuffix(".yaml"))
    if env_dir.is_dir():
        for path in env_dir.glob(".env.agent.*"):
            agent_names.add(path.name.removeprefix(".env.agent."))

    agents: list[dict[str, Any]] = []
    enabled = set(_parse_agents(root_env.get("ENABLED_AGENTS", "")))
    for name in sorted(agent_names):
        if not _valid_agent_name(name):
            continue
        config_path = config_dir / f"config.agent.{name}.yaml"
        env_path = env_dir / f".env.agent.{name}"
        fragment = _read_yaml(config_path)
        agent_env = _read_dotenv_values(env_path)
        caller = fragment.get("caller", {}) if isinstance(fragment.get("caller", {}), dict) else {}
        matrix = fragment.get("matrix", {}) if isinstance(fragment.get("matrix", {}), dict) else {}
        high_risk_tools = fragment.get("high_risk_tools", [])
        if not isinstance(high_risk_tools, list):
            high_risk_tools = []
        token_env = str(caller.get("token_env") or _agent_env_name(name, "GATEWAY_TOKEN_", ""))
        access_token_env = str(matrix.get("access_token_env") or _agent_env_name(name, "", "_MATRIX_ACCESS_TOKEN"))
        agents.append(
            {
                "name": name,
                "enabled": name in enabled,
                "config_path": str(config_path),
                "env_path": str(env_path),
                "has_config": config_path.is_file(),
                "has_env": env_path.is_file(),
                "caller": {
                    "role": caller.get("role", "role_play"),
                    "token_env": token_env,
                    "shared_artifact_read": bool(caller.get("shared_artifact_read", False)),
                    "gateway_token_configured": bool(agent_env.get(token_env) or root_env.get(token_env) or os.getenv(token_env)),
                    "gateway_token": mask_secret_fields({token_env: agent_env.get(token_env, root_env.get(token_env, ""))}).get(token_env, ""),
                },
                "matrix": {
                    "enabled": bool(matrix.get("enabled", True)),
                    "account": matrix.get("account", name),
                    "homeserver_env": matrix.get("homeserver_env", "MATRIX_HOMESERVER"),
                    "access_token_env": access_token_env,
                    "access_token_configured": bool(agent_env.get(access_token_env) or root_env.get(access_token_env) or os.getenv(access_token_env)),
                    "access_token": mask_secret_fields({access_token_env: agent_env.get(access_token_env, root_env.get(access_token_env, ""))}).get(
                        access_token_env,
                        "",
                    ),
                },
                "high_risk_tools": [tool for tool in high_risk_tools if isinstance(tool, str)],
            }
        )
    return agents


def _write_agent_configs(raw_agents: Any) -> dict[str, Any]:
    if not isinstance(raw_agents, list):
        raise ValueError("agents must be a list")
    read_config_dir = Path(os.getenv("AGENT_CONFIG_DIR", "config/agent"))
    read_env_dir = Path(os.getenv("AGENT_ENV_DIR", "."))
    config_dir, env_dir, owned_fields = _agent_write_dirs(read_config_dir, read_env_dir)
    root_env = _current_user_env_values()
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_agent in raw_agents:
        agent = _normalize_agent(raw_agent)
        if agent["name"] in seen:
            raise ValueError(f"duplicate agent name: {agent['name']}")
        seen.add(agent["name"])
        _fill_existing_agent_secrets(agent, read_env_dir, root_env)
        normalized.append(agent)

    existing = set()
    if config_dir.is_dir():
        existing |= {path.name.removeprefix("config.agent.").removesuffix(".yaml") for path in config_dir.glob("config.agent.*.yaml")}
    if env_dir.is_dir():
        existing |= {path.name.removeprefix(".env.agent.") for path in env_dir.glob(".env.agent.*")}

    for agent in normalized:
        _write_agent_config(config_dir / f"config.agent.{agent['name']}.yaml", agent)
        _write_agent_env(env_dir / f".env.agent.{agent['name']}", agent)

    disabled = existing - {agent["name"] for agent in normalized}
    for name in disabled:
        _remove_managed_file(config_dir / f"config.agent.{name}.yaml")
        _remove_managed_file(env_dir / f".env.agent.{name}")

    os.environ["AGENT_CONFIG_DIR"] = str(config_dir)
    os.environ["AGENT_ENV_DIR"] = str(env_dir)
    return {
        "agents": [{"name": agent["name"]} for agent in normalized],
        "agent_config_dir": str(config_dir),
        "agent_env_dir": str(env_dir),
        "owned_fields": owned_fields,
    }


def _agent_write_dirs(read_config_dir: Path, read_env_dir: Path) -> tuple[Path, Path, dict[str, str]]:
    if _can_write_dir(read_config_dir) and _can_write_dir(read_env_dir):
        return read_config_dir, read_env_dir, {}
    webui_root = Path(os.getenv("WEBUI_CONFIG_DIR", "config_webUI"))
    config_dir = webui_root / "agent-config"
    env_dir = webui_root / "agent-env"
    config_dir.mkdir(parents=True, exist_ok=True)
    env_dir.mkdir(parents=True, exist_ok=True)
    if not _can_write_dir(config_dir) or not _can_write_dir(env_dir):
        raise OSError(f"WebUI agent config directory is not writable: {webui_root}")
    return config_dir, env_dir, {
        "AGENT_CONFIG_DIR": str(config_dir),
        "AGENT_ENV_DIR": str(env_dir),
    }


def _can_write_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".webui-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


def _fill_existing_agent_secrets(agent: dict[str, Any], env_dir: Path, root_env: dict[str, str]) -> None:
    agent_env = _read_dotenv_values(env_dir / f".env.agent.{agent['name']}")
    gateway_token_env = agent["caller"]["token_env"]
    matrix_token_env = agent["matrix"]["access_token_env"]
    if not agent["caller"]["gateway_token"]:
        agent["caller"]["gateway_token"] = agent_env.get(gateway_token_env, root_env.get(gateway_token_env, ""))
    if not agent["matrix"]["access_token"]:
        agent["matrix"]["access_token"] = agent_env.get(matrix_token_env, root_env.get(matrix_token_env, ""))


def _normalize_agent(raw_agent: Any) -> dict[str, Any]:
    if not isinstance(raw_agent, dict):
        raise ValueError("agent entries must be objects")
    name = str(raw_agent.get("name", "")).strip()
    if not _valid_agent_name(name):
        raise ValueError("agent name may contain only letters, numbers, underscores, and hyphens")
    caller = raw_agent.get("caller", {}) if isinstance(raw_agent.get("caller", {}), dict) else {}
    matrix = raw_agent.get("matrix", {}) if isinstance(raw_agent.get("matrix", {}), dict) else {}
    high_risk_tools = raw_agent.get("high_risk_tools", [])
    if not isinstance(high_risk_tools, list):
        high_risk_tools = []
    tools = [tool for tool in high_risk_tools if tool in MATRIX_TOOLS]
    return {
        "name": name,
        "caller": {
            "role": str(caller.get("role") or "role_play").strip(),
            "token_env": _agent_env_name(name, "GATEWAY_TOKEN_", ""),
            "shared_artifact_read": bool(caller.get("shared_artifact_read", False)),
            "gateway_token": str(caller.get("gateway_token") or "").strip(),
        },
        "matrix": {
            "enabled": bool(matrix.get("enabled", True)),
            "account": str(matrix.get("account") or name).strip(),
            "homeserver_env": "MATRIX_HOMESERVER",
            "access_token_env": _agent_env_name(name, "", "_MATRIX_ACCESS_TOKEN"),
            "access_token": str(matrix.get("access_token") or "").strip(),
        },
        "high_risk_tools": tools,
    }


def _write_agent_config(path: Path, agent: dict[str, Any]) -> None:
    content = {
        "caller": {
            "role": agent["caller"]["role"],
            "token_env": agent["caller"]["token_env"],
            "shared_artifact_read": agent["caller"]["shared_artifact_read"],
        },
        "matrix": {
            "enabled": agent["matrix"]["enabled"],
            "account": agent["matrix"]["account"],
            "homeserver_env": agent["matrix"]["homeserver_env"],
            "access_token_env": agent["matrix"]["access_token_env"],
        },
        "high_risk_tools": agent["high_risk_tools"],
    }
    path.write_text(MANAGED_AGENT_MARKER + "\n" + yaml.safe_dump(content, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_agent_env(path: Path, agent: dict[str, Any]) -> None:
    existing = _read_dotenv_values(path)
    updates = {
        agent["caller"]["token_env"]: agent["caller"]["gateway_token"] or existing.get(agent["caller"]["token_env"], ""),
        agent["matrix"]["access_token_env"]: agent["matrix"]["access_token"] or existing.get(agent["matrix"]["access_token_env"], ""),
    }
    lines = [MANAGED_AGENT_MARKER, ""]
    for key, value in updates.items():
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _remove_managed_file(path: Path) -> None:
    if not path.is_file():
        return
    first_line = path.read_text(encoding="utf-8").splitlines()[0:1]
    if first_line and first_line[0] in {MANAGED_AGENT_MARKER, "# Managed by tools/apply_agent.ps1"}:
        path.unlink()


def _parse_agents(value: str) -> list[str]:
    agents: list[str] = []
    seen: set[str] = set()
    for raw_name in value.replace(";", ",").split(","):
        name = raw_name.strip()
        if name and _valid_agent_name(name) and name not in seen:
            agents.append(name)
            seen.add(name)
    return agents


def _valid_agent_name(name: str) -> bool:
    return bool(name) and all(char.isalnum() or char in {"_", "-"} for char in name)


def _agent_env_name(agent_name: str, prefix: str, suffix: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in agent_name).upper()
    return f"{prefix}{normalized}{suffix}"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _preserve_existing_secrets(owned_fields: Any) -> dict[str, Any]:
    if not isinstance(owned_fields, dict):
        return owned_fields
    current = read_current_config().owned_fields
    merged = dict(owned_fields)
    for key, value in current.items():
        if not SECRET_ENV_RE.search(key):
            continue
        incoming = str(merged.get(key, "")).strip()
        masked = str(mask_secret_fields({key: value}).get(key, ""))
        if key not in merged or not incoming or incoming == masked:
            merged[key] = value
    return merged
