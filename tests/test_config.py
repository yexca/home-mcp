from __future__ import annotations

import os
import unittest

from app.config import load_settings


class ConfigTests(unittest.TestCase):
    def test_loads_test_config_from_env_directory(self) -> None:
        os.environ["CONFIG_PATH"] = "env/test.config.yaml"
        settings = load_settings()
        self.assertEqual(settings.artifacts["root"], "./tmp/test-artifacts")
        self.assertIn("host_assistant", settings.callers)


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
