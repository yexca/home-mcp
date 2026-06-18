from __future__ import annotations

import asyncio
import json
import os
import threading
import tempfile
import unittest
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from core.errors import POLICY_DENIED
from tests.helpers import fresh_gateway
from transport.mcp_server import GatewayHTTPServer, GatewayRequestHandler


class McpTransportTests(unittest.TestCase):
    def test_root_redirects_to_webui(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        httpd = GatewayHTTPServer(
            ("127.0.0.1", 0),
            GatewayRequestHandler,
            services=services,
            registry=registry,
            dispatcher=dispatcher,
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        try:
            conn.request("GET", "/")
            response = conn.getresponse()
            self.assertEqual(response.status, 302)
            self.assertEqual(response.getheader("Location"), "/webui/")
            response.read()
        finally:
            conn.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_request_body_metadata_caller_cannot_spoof_identity(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        artifact = services.artifacts.create_from_bytes(
            kind="image",
            mime_type="image/png",
            extension="png",
            data=b"image",
            owner="role_default",
            source_tool="test",
        )
        job = services.jobs.create(
            request_id="req_test",
            caller_id="role_default",
            tool_name="health_check",
            input_summary={},
        )
        arguments_by_tool = {
            "artifact_get": {"artifact_id": artifact.id},
            "artifact_get_image": {"artifact_id": artifact.id},
            "artifact_upload_image": {
                "filename": "input.png",
                "mime_type": "image/png",
                "b64_data": "aW1hZ2U=",
            },
            "job_status": {"job_id": job.id},
        }

        for tool in registry.list_tools():
            if tool["name"] == "health_check":
                continue
            with self.subTest(tool=tool["name"]):
                result = asyncio.run(
                    dispatcher.dispatch(
                        tool["name"],
                        arguments_by_tool[tool["name"]],
                        metadata={"caller": "host_assistant"},
                    )
                )
                self.assertFalse(result["ok"])
                self.assertEqual(result["error"]["code"], POLICY_DENIED)

    def test_mcp_sse_endpoint_accepts_jsonrpc_messages(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        httpd = GatewayHTTPServer(
            ("127.0.0.1", 0),
            GatewayRequestHandler,
            services=services,
            registry=registry,
            dispatcher=dispatcher,
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        host, port = httpd.server_address
        stream = HTTPConnection(host, port, timeout=5)
        response = None
        try:
            stream.request("GET", "/mcp")
            response = stream.getresponse()
            self.assertEqual(response.status, 200)
            self.assertIn("text/event-stream", response.getheader("Content-Type", ""))

            endpoint = _read_sse_event(response)
            self.assertEqual(endpoint["event"], "endpoint")
            self.assertTrue(endpoint["data"].startswith("/mcp/messages?sessionId="))

            post = HTTPConnection(host, port, timeout=5)
            post.request(
                "POST",
                endpoint["data"],
                body=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
                headers={"Content-Type": "application/json"},
            )
            post_response = post.getresponse()
            self.assertEqual(post_response.status, 202)
            post_response.read()
            post.close()

            message = _read_sse_event(response)
            self.assertEqual(message["event"], "message")
            payload = json.loads(message["data"])
            self.assertEqual(payload["jsonrpc"], "2.0")
            self.assertEqual(payload["id"], 1)
            self.assertIn("tools", payload["result"])
            self.assertIn("inputSchema", payload["result"]["tools"][0])
        finally:
            if response is not None:
                response.close()
            stream.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_artifact_download_url_uses_request_host(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        artifact = services.artifacts.create_from_bytes(
            kind="image",
            mime_type="image/png",
            extension="png",
            data=b"image",
            owner="role_default",
            source_tool="test",
        )
        httpd = GatewayHTTPServer(
            ("127.0.0.1", 0),
            GatewayRequestHandler,
            services=services,
            registry=registry,
            dispatcher=dispatcher,
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        try:
            conn.request(
                "POST",
                "/mcp",
                body=json.dumps({"tool": "artifact_get", "arguments": {"artifact_id": artifact.id}}),
                headers={
                    "Authorization": "Bearer test-role-token",
                    "Content-Type": "application/json",
                    "Host": "zeroclaw.test:8787",
                },
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
            self.assertTrue(payload["ok"])
            parsed_download = urlparse(payload["artifact"]["download_url"])
            self.assertEqual(
                f"{parsed_download.scheme}://{parsed_download.netloc}{parsed_download.path}",
                f"http://zeroclaw.test:8787/artifacts/{artifact.id}",
            )
            query = parse_qs(parsed_download.query)
            self.assertIn("expires", query)
            self.assertIn("signature", query)
        finally:
            conn.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_signed_artifact_download_url_allows_get_without_bearer(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        image_bytes = b"\x89PNG\r\n\x1a\nsigned-download"
        artifact = services.artifacts.create_from_bytes(
            kind="image",
            mime_type="image/png",
            extension="png",
            data=image_bytes,
            owner="role_default",
            source_tool="test",
        )
        httpd = GatewayHTTPServer(
            ("127.0.0.1", 0),
            GatewayRequestHandler,
            services=services,
            registry=registry,
            dispatcher=dispatcher,
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        try:
            conn.request(
                "POST",
                "/mcp",
                body=json.dumps({"tool": "artifact_get", "arguments": {"artifact_id": artifact.id}}),
                headers={
                    "Authorization": "Bearer test-role-token",
                    "Content-Type": "application/json",
                    "Host": f"{host}:{port}",
                },
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
            download = urlparse(payload["artifact"]["download_url"])

            unauthenticated = HTTPConnection(host, port, timeout=5)
            unauthenticated.request("GET", f"{download.path}?{download.query}")
            download_response = unauthenticated.getresponse()
            self.assertEqual(download_response.status, 200)
            self.assertEqual(download_response.getheader("Content-Type"), "image/png")
            self.assertEqual(download_response.read(), image_bytes)
            unauthenticated.close()

            tampered = parse_qs(download.query)
            bad_query = f"expires={tampered['expires'][0]}&signature=bad"
            rejected = HTTPConnection(host, port, timeout=5)
            rejected.request("GET", f"{download.path}?{bad_query}")
            rejected_response = rejected.getresponse()
            self.assertEqual(rejected_response.status, 403)
            rejected_response.read()
            rejected.close()
        finally:
            conn.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_artifact_get_does_not_return_mcp_image_content(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        image_bytes = b"\x89PNG\r\n\x1a\ninline-image"
        artifact = services.artifacts.create_from_bytes(
            kind="image",
            mime_type="image/png",
            extension="png",
            data=image_bytes,
            owner="role_default",
            source_tool="test",
        )
        httpd = GatewayHTTPServer(
            ("127.0.0.1", 0),
            GatewayRequestHandler,
            services=services,
            registry=registry,
            dispatcher=dispatcher,
        )
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        host, port = httpd.server_address
        conn = HTTPConnection(host, port, timeout=5)
        try:
            conn.request(
                "POST",
                "/mcp",
                body=json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 3,
                        "method": "tools/call",
                        "params": {"name": "artifact_get", "arguments": {"artifact_id": artifact.id}},
                    }
                ),
                headers={
                    "Authorization": "Bearer test-role-token",
                    "Content-Type": "application/json",
                    "Host": "zeroclaw.test:8787",
                },
            )
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            payload = json.loads(response.read().decode("utf-8"))
            content = payload["result"]["content"]
            self.assertEqual(content[0]["type"], "text")
            text_payload = json.loads(content[0]["text"])
            self.assertTrue(text_payload["ok"])
            self.assertEqual(text_payload["artifact"]["id"], artifact.id)
            self.assertNotIn("_mcp_content", text_payload)
            self.assertEqual(len(content), 1)
        finally:
            conn.close()
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=5)

    def test_admin_status_and_config_snapshot_require_admin_token(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        with tempfile.TemporaryDirectory() as tmp:
            previous_webui_dir = os.environ.get("WEBUI_CONFIG_DIR")
            previous_agent_env_dir = os.environ.get("AGENT_ENV_DIR")
            previous_image_model = os.environ.pop("IMAGE_API_MODEL", None)
            os.environ["WEBUI_CONFIG_DIR"] = str(Path(tmp) / "config_webUI")
            agent_env_dir = Path(tmp) / "agent-env"
            agent_env_dir.mkdir()
            (agent_env_dir / ".env").write_text("IMAGE_API_MODEL=model-from-mounted-env\n", encoding="utf-8")
            os.environ["AGENT_ENV_DIR"] = str(agent_env_dir)
            httpd = GatewayHTTPServer(
                ("127.0.0.1", 0),
                GatewayRequestHandler,
                services=services,
                registry=registry,
                dispatcher=dispatcher,
            )
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            host, port = httpd.server_address
            try:
                denied = HTTPConnection(host, port, timeout=5)
                denied.request("GET", "/admin/api/status")
                denied_response = denied.getresponse()
                self.assertEqual(denied_response.status, 401)
                denied_response.read()
                denied.close()

                conn = HTTPConnection(host, port, timeout=5)
                conn.request(
                    "GET",
                    "/admin/api/status",
                    headers={"Authorization": "Bearer test-host-token"},
                )
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                self.assertIn("webui", payload)
                self.assertEqual(payload["local_env"]["IMAGE_API_MODEL"], "model-from-mounted-env")
                conn.close()

                save = HTTPConnection(host, port, timeout=5)
                save.request(
                    "POST",
                    "/admin/api/config",
                    body=json.dumps({"owned_fields": {"IMAGE_MODULE_ENABLED": "true"}}),
                    headers={
                        "Authorization": "Bearer test-host-token",
                        "Content-Type": "application/json",
                    },
                )
                save_response = save.getresponse()
                self.assertEqual(save_response.status, 200)
                save_payload = json.loads(save_response.read().decode("utf-8"))
                self.assertTrue(save_payload["ok"])
                self.assertTrue((Path(tmp) / "config_webUI" / "current.json").is_file())
                save.close()
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
                if previous_webui_dir is None:
                    os.environ.pop("WEBUI_CONFIG_DIR", None)
                else:
                    os.environ["WEBUI_CONFIG_DIR"] = previous_webui_dir
                if previous_agent_env_dir is None:
                    os.environ.pop("AGENT_ENV_DIR", None)
                else:
                    os.environ["AGENT_ENV_DIR"] = previous_agent_env_dir
                if previous_image_model is not None:
                    os.environ["IMAGE_API_MODEL"] = previous_image_model

    def test_admin_config_can_save_matrix_agents(self) -> None:
        services, registry, dispatcher = fresh_gateway()
        with tempfile.TemporaryDirectory() as tmp:
            previous = {
                "WEBUI_CONFIG_DIR": os.environ.get("WEBUI_CONFIG_DIR"),
                "AGENT_CONFIG_DIR": os.environ.get("AGENT_CONFIG_DIR"),
                "AGENT_ENV_DIR": os.environ.get("AGENT_ENV_DIR"),
            }
            os.environ["WEBUI_CONFIG_DIR"] = str(Path(tmp) / "config_webUI")
            os.environ["AGENT_CONFIG_DIR"] = str(Path(tmp) / "config" / "agent")
            os.environ["AGENT_ENV_DIR"] = str(Path(tmp))
            httpd = GatewayHTTPServer(
                ("127.0.0.1", 0),
                GatewayRequestHandler,
                services=services,
                registry=registry,
                dispatcher=dispatcher,
            )
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            host, port = httpd.server_address
            try:
                conn = HTTPConnection(host, port, timeout=5)
                conn.request(
                    "POST",
                    "/admin/api/config",
                    body=json.dumps(
                        {
                            "owned_fields": {"MATRIX_MODULE_ENABLED": "true"},
                            "agents": [
                                {
                                    "name": "agent_web",
                                    "caller": {
                                        "gateway_token": "gateway-token",
                                        "shared_artifact_read": False,
                                    },
                                    "matrix": {
                                        "account": "agent_web",
                                        "access_token": "matrix-token",
                                    },
                                    "high_risk_tools": ["matrix_send_text"],
                                }
                            ],
                        }
                    ),
                    headers={
                        "Authorization": "Bearer test-host-token",
                        "Content-Type": "application/json",
                    },
                )
                response = conn.getresponse()
                self.assertEqual(response.status, 200)
                payload = json.loads(response.read().decode("utf-8"))
                self.assertTrue(payload["ok"])
                self.assertEqual(payload["webui"]["owned_fields"]["ENABLED_AGENTS"], "agent_web")
                self.assertTrue((Path(tmp) / "config" / "agent" / "config.agent.agent_web.yaml").is_file())
                env_text = (Path(tmp) / ".env.agent.agent_web").read_text(encoding="utf-8")
                self.assertIn("GATEWAY_TOKEN_AGENT_WEB=gateway-token", env_text)
                self.assertIn("AGENT_WEB_MATRIX_ACCESS_TOKEN=matrix-token", env_text)
                conn.close()
            finally:
                httpd.shutdown()
                httpd.server_close()
                thread.join(timeout=5)
                for key, value in previous.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


def _read_sse_event(response) -> dict[str, str]:
    event = ""
    data: list[str] = []
    while True:
        raw = response.fp.readline()
        if not raw:
            raise AssertionError("SSE stream closed before an event was received")
        line = raw.decode("utf-8").rstrip("\n")
        if line.endswith("\r"):
            line = line[:-1]
        if line == "":
            if event or data:
                return {"event": event, "data": "\n".join(data)}
            continue
        if line.startswith("event: "):
            event = line[len("event: ") :]
        elif line.startswith("data: "):
            data.append(line[len("data: ") :])


if __name__ == "__main__":
    unittest.main()
