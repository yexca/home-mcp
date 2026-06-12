from __future__ import annotations

import asyncio
import importlib
import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import modules
from app.config import load_settings
from app.main import build_services
from core.errors import GatewayError, INVALID_ARGUMENT
from modules.loader import register_configured_module_tools
from modules.image.schemas import IMAGE_EDIT_INPUT_SCHEMA, IMAGE_GENERATE_INPUT_SCHEMA
from tools.registry import ToolRegistry


class Phase6ModuleExtensionTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["CONFIG_PATH"] = "tests/config/phase6.test.config.yaml"
        os.environ["GATEWAY_TOKEN_HOST"] = "test-host-token"
        os.environ["GATEWAY_TOKEN_ROLE_DEFAULT"] = "test-role-token"
        Path("tmp").mkdir(exist_ok=True)
        self.tempdir = tempfile.TemporaryDirectory(prefix="gateway-phase6-module-", dir="tmp")
        self.module_path = Path(self.tempdir.name)
        self.original_module_paths = list(modules.__path__)
        self._create_dummy_module()
        modules.__path__.append(str(self.module_path))
        importlib.invalidate_caches()

    def tearDown(self) -> None:
        modules.__path__[:] = self.original_module_paths
        for name in list(sys.modules):
            if name == "modules.dummy" or name.startswith("modules.dummy."):
                del sys.modules[name]
        self.tempdir.cleanup()
        importlib.invalidate_caches()

    def test_dummy_module_registers_without_app_or_transport_changes(self) -> None:
        settings = load_settings()
        root = Path(tempfile.mkdtemp(prefix="gateway-phase6-artifacts-", dir="tmp"))
        settings.raw["artifacts"]["root"] = str(root)
        settings.raw["database"]["path"] = str(root / "metadata.sqlite3")

        _, registry, dispatcher = build_services(settings)
        tool_names = {tool["name"] for tool in registry.list_tools()}

        self.assertIn("dummy_echo", tool_names)
        result = asyncio.run(
            dispatcher.dispatch(
                "dummy_echo",
                {"value": "pong"},
                authorization="Bearer test-host-token",
            )
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["value"], "pong")

    def test_enabled_module_without_manifest_package_fails_startup(self) -> None:
        settings = load_settings()
        settings.raw["modules"] = {"missing_phase6": {"enabled": True}}

        with self.assertRaises(GatewayError) as raised:
            register_configured_module_tools(ToolRegistry(), settings)
        self.assertEqual(raised.exception.code, INVALID_ARGUMENT)

    def test_image_provider_settings_stay_out_of_external_schemas(self) -> None:
        serialized = f"{IMAGE_GENERATE_INPUT_SCHEMA} {IMAGE_EDIT_INPUT_SCHEMA}".lower()

        self.assertNotIn("api_key", serialized)
        self.assertNotIn("token", serialized)
        self.assertNotIn("base_url", serialized)
        self.assertNotIn("provider", serialized)

    def test_release_hardening_files_exist(self) -> None:
        required = [
            Path("deploy/Dockerfile"),
            Path("docker-compose.yml"),
            Path("config/config.example.yaml"),
            Path(".env.example"),
            Path("deploy/README.md"),
            Path("dev_documents/module-extension.md"),
            Path("dev_documents/release-checklist.md"),
            Path("CHANGELOG.md"),
        ]

        for path in required:
            with self.subTest(path=str(path)):
                self.assertTrue(path.exists(), f"missing {path}")

    def _create_dummy_module(self) -> None:
        package = self.module_path / "dummy"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (package / "manifest.py").write_text(
            textwrap.dedent(
                """
                from __future__ import annotations

                from tools.registry import ToolDefinition
                from tools.result import success


                async def dummy_echo(arguments, ctx):
                    return success(request_id=ctx.request_id, value=arguments.get("value", "ok"))


                def register_tools(registry, settings):
                    if not settings.modules.get("dummy", {}).get("enabled", False):
                        return
                    registry.register(
                        ToolDefinition(
                            name="dummy_echo",
                            title="Dummy Echo",
                            description="Echo a value for module extension tests.",
                            input_schema={
                                "type": "object",
                                "properties": {"value": {"type": "string"}},
                                "additionalProperties": False,
                            },
                            output_schema=None,
                            risk_level="low",
                            handler=dummy_echo,
                            creates_job=False,
                        )
                    )
                """
            ).lstrip(),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
