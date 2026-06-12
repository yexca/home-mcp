from __future__ import annotations

from typing import Any

DEFAULT_LOCAL_IMAGE_SIZES = ["1024x1024", "1024x1536", "1536x1024", "1280x720", "720x1280"]
DEFAULT_LOCAL_IMAGE_QUALITIES = ["draft", "standard", "high"]
DEFAULT_LOCAL_IMAGE_STYLES = ["default", "anime", "realistic", "illustration"]
DEFAULT_LOCAL_IMAGE_OUTPUT_FORMATS = ["png", "jpeg", "webp"]


def build_local_image_generate_input_schema(localimage_config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = localimage_config or {}
    max_prompt_chars = int(config.get("max_prompt_chars", 4000))
    return {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "minLength": 1, "maxLength": max_prompt_chars},
            "negative_prompt": {"type": "string", "maxLength": max_prompt_chars},
            "size": {
                "type": "string",
                "enum": _configured_strings(config, "allowed_sizes", DEFAULT_LOCAL_IMAGE_SIZES),
                "default": config.get("default_size", "1024x1024"),
            },
            "quality": {
                "type": "string",
                "enum": _configured_strings(config, "allowed_qualities", DEFAULT_LOCAL_IMAGE_QUALITIES),
                "default": config.get("default_quality", "standard"),
            },
            "style": {
                "type": "string",
                "enum": _configured_strings(config, "allowed_styles", DEFAULT_LOCAL_IMAGE_STYLES),
                "default": config.get("default_style", "default"),
            },
            "seed": {"type": "integer", "minimum": 0, "maximum": 18446744073709551615},
            "output_format": {
                "type": "string",
                "enum": _configured_strings(config, "allowed_output_formats", DEFAULT_LOCAL_IMAGE_OUTPUT_FORMATS),
                "default": config.get("default_output_format", "png"),
            },
        },
        "required": ["prompt"],
        "additionalProperties": False,
    }


LOCAL_IMAGE_ARTIFACT_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "id": {"type": "string"},
        "kind": {"type": "string"},
        "mime_type": {"type": "string"},
        "filename": {"type": "string"},
        "size_bytes": {"type": "integer"},
        "sha256": {"type": "string"},
        "download_url": {"type": "string"},
        "metadata": {"type": "object"},
    },
}

LOCAL_IMAGE_GENERATE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "request_id": {"type": "string"},
        "status": {"type": "string"},
        "job_id": {"type": "string"},
        "job": {"type": "object"},
        "artifact": LOCAL_IMAGE_ARTIFACT_OUTPUT_SCHEMA,
        "artifacts": {"type": "array", "items": LOCAL_IMAGE_ARTIFACT_OUTPUT_SCHEMA},
        "provider_output": {"type": "object"},
    },
}


def _configured_strings(config: dict[str, Any], key: str, fallback: list[str]) -> list[str]:
    values = config.get(key) or fallback
    if not isinstance(values, list):
        return list(fallback)
    return _dedupe_strings(values)


def _dedupe_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str) or not value:
            continue
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


LOCAL_IMAGE_GENERATE_INPUT_SCHEMA = build_local_image_generate_input_schema()
