from __future__ import annotations

PRINTABLE_ARTIFACT_SCHEMA = {
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

PRINTER_LIST_INPUT_SCHEMA = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

PRINTER_LIST_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "request_id": {"type": "string"},
        "status": {"type": "string"},
        "printers": {"type": "array", "items": {"type": "object"}},
    },
}

PRINTER_PRINT_FILE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "printer_id": {"type": "string", "minLength": 1},
        "artifact_id": {"type": "string", "minLength": 1},
        "copies": {"type": "integer"},
        "duplex": {"type": "string", "enum": ["none", "long_edge", "short_edge"]},
        "color": {"type": "string", "enum": ["auto", "color", "monochrome"]},
    },
    "required": ["printer_id", "artifact_id"],
    "additionalProperties": False,
}

PRINTER_PRINT_FILE_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {"type": "boolean"},
        "request_id": {"type": "string"},
        "status": {"type": "string"},
        "job_id": {"type": "string"},
        "print_job": {"type": "object"},
        "artifact": PRINTABLE_ARTIFACT_SCHEMA,
    },
}
