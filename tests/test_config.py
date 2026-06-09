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


if __name__ == "__main__":
    unittest.main()
