from __future__ import annotations

import asyncio
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from tools.dispatcher import ToolDispatcher
from tools.registry import ToolRegistry
from transport.artifact_routes import serve_artifact
from transport.request_context import CoreServices


class GatewayHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, *, services: CoreServices, registry: ToolRegistry, dispatcher: ToolDispatcher):
        super().__init__(server_address, RequestHandlerClass)
        self.services = services
        self.registry = registry
        self.dispatcher = dispatcher


class GatewayRequestHandler(BaseHTTPRequestHandler):
    server: GatewayHTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/healthz":
            self._json({"ok": True, "server": self.server.services.config.server["name"]})
            return
        if parsed.path == "/readyz":
            self._json({"ok": True, "modules": self.server.services.config.enabled_modules()})
            return
        if parsed.path == self.server.services.config.server.get("mcp_path", "/mcp"):
            self._json({"ok": True, "server": "home", "tools": self.server.registry.list_tools()})
            return
        artifact_prefix = self.server.services.config.server.get("artifact_path", "/artifacts").rstrip("/") + "/"
        if parsed.path.startswith(artifact_prefix):
            serve_artifact(self, self.server.services, parsed.path[len(artifact_prefix):])
            return
        self._json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != self.server.services.config.server.get("mcp_path", "/mcp"):
            self._json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(body.decode("utf-8") or "{}")
            if payload.get("method") == "tools/list":
                self._json({"ok": True, "tools": self.server.registry.list_tools()})
                return
            tool_name, arguments, metadata = _parse_mcp_payload(payload)
            result = asyncio.run(
                self.server.dispatcher.dispatch(
                    tool_name,
                    arguments,
                    authorization=self.headers.get("Authorization"),
                    metadata=metadata,
                    remote_addr=self.client_address[0],
                )
            )
            self._json(result)
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "invalid json"}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _parse_mcp_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if payload.get("method") == "tools/call":
        params = payload.get("params", {})
        return params.get("name", ""), params.get("arguments", {}) or {}, payload.get("metadata", {})
    return payload.get("tool", ""), payload.get("arguments", {}) or {}, payload.get("metadata", {})


def create_http_server(services: CoreServices, registry: ToolRegistry, dispatcher: ToolDispatcher) -> GatewayHTTPServer:
    host = services.config.server.get("host", "127.0.0.1")
    port = int(services.config.server.get("port", 8787))
    return GatewayHTTPServer((host, port), GatewayRequestHandler, services=services, registry=registry, dispatcher=dispatcher)
