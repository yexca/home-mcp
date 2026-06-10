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
    base_path = Path("config/config.example.yaml")
    data = _load_yaml(base_path)
    override_path = config_path or os.getenv("CONFIG_PATH")
    if override_path:
        data = _deep_merge(data, _load_yaml(Path(override_path)))
    data = _substitute_env(data)
    _validate(data)
    return Settings(data)


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


def _validate(data: dict[str, Any]) -> None:
    for section in ("server", "artifacts", "database", "limits"):
        if section not in data:
            raise ValueError(f"missing required configuration section: {section}")
    if not data["artifacts"].get("root"):
        raise ValueError("artifacts.root is required")
    if not data["database"].get("path"):
        raise ValueError("database.path is required")
    _validate_image_config(data.get("modules", {}).get("image", {}))
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
