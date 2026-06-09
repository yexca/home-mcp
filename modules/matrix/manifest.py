from __future__ import annotations

from app.config import Settings
from modules.matrix.schemas import MATRIX_SEND_AUDIO_INPUT_SCHEMA, MATRIX_SEND_OUTPUT_SCHEMA, MATRIX_SEND_TEXT_INPUT_SCHEMA
from modules.matrix.service import matrix_send_audio, matrix_send_text
from tools.registry import ToolDefinition, ToolRegistry


def register_matrix_tools(registry: ToolRegistry, settings: Settings) -> None:
    matrix_config = settings.modules.get("matrix", {})
    if not bool(matrix_config.get("enabled", False)):
        return
    registry.register(
        ToolDefinition(
            name="matrix_send_text",
            title="Matrix Send Text",
            description="Send a text message to an allowlisted Matrix room.",
            input_schema=MATRIX_SEND_TEXT_INPUT_SCHEMA,
            output_schema=MATRIX_SEND_OUTPUT_SCHEMA,
            risk_level="high",
            handler=matrix_send_text,
            creates_job=True,
        )
    )
    registry.register(
        ToolDefinition(
            name="matrix_send_audio",
            title="Matrix Send Audio",
            description="Upload an audio artifact and send it to an allowlisted Matrix room.",
            input_schema=MATRIX_SEND_AUDIO_INPUT_SCHEMA,
            output_schema=MATRIX_SEND_OUTPUT_SCHEMA,
            risk_level="high",
            handler=matrix_send_audio,
            creates_job=True,
        )
    )


register_tools = register_matrix_tools
