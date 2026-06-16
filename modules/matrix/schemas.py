from __future__ import annotations

MATRIX_SEND_TEXT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "room_id": {"type": "string", "minLength": 1},
        "text": {"type": "string", "minLength": 1, "maxLength": 4000},
    },
    "required": ["room_id", "text"],
    "additionalProperties": False,
}

MATRIX_SEND_AUDIO_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "room_id": {"type": "string", "minLength": 1},
        "audio_artifact_id": {"type": "string", "minLength": 1},
        "body": {"type": "string", "maxLength": 512},
    },
    "required": ["room_id", "audio_artifact_id"],
    "additionalProperties": False,
}

MATRIX_SEND_IMAGE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "room_id": {"type": "string", "minLength": 1},
        "image_artifact_id": {"type": "string", "minLength": 1},
        "body": {"type": "string", "maxLength": 512},
    },
    "required": ["room_id", "image_artifact_id"],
    "additionalProperties": False,
}

MATRIX_SEND_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "request_id": {"type": "string"},
        "status": {"type": "string"},
        "job_id": {"type": "string"},
        "event_id": {"type": "string"},
        "room_id": {"type": "string"},
        "media": {"type": "object"},
    },
}
