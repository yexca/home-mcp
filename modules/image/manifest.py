from __future__ import annotations

from app.config import Settings
from modules.image.schemas import IMAGE_GENERATE_INPUT_SCHEMA, IMAGE_GENERATE_OUTPUT_SCHEMA
from modules.image.service import image_generate
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
        )
    )
