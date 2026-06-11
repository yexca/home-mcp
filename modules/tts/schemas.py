from __future__ import annotations

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
        "status": {"type": "string", "enum": ["accepted"]},
        "job_id": {"type": "string"},
        "job": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "status": {"type": "string"},
                "progress": {"type": "number"},
            },
        },
    },
}
