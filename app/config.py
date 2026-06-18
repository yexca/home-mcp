from __future__ import annotations

import os
import re
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

import yaml

from app.webui_config import read_current_config

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

def _number_env_value(value: str) -> int | float:
    stripped = value.strip()
    if not stripped:
        raise ValueError("environment override value must not be empty")
    try:
        number = float(stripped)
    except ValueError as exc:
        raise ValueError(f"environment override value must be numeric: {stripped}") from exc
    if number.is_integer():
        return int(number)
    return number


_MODULE_ENABLED_ENV_VARS = {
    "image": "IMAGE_MODULE_ENABLED",
    "localimage": "LOCAL_IMAGE_MODULE_ENABLED",
    "tts": "TTS_MODULE_ENABLED",
    "matrix": "MATRIX_MODULE_ENABLED",
    "printer": "PRINTER_MODULE_ENABLED",
}

_ENV_VALUE_OVERRIDES: tuple[tuple[str, tuple[str, ...], Callable[[str], Any]], ...] = (
    ("SYNC_TOOL_TIMEOUT_SECONDS", ("limits", "sync_tool_timeout_seconds"), _number_env_value),
    ("IMAGE_TOTAL_TIMEOUT_SECONDS", ("modules", "image", "total_timeout_seconds"), _number_env_value),
    ("IMAGE_STALE_JOB_GRACE_SECONDS", ("modules", "image", "stale_job_grace_seconds"), _number_env_value),
    ("IMAGE_PROVIDER_TIMEOUT_SECONDS", ("modules", "image", "openai_compatible", "timeout_seconds"), _number_env_value),
    (
        "LOCAL_IMAGE_TOTAL_TIMEOUT_SECONDS",
        ("modules", "localimage", "total_timeout_seconds"),
        _number_env_value,
    ),
    (
        "LOCAL_IMAGE_STALE_JOB_GRACE_SECONDS",
        ("modules", "localimage", "stale_job_grace_seconds"),
        _number_env_value,
    ),
    (
        "LOCAL_IMAGE_COMFYUI_TIMEOUT_SECONDS",
        ("modules", "localimage", "comfyui", "timeout_seconds"),
        _number_env_value,
    ),
    (
        "LOCAL_IMAGE_COMFYUI_MAX_WAIT_SECONDS",
        ("modules", "localimage", "comfyui", "max_wait_seconds"),
        _number_env_value,
    ),
    (
        "LOCAL_IMAGE_COMFYUI_POLL_INTERVAL_SECONDS",
        ("modules", "localimage", "comfyui", "poll_interval_seconds"),
        _number_env_value,
    ),
    ("TTS_TOTAL_TIMEOUT_SECONDS", ("modules", "tts", "total_timeout_seconds"), _number_env_value),
    ("TTS_STALE_JOB_GRACE_SECONDS", ("modules", "tts", "stale_job_grace_seconds"), _number_env_value),
    ("TTS_PROVIDER_TIMEOUT_SECONDS", ("modules", "tts", "local_http", "timeout_seconds"), _number_env_value),
    ("MATRIX_TIMEOUT_SECONDS", ("modules", "matrix", "timeout_seconds"), _number_env_value),
    ("PRINTER_BRIDGE_TIMEOUT_SECONDS", ("modules", "printer", "bridge_http", "timeout_seconds"), _number_env_value),
)


