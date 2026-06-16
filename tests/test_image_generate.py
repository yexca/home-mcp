from __future__ import annotations

import asyncio
import base64
import json
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error

from core.errors import (
    INVALID_ARGUMENT,
    PROVIDER_REJECTED,
    PROVIDER_TIMEOUT,
    PROVIDER_UNAVAILABLE,
    RATE_LIMITED,
)
from core.ids import new_request_id
from core.policy import CallerIdentity
from core.time import utc_now
from modules.image.background import reconcile_stale_image_jobs
from modules.image.providers.openai_compatible import OpenAICompatibleImageProvider, ProviderImageOutput, ProviderImageResponse
from modules.image.service import DownloadedImage, ImageGenerationService, download_image_url
from tests.helpers import fresh_image_gateway
from transport.request_context import RequestContext

PNG_BYTES = b"\x89PNG\r\n\x1a\nunit-test-image"


class FakeProvider:
    model = "test-image-model"

    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return ProviderImageResponse(outputs=self.outputs, usage={"total_tokens": 1})


def fake_downloader(url, image_config):
    return DownloadedImage(data=PNG_BYTES, mime_type="image/png", source_host="cdn.example.test")


def make_context(services) -> RequestContext:
    return RequestContext(
        request_id=new_request_id(),
        caller=CallerIdentity("host_assistant", "admin", True),
        config=services.config,
        artifacts=services.artifacts,
        jobs=services.jobs,
        policy=services.policy,
        audit=services.audit,
        limits=services.limits,
        job_id=None,
        metadata={},
    )


def wait_for_job(services, job_id: str, status: str | None = None, timeout: float = 3):
    caller = CallerIdentity("host_assistant", "admin", True)
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = services.jobs.get(job_id, caller)
        if status and last.status == status:
            return last
        if not status and last.status in {"succeeded", "failed", "canceled"}:
            return last
        time.sleep(0.02)
    return last


def wait_for_audit(services, job_id: str, status: str, timeout: float = 3):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = services.artifacts.conn.execute(
            "SELECT status, error_code FROM audit_events WHERE job_id = ?",
            (job_id,),
        ).fetchone()
        if last and last["status"] == status:
            return last
        time.sleep(0.02)
    return last


