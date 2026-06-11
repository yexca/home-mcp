from __future__ import annotations

from typing import Any

DEFAULT_IMAGE_SIZES = [
    "1024x1024",
    "1024x1536",
    "1536x1024",
    "1280x720",
    "720x1280",
    "1920x1080",
    "1080x1920",
    "2560x1440",
    "1440x2560",
    "3840x2160",
    "2160x3840",
]
DEFAULT_IMAGE_QUALITIES = ["auto", "low", "medium", "high"]
DEFAULT_IMAGE_OUTPUT_FORMATS = ["png", "jpeg", "webp"]


def build_image_generate_input_schema(image_config: dict[str, Any] | None = None) -> dict[str, Any]:
    return _image_input_schema(image_config or {})


def build_image_edit_input_schema(image_config: dict[str, Any] | None = None) -> dict[str, Any]:
    schema = _image_input_schema(image_config or {})
    schema["properties"].update(
        {
            "image_artifact_id": {"type": "string", "minLength": 1},
            "image_artifact_ids": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
            },
        }
    )
    return schema


def _image_input_schema(image_config: dict[str, Any]) -> dict[str, Any]:
    max_prompt_chars = int(image_config.get("max_prompt_chars", 4000))
    return {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "minLength": 1, "maxLength": max_prompt_chars},
            "size": {
                "type": "string",
                "enum": _enum_with_auto(_configured_strings(image_config, "allowed_sizes", DEFAULT_IMAGE_SIZES)),
                "default": "auto",
            },
            "quality": {
                "type": "string",
                "enum": _configured_strings(image_config, "allowed_qualities", DEFAULT_IMAGE_QUALITIES),
                "default": "auto",
            },
            "output_format": {
                "type": "string",
                "enum": _configured_strings(image_config, "allowed_output_formats", DEFAULT_IMAGE_OUTPUT_FORMATS),
                "default": "png",
            },
            "n": {"type": "integer"},
        },
        "required": ["prompt"],
        "additionalProperties": False,
    }


def _configured_strings(image_config: dict[str, Any], key: str, fallback: list[str]) -> list[str]:
    values = image_config.get(key) or fallback
    if not isinstance(values, list):
        return list(fallback)
    return _dedupe_strings(values)


def _enum_with_auto(values: list[str]) -> list[str]:
    return _dedupe_strings(["auto", *values])


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


IMAGE_GENERATE_INPUT_SCHEMA = build_image_generate_input_schema()
IMAGE_EDIT_INPUT_SCHEMA = build_image_edit_input_schema()

IMAGE_ARTIFACT_OUTPUT_SCHEMA = {
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

IMAGE_GENERATE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "request_id": {"type": "string"},
        "status": {"type": "string"},
        "job_id": {"type": "string"},
        "job": {"type": "object"},
        "artifact": IMAGE_ARTIFACT_OUTPUT_SCHEMA,
        "artifacts": {"type": "array", "items": IMAGE_ARTIFACT_OUTPUT_SCHEMA},
        "provider_output": {"type": "object"},
    },
}

IMAGE_EDIT_OUTPUT_SCHEMA = IMAGE_GENERATE_OUTPUT_SCHEMA
