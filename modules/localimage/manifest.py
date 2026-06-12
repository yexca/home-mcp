from __future__ import annotations

from app.config import Settings
from modules.localimage.background import local_image_generate_background, reconcile_stale_localimage_jobs
from modules.localimage.schemas import LOCAL_IMAGE_GENERATE_OUTPUT_SCHEMA, build_local_image_generate_input_schema
from modules.localimage.service import local_image_generate
from tools.registry import ToolDefinition, ToolRegistry
from transport.request_context import CoreServices


def register_localimage_tools(registry: ToolRegistry, settings: Settings) -> None:
    localimage_config = settings.modules.get("localimage", {})
    if not bool(localimage_config.get("enabled", False)):
        return
    registry.register(
        ToolDefinition(
            name="local_image_generate",
            title="Local Image Generate",
            description="Generate one image through the configured ComfyUI workflow and persist it as an artifact.",
            input_schema=build_local_image_generate_input_schema(localimage_config),
            output_schema=LOCAL_IMAGE_GENERATE_OUTPUT_SCHEMA,
            risk_level="medium",
            handler=local_image_generate,
            creates_job=True,
            background_handler=local_image_generate_background,
        )
    )


register_tools = register_localimage_tools


def startup_reconcile(services: CoreServices, settings: Settings) -> None:
    reconcile_stale_localimage_jobs(services)
