from __future__ import annotations

import json
import re
import shutil
import subprocess
from copy import deepcopy
from http import HTTPStatus
from pathlib import Path
from typing import Any, Callable

import yaml

from core.errors import GatewayError
from transport.request_context import CoreServices


WEBUI_ROOT = Path("webui")
WEBUI_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
}
USER_CONFIG_PATH = Path("config/config.yaml")
DEFAULT_AGENT_CONFIG_DIR = Path("config/agent")
MANAGED_AGENT_MARKER = "# Managed by WebUI"
MATRIX_TOOLS = ("matrix_send_text", "matrix_send_image", "matrix_send_audio")
SECRET_ENV_RE = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD)", re.IGNORECASE)


def _number(value: str) -> int | float:
    stripped = value.strip()
    if not stripped:
        return ""
    parsed = float(stripped)
    return int(parsed) if parsed.is_integer() else parsed


def _string(value: str) -> str:
    return value.strip()


def _string_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\n,;]", value) if item.strip()]


def _bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"boolean config value is invalid: {value}")


def mask_secret_fields(values: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in values.items():
        if SECRET_ENV_RE.search(str(key)):
            masked[key] = _mask_value(str(value))
        else:
            masked[key] = value
    return masked


def _mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "********"
    return f"{value[:3]}...{value[-3:]}"


FIELD_PATHS: dict[str, tuple[tuple[str, ...], Callable[[str], Any]]] = {
    "ARTIFACT_PUBLIC_BASE_URL": (("artifacts", "public_base_url"), _string),
    "IMAGE_MODULE_ENABLED": (("modules", "image", "enabled"), _bool),
    "LOCAL_IMAGE_MODULE_ENABLED": (("modules", "localimage", "enabled"), _bool),
    "TTS_MODULE_ENABLED": (("modules", "tts", "enabled"), _bool),
    "MATRIX_MODULE_ENABLED": (("modules", "matrix", "enabled"), _bool),
    "PRINTER_MODULE_ENABLED": (("modules", "printer", "enabled"), _bool),
    "IMAGE_API_BASE_URL": (("modules", "image", "openai_compatible", "base_url"), _string),
    "IMAGE_API_MODEL": (("modules", "image", "openai_compatible", "model"), _string),
    "IMAGE_API_KEY": (("modules", "image", "openai_compatible", "api_key"), _string),
    "IMAGE_TOTAL_TIMEOUT_SECONDS": (("modules", "image", "total_timeout_seconds"), _number),
    "IMAGE_PROVIDER_TIMEOUT_SECONDS": (("modules", "image", "openai_compatible", "timeout_seconds"), _number),
    "IMAGE_MAX_DOWNLOAD_BYTES": (("modules", "image", "max_download_bytes"), _number),
    "LOCAL_IMAGE_COMFYUI_BASE_URL": (("modules", "localimage", "comfyui", "base_url"), _string),
    "LOCAL_IMAGE_COMFYUI_ALLOWED_HOST": (("modules", "localimage", "comfyui", "allowed_hosts", "0"), _string),
    "LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH": (("modules", "localimage", "comfyui", "workflow_path"), _string),
    "LOCAL_IMAGE_DEFAULT_SIZE": (("modules", "localimage", "default_size"), _string),
    "LOCAL_IMAGE_DEFAULT_QUALITY": (("modules", "localimage", "default_quality"), _string),
    "LOCAL_IMAGE_DEFAULT_STYLE": (("modules", "localimage", "default_style"), _string),
    "LOCAL_IMAGE_DEFAULT_OUTPUT_FORMAT": (("modules", "localimage", "default_output_format"), _string),
    "LOCAL_IMAGE_COMFYUI_CHECKPOINT": (("modules", "localimage", "comfyui", "checkpoint"), _string),
    "LOCAL_IMAGE_COMFYUI_UNET_NAME": (("modules", "localimage", "comfyui", "unet_name"), _string),
    "LOCAL_IMAGE_COMFYUI_CLIP_NAME": (("modules", "localimage", "comfyui", "clip_name"), _string),
    "LOCAL_IMAGE_COMFYUI_VAE_NAME": (("modules", "localimage", "comfyui", "vae_name"), _string),
    "LOCAL_IMAGE_COMFYUI_TIMEOUT_SECONDS": (("modules", "localimage", "comfyui", "timeout_seconds"), _number),
    "LOCAL_IMAGE_COMFYUI_POLL_INTERVAL_SECONDS": (("modules", "localimage", "comfyui", "poll_interval_seconds"), _number),
    "LOCAL_IMAGE_COMFYUI_MAX_WAIT_SECONDS": (("modules", "localimage", "comfyui", "max_wait_seconds"), _number),
    "TTS_LOCAL_HTTP_URL": (("modules", "tts", "local_http", "url"), _string),
    "TTS_API_KEY": (("modules", "tts", "local_http", "api_key"), _string),
    "TTS_TOTAL_TIMEOUT_SECONDS": (("modules", "tts", "total_timeout_seconds"), _number),
    "TTS_PROVIDER_TIMEOUT_SECONDS": (("modules", "tts", "local_http", "timeout_seconds"), _number),
    "MATRIX_HOMESERVER": (("modules", "matrix", "homeserver"), _string),
    "MATRIX_TIMEOUT_SECONDS": (("modules", "matrix", "timeout_seconds"), _number),
    "MATRIX_MAX_TEXT_CHARS": (("modules", "matrix", "max_text_chars"), _number),
    "PRINTER_BRIDGE_URL": (("modules", "printer", "bridge_http", "url"), _string),
    "PRINTER_BRIDGE_API_KEY": (("modules", "printer", "bridge_http", "api_key"), _string),
    "PRINTER_ALLOWED_PRINTERS": (("modules", "printer", "allowed_printers"), _string_list),
    "PRINTER_MAX_COPIES": (("modules", "printer", "max_copies"), _number),
    "PRINTER_MAX_FILE_BYTES": (("modules", "printer", "max_file_bytes"), _number),
    "PRINTER_BRIDGE_TIMEOUT_SECONDS": (("modules", "printer", "bridge_http", "timeout_seconds"), _number),
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
        status_config = _status_config(services.config.raw)
        config_values = _config_field_values(status_config)
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
                "webui": {
                    "enabled": True,
                    "active_snapshot": str(USER_CONFIG_PATH),
                    "path": str(USER_CONFIG_PATH),
                    "owned_fields": {},
                },
                "local_env": mask_secret_fields(config_values),
                "agents": _agent_status(status_config),
                "environment": _environment_status(status_config),
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
            status_config = _status_config(services.config.raw)
            owned_fields = _preserve_existing_secrets(payload.get("owned_fields", {}), status_config)
            agents = payload.get("agents")
            agent_result = _prepare_agent_configs(agents, status_config) if agents is not None else None
            candidate_config = _candidate_save_config(status_config, owned_fields, agent_result)
            _validate_enabled_module_requirements(candidate_config)
            result = _write_user_config_fields(owned_fields)
            if agents is not None:
                _write_prepared_agent_configs(agent_result)
                _write_enabled_agents([agent["name"] for agent in agent_result["agents"] if agent.get("enabled")])
        except (OSError, ValueError) as exc:
            _json(handler, {"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        _json(handler, {"ok": True, "webui": result, "agents": _public_agent_result(agent_result)})
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


def _config_field_values(config: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for name, (path, _parser) in FIELD_PATHS.items():
        value = _get_nested(config, path)
        if isinstance(value, bool):
            values[name] = "true" if value else "false"
        elif isinstance(value, list):
            values[name] = "\n".join(str(item) for item in value)
        elif value is None:
            values[name] = ""
        else:
            values[name] = str(value)
    return values


def _status_config(runtime_config: dict[str, Any]) -> dict[str, Any]:
    user_config = _read_yaml(USER_CONFIG_PATH)
    module_enabled_overrides = _module_enabled_values(user_config)
    config = _deep_merge(runtime_config, user_config)
    agents_config = config.get("agents", {})
    if isinstance(agents_config, dict) and "enabled" in agents_config:
        enabled = set(_enabled_agents(config))
        config_dir = _agent_config_dir(config)
        for agent_name in _enabled_agents(config):
            fragment = _read_yaml(config_dir / f"config.agent.{agent_name}.yaml")
            if fragment:
                _merge_agent_fragment(config, agent_name, fragment)
        _prune_disabled_agent_config(config, _configured_agent_names(config) - enabled)
    _restore_module_enabled_values(config, module_enabled_overrides)
    return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _environment_status(config: dict[str, Any]) -> dict[str, Any]:
    agent_config_dir = _agent_config_dir(config)
    return {
        "python": _command_status("python", "--version"),
        "config_main": _path_status(Path("config/config.main.yaml")),
        "config_user": _path_status(USER_CONFIG_PATH),
        "agent_config_dir": _path_status(agent_config_dir),
        "artifact_root": _path_status(Path(str(config.get("artifacts", {}).get("root", "./artifacts")))),
        "database_path": _path_status(Path(str(config.get("database", {}).get("path", "./artifacts/metadata.sqlite3")))),
    }


def _module_enabled_values(config: dict[str, Any]) -> dict[str, bool]:
    modules = config.get("modules", {})
    if not isinstance(modules, dict):
        return {}
    values: dict[str, bool] = {}
    for module_name, module_config in modules.items():
        if isinstance(module_config, dict) and "enabled" in module_config:
            values[str(module_name)] = bool(module_config["enabled"])
    return values


def _restore_module_enabled_values(config: dict[str, Any], values: dict[str, bool]) -> None:
    modules = config.setdefault("modules", {})
    for module_name, enabled in values.items():
        modules.setdefault(module_name, {})["enabled"] = enabled


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


def _agent_status(config: dict[str, Any]) -> list[dict[str, Any]]:
    agent_names = set(_enabled_agents(config))
    config_dir = _agent_config_dir(config)
    if config_dir.is_dir():
        for path in config_dir.glob("config.agent.*.yaml"):
            agent_names.add(path.name.removeprefix("config.agent.").removesuffix(".yaml"))

    agents: list[dict[str, Any]] = []
    enabled = set(_enabled_agents(config))
    for name in sorted(agent_names):
        if not _valid_agent_name(name):
            continue
        config_path = config_dir / f"config.agent.{name}.yaml"
        fragment = _read_yaml(config_path)
        caller = fragment.get("caller", {}) if isinstance(fragment.get("caller", {}), dict) else {}
        matrix = fragment.get("matrix", {}) if isinstance(fragment.get("matrix", {}), dict) else {}
        high_risk_tools = fragment.get("high_risk_tools", [])
        if not isinstance(high_risk_tools, list):
            high_risk_tools = []
        token = str(caller.get("token") or "")
        access_token = str(matrix.get("access_token") or "")
        agents.append(
            {
                "name": name,
                "enabled": name in enabled,
                "config_path": str(config_path),
                "has_config": config_path.is_file(),
                "caller": {
                    "role": caller.get("role", "role_play"),
                    "shared_artifact_read": bool(caller.get("shared_artifact_read", False)),
                    "gateway_token_configured": bool(token),
                    "gateway_token": mask_secret_fields({"gateway_token": token}).get("gateway_token", ""),
                },
                "matrix": {
                    "enabled": bool(matrix.get("enabled", True)),
                    "account": matrix.get("account", name),
                    "homeserver": matrix.get("homeserver", config.get("modules", {}).get("matrix", {}).get("homeserver", "")),
                    "access_token_configured": bool(access_token),
                    "access_token": mask_secret_fields({"access_token": access_token}).get("access_token", ""),
                },
                "high_risk_tools": [tool for tool in high_risk_tools if isinstance(tool, str)],
            }
        )
    return agents


def _write_user_config_fields(raw_fields: Any) -> dict[str, Any]:
    if not isinstance(raw_fields, dict):
        raise ValueError("owned_fields must be an object")
    config = _read_yaml(USER_CONFIG_PATH)
    _apply_config_fields(config, raw_fields)
    _write_yaml(USER_CONFIG_PATH, config)
    return {
        "path": str(USER_CONFIG_PATH),
        "owned_fields": mask_secret_fields(_config_field_values(config)),
    }


def _apply_config_fields(config: dict[str, Any], raw_fields: dict[str, Any]) -> None:
    for name, raw_value in raw_fields.items():
        if name not in FIELD_PATHS:
            continue
        path, parser = FIELD_PATHS[name]
        value = parser(str(raw_value))
        _set_nested(config, path, value)


def _write_enabled_agents(agent_names: list[str]) -> None:
    config = _read_yaml(USER_CONFIG_PATH)
    config.setdefault("agents", {})["enabled"] = agent_names
    config.setdefault("agents", {})["config_dir"] = str(DEFAULT_AGENT_CONFIG_DIR).replace("\\", "/")
    _write_yaml(USER_CONFIG_PATH, config)


def _write_agent_configs(raw_agents: Any, config: dict[str, Any]) -> dict[str, Any]:
    prepared = _prepare_agent_configs(raw_agents, config)
    _write_prepared_agent_configs(prepared)
    return _public_agent_result(prepared) or {"agents": [], "agent_config_dir": str(_agent_config_dir(config))}


def _prepare_agent_configs(raw_agents: Any, config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_agents, list):
        raise ValueError("agents must be a list")
    config_dir = _agent_config_dir(config)
    if not _can_write_dir(config_dir):
        raise OSError(f"agent config directory is not writable: {config_dir}")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_agent in raw_agents:
        agent = _normalize_agent(raw_agent)
        if agent["name"] in seen:
            raise ValueError(f"duplicate agent name: {agent['name']}")
        seen.add(agent["name"])
        _fill_existing_agent_secrets(agent, config_dir)
        if agent["enabled"]:
            _validate_enabled_agent(agent)
        normalized.append(agent)

    return {
        "agents": [{"name": agent["name"], "enabled": agent["enabled"]} for agent in normalized],
        "agent_config_dir": str(config_dir),
        "_normalized": normalized,
    }


def _validate_enabled_agent(agent: dict[str, Any]) -> None:
    if not agent["caller"]["gateway_token"]:
        raise ValueError(f"Gateway Token is required when agent is enabled: {agent['name']}")
    if not agent["matrix"]["access_token"]:
        raise ValueError(f"Matrix Access Token is required when agent is enabled: {agent['name']}")
    if not agent["matrix"]["account"]:
        raise ValueError(f"Matrix Account is required when agent is enabled: {agent['name']}")


def _public_agent_result(prepared: dict[str, Any] | None) -> dict[str, Any] | None:
    if prepared is None:
        return None
    return {
        "agents": prepared.get("agents", []),
        "agent_config_dir": prepared.get("agent_config_dir", str(DEFAULT_AGENT_CONFIG_DIR)),
    }


def _write_prepared_agent_configs(prepared: dict[str, Any] | None) -> None:
    if not prepared:
        return
    config_dir = Path(str(prepared["agent_config_dir"]))
    normalized = prepared.get("_normalized", [])
    existing = set()
    if config_dir.is_dir():
        existing |= {path.name.removeprefix("config.agent.").removesuffix(".yaml") for path in config_dir.glob("config.agent.*.yaml")}

    for agent in normalized:
        _write_agent_config(config_dir / f"config.agent.{agent['name']}.yaml", agent)

    disabled = existing - {agent["name"] for agent in normalized}
    for name in disabled:
        _remove_managed_file(config_dir / f"config.agent.{name}.yaml")


def _can_write_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".webui-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError:
        return False
    return True


def _fill_existing_agent_secrets(agent: dict[str, Any], config_dir: Path) -> None:
    existing = _read_yaml(config_dir / f"config.agent.{agent['name']}.yaml")
    caller = existing.get("caller", {}) if isinstance(existing.get("caller", {}), dict) else {}
    matrix = existing.get("matrix", {}) if isinstance(existing.get("matrix", {}), dict) else {}
    if not agent["caller"]["gateway_token"]:
        agent["caller"]["gateway_token"] = str(caller.get("token") or "")
    if not agent["matrix"]["access_token"]:
        agent["matrix"]["access_token"] = str(matrix.get("access_token") or "")


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
        "enabled": bool(raw_agent.get("enabled", True)),
        "caller": {
            "role": str(caller.get("role") or "role_play").strip(),
            "shared_artifact_read": bool(caller.get("shared_artifact_read", False)),
            "gateway_token": str(caller.get("gateway_token") or "").strip(),
        },
        "matrix": {
            "enabled": bool(matrix.get("enabled", True)),
            "account": str(matrix.get("account") or name).strip(),
            "homeserver": str(matrix.get("homeserver") or "").strip(),
            "access_token": str(matrix.get("access_token") or "").strip(),
        },
        "high_risk_tools": tools,
    }


def _write_agent_config(path: Path, agent: dict[str, Any]) -> None:
    content = _agent_config_content(agent)
    path.write_text(MANAGED_AGENT_MARKER + "\n" + yaml.safe_dump(content, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _agent_config_content(agent: dict[str, Any]) -> dict[str, Any]:
    content = {
        "caller": {
            "role": agent["caller"]["role"],
            "token": agent["caller"]["gateway_token"],
            "shared_artifact_read": agent["caller"]["shared_artifact_read"],
        },
        "matrix": {
            "enabled": agent["matrix"]["enabled"],
            "account": agent["matrix"]["account"],
            "access_token": agent["matrix"]["access_token"],
        },
        "high_risk_tools": agent["high_risk_tools"],
    }
    if agent["matrix"]["homeserver"]:
        content["matrix"]["homeserver"] = agent["matrix"]["homeserver"]
    return content


def _candidate_save_config(
    status_config: dict[str, Any],
    owned_fields: dict[str, Any],
    agent_result: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate = deepcopy(status_config)
    _apply_config_fields(candidate, owned_fields)
    if agent_result is not None:
        enabled_agent_names = [agent["name"] for agent in agent_result["agents"] if agent.get("enabled")]
        candidate.setdefault("agents", {})["enabled"] = enabled_agent_names
        candidate.setdefault("agents", {})["config_dir"] = str(DEFAULT_AGENT_CONFIG_DIR).replace("\\", "/")
        _prune_disabled_agent_config(candidate, _configured_agent_names(candidate) - set(enabled_agent_names))
        for agent in agent_result.get("_normalized", []):
            if not agent["enabled"]:
                continue
            _merge_agent_fragment(candidate, agent["name"], _agent_config_content(agent))
    return candidate


def _validate_enabled_module_requirements(config: dict[str, Any]) -> None:
    modules = config.get("modules", {})
    if not isinstance(modules, dict):
        return
    _require_image_config(modules.get("image", {}))
    _require_localimage_config(modules.get("localimage", {}))
    _require_tts_config(modules.get("tts", {}))
    _require_matrix_config(modules.get("matrix", {}))
    _require_printer_config(modules.get("printer", {}))


def _module_enabled(module_config: Any) -> bool:
    return isinstance(module_config, dict) and bool(module_config.get("enabled", False))


def _require_text(config: dict[str, Any], path: tuple[str, ...], label: str) -> None:
    value = _get_nested(config, path)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required when its module is enabled")


def _require_list(config: dict[str, Any], path: tuple[str, ...], label: str) -> None:
    value = _get_nested(config, path)
    if not isinstance(value, list) or not any(str(item).strip() for item in value):
        raise ValueError(f"{label} is required when its module is enabled")


def _require_image_config(image_config: Any) -> None:
    if not _module_enabled(image_config):
        return
    _require_text(image_config, ("openai_compatible", "base_url"), "IMAGE_API_BASE_URL")
    _require_text(image_config, ("openai_compatible", "model"), "IMAGE_API_MODEL")
    _require_text(image_config, ("openai_compatible", "api_key"), "IMAGE_API_KEY")


def _require_localimage_config(localimage_config: Any) -> None:
    if not _module_enabled(localimage_config):
        return
    _require_text(localimage_config, ("comfyui", "base_url"), "LOCAL_IMAGE_COMFYUI_BASE_URL")
    _require_list(localimage_config, ("comfyui", "allowed_hosts"), "LOCAL_IMAGE_COMFYUI_ALLOWED_HOST")
    _require_text(localimage_config, ("comfyui", "workflow_path"), "LOCAL_IMAGE_COMFYUI_WORKFLOW_PATH")
    _require_text(localimage_config, ("default_size",), "LOCAL_IMAGE_DEFAULT_SIZE")
    _require_text(localimage_config, ("default_quality",), "LOCAL_IMAGE_DEFAULT_QUALITY")
    _require_text(localimage_config, ("default_style",), "LOCAL_IMAGE_DEFAULT_STYLE")
    _require_text(localimage_config, ("default_output_format",), "LOCAL_IMAGE_DEFAULT_OUTPUT_FORMAT")


def _require_tts_config(tts_config: Any) -> None:
    if not _module_enabled(tts_config):
        return
    if tts_config.get("provider", "local_http") == "local_http":
        _require_text(tts_config, ("local_http", "url"), "TTS_LOCAL_HTTP_URL")


def _require_matrix_config(matrix_config: Any) -> None:
    if not _module_enabled(matrix_config):
        return
    _require_text(matrix_config, ("homeserver",), "MATRIX_HOMESERVER")
    accounts = matrix_config.get("accounts", {})
    account_tokens = []
    if isinstance(accounts, dict):
        account_tokens = [
            spec.get("access_token")
            for spec in accounts.values()
            if isinstance(spec, dict) and str(spec.get("access_token") or "").strip()
        ]
    if not str(matrix_config.get("access_token") or "").strip() and not account_tokens:
        raise ValueError("MATRIX access token is required when the Matrix module is enabled")


def _require_printer_config(printer_config: Any) -> None:
    if not _module_enabled(printer_config):
        return
    _require_text(printer_config, ("bridge_http", "url"), "PRINTER_BRIDGE_URL")
    _require_list(printer_config, ("allowed_printers",), "allowed_printers")


def _remove_managed_file(path: Path) -> None:
    if not path.is_file():
        return
    first_line = path.read_text(encoding="utf-8").splitlines()[0:1]
    if first_line and first_line[0] in {MANAGED_AGENT_MARKER, "# Managed by tools/apply_agent.ps1"}:
        path.unlink()


def _preserve_existing_secrets(owned_fields: Any, config: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(owned_fields, dict):
        return {}
    current_values = _config_field_values(config)
    merged = dict(owned_fields)
    masked_values = mask_secret_fields(current_values)
    for key, value in current_values.items():
        if not SECRET_ENV_RE.search(key):
            continue
        incoming = str(merged.get(key, "")).strip()
        if key not in merged or not incoming or incoming == str(masked_values.get(key, "")):
            merged[key] = value
    return merged


def _enabled_agents(config: dict[str, Any]) -> list[str]:
    agents_config = config.get("agents", {})
    if not isinstance(agents_config, dict):
        return []
    raw = agents_config.get("enabled", [])
    if isinstance(raw, str):
        items = raw.replace(";", ",").split(",")
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    agents: list[str] = []
    seen: set[str] = set()
    for item in items:
        name = str(item).strip()
        if name and _valid_agent_name(name) and name not in seen:
            agents.append(name)
            seen.add(name)
    return agents


def _agent_config_dir(config: dict[str, Any]) -> Path:
    agents_config = config.get("agents", {})
    if isinstance(agents_config, dict) and agents_config.get("config_dir"):
        return Path(str(agents_config["config_dir"]))
    return DEFAULT_AGENT_CONFIG_DIR


def _merge_agent_fragment(config: dict[str, Any], agent_name: str, fragment: dict[str, Any]) -> None:
    caller = fragment.get("caller", {}) if isinstance(fragment.get("caller", {}), dict) else {}
    config.setdefault("callers", {})[agent_name] = {
        "role": caller.get("role", "role_play"),
        "token": caller.get("token", ""),
        "shared_artifact_read": bool(caller.get("shared_artifact_read", False)),
    }
    high_risk_tools = fragment.get("high_risk_tools", [])
    if isinstance(high_risk_tools, list) and high_risk_tools:
        config.setdefault("policy", {}).setdefault("high_risk_allowed_callers", {})[agent_name] = [
            tool for tool in high_risk_tools if isinstance(tool, str)
        ]
    matrix = fragment.get("matrix", {}) if isinstance(fragment.get("matrix", {}), dict) else {}
    if bool(matrix.get("enabled", False)):
        matrix_config = config.setdefault("modules", {}).setdefault("matrix", {})
        matrix_config["enabled"] = True
        account = str(matrix.get("account") or agent_name)
        matrix_config.setdefault("caller_accounts", {})[agent_name] = account
        account_config = matrix_config.setdefault("accounts", {}).setdefault(account, {})
        if matrix.get("homeserver"):
            account_config["homeserver"] = matrix["homeserver"]
        account_config["access_token"] = matrix.get("access_token", "")


def _configured_agent_names(config: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    callers = config.get("callers", {})
    if isinstance(callers, dict):
        names |= {name for name in callers if _is_agent_managed_name(name)}
    high_risk = config.get("policy", {}).get("high_risk_allowed_callers", {}) if isinstance(config.get("policy"), dict) else {}
    if isinstance(high_risk, dict):
        names |= {name for name in high_risk if _is_agent_managed_name(name)}
    matrix = config.get("modules", {}).get("matrix", {}) if isinstance(config.get("modules"), dict) else {}
    if isinstance(matrix, dict):
        caller_accounts = matrix.get("caller_accounts", {})
        if isinstance(caller_accounts, dict):
            names |= {name for name in caller_accounts if _is_agent_managed_name(name)}
        accounts = matrix.get("accounts", {})
        if isinstance(accounts, dict):
            names |= {name for name in accounts if _is_agent_managed_name(name)}
    return names


def _prune_disabled_agent_config(config: dict[str, Any], disabled_agents: set[str]) -> None:
    callers = config.get("callers", {})
    if isinstance(callers, dict):
        for agent_name in disabled_agents:
            callers.pop(agent_name, None)
    policy = config.get("policy", {})
    if isinstance(policy, dict):
        high_risk = policy.get("high_risk_allowed_callers", {})
        if isinstance(high_risk, dict):
            for agent_name in disabled_agents:
                high_risk.pop(agent_name, None)
    matrix = config.get("modules", {}).get("matrix", {}) if isinstance(config.get("modules"), dict) else {}
    if isinstance(matrix, dict):
        caller_accounts = matrix.get("caller_accounts", {})
        if isinstance(caller_accounts, dict):
            for agent_name in disabled_agents:
                caller_accounts.pop(agent_name, None)
        accounts = matrix.get("accounts", {})
        if isinstance(accounts, dict):
            for agent_name in disabled_agents:
                accounts.pop(agent_name, None)


def _is_agent_managed_name(name: Any) -> bool:
    return isinstance(name, str) and name not in {"host_assistant", "role_default"}


def _valid_agent_name(name: str) -> bool:
    return bool(name) and all(char.isalnum() or char in {"_", "-"} for char in name)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return loaded if isinstance(loaded, dict) else {}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _get_nested(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if isinstance(current, dict):
            current = current.get(key)
            continue
        if isinstance(current, list) and key.isdigit():
            index = int(key)
            current = current[index] if index < len(current) else None
            continue
        return None
    return current


def _set_nested(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current: Any = data
    for index, key in enumerate(path[:-1]):
        next_key = path[index + 1]
        if next_key.isdigit():
            container = current.setdefault(key, []) if isinstance(current, dict) else current[int(key)]
            if not isinstance(container, list):
                container = []
                current[key] = container
            current = container
            continue
        if isinstance(current, list) and key.isdigit():
            list_index = int(key)
            while len(current) <= list_index:
                current.append({})
            if not isinstance(current[list_index], dict):
                current[list_index] = {}
            current = current[list_index]
            continue
        next_value = current.setdefault(key, {})
        if not isinstance(next_value, dict):
            next_value = {}
            current[key] = next_value
        current = next_value
    last = path[-1]
    if isinstance(current, list) and last.isdigit():
        list_index = int(last)
        while len(current) <= list_index:
            current.append("")
        current[list_index] = value
    else:
        current[last] = value
