from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WEBUI_CONFIG_VERSION = 1
WEBUI_CONFIG_DIR_ENV = "WEBUI_CONFIG_DIR"

_ENV_NAME_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SECRET_RE = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD)", re.IGNORECASE)

DEFAULT_WEBUI_CONFIG_DIR = "config_webUI"


@dataclass(frozen=True, slots=True)
class WebUIConfig:
    owned_fields: dict[str, str] = field(default_factory=dict)
    path: Path | None = None
    active_snapshot: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.owned_fields)


def config_dir() -> Path:
    import os

    return Path(os.getenv(WEBUI_CONFIG_DIR_ENV, DEFAULT_WEBUI_CONFIG_DIR))


def read_current_config(root: Path | None = None) -> WebUIConfig:
    root = root or config_dir()
    current_path = root / "current.json"
    if not current_path.is_file():
        return WebUIConfig()
    current = _read_json(current_path)
    active_snapshot = _clean_relative_path(current.get("active_snapshot"))
    if active_snapshot:
        snapshot_path = (root / active_snapshot).resolve()
        try:
            snapshot_path.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("WebUI active_snapshot must stay inside config_webUI") from exc
        if not snapshot_path.is_file():
            raise ValueError(f"WebUI active snapshot does not exist: {active_snapshot}")
        snapshot = _read_json(snapshot_path)
        return WebUIConfig(
            owned_fields=_normalize_owned_fields(snapshot.get("owned_fields", {})),
            path=snapshot_path,
            active_snapshot=active_snapshot,
        )
    return WebUIConfig(
        owned_fields=_normalize_owned_fields(current.get("owned_fields", {})),
        path=current_path,
    )


def write_snapshot(owned_fields: dict[str, Any], root: Path | None = None) -> dict[str, Any]:
    root = root or config_dir()
    snapshots_dir = root / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_owned_fields(owned_fields)
    timestamp = _timestamp()
    snapshot_name = f"webui.{timestamp}.json"
    relative_snapshot = f"snapshots/{snapshot_name}"
    snapshot = {
        "version": WEBUI_CONFIG_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owned_fields": normalized,
    }
    snapshot_path = snapshots_dir / snapshot_name
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    current = {
        "version": WEBUI_CONFIG_VERSION,
        "active_snapshot": relative_snapshot,
        "updated_at": snapshot["created_at"],
    }
    (root / "current.json").write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"snapshot": relative_snapshot, "owned_fields": normalized}


def archive_current_config(root: Path | None = None) -> dict[str, Any]:
    root = root or config_dir()
    current_path = root / "current.json"
    if not current_path.exists():
        return {"archived": False}
    backup_dir = root / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = _timestamp()
    target = backup_dir / f"current.{timestamp}.json"
    current_path.replace(target)
    return {"archived": True, "backup": str(target)}


def public_status(config: WebUIConfig) -> dict[str, Any]:
    return {
        "enabled": config.enabled,
        "active_snapshot": config.active_snapshot,
        "path": str(config.path) if config.path else None,
        "owned_fields": mask_secret_fields(config.owned_fields),
    }


def mask_secret_fields(values: dict[str, Any]) -> dict[str, Any]:
    masked: dict[str, Any] = {}
    for key, value in values.items():
        if _SECRET_RE.search(key):
            masked[key] = _mask_value(str(value))
        else:
            masked[key] = value
    return masked


def _normalize_owned_fields(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError("WebUI owned_fields must be an object")
    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key).strip()
        if not _ENV_NAME_RE.fullmatch(key):
            raise ValueError(f"invalid WebUI environment key: {key}")
        if raw_value is None:
            continue
        normalized[key] = str(raw_value).strip()
    return normalized


def _read_json(path: Path) -> dict[str, Any]:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid WebUI config JSON: {path}") from exc
    if not isinstance(loaded, dict):
        raise ValueError(f"WebUI config root must be an object: {path}")
    return loaded


def _clean_relative_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    cleaned = value.replace("\\", "/").strip().lstrip("/")
    if ".." in Path(cleaned).parts:
        raise ValueError("WebUI active_snapshot must be a relative path without '..'")
    return cleaned


def _mask_value(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "********"
    return f"{value[:3]}...{value[-3:]}"


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")
