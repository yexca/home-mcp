from __future__ import annotations

import os
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    Path(data["artifacts"]["root"]).mkdir(parents=True, exist_ok=True)
