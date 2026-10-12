from __future__ import annotations

import json
import io
import os
import sqlite3
import threading
import unittest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import yaml

from app.config import load_settings
from app.config import Settings
from app.main import build_services
from modules.image.providers.openai_compatible import OpenAICompatibleImageProvider
from tests.helpers import fresh_gateway, fresh_image_gateway
from transport.mcp_server import GatewayHTTPServer, GatewayRequestHandler


class ModelEndpoint(BaseHTTPRequestHandler):
    def do_GET(self):
        user_agent = self.headers.get("User-Agent")
        self.server.received.append((self.path, self.headers.get("Authorization"), user_agent))
        # Some provider WAFs reject urllib's default client identification.
        if user_agent != "home-mcp-gateway/0.2.2":
            self.send_response(403)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        body = json.dumps({"data": [{"id": "text-a"}, {"id": "image-a"}, {"id": "text-a"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class ManagementTests(unittest.TestCase):
    def setUp(self):
        auth = patch.dict(os.environ, {"HOME_MCP_LOGIN_KEY": "separate-login-key", "HOME_MCP_DEV_MODE": "false"})
        auth.start()
        self.addCleanup(auth.stop)
        self.services, registry, dispatcher = fresh_gateway()
        self.addCleanup(self.services.close)
        self.server = GatewayHTTPServer(("127.0.0.1", 0), GatewayRequestHandler, services=self.services, registry=registry, dispatcher=dispatcher)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(5)

    def api(self, path, body=None, key="separate-login-key", headers=None):
        conn = HTTPConnection(*self.server.server_address, timeout=5)
        request_headers = {"Content-Type": "application/json", **(headers or {})}
        if key is not None:
            request_headers["Authorization"] = f"Bearer {key}"
        conn.request("POST" if body is not None else "GET", path, body=json.dumps(body) if body is not None else None, headers=request_headers)
        response = conn.getresponse()
        result = response.status, json.loads(response.read())
        conn.close()
        return result

    def provider(self):
        code, payload = self.api("/admin/api/llm/providers/save", {"name": "Test", "base_url": "https://api.example.test/v1", "api_key": "private-api-key"})
        self.assertEqual(code, 200, payload)
        return payload["provider_id"]

    def test_login_key_is_independent_of_mcp_tokens_and_not_persisted(self):
        self.assertEqual(self.api("/admin/api/status", key=None)[0], 401)
        self.assertEqual(self.api("/admin/api/status", key="test-host-token")[0], 403)
        code, payload = self.api("/admin/api/status")
        self.assertEqual(code, 200)
        self.assertNotIn("separate-login-key", json.dumps(payload))
        self.assertNotIn("separate-login-key", json.dumps(self.services.management.load()))
        with patch.dict(os.environ, {"HOME_MCP_LOGIN_KEY": ""}):
            self.assertEqual(self.api("/admin/api/status")[0], 503)

    def test_dev_mode_enters_webui_without_key_and_keeps_mcp_identity(self):
        with patch.dict(os.environ, {"HOME_MCP_DEV_MODE": "true", "HOME_MCP_LOGIN_KEY": ""}):
            self.assertTrue(self.api("/admin/api/auth", key=None)[1]["dev_mode"])
            self.assertEqual(self.api("/admin/api/status", key=None)[0], 200)
            self.assertEqual(self.api("/admin/api/status", key=None, headers={"Origin": "https://other.example"})[0], 403)
            self.assertEqual(self.services.policy.resolve_caller(None).caller_id, "anonymous")

    def test_operational_controls_save_through_http_without_restart(self):
        status = self.api("/admin/api/status")[1]
        self.assertIn("IMAGE_JOBS_PER_CALLER_PER_DAY", status["settings_schema"])
        self.assertEqual(status["local_env"]["IMAGE_RATE_WINDOW_SECONDS"], "86400")
        code, result = self.api("/admin/api/config", {"owned_fields": {
            "IMAGE_JOBS_PER_CALLER_PER_DAY": "60", "IMAGE_RATE_WINDOW_SECONDS": "3600",
            "IMAGE_ALLOW_HTTP_IMAGE_URLS": "false", "LOCAL_IMAGE_STYLE_PRESETS": "{}",
        }})
        self.assertEqual(code, 200, result)
        self.assertEqual(self.services.config.limits["image_jobs_per_caller_per_day"], 60)
        status = self.api("/admin/api/status")[1]
        self.assertEqual(status["local_env"]["IMAGE_JOBS_PER_CALLER_PER_DAY"], "60")
        self.assertEqual(status["local_env"]["LOCAL_IMAGE_STYLE_PRESETS"], "{}")
        self.assertFalse(status["restart_required"])
        self.assertEqual(self.api("/admin/api/config", {"owned_fields": {"IMAGE_JOBS_PER_CALLER_PER_DAY": "-1"}})[0], 400)

    def test_fetch_models_and_preserve_keys_without_returning_them(self):
        remote = ThreadingHTTPServer(("127.0.0.1", 0), ModelEndpoint)
        remote.received = []
        thread = threading.Thread(target=remote.serve_forever, daemon=True)
        thread.start()
        try:
            address = f"http://127.0.0.1:{remote.server_port}/v1"
            code, saved = self.api("/admin/api/llm/providers/save", {"name": "Remote", "base_url": address, "api_key": "private-api-key"})
            self.assertEqual(code, 200)
            provider_id = saved["provider_id"]
            self.assertNotIn("private-api-key", json.dumps(saved))
            code, payload = self.api("/admin/api/llm/discover", {"provider_id": provider_id})
            self.assertEqual(code, 200)
            self.assertEqual(payload["models"], ["image-a", "text-a"])
            self.assertEqual(remote.received, [("/v1/models", "Bearer private-api-key", "home-mcp-gateway/0.2.2")])
            code, _ = self.api("/admin/api/llm/providers/save", {"id": provider_id, "name": "Renamed", "base_url": address, "api_key": ""})
            self.assertEqual(code, 200)
            self.assertEqual(self.services.llm.provider(provider_id)["api_key"], "private-api-key")
        finally:
            remote.shutdown()
            remote.server_close()
            thread.join(5)

    def test_selected_image_model_validation_and_deletion_protection(self):
        provider_id = self.provider()
        self.api("/admin/api/llm/models/save", {"provider_id": provider_id, "models": [{"model_id": "text", "tags": ["text"]}, {"model_id": "image", "tags": ["image", "text"]}]})
        models = {row["model_id"]: row for row in self.services.llm.models(provider_id)}
        self.assertEqual(self.api("/admin/api/config", {"owned_fields": {"IMAGE_MODEL_ID": models["text"]["id"]}})[0], 400)
        self.assertEqual(self.api("/admin/api/config", {"owned_fields": {"IMAGE_MODEL_ID": "unknown"}})[0], 400)
        code, result = self.api("/admin/api/config", {"owned_fields": {"IMAGE_MODEL_ID": models["image"]["id"], "IMAGE_MODULE_ENABLED": "true"}})
        self.assertEqual(code, 200, result)
        config = self.services.management.load()
        self.assertNotIn("api_key", config["modules"]["image"]["openai_compatible"])
        provider = OpenAICompatibleImageProvider.from_settings(self.services.config)
        self.assertEqual((provider.model, provider.api_key), ("image", "private-api-key"))
        sent = []
        def image_opener(req, **kwargs):
            sent.append(req)
            return io.BytesIO(b'{"data": [{"b64_json": "aW1hZ2U="}]}')
        provider.opener = image_opener
        provider.generate(prompt="test", n=1, size="1024x1024", quality="auto", output_format="png")
        self.assertEqual(sent[0].full_url, "https://api.example.test/v1/images/generations")
        self.assertEqual(json.loads(sent[0].data)["model"], "image")
        self.assertEqual(sent[0].get_header("Authorization"), "Bearer private-api-key")
        self.assertEqual(self.api("/admin/api/llm/providers/delete", {"provider_id": provider_id})[0], 400)
        self.assertEqual(self.api("/admin/api/llm/models/save", {"provider_id": provider_id, "models": [{"model_id": "image", "tags": ["text"]}]})[0], 400)
        self.assertEqual(self.api("/admin/api/llm/models/save", {"provider_id": provider_id, "models": []})[0], 400)
        self.assertEqual(len(self.services.llm.models(provider_id)), 2)
        self.assertEqual(self.api("/admin/api/config", {"owned_fields": {"IMAGE_MODEL_ID": "", "IMAGE_MODULE_ENABLED": "false"}})[0], 200)
        self.assertEqual(self.api("/admin/api/llm/providers/delete", {"provider_id": provider_id})[0], 200)
        self.assertEqual(self.services.llm.catalog()["providers"], [])
        self.assertIsNotNone(self.provider())

    def test_invalid_model_tags_and_duplicate_ids_do_not_replace_models(self):
        provider_id = self.provider()
        self.services.llm.save_models(provider_id, [{"model_id": "ok", "tags": ["text"]}])
        for models in ([{"model_id": "a", "tags": []}], [{"model_id": "a", "tags": ["audio"]}], [{"model_id": "a", "tags": ["text"]}] * 2):
            self.assertEqual(self.api("/admin/api/llm/models/save", {"provider_id": provider_id, "models": models})[0], 400)
            self.assertEqual(self.services.llm.models(provider_id)[0]["model_id"], "ok")
        self.assertEqual(self.api("/admin/api/llm/models/save", {"provider_id": "unknown", "models": []})[0], 400)

    def test_image_switch_keeps_health_consistent_with_registered_tools_until_restart(self):
        provider_id = self.provider()
        self.services.llm.save_models(provider_id, [{"model_id": "image", "tags": ["image"]}])
        model_id = self.services.llm.models(provider_id)[0]["id"]
        code, saved = self.api("/admin/api/config", {"owned_fields": {"IMAGE_MODEL_ID": model_id, "IMAGE_MODULE_ENABLED": "true"}})
        self.assertEqual(code, 200, saved)
        status = self.api("/admin/api/status")[1]
        self.assertFalse(status["modules"]["image"]["enabled"])
        self.assertTrue(status["configured_modules"]["image"]["enabled"])
        self.assertTrue(status["restart_required"])
        self.assertFalse(self.api("/readyz", key=None)[1]["modules"]["image"]["enabled"])
        self.assertNotIn("image_generate", {tool["name"] for tool in self.server.registry.list_tools()})
        self.assertNotIn("image_edit", {tool["name"] for tool in self.server.registry.list_tools()})
        restarted, registry, _ = build_services(Settings(self.services.management.load()))
        try:
            self.assertTrue(restarted.config.modules["image"]["enabled"])
            self.assertTrue({"image_generate", "image_edit"}.issubset({tool["name"] for tool in registry.list_tools()}))
            self.assertEqual(restarted.config.modules["image"]["openai_compatible"]["model"], "image")
        finally:
            restarted.close()

    def test_agents_roundtrip_from_sqlite_and_preserve_masked_tokens(self):
        agent = {"name": "robot", "enabled": True, "caller": {"gateway_token": "long-gateway-token"}, "matrix": {"enabled": True, "account": "robot", "access_token": "long-matrix-token"}}
        code, payload = self.api("/admin/api/config", {"owned_fields": {"MATRIX_HOMESERVER": "https://matrix.example"}, "agents": [agent]})
        self.assertEqual(code, 200, payload)
        status = self.api("/admin/api/status")[1]
        self.assertNotIn("long-gateway-token", json.dumps(status))
        self.assertEqual(self.api("/admin/api/config", {"agents": status["agents"]})[0], 200)
        stored = self.services.management.load()
        self.assertEqual(stored["_agent_fragments"]["robot"]["caller"]["token"], "long-gateway-token")
        self.assertEqual(stored["_agent_fragments"]["robot"]["matrix"]["access_token"], "long-matrix-token")
        self.assertEqual(self.api("/admin/api/config", {"agents": [], "owned_fields": {"MATRIX_MODULE_ENABLED": "false"}})[0], 200)
        stored = self.services.management.load()
        self.assertNotIn("robot", stored["callers"])
        self.assertEqual(stored["_agent_fragments"], {})

    def test_restart_restores_sqlite_models_and_agents_without_fragment_files(self):
        provider_id = self.provider()
        self.services.llm.save_models(provider_id, [{"model_id": "persisted-image", "tags": ["image"]}])
        model_id = self.services.llm.models(provider_id)[0]["id"]
        agent = {"name": "saved", "enabled": True, "caller": {"gateway_token": "gateway-key"}, "matrix": {"enabled": False}}
        self.assertEqual(self.api("/admin/api/config", {"owned_fields": {"IMAGE_MODEL_ID": model_id, "IMAGE_MODULE_ENABLED": "true"}, "agents": [agent]})[0], 200)
        root = Path(self.services.config.database["path"]).resolve().parent
        restored_path = root / "restored.sqlite3"
        restored_conn = sqlite3.connect(restored_path)
        self.services.management.conn.backup(restored_conn)
        restored_conn.close()
        config_path = root / "bootstrap.yaml"
        config_path.write_text(yaml.safe_dump({"database": {"path": str(restored_path)}}), encoding="utf-8")
        settings = load_settings(str(config_path))
        self.assertEqual(settings.database["path"], str(restored_path))
        restarted, _, _ = build_services(settings)
        try:
            self.assertEqual(restarted.config.callers["saved"]["token"], "gateway-key")
            self.assertEqual(restarted.config.modules["image"]["openai_compatible"]["model"], "persisted-image")
            self.assertEqual(restarted.llm.models(provider_id)[0]["id"], model_id)
        finally:
            restarted.close()

    def test_legacy_image_import_happens_only_once(self):
        legacy, _, _ = fresh_image_gateway()
        try:
            catalog = legacy.llm.catalog()
            self.assertEqual(len(catalog["providers"]), 1)
            model = catalog["providers"][0]["models"][0]
            self.assertEqual(model["tags"], ["image"])
            self.assertEqual(legacy.management.load()["modules"]["image"]["model_id"], model["id"])
            restarted, _, _ = build_services(legacy.config)
            try:
                self.assertEqual(len(restarted.llm.catalog()["providers"]), 1)
            finally:
                restarted.close()
        finally:
            legacy.close()
