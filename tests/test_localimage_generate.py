from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error

from core.errors import INVALID_ARGUMENT, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE
from core.ids import new_request_id
from core.policy import CallerIdentity
from core.time import utc_now
from modules.localimage.background import reconcile_stale_localimage_jobs
from modules.localimage.providers.comfyui import ComfyUIProvider
from modules.localimage.service import LocalImageGenerationService, prepare_local_image_generate
from tests.helpers import fresh_localimage_gateway
from transport.request_context import RequestContext

PNG_BYTES = b"\x89PNG\r\n\x1a\nlocal-image-test"


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


class LocalImageGenerateTests(unittest.TestCase):
    def test_registered_schema_exposes_semantic_enums_only(self) -> None:
        _, registry, _ = fresh_localimage_gateway()
        tools = {tool["name"]: tool for tool in registry.list_tools()}

        props = tools["local_image_generate"]["input_schema"]["properties"]
        serialized = json.dumps(tools["local_image_generate"]["input_schema"])

        self.assertEqual(props["prompt"]["maxLength"], 100)
        self.assertEqual(props["size"]["enum"], ["1024x1024", "1280x720", "720x1280"])
        self.assertEqual(props["quality"]["enum"], ["draft", "standard", "high"])
        self.assertEqual(props["style"]["enum"], ["default", "anime"])
        self.assertEqual(props["output_format"]["enum"], ["png", "jpeg", "webp"])
        self.assertNotIn("base_url", serialized)
        self.assertNotIn("workflow_path", serialized)
        self.assertNotIn("node_mappings", serialized)

    def test_prepare_injects_workflow_values(self) -> None:
        services, _, _ = fresh_localimage_gateway()
        prepared = prepare_local_image_generate(
            {
                "prompt": "draw a quiet room",
                "negative_prompt": "watermark",
                "size": "1280x720",
                "quality": "draft",
                "style": "default",
                "seed": 42,
                "output_format": "webp",
            },
            make_context(services),
        )

        self.assertEqual(prepared.workflow["6"]["inputs"]["text"], "draw a quiet room")
        self.assertEqual(prepared.workflow["7"]["inputs"]["text"], "watermark")
        self.assertEqual(prepared.workflow["5"]["inputs"]["width"], 1280)
        self.assertEqual(prepared.workflow["5"]["inputs"]["height"], 720)
        self.assertEqual(prepared.workflow["3"]["inputs"]["seed"], 42)
        self.assertEqual(prepared.workflow["3"]["inputs"]["steps"], 8)
        self.assertEqual(prepared.workflow["4"]["inputs"]["ckpt_name"], "test-checkpoint.safetensors")
        self.assertEqual(prepared.workflow["9"]["inputs"]["filename_prefix"], "localimage_webp")

    def test_prepare_injects_anima_workflow_values(self) -> None:
        services, _, _ = fresh_localimage_gateway()
        config = services.config.raw["modules"]["localimage"]
        config["comfyui"]["workflow_path"] = "./config/comfyui/anima_text_to_image.example.json"
        config["comfyui"]["checkpoint"] = ""
        config["comfyui"]["unet_name"] = "miaomiaoRealskin_anima10.safetensors"
        config["comfyui"]["clip_name"] = "miaomiaoRealskin_anima10_txt.safetensors"
        config["comfyui"]["vae_name"] = "qwen_image_vae.safetensors"
        config["comfyui"]["node_mappings"] = {
            "positive_prompt": "11",
            "negative_prompt": "12",
            "latent_image": "28",
            "sampler": "19",
            "save_image": "46",
        }

        prepared = prepare_local_image_generate(
            {
                "prompt": "draw an anime portrait",
                "negative_prompt": "watermark",
                "size": "720x1280",
                "quality": "standard",
                "seed": 99,
            },
            make_context(services),
        )

        self.assertEqual(prepared.workflow["11"]["inputs"]["text"], "draw an anime portrait")
        self.assertEqual(prepared.workflow["12"]["inputs"]["text"], "watermark")
        self.assertEqual(prepared.workflow["28"]["inputs"]["width"], 720)
        self.assertEqual(prepared.workflow["28"]["inputs"]["height"], 1280)
        self.assertEqual(prepared.workflow["19"]["inputs"]["seed"], 99)
        self.assertEqual(prepared.workflow["44"]["inputs"]["unet_name"], "miaomiaoRealskin_anima10.safetensors")
        self.assertEqual(prepared.workflow["63"]["inputs"]["clip_name"], "miaomiaoRealskin_anima10_txt.safetensors")
        self.assertEqual(prepared.workflow["15"]["inputs"]["vae_name"], "qwen_image_vae.safetensors")
        self.assertEqual(prepared.workflow["46"]["inputs"]["filename_prefix"], "localimage_png")

    def test_service_persists_comfyui_output_as_artifact(self) -> None:
        services, _, _ = fresh_localimage_gateway()
        server = ThreadingHTTPServer(("127.0.0.1", 0), ComfyUIHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        provider = ComfyUIProvider(base_url=f"http://{host}:{port}", timeout_seconds=2, poll_interval_seconds=0.01, max_wait_seconds=2)
        ctx = make_context(services)
        try:
            result = asyncio.run(
                LocalImageGenerationService(provider).generate(
                    {"prompt": "draw", "size": "1024x1024", "quality": "standard", "output_format": "png"},
                    ctx,
                )
            )
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        artifact = services.artifacts.get(result["artifact"]["id"], ctx.caller)
        self.assertTrue(result["ok"])
        self.assertEqual(artifact.mime_type, "image/png")
        self.assertEqual(artifact.metadata["provider"], "comfyui")
        self.assertNotIn("workflow", str(result).lower())
        self.assertNotIn(str(port), str(result))

    def test_invalid_arguments_map_to_invalid_argument(self) -> None:
        _, _, dispatcher = fresh_localimage_gateway()

        bad_size = asyncio.run(
            dispatcher.dispatch(
                "local_image_generate",
                {"prompt": "draw", "size": "4096x4096"},
                authorization="Bearer test-host-token",
            )
        )
        bad_seed = asyncio.run(
            dispatcher.dispatch(
                "local_image_generate",
                {"prompt": "draw", "seed": -1},
                authorization="Bearer test-host-token",
            )
        )

        self.assertEqual(bad_size["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(bad_seed["error"]["code"], INVALID_ARGUMENT)

    def test_background_generation_returns_accepted_then_succeeds(self) -> None:
        ComfyUIHTTPRequestHandler.reset()
        server = ThreadingHTTPServer(("127.0.0.1", 0), ComfyUIHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        services, _, dispatcher = fresh_localimage_gateway()
        services.config.raw["modules"]["localimage"]["comfyui"]["base_url"] = f"http://{host}:{port}"
        try:
            result = asyncio.run(
                dispatcher.dispatch(
                    "local_image_generate",
                    {"prompt": "draw a local image", "seed": 7},
                    authorization="Bearer test-host-token",
                )
            )
            job = wait_for_job(services, result["job_id"], "succeeded")
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(job.status, "succeeded")
        self.assertEqual(len(job.artifact_ids), 1)
        self.assertEqual(ComfyUIHTTPRequestHandler.prompt_body["prompt"]["3"]["inputs"]["seed"], 7)

    def test_background_deadline_marks_job_failed(self) -> None:
        SlowComfyUIHTTPRequestHandler.reset()
        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowComfyUIHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        services, _, dispatcher = fresh_localimage_gateway()
        services.config.raw["modules"]["localimage"]["comfyui"]["base_url"] = f"http://{host}:{port}"
        services.config.raw["modules"]["localimage"]["total_timeout_seconds"] = 0.1
        try:
            result = asyncio.run(
                dispatcher.dispatch(
                    "local_image_generate",
                    {"prompt": "draw slowly"},
                    authorization="Bearer test-host-token",
                )
            )
            job = wait_for_job(services, result["job_id"], "failed")
        finally:
            SlowComfyUIHTTPRequestHandler.release_event.set()
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(job.status, "failed")
        self.assertEqual(job.error_code, PROVIDER_TIMEOUT)

    def test_stale_local_image_jobs_are_reconciled(self) -> None:
        services, _, _ = fresh_localimage_gateway()
        services.config.raw["modules"]["localimage"]["total_timeout_seconds"] = 1
        job = services.jobs.create(
            request_id="req_stale",
            caller_id="host_assistant",
            tool_name="local_image_generate",
            input_summary={"prompt": {"prefix": "draw", "length": 4}},
        )
        services.jobs.mark_running(job.id)
        audit_id = services.audit.start(
            request_id="req_stale",
            job_id=job.id,
            caller_id="host_assistant",
            tool_name="local_image_generate",
            risk_level="medium",
            arguments={"prompt": "draw"},
        )
        old = (utc_now().replace(year=2000)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with services.artifacts.conn:
            services.artifacts.conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (old, job.id))

        reconciled = reconcile_stale_localimage_jobs(services)
        updated = services.jobs.get(job.id, CallerIdentity("host_assistant", "admin", True))
        audit = services.artifacts.conn.execute("SELECT status, error_code FROM audit_events WHERE id = ?", (audit_id,)).fetchone()

        self.assertEqual(reconciled, [job.id])
        self.assertEqual(updated.status, "failed")
        self.assertEqual(updated.error_code, PROVIDER_TIMEOUT)
        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["error_code"], PROVIDER_TIMEOUT)


class ComfyUIProviderTests(unittest.TestCase):
    def test_timeout_mapping(self) -> None:
        def timed_out(req, timeout):
            raise error.URLError(socket.timeout("slow"))

        provider = ComfyUIProvider(base_url="http://127.0.0.1:1", opener=timed_out)
        with self.assertRaises(Exception) as raised:
            provider.generate({"1": {"inputs": {}}})
        self.assertEqual(raised.exception.code, PROVIDER_TIMEOUT)

    def test_empty_outputs_mapping(self) -> None:
        EmptyComfyUIHTTPRequestHandler.reset()
        server = ThreadingHTTPServer(("127.0.0.1", 0), EmptyComfyUIHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        provider = ComfyUIProvider(base_url=f"http://{host}:{port}", timeout_seconds=2, poll_interval_seconds=0.01, max_wait_seconds=1)
        try:
            with self.assertRaises(Exception) as raised:
                provider.generate({"1": {"inputs": {}}})
        finally:
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()
        self.assertEqual(raised.exception.code, PROVIDER_UNAVAILABLE)


class ComfyUIHTTPRequestHandler(BaseHTTPRequestHandler):
    prompt_body = {}

    @classmethod
    def reset(cls) -> None:
        cls.prompt_body = {}

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).prompt_body = json.loads(body.decode("utf-8"))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"prompt_id": "prompt-test"}).encode("utf-8"))

    def do_GET(self) -> None:
        if self.path.startswith("/history/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {
                        "prompt-test": {
                            "status": {"status_str": "success", "completed": True},
                            "outputs": {"9": {"images": [{"filename": "out.png", "subfolder": "", "type": "output"}]}},
                        }
                    }
                ).encode("utf-8")
            )
            return
        if self.path.startswith("/view"):
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.end_headers()
            self.wfile.write(PNG_BYTES)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


class SlowComfyUIHTTPRequestHandler(BaseHTTPRequestHandler):
    release_event = threading.Event()

    @classmethod
    def reset(cls) -> None:
        cls.release_event = threading.Event()

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"prompt_id": "prompt-slow"}).encode("utf-8"))

    def do_GET(self) -> None:
        type(self).release_event.wait(timeout=5)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({}).encode("utf-8"))

    def log_message(self, format, *args):
        return


class EmptyComfyUIHTTPRequestHandler(BaseHTTPRequestHandler):
    @classmethod
    def reset(cls) -> None:
        return

    def do_POST(self) -> None:
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"prompt_id": "prompt-empty"}).encode("utf-8"))

    def do_GET(self) -> None:
        if self.path.startswith("/history/"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"prompt-empty": {"outputs": {"9": {"images": []}}}}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    unittest.main()
