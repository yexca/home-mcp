from __future__ import annotations

import asyncio
import json
import queue
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from tools.dispatcher import ToolDispatcher
from tools.registry import ToolRegistry
from transport.admin_routes import handle_admin_get, handle_admin_post, serve_webui
from transport.artifact_routes import serve_artifact
from transport.request_context import CoreServices


class GatewayHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, RequestHandlerClass, *, services: CoreServices, registry: ToolRegistry, dispatcher: ToolDispatcher):
        super().__init__(server_address, RequestHandlerClass)
        self.services = services
        self.registry = registry
        self.dispatcher = dispatcher
        self.sse_sessions: dict[str, SseSession] = {}


class SseSession:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.events: queue.Queue[tuple[str, dict[str, Any]] | None] = queue.Queue()
        self.closed = False

    def send(self, event: str, payload: dict[str, Any]) -> None:
        if not self.closed:
            self.events.put((event, payload))

    def close(self) -> None:
        self.closed = True
        self.events.put(None)


class GatewayRequestHandler(BaseHTTPRequestHandler):
    server: GatewayHTTPServer

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/webui/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if parsed.path == "/webui" or parsed.path.startswith("/webui/"):
            serve_webui(self, parsed.path)
            return
        if parsed.path.startswith("/admin/api/"):
            handle_admin_get(self, self.server.services, parsed.path)
            return
        if parsed.path == "/healthz":
            self._json({"ok": True, "server": self.server.services.config.server["name"]})
            return
        if parsed.path == "/readyz":
            self._json({"ok": True, "modules": self.server.services.config.enabled_modules()})
            return
        if parsed.path == self.server.services.config.server.get("mcp_path", "/mcp"):
            self._serve_mcp_sse()
            return
        artifact_prefix = self.server.services.config.server.get("artifact_path", "/artifacts").rstrip("/") + "/"
        if parsed.path.startswith(artifact_prefix):
            serve_artifact(self, self.server.services, parsed.path[len(artifact_prefix):], parsed.query)
            return
        self._json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/admin/api/"):
            handle_admin_post(self, self.server.services, parsed.path)
            return
        mcp_path = self.server.services.config.server.get("mcp_path", "/mcp")
        if parsed.path == f"{mcp_path.rstrip('/')}/messages":
            self._handle_sse_message(parsed)
            return
        if parsed.path != mcp_path:
            self._json({"ok": False, "error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(body.decode("utf-8") or "{}")
            if "jsonrpc" in payload:
                response = asyncio.run(self._handle_jsonrpc_request(payload))
                status = HTTPStatus.ACCEPTED if response is None else HTTPStatus.OK
                self._json(response or {"ok": True}, status=status)
                return
            if payload.get("method") == "tools/list":
                self._json({"ok": True, "tools": self.server.registry.list_tools()})
                return
            tool_name, arguments, metadata = _parse_mcp_payload(payload)
            result = asyncio.run(
                self.server.dispatcher.dispatch(
                    tool_name,
                    arguments,
                    authorization=self.headers.get("Authorization"),
                    metadata=self._with_request_metadata(metadata),
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

    def _serve_mcp_sse(self) -> None:
        session_id = secrets.token_urlsafe(16)
        session = SseSession(session_id)
        self.server.sse_sessions[session_id] = session
        message_path = f"{self.server.services.config.server.get('mcp_path', '/mcp').rstrip('/')}/messages?sessionId={session_id}"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            self._write_sse_event("endpoint", message_path)
            while not session.closed:
                try:
                    item = session.events.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    continue
                if item is None:
                    break
                event, payload = item
                self._write_sse_event(event, payload)
        except (BrokenPipeError, ConnectionError):
            pass
        finally:
            session.close()
            self.server.sse_sessions.pop(session_id, None)

    def _write_sse_event(self, event: str, payload: Any) -> None:
        data = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=True)
        self.wfile.write(f"event: {event}\n".encode("utf-8"))
        for line in data.splitlines() or [""]:
            self.wfile.write(f"data: {line}\n".encode("utf-8"))
        self.wfile.write(b"\n")
        self.wfile.flush()

    def _handle_sse_message(self, parsed) -> None:
        params = parse_qs(parsed.query)
        session_id = (params.get("sessionId") or params.get("session_id") or [""])[0]
        session = self.server.sse_sessions.get(session_id)
        if not session:
            self._json({"ok": False, "error": "unknown SSE session"}, status=HTTPStatus.NOT_FOUND)
            return
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or "0"))
            payload = json.loads(body.decode("utf-8") or "{}")
            response = asyncio.run(self._handle_jsonrpc_request(payload))
            if response is not None:
                session.send("message", response)
            self.send_response(HTTPStatus.ACCEPTED)
            self.send_header("Content-Length", "0")
            self.end_headers()
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "invalid json"}, status=HTTPStatus.BAD_REQUEST)

    async def _handle_jsonrpc_request(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        request_id = payload.get("id")
        method = payload.get("method")
        if request_id is None:
            return None
        if method == "initialize":
            return _jsonrpc_result(
                request_id,
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {
                        "name": self.server.services.config.server.get("name", "home"),
                        "version": str(self.server.services.config.server.get("version", "0.2.2")),
                    },
                },
            )
        if method == "ping":
            return _jsonrpc_result(request_id, {})
        if method == "tools/list":
            return _jsonrpc_result(request_id, {"tools": _mcp_tools(self.server.registry.list_tools())})
        if method == "tools/call":
            params = payload.get("params", {}) if isinstance(payload.get("params"), dict) else {}
            result = await self.server.dispatcher.dispatch(
                str(params.get("name", "")),
                params.get("arguments", {}) or {},
                authorization=self.headers.get("Authorization"),
                metadata=self._with_request_metadata(
                    payload.get("metadata", {}) if isinstance(payload.get("metadata"), dict) else {}
                ),
                remote_addr=self.client_address[0],
            )
            return _jsonrpc_result(request_id, _mcp_tool_result(result))
        return _jsonrpc_error(request_id, -32601, f"unsupported method: {method}")

    def _with_request_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        merged = dict(metadata)
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host")
        if host:
            proto = self.headers.get("X-Forwarded-Proto") or "http"
            merged["request_base_url"] = f"{proto}://{host}"
        return merged


