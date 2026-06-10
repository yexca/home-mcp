from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_loads_test_config_from_env_directory(self) -> None:
        os.environ["CONFIG_PATH"] = "env/test.config.yaml"
        settings = load_settings()
        self.assertEqual(settings.artifacts["root"], "./tmp/test-artifacts")
        self.assertIn("host_assistant", settings.callers)

    def test_auto_loads_user_config_when_config_path_is_not_set(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / "config" / "config.example.yaml").write_text(
                    "\n".join(
                        [
                            "server:",
                            "  host: 127.0.0.1",
                            "  port: 8787",
                            "artifacts:",
                            "  root: ./base-artifacts",
                            "database:",
                            "  path: ./base-artifacts/metadata.sqlite3",
                            "limits: {}",
                        ]
                    ),
                    encoding="utf-8",
                )
                (root / "config" / "user.config.yaml").write_text(
                    "\n".join(
                        [
                            "server:",
                            "  port: 9898",
                            "artifacts:",
                            "  root: ./user-artifacts",
                            "database:",
                            "  path: ./user-artifacts/metadata.sqlite3",
                        ]
                    ),
                    encoding="utf-8",
                )
                os.chdir(root)
                try:
                    settings = load_settings()
                    self.assertEqual(settings.server["port"], 9898)
                    self.assertEqual(settings.artifacts["root"], "./user-artifacts")
                    self.assertEqual(settings.database["path"], "./user-artifacts/metadata.sqlite3")
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_image_base_url_rejects_images_endpoint_path(self) -> None:
        previous = {
            "IMAGE_API_BASE_URL": os.environ.get("IMAGE_API_BASE_URL"),
            "IMAGE_API_MODEL": os.environ.get("IMAGE_API_MODEL"),
            "IMAGE_API_KEY": os.environ.get("IMAGE_API_KEY"),
        }
        try:
            os.environ["IMAGE_API_BASE_URL"] = "https://api.example.test/v1/images"
            os.environ["IMAGE_API_MODEL"] = "test-image-model"
            os.environ["IMAGE_API_KEY"] = "test-image-api-key"

            with self.assertRaisesRegex(ValueError, "API root"):
                load_settings("env/image.test.config.yaml")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
