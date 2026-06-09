from __future__ import annotations

import unittest

from core.errors import GatewayError
from tools.registry import ToolDefinition, ToolRegistry


async def noop(arguments, ctx):
    return {"ok": True}


class RegistryTests(unittest.TestCase):
    def test_rejects_duplicate_tools(self) -> None:
        registry = ToolRegistry()
        definition = ToolDefinition(
            name="image_generate",
            title="Image Generate",
            description="test",
            input_schema={"type": "object", "properties": {}},
            output_schema=None,
            risk_level="medium",
            handler=noop,
        )
        registry.register(definition)
        with self.assertRaises(GatewayError):
            registry.register(definition)

    def test_rejects_secret_schema_fields(self) -> None:
        registry = ToolRegistry()
        with self.assertRaises(GatewayError):
            registry.register(
                ToolDefinition(
                    name="bad_tool",
                    title="Bad",
                    description="test",
                    input_schema={"type": "object", "properties": {"api_key": {"type": "string"}}},
                    output_schema=None,
                    risk_level="low",
                    handler=noop,
                )
            )


if __name__ == "__main__":
    unittest.main()
