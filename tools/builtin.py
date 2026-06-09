from __future__ import annotations

from typing import Any

from tools.registry import ToolDefinition, ToolRegistry
from tools.result import success
from transport.request_context import RequestContext


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


async def job_status(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    job = ctx.jobs.get(arguments["job_id"], ctx.caller)
    return success(request_id=ctx.request_id, job=job.to_dict())


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
