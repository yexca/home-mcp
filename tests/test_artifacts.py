from __future__ import annotations

import unittest

from core.errors import ARTIFACT_FORBIDDEN, GatewayError
from core.policy import CallerIdentity
from tests.helpers import fresh_gateway


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


if __name__ == "__main__":
    unittest.main()
