from __future__ import annotations

import base64
import binascii
from typing import Any

from core.errors import GatewayError, INVALID_ARGUMENT, UNSUPPORTED_MEDIA_TYPE
from tools.registry import ToolDefinition, ToolRegistry
from tools.result import success
from transport.request_context import RequestContext

IMAGE_UPLOAD_EXTENSIONS = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}

ARTIFACT_UPLOAD_IMAGE_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "filename": {"type": "string", "minLength": 1, "maxLength": 255},
        "mime_type": {"type": "string", "enum": ["image/png", "image/jpeg", "image/webp"]},
        "b64_data": {"type": "string", "minLength": 1},
    },
    "required": ["filename", "mime_type", "b64_data"],
    "additionalProperties": False,
}


async def health_check(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    return success(
        request_id=ctx.request_id,
        server=ctx.config.server["name"],
        version=str(ctx.config.server.get("version", "0.1.0")),
        modules=ctx.config.enabled_modules(),
    )


async def artifact_get(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    artifact = ctx.artifacts.get(arguments["artifact_id"], ctx.caller)
    return success(
        request_id=ctx.request_id,
        artifact=artifact.to_metadata(ctx.config.artifacts.get("public_base_url")),
    )


async def artifact_upload_image(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    mime_type = _normalize_mime(arguments["mime_type"])
    allowed_mimes = set(
        ctx.config.modules.get("image", {}).get("allowed_edit_input_mime_types")
        or IMAGE_UPLOAD_EXTENSIONS.keys()
    )
    if mime_type not in allowed_mimes or mime_type not in IMAGE_UPLOAD_EXTENSIONS:
        raise GatewayError(UNSUPPORTED_MEDIA_TYPE, "image MIME type is not supported", retryable=False)

    b64_data = arguments["b64_data"]
    max_bytes = int(ctx.config.artifacts.get("max_artifact_bytes", 50 * 1024 * 1024))
    estimated_bytes = (len(b64_data) * 3) // 4
    if estimated_bytes > max_bytes:
        raise GatewayError(INVALID_ARGUMENT, "image exceeds max artifact size")
    try:
        data = base64.b64decode(b64_data, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise GatewayError(INVALID_ARGUMENT, "b64_data is not valid base64") from exc
    if not data:
        raise GatewayError(INVALID_ARGUMENT, "b64_data must not be empty")
    if len(data) > max_bytes:
        raise GatewayError(INVALID_ARGUMENT, "image exceeds max artifact size")

    artifact = ctx.artifacts.create_from_bytes(
        kind="image",
        mime_type=mime_type,
        extension=IMAGE_UPLOAD_EXTENSIONS[mime_type],
        data=data,
        owner=ctx.caller,
        source_tool="artifact_upload_image",
        source_job_id=ctx.job_id,
        metadata={"original_filename": arguments["filename"]},
    )
    return success(
        request_id=ctx.request_id,
        artifact=artifact.to_metadata(ctx.config.artifacts.get("public_base_url")),
    )


async def job_status(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    job = ctx.jobs.get(arguments["job_id"], ctx.caller)
    return success(request_id=ctx.request_id, job=job.to_dict())


def _normalize_mime(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def register_builtin_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            name="health_check",
            title="Health Check",
            description="Return process health and enabled module summary.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
            output_schema=None,
            risk_level="low",
            handler=health_check,
            creates_job=False,
        )
    )
    registry.register(
        ToolDefinition(
            name="artifact_get",
            title="Artifact Get",
            description="Return artifact metadata and a download URL when caller may read it.",
            input_schema={
                "type": "object",
                "properties": {"artifact_id": {"type": "string", "minLength": 5}},
                "required": ["artifact_id"],
                "additionalProperties": False,
            },
            output_schema=None,
            risk_level="low",
            handler=artifact_get,
            creates_job=False,
        )
    )
    registry.register(
        ToolDefinition(
            name="artifact_upload_image",
            title="Artifact Upload Image",
            description="Import base64-encoded image bytes into the gateway artifact store.",
            input_schema=ARTIFACT_UPLOAD_IMAGE_INPUT_SCHEMA,
            output_schema=None,
            risk_level="low",
            handler=artifact_upload_image,
            creates_job=False,
        )
    )
    registry.register(
        ToolDefinition(
            name="job_status",
            title="Job Status",
            description="Return job status visible to the caller.",
            input_schema={
                "type": "object",
                "properties": {"job_id": {"type": "string", "minLength": 5}},
                "required": ["job_id"],
                "additionalProperties": False,
            },
            output_schema=None,
            risk_level="low",
            handler=job_status,
            creates_job=False,
        )
    )
