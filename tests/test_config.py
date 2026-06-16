from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from app.config import load_settings


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


class ConfigTests(unittest.TestCase):
    def test_loads_test_config_from_config_test_directory(self) -> None:
        os.environ["CONFIG_PATH"] = "tests/config/test.config.yaml"
        settings = load_settings()
        self.assertEqual(settings.artifacts["root"], "./tmp/test-artifacts")
        self.assertIn("host_assistant", settings.callers)

    def test_artifact_public_base_url_can_be_overridden_by_env(self) -> None:
        previous = os.environ.get("ARTIFACT_PUBLIC_BASE_URL")
        try:
            os.environ["ARTIFACT_PUBLIC_BASE_URL"] = "http://home-mcp:8787/artifacts"
            settings = load_settings("tests/config/test.config.yaml")
            self.assertEqual(settings.artifacts["public_base_url"], "http://home-mcp:8787/artifacts")
        finally:
            if previous is None:
                os.environ.pop("ARTIFACT_PUBLIC_BASE_URL", None)
            else:
                os.environ["ARTIFACT_PUBLIC_BASE_URL"] = previous

    def test_module_enabled_can_be_overridden_by_env(self) -> None:
        previous = {
            "MATRIX_ACCESS_TOKEN": os.environ.get("MATRIX_ACCESS_TOKEN"),
            "TTS_MODULE_ENABLED": os.environ.get("TTS_MODULE_ENABLED"),
        }
        try:
            os.environ["MATRIX_ACCESS_TOKEN"] = "test-matrix-token"
            os.environ["TTS_MODULE_ENABLED"] = "false"
            settings = load_settings("tests/config/phase4.test.config.yaml")
            self.assertFalse(settings.modules["tts"]["enabled"])
        finally:
            _restore_env(previous)

    def test_module_timeout_can_be_overridden_by_env(self) -> None:
        previous = {
            "MATRIX_ACCESS_TOKEN": os.environ.get("MATRIX_ACCESS_TOKEN"),
            "TTS_TOTAL_TIMEOUT_SECONDS": os.environ.get("TTS_TOTAL_TIMEOUT_SECONDS"),
        }
        try:
            os.environ["MATRIX_ACCESS_TOKEN"] = "test-matrix-token"
            os.environ["TTS_TOTAL_TIMEOUT_SECONDS"] = "3.5"
            settings = load_settings("tests/config/phase4.test.config.yaml")
            self.assertEqual(settings.modules["tts"]["total_timeout_seconds"], 3.5)
        finally:
            _restore_env(previous)

    def test_env_example_module_switch_does_not_override_yaml(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous_tts_enabled = os.environ.pop("TTS_MODULE_ENABLED", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / ".env.example").write_text("TTS_MODULE_ENABLED=false\n", encoding="utf-8")
                (root / "config" / "config.example.yaml").write_text(
                    "\n".join(
                        [
                            "server:",
                            "  host: 127.0.0.1",
                            "  port: 8787",
                            "artifacts:",
                            "  root: ./artifacts",
                            "database:",
                            "  path: ./artifacts/metadata.sqlite3",
                            "limits: {}",
                            "modules:",
                            "  tts:",
                            "    enabled: true",
                            "    provider: mock",
                            "    default_voice: default",
                            "    voices: [default]",
                            "    default_language: en-US",
                            "    languages: [en-US]",
                            "    default_format: wav",
                            "    allowed_formats: [wav]",
                        ]
                    ),
                    encoding="utf-8",
                )
                os.chdir(root)
                try:
                    settings = load_settings()
                    self.assertTrue(settings.modules["tts"]["enabled"])
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            os.environ.pop("TTS_MODULE_ENABLED", None)
            if previous_tts_enabled is not None:
                os.environ["TTS_MODULE_ENABLED"] = previous_tts_enabled
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_env_example_module_switch_stays_default_across_repeated_loads(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous_tts_enabled = os.environ.pop("TTS_MODULE_ENABLED", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / ".env.example").write_text("TTS_MODULE_ENABLED=false\n", encoding="utf-8")
                (root / "config" / "config.example.yaml").write_text(
                    "\n".join(
                        [
                            "server:",
                            "  host: 127.0.0.1",
                            "  port: 8787",
                            "artifacts:",
                            "  root: ./artifacts",
                            "database:",
                            "  path: ./artifacts/metadata.sqlite3",
                            "limits: {}",
                            "modules:",
                            "  tts:",
                            "    enabled: true",
                            "    provider: mock",
                            "    default_voice: default",
                            "    voices: [default]",
                            "    default_language: en-US",
                            "    languages: [en-US]",
                            "    default_format: wav",
                            "    allowed_formats: [wav]",
                        ]
                    ),
                    encoding="utf-8",
                )
                os.chdir(root)
                try:
                    self.assertTrue(load_settings().modules["tts"]["enabled"])
                    self.assertTrue(load_settings().modules["tts"]["enabled"])
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            os.environ.pop("TTS_MODULE_ENABLED", None)
            if previous_tts_enabled is not None:
                os.environ["TTS_MODULE_ENABLED"] = previous_tts_enabled
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_auto_loads_config_yaml_when_config_path_is_not_set(self) -> None:
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
                (root / "config" / "config.yaml").write_text(
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

    def test_env_example_supplies_defaults_and_env_overrides_it(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous_host = os.environ.pop("TEST_SERVER_HOST", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / ".env.example").write_text("TEST_SERVER_HOST=0.0.0.0\n", encoding="utf-8")
                (root / ".env").write_text("TEST_SERVER_HOST=127.0.0.1\n", encoding="utf-8")
                (root / "config" / "config.example.yaml").write_text(
                    "\n".join(
                        [
                            "server:",
                            "  host: ${TEST_SERVER_HOST}",
                            "  port: 8787",
                            "artifacts:",
                            "  root: ./artifacts",
                            "database:",
                            "  path: ./artifacts/metadata.sqlite3",
                            "limits: {}",
                        ]
                    ),
                    encoding="utf-8",
                )
                os.chdir(root)
                try:
                    settings = load_settings()
                    self.assertEqual(settings.server["host"], "127.0.0.1")
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            os.environ.pop("TEST_SERVER_HOST", None)
            if previous_host is not None:
                os.environ["TEST_SERVER_HOST"] = previous_host
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_config_yaml_overrides_config_example_defaults(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous_port = os.environ.pop("TEST_SERVER_PORT", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / ".env.example").write_text("TEST_SERVER_PORT=8787\n", encoding="utf-8")
                (root / "config" / "config.example.yaml").write_text(
                    "\n".join(
                        [
                            "server:",
                            "  host: 127.0.0.1",
                            "  port: ${TEST_SERVER_PORT}",
                            "artifacts:",
                            "  root: ./base-artifacts",
                            "database:",
                            "  path: ./base-artifacts/metadata.sqlite3",
                            "limits: {}",
                        ]
                    ),
                    encoding="utf-8",
                )
                (root / "config" / "config.yaml").write_text(
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
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            os.environ.pop("TEST_SERVER_PORT", None)
            if previous_port is not None:
                os.environ["TEST_SERVER_PORT"] = previous_port
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
                load_settings("tests/config/image.test.config.yaml")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