def _parse_mcp_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if payload.get("method") == "tools/call":
        params = payload.get("params", {})
        return params.get("name", ""), params.get("arguments", {}) or {}, payload.get("metadata", {})
    return payload.get("tool", ""), payload.get("arguments", {}) or {}, payload.get("metadata", {})


def _jsonrpc_result(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _jsonrpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _mcp_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": tool["name"],
            "title": tool.get("title"),
            "description": tool.get("description", ""),
            "inputSchema": tool.get("input_schema", {}),
        }
        for tool in tools
    ]


def _mcp_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    text_payload = {key: value for key, value in result.items() if key != "_mcp_content"}
    content: list[dict[str, Any]] = [{"type": "text", "text": json.dumps(text_payload, ensure_ascii=True, sort_keys=True)}]
    for item in result.get("_mcp_content") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "image" and isinstance(item.get("data"), str) and isinstance(item.get("mimeType"), str):
            content.append({"type": "image", "data": item["data"], "mimeType": item["mimeType"]})
    return {
        "content": content,
        "isError": not bool(result.get("ok", False)),
    }


def create_http_server(services: CoreServices, registry: ToolRegistry, dispatcher: ToolDispatcher) -> GatewayHTTPServer:
    host = services.config.server.get("host", "127.0.0.1")
    port = int(services.config.server.get("port", 8787))
    return GatewayHTTPServer((host, port), GatewayRequestHandler, services=services, registry=registry, dispatcher=dispatcher)
