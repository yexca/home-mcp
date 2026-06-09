from __future__ import annotations

IMAGE_GENERATE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "prompt": {"type": "string", "minLength": 1, "maxLength": 4000},
        "size": {"type": "string"},
        "quality": {"type": "string"},
        "output_format": {"type": "string", "enum": ["png", "jpeg", "webp"]},
        "n": {"type": "integer"},
    },
    "required": ["prompt"],
    "additionalProperties": False,
}

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
        "artifact": IMAGE_ARTIFACT_OUTPUT_SCHEMA,
        "artifacts": {"type": "array", "items": IMAGE_ARTIFACT_OUTPUT_SCHEMA},
        "provider_output": {"type": "object"},
    },
}