class ImageGenerateServiceTests(unittest.TestCase):
    def test_registered_schema_exposes_configured_image_enums(self) -> None:
        _, registry, _ = fresh_image_gateway()
        tools = {tool["name"]: tool for tool in registry.list_tools()}

        generate_props = tools["image_generate"]["input_schema"]["properties"]
        edit_props = tools["image_edit"]["input_schema"]["properties"]

        self.assertEqual(generate_props["prompt"]["maxLength"], 100)
        self.assertEqual(
            generate_props["size"]["enum"],
            [
                "auto",
                "1024x1024",
                "1024x1536",
                "1536x1024",
                "1280x720",
                "720x1280",
                "1920x1080",
                "1080x1920",
                "2560x1440",
                "1440x2560",
                "3840x2160",
                "2160x3840",
            ],
        )
        self.assertEqual(generate_props["quality"]["enum"], ["auto", "high"])
        self.assertEqual(generate_props["output_format"]["enum"], ["png", "jpeg", "webp"])
        self.assertEqual(edit_props["size"]["enum"], generate_props["size"]["enum"])
        self.assertEqual(edit_props["quality"]["enum"], generate_props["quality"]["enum"])

    def test_url_response_creates_image_artifact_without_provider_url(self) -> None:
        services, _, _ = fresh_image_gateway()
        provider = FakeProvider([ProviderImageOutput("url", url="https://cdn.example.test/image.png")])
        result = asyncio.run(
            ImageGenerationService(provider, downloader=fake_downloader).generate(
                {
                    "prompt": "draw a small test card",
                    "size": "auto",
                    "quality": "auto",
                    "output_format": "png",
                    "n": 1,
                },
                make_context(services),
            )
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["artifact"]["mime_type"], "image/png")
        self.assertNotIn("https://cdn.example.test/image.png", str(result))
        self.assertEqual(provider.calls[0]["size"], "auto")

    def test_base64_response_creates_downloadable_artifact_without_b64_payload(self) -> None:
        services, _, _ = fresh_image_gateway()
        encoded = base64.b64encode(PNG_BYTES).decode("ascii")
        provider = FakeProvider([ProviderImageOutput("b64_json", b64_json=encoded)])
        ctx = make_context(services)
        result = asyncio.run(
            ImageGenerationService(provider).generate(
                {"prompt": "draw", "size": "1024x1024", "quality": "high", "output_format": "png", "n": 1},
                ctx,
            )
        )

        artifact = services.artifacts.get(result["artifact"]["id"], ctx.caller)
        self.assertEqual(artifact.mime_type, "image/png")
        self.assertNotIn(encoded, str(result))

    def test_invalid_arguments_map_to_invalid_argument(self) -> None:
        services, _, dispatcher = fresh_image_gateway()

        empty_prompt = asyncio.run(
            dispatcher.dispatch(
                "image_generate",
                {"prompt": "   "},
                authorization="Bearer test-host-token",
            )
        )
        bad_size = asyncio.run(
            dispatcher.dispatch(
                "image_generate",
                {"prompt": "draw", "size": "4096x4096"},
                authorization="Bearer test-host-token",
            )
        )
        bad_n = asyncio.run(
            dispatcher.dispatch(
                "image_generate",
                {"prompt": "draw", "n": 2},
                authorization="Bearer test-host-token",
            )
        )

        self.assertEqual(empty_prompt["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(bad_size["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(bad_n["error"]["code"], INVALID_ARGUMENT)

    def test_provider_url_download_safety(self) -> None:
        services, _, _ = fresh_image_gateway()
        ctx = make_context(services)
        http_provider = FakeProvider([ProviderImageOutput("url", url="http://cdn.example.test/image.png")])
        host_provider = FakeProvider([ProviderImageOutput("url", url="https://evil.example.test/image.png")])

        with self.assertRaisesRegex(Exception, "scheme"):
            asyncio.run(ImageGenerationService(http_provider).generate({"prompt": "draw"}, ctx))
        with self.assertRaisesRegex(Exception, "host"):
            asyncio.run(ImageGenerationService(host_provider).generate({"prompt": "draw"}, ctx))

    def test_download_image_url_sends_user_agent_and_accepts_image_host(self) -> None:
        image_server = ThreadingHTTPServer(("127.0.0.1", 0), ImageDownloadHTTPRequestHandler)
        thread = threading.Thread(target=image_server.serve_forever, daemon=True)
        thread.start()
        host, port = image_server.server_address
        try:
            downloaded = download_image_url(
                f"http://{host}:{port}/image.png?signature=secret",
                {
                    "allow_http_image_urls": True,
                    "max_download_bytes": 1024,
                    "openai_compatible": {
                        "timeout_seconds": 2,
                        "allowed_image_url_hosts": [host],
                    },
                },
            )
        finally:
            image_server.shutdown()
            thread.join(timeout=2)
            image_server.server_close()

        self.assertEqual(downloaded.data, PNG_BYTES)
        self.assertEqual(downloaded.mime_type, "image/png")
        self.assertIn("home-mcp-gateway/0.2.1", ImageDownloadHTTPRequestHandler.user_agent)
        self.assertIn("*/*", ImageDownloadHTTPRequestHandler.accept_header)

    def test_download_image_url_http_error_keeps_status_without_signed_url(self) -> None:
        image_server = ThreadingHTTPServer(("127.0.0.1", 0), ImageRejectHTTPRequestHandler)
        thread = threading.Thread(target=image_server.serve_forever, daemon=True)
        thread.start()
        host, port = image_server.server_address
        signed_url = f"http://{host}:{port}/image.png?signature=secret"
        try:
            with self.assertRaises(Exception) as raised:
                download_image_url(
                    signed_url,
                    {
                        "allow_http_image_urls": True,
                        "max_download_bytes": 1024,
                        "openai_compatible": {
                            "timeout_seconds": 2,
                            "allowed_image_url_hosts": [host],
                        },
                    },
                )
        finally:
            image_server.shutdown()
            thread.join(timeout=2)
            image_server.server_close()

        self.assertEqual(raised.exception.code, PROVIDER_UNAVAILABLE)
        self.assertIn("HTTP 403", raised.exception.message)
        self.assertNotIn(signed_url, raised.exception.message)
        self.assertNotIn("signature=secret", raised.exception.message)

    def test_dispatcher_audit_does_not_store_image_api_key(self) -> None:
        services, _, dispatcher = fresh_image_gateway()
        result = asyncio.run(
            dispatcher.dispatch(
                "image_generate",
                {"prompt": "draw"},
                authorization="Bearer test-host-token",
            )
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")
        job = wait_for_job(services, result["job_id"], "failed")
        rows = services.artifacts.conn.execute("SELECT input_summary_json, error_message FROM audit_events").fetchall()

        self.assertEqual(job.error_code, PROVIDER_UNAVAILABLE)
        self.assertNotIn("test-image-api-key", str(result))
        self.assertNotIn("test-image-api-key", str([tuple(row) for row in rows]))

    def test_image_generate_returns_job_before_provider_completion(self) -> None:
        AsyncProviderHTTPRequestHandler.reset()
        server = ThreadingHTTPServer(("127.0.0.1", 0), AsyncProviderHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        services, _, dispatcher = fresh_image_gateway()
        services.config.raw["modules"]["image"]["openai_compatible"]["base_url"] = f"http://{host}:{port}"
        try:
            started = time.monotonic()
            result = asyncio.run(
                dispatcher.dispatch(
                    "image_generate",
                    {"prompt": "draw a queued image"},
                    authorization="Bearer test-host-token",
                )
            )
            elapsed = time.monotonic() - started
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "accepted")
            self.assertLess(elapsed, 0.5)
            running = services.jobs.get(result["job_id"], CallerIdentity("host_assistant", "admin", True))
            self.assertEqual(running.status, "running")

            AsyncProviderHTTPRequestHandler.release_event.set()
            job = wait_for_job(services, result["job_id"], "succeeded")
        finally:
            AsyncProviderHTTPRequestHandler.release_event.set()
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(job.status, "succeeded")
        self.assertEqual(len(job.artifact_ids), 1)
        self.assertEqual(job.result_summary["status"], "succeeded")

    def test_image_generate_deadline_marks_job_failed(self) -> None:
        AsyncProviderHTTPRequestHandler.reset()
        server = ThreadingHTTPServer(("127.0.0.1", 0), AsyncProviderHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        services, _, dispatcher = fresh_image_gateway()
        services.config.raw["modules"]["image"]["openai_compatible"]["base_url"] = f"http://{host}:{port}"
        services.config.raw["modules"]["image"]["total_timeout_seconds"] = 0.1
        try:
            result = asyncio.run(
                dispatcher.dispatch(
                    "image_generate",
                    {"prompt": "draw a slow image"},
                    authorization="Bearer test-host-token",
                )
            )
            job = wait_for_job(services, result["job_id"], "failed")
            audit = wait_for_audit(services, result["job_id"], "failed")
        finally:
            AsyncProviderHTTPRequestHandler.release_event.set()
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error_code, PROVIDER_TIMEOUT)
        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["error_code"], PROVIDER_TIMEOUT)

    def test_stale_image_generate_jobs_are_reconciled(self) -> None:
        services, _, _ = fresh_image_gateway()
        services.config.raw["modules"]["image"]["total_timeout_seconds"] = 1
        job = services.jobs.create(
            request_id="req_stale",
            caller_id="host_assistant",
            tool_name="image_generate",
            input_summary={"prompt": {"prefix": "draw", "length": 4}},
        )
        services.jobs.mark_running(job.id)
        audit_id = services.audit.start(
            request_id="req_stale",
            job_id=job.id,
            caller_id="host_assistant",
            tool_name="image_generate",
            risk_level="medium",
            arguments={"prompt": "draw"},
        )
        old = (utc_now().replace(year=2000)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with services.artifacts.conn:
            services.artifacts.conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (old, job.id))

        reconciled = reconcile_stale_image_jobs(services)
        updated = services.jobs.get(job.id, CallerIdentity("host_assistant", "admin", True))
        audit = services.artifacts.conn.execute("SELECT status, error_code FROM audit_events WHERE id = ?", (audit_id,)).fetchone()

        self.assertEqual(reconciled, [job.id])
        self.assertEqual(updated.status, "failed")
        self.assertEqual(updated.error_code, PROVIDER_TIMEOUT)
        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["error_code"], PROVIDER_TIMEOUT)


class AsyncProviderHTTPRequestHandler(BaseHTTPRequestHandler):
    release_event = threading.Event()
    request_started = threading.Event()

    @classmethod
    def reset(cls) -> None:
        cls.release_event = threading.Event()
        cls.request_started = threading.Event()

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).request_started.set()
        type(self).release_event.wait(timeout=5)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"b64_json": base64.b64encode(PNG_BYTES).decode("ascii")}]}).encode("utf-8"))

    def log_message(self, format, *args):
        return


