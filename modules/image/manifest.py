from __future__ import annotations

from app.config import Settings
from transport.request_context import CoreServices
from modules.image.schemas import (
    IMAGE_EDIT_INPUT_SCHEMA,
    IMAGE_EDIT_OUTPUT_SCHEMA,
    IMAGE_GENERATE_INPUT_SCHEMA,
    IMAGE_GENERATE_OUTPUT_SCHEMA,
)
from modules.image.background import image_generate_background, reconcile_stale_image_jobs
from modules.image.service import image_edit, image_generate
from tools.registry import ToolDefinition, ToolRegistry


def register_image_tools(registry: ToolRegistry, settings: Settings) -> None:
    image_config = settings.modules.get("image", {})
    if not bool(image_config.get("enabled", False)):
        return
    registry.register(
        ToolDefinition(
            name="image_generate",
            title="Image Generate",
            description="Generate one image from a text prompt and persist it as an artifact.",
            input_schema=IMAGE_GENERATE_INPUT_SCHEMA,
            output_schema=IMAGE_GENERATE_OUTPUT_SCHEMA,
            risk_level="medium",
            handler=image_generate,
            creates_job=True,
            background_handler=image_generate_background,
        )
    )
    registry.register(
        ToolDefinition(
            name="image_edit",
            title="Image Edit",
            description="Edit one or more image artifacts with a text prompt and persist the result as an artifact.",
            input_schema=IMAGE_EDIT_INPUT_SCHEMA,
            output_schema=IMAGE_EDIT_OUTPUT_SCHEMA,
            risk_level="medium",
            handler=image_edit,
            creates_job=True,
        )
    )


register_tools = register_image_tools


def startup_reconcile(services: CoreServices, settings: Settings) -> None:
    reconcile_stale_image_jobs(services)
