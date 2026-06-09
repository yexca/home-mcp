from __future__ import annotations

from app.config import Settings
from modules.tts.schemas import TTS_SYNTHESIZE_INPUT_SCHEMA, TTS_SYNTHESIZE_OUTPUT_SCHEMA
from modules.tts.service import tts_synthesize
from tools.registry import ToolDefinition, ToolRegistry


def register_tts_tools(registry: ToolRegistry, settings: Settings) -> None:
    tts_config = settings.modules.get("tts", {})
    if not bool(tts_config.get("enabled", False)):
        return
    registry.register(
        ToolDefinition(
            name="tts_synthesize",
            title="TTS Synthesize",
            description="Generate speech audio from text and persist it as an artifact.",
            input_schema=TTS_SYNTHESIZE_INPUT_SCHEMA,
            output_schema=TTS_SYNTHESIZE_OUTPUT_SCHEMA,
            risk_level="medium",
            handler=tts_synthesize,
            creates_job=True,
        )
    )


register_tools = register_tts_tools
