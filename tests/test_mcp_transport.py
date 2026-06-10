from __future__ import annotations

import asyncio
import json
import threading
import unittest
from http.client import HTTPConnection

from core.errors import POLICY_DENIED
from tests.helpers import fresh_gateway
from transport.mcp_server import GatewayHTTPServer, GatewayRequestHandler


class McpTransportTests(unittest.TestCase):
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
