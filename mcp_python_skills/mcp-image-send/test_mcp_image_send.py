from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import Any


MODULE_PATH = Path(__file__).with_name("mcp_image_send.py")
SPEC = importlib.util.spec_from_file_location("mcp_image_send", MODULE_PATH)
assert SPEC is not None
mcp_image_send = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mcp_image_send)


class McpImageSendTests(unittest.TestCase):
    def test_local_text_to_image_sends_artifact_without_marker_or_download(self) -> None:
        calls: list[tuple[str, dict[str, Any]]] = []

        def fake_mcp_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            calls.append((tool_name, dict(arguments)))
            if tool_name == "local_image_generate":
                return {"ok": True, "status": "accepted", "job_id": "job_123"}
            if tool_name == "job_status":
                return {
                    "ok": True,
                    "job": {
                        "id": "job_123",
                        "status": "succeeded",
                        "artifact_ids": ["art_one", "art_two"],
                    },
                }
            if tool_name == "matrix_send_image":
                self.assertNotIn("access_token", arguments)
                self.assertNotIn("matrix_account", arguments)
                self.assertEqual(arguments["room_id"], "!room:example.test")
                self.assertEqual(arguments["image_artifact_id"], "art_one")
                self.assertEqual(arguments["body"], "preview.png")
                return {
                    "ok": True,
                    "status": "succeeded",
                    "event_id": "$event",
                    "room_id": arguments["room_id"],
                    "media": {"artifact_id": arguments["image_artifact_id"]},
                }
            self.fail(f"unexpected MCP tool: {tool_name}")

        original_mcp_call = mcp_image_send.mcp_call
        original_fetch = mcp_image_send.fetch_artifact_to_workspace
        mcp_image_send.mcp_call = fake_mcp_call
        mcp_image_send.fetch_artifact_to_workspace = lambda *args, **kwargs: self.fail("download should not run")
        try:
            result = mcp_image_send.local_text_to_image(
                {"prompt": "a small lamp", "room_id": "!room:example.test", "body": "preview.png"}
            )
        finally:
            mcp_image_send.mcp_call = original_mcp_call
            mcp_image_send.fetch_artifact_to_workspace = original_fetch

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "sent")
        self.assertEqual(result["selected_artifact_ids"], ["art_one"])
        self.assertEqual(result["files"], [])
        self.assertNotIn("image_markers", result)
        self.assertNotIn("send_text", result)
        self.assertEqual(calls[-1][0], "matrix_send_image")

    def test_room_id_can_fallback_to_environment(self) -> None:
        original_env = mcp_image_send.os.environ.get("MATRIX_DEFAULT_ROOM_ID")
        mcp_image_send.os.environ["MATRIX_DEFAULT_ROOM_ID"] = "!fallback:example.test"
        try:
            self.assertEqual(mcp_image_send.room_id_from_payload({}), "!fallback:example.test")
        finally:
            if original_env is None:
                mcp_image_send.os.environ.pop("MATRIX_DEFAULT_ROOM_ID", None)
            else:
                mcp_image_send.os.environ["MATRIX_DEFAULT_ROOM_ID"] = original_env

    def test_missing_room_id_returns_structured_error(self) -> None:
        original_env = mcp_image_send.os.environ.get("MATRIX_DEFAULT_ROOM_ID")
        mcp_image_send.os.environ.pop("MATRIX_DEFAULT_ROOM_ID", None)
        try:
            with self.assertRaises(mcp_image_send.SkillError) as raised:
                mcp_image_send.room_id_from_payload({})
        finally:
            if original_env is not None:
                mcp_image_send.os.environ["MATRIX_DEFAULT_ROOM_ID"] = original_env

        self.assertEqual(raised.exception.stage, "parse_args")
        self.assertEqual(raised.exception.error_type, "missing_room_id")


if __name__ == "__main__":
    unittest.main()
