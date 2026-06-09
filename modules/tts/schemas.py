from __future__ import annotations

AUDIO_ARTIFACT_OUTPUT_SCHEMA = {
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

TTS_SYNTHESIZE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "minLength": 1, "maxLength": 4000},
        "voice": {"type": "string"},
        "language": {"type": "string"},
        "format": {"type": "string", "enum": ["ogg", "mp3", "wav"]},
        "speed": {"type": "number"},
    },
    "required": ["text"],
    "additionalProperties": False,
}

TTS_SYNTHESIZE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "request_id": {"type": "string"},
        "status": {"type": "string"},
        "job_id": {"type": "string"},
        "artifact": AUDIO_ARTIFACT_OUTPUT_SCHEMA,
        "provider_output": {"type": "object"},
    },
}
