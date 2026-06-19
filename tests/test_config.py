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


_MODULE_SWITCH_ENV_VARS = (
    "IMAGE_MODULE_ENABLED",
    "LOCAL_IMAGE_MODULE_ENABLED",
    "TTS_MODULE_ENABLED",
    "MATRIX_MODULE_ENABLED",
    "PRINTER_MODULE_ENABLED",
)


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self._previous_module_switches = {key: os.environ.get(key) for key in _MODULE_SWITCH_ENV_VARS}
        for key in _MODULE_SWITCH_ENV_VARS:
            os.environ[key] = ""

    def tearDown(self) -> None:
        _restore_env(self._previous_module_switches)

    def test_loads_test_config_from_config_test_directory(self) -> None:
        os.environ["CONFIG_PATH"] = "tests/config/test.config.yaml"
        settings = load_settings()
        self.assertEqual(settings.artifacts["root"], "./tmp/test-artifacts")
        self.assertIn("host_assistant", settings.callers)

    def test_artifact_public_base_url_comes_from_yaml(self) -> None:
        settings = load_settings("tests/config/test.config.yaml")
        self.assertEqual(settings.artifacts["public_base_url"], "http://127.0.0.1:8787/artifacts")

    def test_module_enabled_comes_from_yaml(self) -> None:
        previous = {"MATRIX_ACCESS_TOKEN": os.environ.get("MATRIX_ACCESS_TOKEN")}
        try:
            os.environ["MATRIX_ACCESS_TOKEN"] = "test-matrix-token"
            settings = load_settings("tests/config/phase4.test.config.yaml")
            self.assertTrue(settings.modules["tts"]["enabled"])
        finally:
            _restore_env(previous)

    def test_module_timeout_comes_from_yaml(self) -> None:
        previous = {"MATRIX_ACCESS_TOKEN": os.environ.get("MATRIX_ACCESS_TOKEN")}
        try:
            os.environ["MATRIX_ACCESS_TOKEN"] = "test-matrix-token"
            settings = load_settings("tests/config/phase4.test.config.yaml")
            self.assertEqual(settings.modules["matrix"]["timeout_seconds"], 2)
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
                (root / "config" / "config.main.yaml").write_text(
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
                (root / "config" / "config.main.yaml").write_text(
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

    def test_default_merges_local_config_yaml_when_config_path_is_not_set(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / "config" / "config.main.yaml").write_text(
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

    def test_environment_placeholders_are_still_supported_for_advanced_configs(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous_host = os.environ.pop("TEST_SERVER_HOST", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / "config" / "config.main.yaml").write_text(
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
                    os.environ["TEST_SERVER_HOST"] = "127.0.0.1"
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

    def test_config_yaml_overrides_main_config(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous = {
            "TTS_MODULE_ENABLED": os.environ.pop("TTS_MODULE_ENABLED", None),
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / "config" / "config.main.yaml").write_text(
                    "\n".join(
                        [
                            "server: {host: 127.0.0.1, port: 8787}",
                            "artifacts: {root: ./artifacts}",
                            "database: {path: ./artifacts/metadata.sqlite3}",
                            "limits: {}",
                            "modules:",
                            "  tts:",
                            "    enabled: false",
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
                (root / "config" / "config.yaml").write_text(
                    "modules:\n  tts:\n    enabled: true\n",
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
            _restore_env(previous)
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_enabled_agents_merge_agent_config_fragments(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous = {
            "MATRIX_MODULE_ENABLED": os.environ.pop("MATRIX_MODULE_ENABLED", None),
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config" / "agent").mkdir(parents=True)
                (root / "config" / "config.yaml").write_text("agents:\n  enabled: [agent1]\n", encoding="utf-8")
                (root / "config" / "agent" / "config.agent.agent1.yaml").write_text(
                    "\n".join(
                        [
                            "caller:",
                            "  role: role_play",
                            "  token: test-agent-token",
                            "matrix:",
                            "  enabled: true",
                            "  account: agent1",
                            "  homeserver: http://matrix.test",
                            "  access_token: test-matrix-token",
                            "high_risk_tools:",
                            "  - matrix_send_text",
                        ]
                    ),
                    encoding="utf-8",
                )
                (root / "config" / "config.main.yaml").write_text(
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
                            "callers:",
                            "  host_assistant:",
                            "    role: admin",
                            "    token: test-host-token",
                            "policy:",
                            "  high_risk_allowed_callers: {}",
                            "modules:",
                            "  matrix:",
                            "    enabled: false",
                            "    homeserver: http://matrix.test",
                            "    access_token: ''",
                            "    timeout_seconds: 2",
                        ]
                    ),
                    encoding="utf-8",
                )
                os.chdir(root)
                try:
                    settings = load_settings()
                    self.assertIn("agent1", settings.callers)
                    self.assertEqual(settings.callers["agent1"]["token"], "test-agent-token")
                    self.assertTrue(settings.modules["matrix"]["enabled"])
                    self.assertEqual(settings.modules["matrix"]["caller_accounts"]["agent1"], "agent1")
                    self.assertEqual(settings.modules["matrix"]["accounts"]["agent1"]["access_token"], "test-matrix-token")
                    self.assertEqual(settings.policy["high_risk_allowed_callers"]["agent1"], ["matrix_send_text"])
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            _restore_env(previous)
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_yaml_module_switch_overrides_agent_matrix_enablement(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous = {
            "MATRIX_MODULE_ENABLED": os.environ.pop("MATRIX_MODULE_ENABLED", None),
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config" / "agent").mkdir(parents=True)
                (root / "config" / "config.yaml").write_text("agents:\n  enabled: [agent1]\nmodules:\n  matrix:\n    enabled: false\n", encoding="utf-8")
                (root / "config" / "agent" / "config.agent.agent1.yaml").write_text(
                    "matrix:\n  enabled: true\n  access_token: test-matrix-token\nhigh_risk_tools:\n  - matrix_send_text\n",
                    encoding="utf-8",
                )
                (root / "config" / "config.main.yaml").write_text(
                    "\n".join(
                        [
                            "server: {host: 127.0.0.1, port: 8787}",
                            "artifacts: {root: ./artifacts}",
                            "database: {path: ./artifacts/metadata.sqlite3}",
                            "limits: {}",
                            "modules:",
                            "  matrix:",
                            "    enabled: false",
                            "    homeserver: http://matrix.test",
                            "    access_token: ''",
                        ]
                    ),
                    encoding="utf-8",
                )
                os.chdir(root)
                try:
                    settings = load_settings()
                    self.assertFalse(settings.modules["matrix"]["enabled"])
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            _restore_env(previous)
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_enabled_agents_prunes_legacy_disabled_agent_runtime_config(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous = {
        }
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config" / "agent").mkdir(parents=True)
                (root / "config" / "config.yaml").write_text("agents:\n  enabled: [agent1]\n", encoding="utf-8")
                (root / "config" / "agent" / "config.agent.agent1.yaml").write_text(
                    "matrix:\n  enabled: true\n  access_token: test-matrix-token\n",
                    encoding="utf-8",
                )
                (root / "config" / "config.main.yaml").write_text(
                    "\n".join(
                        [
                            "server: {host: 127.0.0.1, port: 8787}",
                            "artifacts: {root: ./artifacts}",
                            "database: {path: ./artifacts/metadata.sqlite3}",
                            "limits: {}",
                            "callers:",
                            "  host_assistant: {role: admin, token_env: GATEWAY_TOKEN_HOST}",
                            "  role_default: {role: role_play, token_env: GATEWAY_TOKEN_ROLE_DEFAULT}",
                            "  agent2: {role: role_play, token_env: GATEWAY_TOKEN_AGENT2}",
                            "policy:",
                            "  high_risk_allowed_callers:",
                            "    agent2: [matrix_send_text]",
                            "modules:",
                            "  matrix:",
                            "    enabled: false",
                            "    homeserver: http://matrix.test",
                            "    access_token: ''",
                            "    caller_accounts:",
                            "      role_default: agent2",
                            "      agent2: agent2",
                            "    accounts:",
                            "      agent2:",
                            "        access_token: old-token",
                        ]
                    ),
                    encoding="utf-8",
                )
                os.chdir(root)
                try:
                    settings = load_settings()
                    self.assertIn("role_default", settings.callers)
                    self.assertNotIn("agent2", settings.callers)
                    self.assertNotIn("agent2", settings.policy["high_risk_allowed_callers"])
                    self.assertNotIn("role_default", settings.modules["matrix"]["caller_accounts"])
                    self.assertNotIn("agent2", settings.modules["matrix"]["accounts"])
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            _restore_env(previous)
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_config_path_overrides_main_config_defaults(self) -> None:
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        previous_port = os.environ.pop("TEST_SERVER_PORT", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                (root / "template.env").write_text("TEST_SERVER_PORT=8787\n", encoding="utf-8")
                (root / "config" / "config.main.yaml").write_text(
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
                (root / "custom.config.yaml").write_text(
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
                    os.environ["TEST_SERVER_PORT"] = "8787"
                    os.environ["CONFIG_PATH"] = "custom.config.yaml"
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

    def test_image_provider_requires_openai_compatible_name(self) -> None:
        previous = {
            "IMAGE_API_BASE_URL": os.environ.get("IMAGE_API_BASE_URL"),
            "IMAGE_API_MODEL": os.environ.get("IMAGE_API_MODEL"),
            "IMAGE_API_KEY": os.environ.get("IMAGE_API_KEY"),
        }
        old_cwd = Path.cwd()
        old_config_path = os.environ.pop("CONFIG_PATH", None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "config").mkdir()
                os.environ["IMAGE_API_BASE_URL"] = "https://api.example.test"
                os.environ["IMAGE_API_MODEL"] = "test-image-model"
                os.environ["IMAGE_API_KEY"] = "test-image-api-key"
                (root / "config" / "config.main.yaml").write_text(
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
                            "  image:",
                            "    enabled: true",
                            "    provider: unsupported_provider",
                            "    default_size: 1024x1024",
                            "    allowed_sizes: [1024x1024]",
                            "    openai_compatible:",
                            "      base_url: ${IMAGE_API_BASE_URL}",
                            "      model: ${IMAGE_API_MODEL}",
                            "      api_key: ${IMAGE_API_KEY}",
                        ]
                    ),
                    encoding="utf-8",
                )
                os.chdir(root)
                try:
                    with self.assertRaisesRegex(ValueError, "openai_compatible"):
                        load_settings()
                finally:
                    os.chdir(old_cwd)
        finally:
            os.chdir(old_cwd)
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            if old_config_path is not None:
                os.environ["CONFIG_PATH"] = old_config_path

    def test_image_provider_timeout_comes_from_yaml(self) -> None:
        previous = {
            "IMAGE_API_BASE_URL": os.environ.get("IMAGE_API_BASE_URL"),
            "IMAGE_API_MODEL": os.environ.get("IMAGE_API_MODEL"),
            "IMAGE_API_KEY": os.environ.get("IMAGE_API_KEY"),
        }
        try:
            os.environ["IMAGE_API_BASE_URL"] = "https://api.example.test"
            os.environ["IMAGE_API_MODEL"] = "test-image-model"
            os.environ["IMAGE_API_KEY"] = "test-image-api-key"

            settings = load_settings("tests/config/image.test.config.yaml")

            self.assertEqual(settings.modules["image"]["openai_compatible"]["timeout_seconds"], 5)
            self.assertEqual(settings.modules["image"]["provider"], "openai_compatible")
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
