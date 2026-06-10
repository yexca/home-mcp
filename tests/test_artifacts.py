from __future__ import annotations

import asyncio
import base64
import json
import unittest

from core.errors import (
    ARTIFACT_FORBIDDEN,
    INVALID_ARGUMENT,
    POLICY_DENIED,
    UNSUPPORTED_MEDIA_TYPE,
    GatewayError,
)
from core.policy import CallerIdentity
from tests.helpers import fresh_gateway

PNG_BYTES = b"\x89PNG\r\n\x1a\nupload-test-image"


class ArtifactStoreTests(unittest.TestCase):
    def test_create_get_grant_and_metadata_url(self) -> None:
        services, _, _ = fresh_gateway()
        owner = CallerIdentity("role_default", "role_play")
        other = CallerIdentity("other", "role_play")
        artifact = services.artifacts.create_from_bytes(
            kind="image",
            mime_type="image/png",
            extension="png",
            data=b"png-data",
            owner=owner,
            source_tool="test_tool",
            metadata={"purpose": "unit"},
        )

        self.assertEqual(services.artifacts.get(artifact.id, owner).sha256, artifact.sha256)
        with self.assertRaises(GatewayError) as denied:
            services.artifacts.get(artifact.id, other)
        self.assertEqual(denied.exception.code, ARTIFACT_FORBIDDEN)

        services.artifacts.grant(artifact.id, "other")
        granted = services.artifacts.get(artifact.id, other)
        self.assertIn("/artifacts/", granted.to_metadata(services.config.artifacts["public_base_url"])["download_url"])

    def test_artifact_upload_image_imports_base64_for_authenticated_owner(self) -> None:
        services, _, dispatcher = fresh_gateway()
        encoded = base64.b64encode(PNG_BYTES).decode("ascii")

        result = asyncio.run(
            dispatcher.dispatch(
                "artifact_upload_image",
                {
                    "filename": "input.png",
                    "mime_type": "image/png",
                    "b64_data": encoded,
                },
                authorization="Bearer test-role-token",
            )
        )

        self.assertTrue(result["ok"])
        artifact = result["artifact"]
        self.assertEqual(artifact["kind"], "image")
        self.assertEqual(artifact["mime_type"], "image/png")
        self.assertEqual(artifact["size_bytes"], len(PNG_BYTES))
        self.assertEqual(artifact["metadata"]["original_filename"], "input.png")
        self.assertTrue(artifact["filename"].startswith(artifact["id"]))
        self.assertNotEqual(artifact["filename"], "input.png")
        self.assertIn("/artifacts/", artifact["download_url"])

        stored = services.artifacts.get(artifact["id"], CallerIdentity("role_default", "role_play"))
        self.assertEqual(stored.owner_caller_id, "role_default")
        self.assertEqual(services.artifacts.safe_path(stored).read_bytes(), PNG_BYTES)
        with self.assertRaises(GatewayError) as denied:
            services.artifacts.get(artifact["id"], CallerIdentity("other", "role_play"))
        self.assertEqual(denied.exception.code, ARTIFACT_FORBIDDEN)

        rows = services.artifacts.conn.execute(
            "SELECT input_summary_json, artifact_ids_json FROM audit_events WHERE tool_name = 'artifact_upload_image'"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        summary = json.loads(rows[0]["input_summary_json"])
        self.assertEqual(summary["b64_data"], "[redacted]")
        self.assertNotIn(encoded, str([tuple(row) for row in rows]))
        self.assertIn(artifact["id"], json.loads(rows[0]["artifact_ids_json"]))

    def test_artifact_upload_image_rejects_invalid_inputs_and_anonymous_callers(self) -> None:
        services, _, dispatcher = fresh_gateway()
        services.config.raw["artifacts"]["max_artifact_bytes"] = 8

        cases = [
            (
                "anonymous",
                {
                    "filename": "input.png",
                    "mime_type": "image/png",
                    "b64_data": base64.b64encode(PNG_BYTES[:4]).decode("ascii"),
                },
                None,
                POLICY_DENIED,
            ),
            (
                "mime",
                {
                    "filename": "input.gif",
                    "mime_type": "image/gif",
                    "b64_data": base64.b64encode(PNG_BYTES[:4]).decode("ascii"),
                },
                "Bearer test-role-token",
                INVALID_ARGUMENT,
            ),
            (
                "invalid_base64",
                {"filename": "input.png", "mime_type": "image/png", "b64_data": "not base64"},
                "Bearer test-role-token",
                INVALID_ARGUMENT,
            ),
            (
                "empty_base64",
                {"filename": "input.png", "mime_type": "image/png", "b64_data": ""},
                "Bearer test-role-token",
                INVALID_ARGUMENT,
            ),
            (
                "oversized",
                {
                    "filename": "input.png",
                    "mime_type": "image/png",
                    "b64_data": base64.b64encode(PNG_BYTES).decode("ascii"),
                },
                "Bearer test-role-token",
                INVALID_ARGUMENT,
            ),
        ]
        for name, arguments, authorization, code in cases:
            with self.subTest(name=name):
                result = asyncio.run(
                    dispatcher.dispatch(
                        "artifact_upload_image",
                        arguments,
                        authorization=authorization,
                    )
                )
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], code)

        services.config.raw["artifacts"]["max_artifact_bytes"] = 1024
        services.config.raw["modules"]["image"]["allowed_edit_input_mime_types"] = ["image/jpeg"]
        unsupported = asyncio.run(
            dispatcher.dispatch(
                "artifact_upload_image",
                {
                    "filename": "input.png",
                    "mime_type": "image/png",
                    "b64_data": base64.b64encode(PNG_BYTES[:4]).decode("ascii"),
                },
                authorization="Bearer test-role-token",
            )
        )
        self.assertEqual(unsupported["error"]["code"], UNSUPPORTED_MEDIA_TYPE)


if __name__ == "__main__":
    unittest.main()