@dataclass(frozen=True, slots=True)
class EnvDefaults:
    explicit_keys: set[str] = field(default_factory=set)
    enabled_agents_declared: bool = False
    enabled_agents: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Settings:
    raw: dict[str, Any]

    @property
    def server(self) -> dict[str, Any]:
        return self.raw["server"]

    @property
    def artifacts(self) -> dict[str, Any]:
        return self.raw["artifacts"]

    @property
    def database(self) -> dict[str, Any]:
        return self.raw["database"]

    @property
    def limits(self) -> dict[str, Any]:
        return self.raw["limits"]

    @property
    def callers(self) -> dict[str, dict[str, Any]]:
        return self.raw.get("callers", {})

    @property
    def policy(self) -> dict[str, Any]:
        return self.raw.get("policy", {})

    @property
    def audit(self) -> dict[str, Any]:
        return self.raw.get("audit", {})

    @property
    def modules(self) -> dict[str, Any]:
        return self.raw.get("modules", {})

    def enabled_modules(self) -> dict[str, Any]:
        return {
            name: {"enabled": bool(spec.get("enabled", False)), "provider": spec.get("provider")}
            for name, spec in self.modules.items()
        }


def load_settings(config_path: str | None = None) -> Settings:
    webui_config = read_current_config()
    _apply_webui_env_values(webui_config.owned_fields)
    env_defaults = _load_env_defaults()
    data = _load_config_with_defaults(config_path)
    _apply_agent_config_fragments(data, env_defaults)
    data = _substitute_env(data, _load_env_template_values())
    _apply_env_overrides(data, env_defaults)
    _apply_webui_overrides(data, webui_config.owned_fields)
    _validate(data)
    return Settings(data)


def _load_env_defaults() -> EnvDefaults:
    _apply_webui_agent_dir_env_values(read_current_config().owned_fields)
    initial_keys = set(os.environ)
    dotenv_declared_keys = _read_dotenv_keys(Path(".env"))
    dotenv_keys = _load_dotenv(Path(".env"))
    root_explicit_keys = initial_keys | dotenv_declared_keys | dotenv_keys
    enabled_agents_declared = "ENABLED_AGENTS" in root_explicit_keys
    enabled_agents = _parse_enabled_agents(os.getenv("ENABLED_AGENTS", "")) if enabled_agents_declared else ()
    agent_declared_keys, agent_loaded_keys = _load_agent_dotenvs(enabled_agents)
    return EnvDefaults(
        explicit_keys=root_explicit_keys,
        enabled_agents_declared=enabled_agents_declared,
        enabled_agents=enabled_agents,
    )


def _apply_webui_agent_dir_env_values(owned_fields: dict[str, str]) -> None:
    for key in ("AGENT_CONFIG_DIR", "AGENT_ENV_DIR"):
        value = owned_fields.get(key)
        if value is not None and value.strip():
            os.environ[key] = value.strip()


def _load_config_with_defaults(config_path: str | None = None) -> dict[str, Any]:
    base_path = Path("config/config.main.yaml")
    override_path = config_path or os.getenv("CONFIG_PATH")
    if override_path:
        return _deep_fill_defaults(_load_yaml(Path(override_path)), _load_yaml(base_path))
    return _load_yaml(base_path)


def _parse_enabled_agents(value: str) -> tuple[str, ...]:
    agents: list[str] = []
    seen: set[str] = set()
    for raw_name in re.split(r"[,;]", value):
        name = raw_name.strip()
        if not name:
            continue
        _validate_agent_name(name)
        if name not in seen:
            agents.append(name)
            seen.add(name)
    return tuple(agents)


