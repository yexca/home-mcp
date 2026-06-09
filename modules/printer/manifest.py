from __future__ import annotations

from app.config import Settings
from modules.printer.schemas import (
    PRINTER_LIST_INPUT_SCHEMA,
    PRINTER_LIST_OUTPUT_SCHEMA,
    PRINTER_PRINT_FILE_INPUT_SCHEMA,
    PRINTER_PRINT_FILE_OUTPUT_SCHEMA,
)
from modules.printer.service import printer_list, printer_print_file
from tools.registry import ToolDefinition, ToolRegistry


def register_printer_tools(registry: ToolRegistry, settings: Settings) -> None:
    printer_config = settings.modules.get("printer", {})
    if not bool(printer_config.get("enabled", False)):
        return
    registry.register(
        ToolDefinition(
            name="printer_list",
            title="Printer List",
            description="List allowlisted printers available through the printer bridge.",
            input_schema=PRINTER_LIST_INPUT_SCHEMA,
            output_schema=PRINTER_LIST_OUTPUT_SCHEMA,
            risk_level="low",
            handler=printer_list,
            creates_job=False,
        )
    )
    registry.register(
        ToolDefinition(
            name="printer_print_file",
            title="Printer Print File",
            description="Print a document or image artifact through an allowlisted printer bridge.",
            input_schema=PRINTER_PRINT_FILE_INPUT_SCHEMA,
            output_schema=PRINTER_PRINT_FILE_OUTPUT_SCHEMA,
            risk_level="high",
            handler=printer_print_file,
            creates_job=True,
        )
    )
