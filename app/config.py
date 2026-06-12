from __future__ import annotations

import os
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


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
    _load_dotenv(Path(".env"))
    base_path = Path("config/config.example.yaml")
    data = _load_yaml(base_path)
    override_path = config_path or os.getenv("CONFIG_PATH") or _default_user_config_path()
    if override_path:
        data = _deep_merge(data, _load_yaml(Path(override_path)))
    data = _substitute_env(data)
    _apply_env_overrides(data)
    _validate(data)
    return Settings(data)


def _default_user_config_path() -> str | None:
    path = Path("config/config.yaml")
    return str(path) if path.is_file() else None


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
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


def _substitute_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _substitute_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_substitute_env(item) for item in value]
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), ""), value)
    return value


def _apply_env_overrides(data: dict[str, Any]) -> None:
    artifact_public_base_url = os.getenv("ARTIFACT_PUBLIC_BASE_URL", "").strip()
    if artifact_public_base_url:
        data.setdefault("artifacts", {})["public_base_url"] = artifact_public_base_url


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
    if image_config.get("provider") != "ikun":
        raise ValueError("modules.image.provider must be ikun")
    ikun = image_config.get("ikun", {})
    for key in ("base_url", "model", "api_key"):
        if not ikun.get(key):
            raise ValueError(f"missing required image provider setting: {key}")
    parsed_base_url = urlparse(str(ikun["base_url"]))
    if parsed_base_url.path.rstrip("/").endswith("/v1/images"):
        raise ValueError("modules.image.ikun.base_url must be the API root, not a /v1/images endpoint path")
    allowed_sizes = image_config.get("allowed_sizes") or []
    default_size = image_config.get("default_size")
    if not default_size or default_size not in allowed_sizes:
        raise ValueError("modules.image.default_size must be in allowed_sizes")
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
    if not matrix_config.get("access_token"):
        raise ValueError("modules.matrix.access_token is required")


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
