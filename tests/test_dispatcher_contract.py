from __future__ import annotations

import asyncio
import unittest

from core.errors import INTERNAL_ERROR
from tools.registry import ToolDefinition
from tests.helpers import fresh_gateway


async def broken_handler(arguments, ctx):
    raise RuntimeError("secret traceback should not escape")


class DispatcherContractTests(unittest.TestCase):
    def test_health_check_success_has_request_id_and_no_secret_schema(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        result = asyncio.run(dispatcher.dispatch("health_check"))
        self.assertTrue(result["ok"])
        self.assertTrue(result["request_id"].startswith("req_"))
        serialized_tools = str(registry.list_tools()).lower()
        self.assertNotIn("api_key", serialized_tools)
        self.assertNotIn("base_url", serialized_tools)

    def test_handler_exception_maps_to_internal_error_without_traceback(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        registry.register(
            ToolDefinition(
                name="broken_tool",
                title="Broken",
                description="Raises",
                input_schema={"type": "object", "properties": {}, "additionalProperties": False},
                output_schema=None,
                risk_level="low",
                handler=broken_handler,
            )
        )
        result = asyncio.run(
            dispatcher.dispatch(
                "broken_tool",
                authorization="Bearer test-host-token",
            )
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], INTERNAL_ERROR)
        self.assertNotIn("traceback", str(result).lower())
        self.assertNotIn("secret traceback", str(result).lower())

    def test_artifact_get_contract_requires_owner_or_grant(self) -> None:
        services, _, dispatcher = fresh_gateway()
        artifact = services.artifacts.create_from_bytes(
            kind="image",
            mime_type="image/png",
            extension="png",
            data=b"image",
            owner="role_default",
            source_tool="test",
        )
        denied = asyncio.run(dispatcher.dispatch("artifact_get", {"artifact_id": artifact.id}))
        self.assertFalse(denied["ok"])
        allowed = asyncio.run(
            dispatcher.dispatch(
                "artifact_get",
                {"artifact_id": artifact.id},
                authorization="Bearer test-role-token",
            )
        )
        self.assertTrue(allowed["ok"])
        self.assertEqual(allowed["artifact"]["id"], artifact.id)


if __name__ == "__main__":
    unittest.main()