class ProviderHTTPRequestHandler(BaseHTTPRequestHandler):
    response_status = 200
    response_body = {"data": [{"b64_json": base64.b64encode(PNG_BYTES).decode("ascii")}]}
    request_body = {}
    auth_header = ""

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).request_body = json.loads(body.decode("utf-8"))
        type(self).auth_header = self.headers.get("Authorization", "")
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        payload = type(self).response_body
        if isinstance(payload, bytes):
            self.wfile.write(payload)
        else:
            self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        return


class OpenAICompatibleProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        ProviderHTTPRequestHandler.response_status = 200
        ProviderHTTPRequestHandler.response_body = {"data": [{"b64_json": base64.b64encode(PNG_BYTES).decode("ascii")}]}
        ProviderHTTPRequestHandler.request_body = {}
        ProviderHTTPRequestHandler.auth_header = ""
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ProviderHTTPRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.provider = OpenAICompatibleImageProvider(
            base_url=f"http://{host}:{port}",
            model="test-image-model",
            api_key="test-image-api-key",
            timeout_seconds=2,
        )

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_generate_sends_openai_compatible_json_body(self) -> None:
        response = self.provider.generate(prompt="draw", n=1, size="1024x1024", quality="auto", output_format="png")

        self.assertEqual(response.outputs[0].response_type, "b64_json")
        self.assertEqual(ProviderHTTPRequestHandler.request_body["model"], "test-image-model")
        self.assertEqual(ProviderHTTPRequestHandler.request_body["prompt"], "draw")
        self.assertEqual(ProviderHTTPRequestHandler.request_body["n"], 1)
        self.assertEqual(ProviderHTTPRequestHandler.request_body["size"], "1024x1024")
        self.assertEqual(ProviderHTTPRequestHandler.request_body["quality"], "auto")
        self.assertEqual(ProviderHTTPRequestHandler.request_body["output_format"], "png")
        self.assertEqual(ProviderHTTPRequestHandler.auth_header, "Bearer test-image-api-key")

    def test_http_status_error_mapping(self) -> None:
        cases = {
            401: PROVIDER_REJECTED,
            403: PROVIDER_REJECTED,
            429: RATE_LIMITED,
            500: PROVIDER_UNAVAILABLE,
        }
        for status, code in cases.items():
            ProviderHTTPRequestHandler.response_status = status
            with self.subTest(status=status), self.assertRaises(Exception) as raised:
                self.provider.generate(prompt="draw", n=1, size="1024x1024", quality="auto", output_format="png")
            self.assertEqual(raised.exception.code, code)

    def test_non_json_and_empty_data_mapping(self) -> None:
        ProviderHTTPRequestHandler.response_status = 200
        ProviderHTTPRequestHandler.response_body = b"not-json"
        with self.assertRaises(Exception) as non_json:
            self.provider.generate(prompt="draw", n=1, size="1024x1024", quality="auto", output_format="png")
        self.assertEqual(non_json.exception.code, PROVIDER_UNAVAILABLE)

        ProviderHTTPRequestHandler.response_body = {"data": []}
        with self.assertRaises(Exception) as empty:
            self.provider.generate(prompt="draw", n=1, size="1024x1024", quality="auto", output_format="png")
        self.assertEqual(empty.exception.code, PROVIDER_UNAVAILABLE)

    def test_timeout_mapping(self) -> None:
        def timed_out(req, timeout):
            raise error.URLError(socket.timeout("slow"))

        provider = OpenAICompatibleImageProvider(
            base_url="http://127.0.0.1:1",
            model="test-image-model",
            api_key="test-image-api-key",
            opener=timed_out,
        )
        with self.assertRaises(Exception) as raised:
            provider.generate(prompt="draw", n=1, size="1024x1024", quality="auto", output_format="png")
        self.assertEqual(raised.exception.code, PROVIDER_TIMEOUT)


class ImageDownloadHTTPRequestHandler(BaseHTTPRequestHandler):
    user_agent = ""
    accept_header = ""

    def do_GET(self) -> None:
        type(self).user_agent = self.headers.get("User-Agent", "")
        type(self).accept_header = self.headers.get("Accept", "")
        if type(self).user_agent != "home-mcp-gateway/0.2.1":
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()
        self.wfile.write(PNG_BYTES)

    def log_message(self, format, *args):
        return


class ImageRejectHTTPRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(403)
        self.end_headers()

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    unittest.main()