def _validate_agent_name(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError("ENABLED_AGENTS entries may contain only letters, numbers, underscores, and hyphens")


def _load_agent_dotenvs(enabled_agents: tuple[str, ...]) -> tuple[set[str], set[str]]:
    declared_keys: set[str] = set()
    loaded_keys: set[str] = set()
    env_dir = Path(os.getenv("AGENT_ENV_DIR", "."))
    for agent_name in enabled_agents:
        env_path = env_dir / f".env.agent.{agent_name}"
        declared_keys |= _read_dotenv_keys(env_path)
        loaded_keys |= _load_dotenv(env_path)
    return declared_keys, loaded_keys


def _apply_agent_config_fragments(data: dict[str, Any], env_defaults: EnvDefaults) -> None:
    if not env_defaults.enabled_agents_declared:
        return
    enabled_agents = set(env_defaults.enabled_agents)
    config_dir = Path(os.getenv("AGENT_CONFIG_DIR", "config/agent"))
    _prune_disabled_agent_config(data, _configured_agent_names(data) | (_discover_agent_fragment_names(config_dir) - enabled_agents))
    for agent_name in env_defaults.enabled_agents:
        fragment_path = config_dir / f"config.agent.{agent_name}.yaml"
        if not fragment_path.is_file():
            raise ValueError(f"missing enabled agent config: {fragment_path}")
        _merge_agent_fragment(data, agent_name, _load_yaml(fragment_path))


def _discover_agent_fragment_names(config_dir: Path) -> set[str]:
    names: set[str] = set()
    if config_dir.is_dir():
        for path in config_dir.glob("config.agent.*.yaml"):
            suffix = path.name.removeprefix("config.agent.").removesuffix(".yaml")
            if suffix:
                names.add(suffix)
    env_dir = Path(os.getenv("AGENT_ENV_DIR", "."))
    if env_dir.is_dir():
        for path in env_dir.glob(".env.agent.*"):
            suffix = path.name.removeprefix(".env.agent.")
            if suffix:
                names.add(suffix)
    return names


def _configured_agent_names(data: dict[str, Any]) -> set[str]:
    agent_names: set[str] = set()
    callers = data.get("callers", {})
    if isinstance(callers, dict):
        agent_names |= {name for name in callers if _is_agent_managed_caller(name)}
    policy = data.get("policy", {})
    high_risk = policy.get("high_risk_allowed_callers", {}) if isinstance(policy, dict) else {}
    if isinstance(high_risk, dict):
        agent_names |= {name for name in high_risk if _is_agent_managed_caller(name)}
    matrix = data.get("modules", {}).get("matrix", {}) if isinstance(data.get("modules"), dict) else {}
    if isinstance(matrix, dict):
        caller_accounts = matrix.get("caller_accounts", {})
        if isinstance(caller_accounts, dict):
            agent_names |= {name for name in caller_accounts if _is_agent_managed_caller(name)}
        accounts = matrix.get("accounts", {})
        if isinstance(accounts, dict):
            agent_names |= {name for name in accounts if _is_agent_managed_caller(name)}
    return agent_names


def _is_agent_managed_caller(name: Any) -> bool:
    return isinstance(name, str) and name not in {"host_assistant", "role_default"}


def _prune_disabled_agent_config(data: dict[str, Any], disabled_agents: set[str]) -> None:
    if not disabled_agents:
        return
    callers = data.get("callers", {})
    if isinstance(callers, dict):
        for agent_name in disabled_agents:
            callers.pop(agent_name, None)
    policy = data.get("policy", {})
    if isinstance(policy, dict):
        high_risk = policy.get("high_risk_allowed_callers", {})
        if isinstance(high_risk, dict):
            for agent_name in disabled_agents:
                high_risk.pop(agent_name, None)
    matrix = data.get("modules", {}).get("matrix", {}) if isinstance(data.get("modules"), dict) else {}
    if isinstance(matrix, dict):
        caller_accounts = matrix.get("caller_accounts", {})
        if isinstance(caller_accounts, dict):
            for caller_id, account_name in list(caller_accounts.items()):
                if isinstance(account_name, str) and account_name in disabled_agents and caller_id not in disabled_agents:
                    caller_accounts.pop(caller_id, None)
            for agent_name in disabled_agents:
                account_name = caller_accounts.pop(agent_name, agent_name)
                if isinstance(account_name, str):
                    accounts = matrix.get("accounts", {})
                    if isinstance(accounts, dict):
                        accounts.pop(account_name, None)
        accounts = matrix.get("accounts", {})
        if isinstance(accounts, dict):
            for agent_name in disabled_agents:
                accounts.pop(agent_name, None)


def _merge_agent_fragment(data: dict[str, Any], agent_name: str, fragment: dict[str, Any]) -> None:
    caller = fragment.get("caller", {})
    if caller is None:
        caller = {}
    if not isinstance(caller, dict):
        raise ValueError(f"agent caller config must be an object: {agent_name}")
    token_env = _configured_env_name(caller.get("token_env")) or _agent_env_name(agent_name, "GATEWAY_TOKEN_", "")
    data.setdefault("callers", {})[agent_name] = {
        "role": caller.get("role", "role_play"),
        "token_env": token_env,
        "shared_artifact_read": bool(caller.get("shared_artifact_read", False)),
    }

    high_risk_tools = fragment.get("high_risk_tools", [])
    if high_risk_tools is None:
        high_risk_tools = []
    if not isinstance(high_risk_tools, list) or any(not isinstance(item, str) for item in high_risk_tools):
        raise ValueError(f"agent high_risk_tools must be a string list: {agent_name}")
    if high_risk_tools:
        high_risk = data.setdefault("policy", {}).setdefault("high_risk_allowed_callers", {})
        existing = high_risk.setdefault(agent_name, [])
        if not isinstance(existing, list):
            existing = []
            high_risk[agent_name] = existing
        for tool_name in high_risk_tools:
            if tool_name not in existing:
                existing.append(tool_name)

    matrix = fragment.get("matrix", {})
    if matrix is None:
        matrix = {}
    if not isinstance(matrix, dict):
        raise ValueError(f"agent matrix config must be an object: {agent_name}")
    if bool(matrix.get("enabled", False)):
        matrix_config = data.setdefault("modules", {}).setdefault("matrix", {})
        matrix_config["enabled"] = True
        account_name = _configured_env_name(matrix.get("account")) or agent_name
        matrix_config.setdefault("caller_accounts", {})[agent_name] = account_name
        account_config = matrix_config.setdefault("accounts", {}).setdefault(account_name, {})
        homeserver_env = _configured_env_name(matrix.get("homeserver_env"))
        access_token_env = _configured_env_name(matrix.get("access_token_env")) or _agent_env_name(
            agent_name,
            "",
            "_MATRIX_ACCESS_TOKEN",
        )
        if homeserver_env:
            account_config["homeserver"] = "${" + homeserver_env + "}"
        elif _configured_env_name(matrix.get("homeserver")):
            account_config["homeserver"] = matrix["homeserver"]
        account_config["access_token"] = "${" + access_token_env + "}"


def _configured_env_name(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _agent_env_name(agent_name: str, prefix: str, suffix: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in agent_name).upper()
    return f"{prefix}{normalized}{suffix}"


def _load_dotenv(path: Path) -> set[str]:
    loaded_keys: set[str] = set()
    if not path.is_file():
        return loaded_keys
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            os.environ[key] = _unquote_env_value(value.strip())
            loaded_keys.add(key)
    return loaded_keys


def _load_env_template_values() -> dict[str, str]:
    template_values = _read_dotenv_values(Path(".env.example"))
    template_values.update(os.environ)
    return template_values


def _apply_webui_env_values(owned_fields: dict[str, str]) -> None:
    for key, value in owned_fields.items():
        os.environ[key] = value


def _read_dotenv_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.is_file():
        return keys
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _ = line.split("=", 1)
            key = key.strip()
            if key:
                keys.add(key)
    return keys


def _read_dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key and key not in values:
                values[key] = _unquote_env_value(value.strip())
    return values


def _unquote_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"configuration root must be an object: {path}")
    return loaded


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _deep_fill_defaults(data: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(data)
    for key, value in defaults.items():
        if key not in result:
            result[key] = deepcopy(value)
        elif isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_fill_defaults(result[key], value)
    return result


def _substitute_env(value: Any, env_values: dict[str, str]) -> Any:
    if isinstance(value, dict):
        return {key: _substitute_env(item, env_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute_env(item, env_values) for item in value]
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda match: env_values.get(match.group(1), ""), value)
    return value


def _apply_env_overrides(data: dict[str, Any], env_defaults: EnvDefaults) -> None:
    artifact_public_base_url = os.getenv("ARTIFACT_PUBLIC_BASE_URL", "").strip()
    if artifact_public_base_url:
        data.setdefault("artifacts", {})["public_base_url"] = artifact_public_base_url
    _apply_module_enabled_env_overrides(data, env_defaults)
    _apply_value_env_overrides(data, env_defaults)


def _apply_webui_overrides(data: dict[str, Any], owned_fields: dict[str, str]) -> None:
    if not owned_fields:
        return
    artifact_public_base_url = owned_fields.get("ARTIFACT_PUBLIC_BASE_URL", "").strip()
    if artifact_public_base_url:
        data.setdefault("artifacts", {})["public_base_url"] = artifact_public_base_url
    modules = data.setdefault("modules", {})
    for module_name, env_name in _MODULE_ENABLED_ENV_VARS.items():
        raw_value = owned_fields.get(env_name)
        if raw_value is None or not raw_value.strip():
            continue
        modules.setdefault(module_name, {})["enabled"] = _parse_bool_env(env_name, raw_value)
    for env_name, path, parser in _ENV_VALUE_OVERRIDES:
        raw_value = owned_fields.get(env_name)
        if raw_value is None or not raw_value.strip():
            continue
        _set_nested(data, path, parser(raw_value))


def _apply_module_enabled_env_overrides(data: dict[str, Any], env_defaults: EnvDefaults) -> None:
    modules = data.setdefault("modules", {})
    for module_name, env_name in _MODULE_ENABLED_ENV_VARS.items():
        raw_value = _explicit_env(env_name, env_defaults)
        if raw_value is None:
            continue
        modules.setdefault(module_name, {})["enabled"] = _parse_bool_env(env_name, raw_value)


def _apply_value_env_overrides(data: dict[str, Any], env_defaults: EnvDefaults) -> None:
    for env_name, path, parser in _ENV_VALUE_OVERRIDES:
        raw_value = _explicit_env(env_name, env_defaults)
        if raw_value is None:
            continue
        _set_nested(data, path, parser(raw_value))


def _explicit_env(env_name: str, env_defaults: EnvDefaults) -> str | None:
    if env_name not in env_defaults.explicit_keys:
        return None
    value = os.getenv(env_name)
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return value


def _parse_bool_env(env_name: str, value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"{env_name} must be a boolean value")


def _set_nested(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = data
    for key in path[:-1]:
        next_value = current.setdefault(key, {})
        if not isinstance(next_value, dict):
            raise ValueError(f"cannot override non-object configuration path: {'.'.join(path[:-1])}")
        current = next_value
    current[path[-1]] = value


def _validate(data: dict[str, Any]) -> None:
    for section in ("server", "artifacts", "database", "limits"):
        if section not in data:
            raise ValueError(f"missing required configuration section: {section}")
    if not data["artifacts"].get("root"):
        raise ValueError("artifacts.root is required")
    if not data["database"].get("path"):
        raise ValueError("database.path is required")
    if int(data["artifacts"].get("signed_url_ttl_seconds", 300)) <= 0:
        raise ValueError("artifacts.signed_url_ttl_seconds must be greater than 0")
    _validate_image_config(data.get("modules", {}).get("image", {}))
    _validate_localimage_config(data.get("modules", {}).get("localimage", {}))
    _validate_tts_config(data.get("modules", {}).get("tts", {}))
    _validate_matrix_config(data.get("modules", {}).get("matrix", {}))
    _validate_printer_config(data.get("modules", {}).get("printer", {}))
    Path(data["artifacts"]["root"]).mkdir(parents=True, exist_ok=True)


def _validate_image_config(image_config: dict[str, Any]) -> None:
    if not image_config or not bool(image_config.get("enabled", False)):
        return
    if image_config.get("provider") != "openai_compatible":
        raise ValueError("modules.image.provider must be openai_compatible")
    provider_config = image_config.get("openai_compatible", {})
    for key in ("base_url", "model", "api_key"):
        if not provider_config.get(key):
            raise ValueError(f"missing required image provider setting: {key}")
    parsed_base_url = urlparse(str(provider_config["base_url"]))
    if parsed_base_url.path.rstrip("/").endswith("/v1/images"):
        raise ValueError("modules.image.openai_compatible.base_url must be the API root, not a /v1/images endpoint path")
    allowed_sizes = image_config.get("allowed_sizes") or []
    default_size = image_config.get("default_size")
    if default_size != "auto" and (not default_size or default_size not in allowed_sizes):
        raise ValueError("modules.image.default_size must be auto or in allowed_sizes")
    if float(image_config.get("total_timeout_seconds", 600)) <= 0:
        raise ValueError("modules.image.total_timeout_seconds must be greater than 0")
    if float(image_config.get("stale_job_grace_seconds", 30)) < 0:
        raise ValueError("modules.image.stale_job_grace_seconds must be at least 0")


def _validate_localimage_config(localimage_config: dict[str, Any]) -> None:
    if not localimage_config or not bool(localimage_config.get("enabled", False)):
        return
    if localimage_config.get("provider") != "comfyui":
        raise ValueError("modules.localimage.provider must be comfyui")
    comfyui = localimage_config.get("comfyui", {})
    base_url = str(comfyui.get("base_url", "")).strip()
    if not base_url:
        raise ValueError("modules.localimage.comfyui.base_url is required")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("modules.localimage.comfyui.base_url must be an http(s) URL")
    allowed_hosts = comfyui.get("allowed_hosts") or []
    if not isinstance(allowed_hosts, list) or not allowed_hosts:
        raise ValueError("modules.localimage.comfyui.allowed_hosts is required")
    if parsed.hostname not in set(str(item) for item in allowed_hosts):
        raise ValueError("modules.localimage.comfyui.base_url host must be in allowed_hosts")
    workflow_path = str(comfyui.get("workflow_path", "")).strip()
    if not workflow_path:
        raise ValueError("modules.localimage.comfyui.workflow_path is required")
    if not Path(workflow_path).is_file():
        raise ValueError("modules.localimage.comfyui.workflow_path must exist")
    allowed_sizes = localimage_config.get("allowed_sizes") or []
    default_size = localimage_config.get("default_size")
    if not default_size or default_size not in allowed_sizes:
        raise ValueError("modules.localimage.default_size must be in allowed_sizes")
    allowed_qualities = localimage_config.get("allowed_qualities") or []
    default_quality = localimage_config.get("default_quality")
    if not default_quality or default_quality not in allowed_qualities:
        raise ValueError("modules.localimage.default_quality must be in allowed_qualities")
    allowed_styles = localimage_config.get("allowed_styles") or []
    default_style = localimage_config.get("default_style")
    if not default_style or default_style not in allowed_styles:
        raise ValueError("modules.localimage.default_style must be in allowed_styles")
    allowed_output_formats = localimage_config.get("allowed_output_formats") or []
    default_output_format = localimage_config.get("default_output_format", "png")
    if not default_output_format or default_output_format not in allowed_output_formats:
        raise ValueError("modules.localimage.default_output_format must be in allowed_output_formats")
    if float(localimage_config.get("total_timeout_seconds", 900)) <= 0:
        raise ValueError("modules.localimage.total_timeout_seconds must be greater than 0")
    if float(localimage_config.get("stale_job_grace_seconds", 30)) < 0:
        raise ValueError("modules.localimage.stale_job_grace_seconds must be at least 0")
    if int(comfyui.get("timeout_seconds", 30)) <= 0:
        raise ValueError("modules.localimage.comfyui.timeout_seconds must be greater than 0")
    if float(comfyui.get("poll_interval_seconds", 1)) <= 0:
        raise ValueError("modules.localimage.comfyui.poll_interval_seconds must be greater than 0")
    if float(comfyui.get("max_wait_seconds", localimage_config.get("total_timeout_seconds", 900))) <= 0:
        raise ValueError("modules.localimage.comfyui.max_wait_seconds must be greater than 0")


def _validate_tts_config(tts_config: dict[str, Any]) -> None:
    if not tts_config or not bool(tts_config.get("enabled", False)):
        return
    provider = tts_config.get("provider", "mock")
    if provider not in {"local_http", "mock"}:
        raise ValueError("modules.tts.provider must be local_http or mock")
    voices = tts_config.get("voices") or []
    default_voice = tts_config.get("default_voice")
    if not default_voice or default_voice not in voices:
        raise ValueError("modules.tts.default_voice must be in voices")
    languages = tts_config.get("languages") or []
    default_language = tts_config.get("default_language")
    if not default_language or default_language not in languages:
        raise ValueError("modules.tts.default_language must be in languages")
    allowed_formats = tts_config.get("allowed_formats") or []
    default_format = tts_config.get("default_format")
    if not default_format or default_format not in allowed_formats:
        raise ValueError("modules.tts.default_format must be in allowed_formats")
    if float(tts_config.get("total_timeout_seconds", 120)) <= 0:
        raise ValueError("modules.tts.total_timeout_seconds must be greater than 0")
    if float(tts_config.get("stale_job_grace_seconds", 30)) < 0:
        raise ValueError("modules.tts.stale_job_grace_seconds must be at least 0")
    if provider == "local_http" and not tts_config.get("local_http", {}).get("url"):
        raise ValueError("modules.tts.local_http.url is required")


def _validate_matrix_config(matrix_config: dict[str, Any]) -> None:
    if not matrix_config or not bool(matrix_config.get("enabled", False)):
        return
    if not matrix_config.get("homeserver"):
        raise ValueError("modules.matrix.homeserver is required")
    accounts = matrix_config.get("accounts", {})
    account_tokens = []
    if isinstance(accounts, dict):
        account_tokens = [
            spec.get("access_token")
            for spec in accounts.values()
            if isinstance(spec, dict) and spec.get("access_token")
        ]
    if not matrix_config.get("access_token") and not account_tokens:
        raise ValueError("modules.matrix.access_token or modules.matrix.accounts.*.access_token is required")


def _validate_printer_config(printer_config: dict[str, Any]) -> None:
    if not printer_config or not bool(printer_config.get("enabled", False)):
        return
    provider = printer_config.get("provider", "bridge_http")
    if provider != "bridge_http":
        raise ValueError("modules.printer.provider must be bridge_http")
    if not printer_config.get("bridge_http", {}).get("url"):
        raise ValueError("modules.printer.bridge_http.url is required")
    if not printer_config.get("allowed_printers"):
        raise ValueError("modules.printer.allowed_printers is required")
    allowed_mime_types = printer_config.get("allowed_mime_types") or []
    if not allowed_mime_types:
        raise ValueError("modules.printer.allowed_mime_types is required")
    max_copies = int(printer_config.get("max_copies", 0))
    if max_copies < 1:
        raise ValueError("modules.printer.max_copies must be at least 1")
    duplex_modes = printer_config.get("duplex_modes") or []
    default_duplex = printer_config.get("default_duplex")
    if not default_duplex or default_duplex not in duplex_modes:
        raise ValueError("modules.printer.default_duplex must be in duplex_modes")
    color_modes = printer_config.get("color_modes") or []
    default_color = printer_config.get("default_color")
    if not default_color or default_color not in color_modes:
        raise ValueError("modules.printer.default_color must be in color_modes")
