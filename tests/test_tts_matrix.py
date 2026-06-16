from __future__ import annotations

import asyncio
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from core.errors import ARTIFACT_FORBIDDEN, INVALID_ARGUMENT, POLICY_DENIED, PROVIDER_TIMEOUT, UNSUPPORTED_MEDIA_TYPE
from core.ids import new_request_id
from core.policy import CallerIdentity
from core.time import utc_now
from modules.tts.background import reconcile_stale_tts_jobs
from modules.matrix.providers.http_client import MatrixHttpClient
from modules.tts.providers.local_http import LocalHttpTTSProvider, ProviderAudioResponse
from modules.tts.service import TTSSynthesisService
from tests.helpers import fresh_phase4_gateway
from transport.request_context import RequestContext

AUDIO_BYTES = b"RIFFphase4-audio"
IMAGE_BYTES = b"\x89PNG\r\n\x1a\nphase4-image"


def make_context(services, caller: CallerIdentity | None = None) -> RequestContext:
    return RequestContext(
        request_id=new_request_id(),
        caller=caller or CallerIdentity("host_assistant", "admin", True),
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


class FakeTTSProvider:
    def __init__(self, mime_type: str = "audio/wav") -> None:
        self.mime_type = mime_type
        self.calls = []

    def synthesize(self, **kwargs):
        self.calls.append(kwargs)
        return ProviderAudioResponse(
            data=AUDIO_BYTES,
            mime_type=self.mime_type,
            provider="fake",
            voice=kwargs["voice"],
            language=kwargs["language"],
            format=kwargs["format"],
        )


class TTSSynthesisTests(unittest.TestCase):
    def test_tts_synthesize_outputs_audio_artifact(self) -> None:
        services, _, _ = fresh_phase4_gateway()
        provider = FakeTTSProvider()
        result = asyncio.run(
            TTSSynthesisService(provider).synthesize(
                {"text": "hello", "voice": "calm", "language": "en-US", "format": "wav", "speed": 1.25},
                make_context(services),
            )
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["artifact"]["kind"], "audio")
        self.assertEqual(result["artifact"]["mime_type"], "audio/wav")
        self.assertEqual(provider.calls[0]["speed"], 1.25)
        self.assertNotIn(AUDIO_BYTES.decode("latin1"), str(result))

    def test_tts_invalid_text_speed_and_mime(self) -> None:
        services, _, dispatcher = fresh_phase4_gateway()
        overlong = asyncio.run(
            dispatcher.dispatch(
                "tts_synthesize",
                {"text": "x" * 33},
                authorization="Bearer test-host-token",
            )
        )
        bad_speed = asyncio.run(
            dispatcher.dispatch(
                "tts_synthesize",
                {"text": "hello", "speed": 2.5},
                authorization="Bearer test-host-token",
            )
        )
        bad_mime_provider = FakeTTSProvider("audio/flac")

        with self.assertRaises(Exception) as bad_mime:
            asyncio.run(TTSSynthesisService(bad_mime_provider).synthesize({"text": "hello"}, make_context(services)))

        self.assertEqual(overlong["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(bad_speed["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(bad_mime.exception.code, UNSUPPORTED_MEDIA_TYPE)

    def test_tts_synthesize_returns_accepted_and_completes_through_shared_tools(self) -> None:
        services, _, dispatcher = fresh_phase4_gateway()
        accepted = asyncio.run(
            dispatcher.dispatch(
                "tts_synthesize",
                {"text": "hello", "voice": "calm", "language": "en-US", "format": "wav"},
                authorization="Bearer test-host-token",
            )
        )

        self.assertTrue(accepted["ok"])
        self.assertEqual(accepted["status"], "accepted")
        self.assertIn("job_id", accepted)
        self.assertNotIn("artifact", accepted)

        job = wait_for_job(services, accepted["job_id"], "succeeded")
        status = asyncio.run(
            dispatcher.dispatch(
                "job_status",
                {"job_id": accepted["job_id"]},
                authorization="Bearer test-host-token",
            )
        )
        artifact = asyncio.run(
            dispatcher.dispatch(
                "artifact_get",
                {"artifact_id": job.artifact_ids[0]},
                authorization="Bearer test-host-token",
            )
        )

        self.assertEqual(status["job"]["status"], "succeeded")
        self.assertEqual(status["job"]["artifact_ids"], job.artifact_ids)
        self.assertEqual(status["job"]["result_summary"]["provider"], "mock")
        self.assertEqual(artifact["artifact"]["kind"], "audio")
        self.assertIn("download_url", artifact["artifact"])

    def test_tts_synthesize_returns_job_before_provider_completion(self) -> None:
        AsyncTTSProviderHTTPRequestHandler.reset()
        server = ThreadingHTTPServer(("127.0.0.1", 0), AsyncTTSProviderHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        services, _, dispatcher = fresh_phase4_gateway()
        services.config.raw["modules"]["tts"]["provider"] = "local_http"
        services.config.raw["modules"]["tts"]["local_http"]["url"] = f"http://{host}:{port}/synthesize"
        try:
            started = time.monotonic()
            accepted = asyncio.run(
                dispatcher.dispatch(
                    "tts_synthesize",
                    {"text": "hello", "voice": "calm", "language": "en-US", "format": "wav"},
                    authorization="Bearer test-host-token",
                )
            )
            elapsed = time.monotonic() - started

            self.assertTrue(accepted["ok"])
            self.assertEqual(accepted["status"], "accepted")
            self.assertLess(elapsed, 0.5)
            self.assertNotIn("artifact", accepted)
            running = services.jobs.get(accepted["job_id"], CallerIdentity("host_assistant", "admin", True))
            self.assertEqual(running.status, "running")

            AsyncTTSProviderHTTPRequestHandler.release_event.set()
            job = wait_for_job(services, accepted["job_id"], "succeeded")
        finally:
            AsyncTTSProviderHTTPRequestHandler.release_event.set()
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(job.status, "succeeded")
        self.assertEqual(len(job.artifact_ids), 1)
        self.assertEqual(job.result_summary["mime_type"], "audio/wav")
        self.assertNotIn("download_url", str(job.result_summary))

    def test_tts_provider_mime_error_fails_background_job(self) -> None:
        TTSProviderHTTPRequestHandler.response_mime = "audio/flac"
        services, _, dispatcher = fresh_phase4_gateway()
        services.config.raw["modules"]["tts"]["provider"] = "local_http"
        host, port = self._start_tts_provider(TTSProviderHTTPRequestHandler)
        services.config.raw["modules"]["tts"]["local_http"]["url"] = f"http://{host}:{port}/synthesize"
        try:
            accepted = asyncio.run(
                dispatcher.dispatch(
                    "tts_synthesize",
                    {"text": "hello"},
                    authorization="Bearer test-host-token",
                )
            )
            job = wait_for_job(services, accepted["job_id"], "failed")
        finally:
            self._stop_tts_provider()
            TTSProviderHTTPRequestHandler.response_mime = "audio/wav"

        self.assertEqual(job.error_code, UNSUPPORTED_MEDIA_TYPE)

    def test_tts_deadline_marks_job_failed(self) -> None:
        AsyncTTSProviderHTTPRequestHandler.reset()
        server = ThreadingHTTPServer(("127.0.0.1", 0), AsyncTTSProviderHTTPRequestHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        services, _, dispatcher = fresh_phase4_gateway()
        services.config.raw["modules"]["tts"]["provider"] = "local_http"
        services.config.raw["modules"]["tts"]["local_http"]["url"] = f"http://{host}:{port}/synthesize"
        services.config.raw["modules"]["tts"]["total_timeout_seconds"] = 0.1
        try:
            accepted = asyncio.run(
                dispatcher.dispatch(
                    "tts_synthesize",
                    {"text": "slow"},
                    authorization="Bearer test-host-token",
                )
            )
            job = wait_for_job(services, accepted["job_id"], "failed")
            audit = services.artifacts.conn.execute(
                "SELECT status, error_code FROM audit_events WHERE job_id = ?",
                (accepted["job_id"],),
            ).fetchone()
        finally:
            AsyncTTSProviderHTTPRequestHandler.release_event.set()
            server.shutdown()
            thread.join(timeout=2)
            server.server_close()

        self.assertEqual(job.error_code, PROVIDER_TIMEOUT)
        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["error_code"], PROVIDER_TIMEOUT)

    def test_stale_tts_jobs_are_reconciled(self) -> None:
        services, _, _ = fresh_phase4_gateway()
        services.config.raw["modules"]["tts"]["total_timeout_seconds"] = 1
        job = services.jobs.create(
            request_id="req_stale",
            caller_id="host_assistant",
            tool_name="tts_synthesize",
            input_summary={"text": {"prefix": "hello", "length": 5}},
        )
        services.jobs.mark_running(job.id)
        audit_id = services.audit.start(
            request_id="req_stale",
            job_id=job.id,
            caller_id="host_assistant",
            tool_name="tts_synthesize",
            risk_level="medium",
            arguments={"text": "hello"},
        )
        old = (utc_now().replace(year=2000)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        with services.artifacts.conn:
            services.artifacts.conn.execute("UPDATE jobs SET updated_at = ? WHERE id = ?", (old, job.id))

        reconciled = reconcile_stale_tts_jobs(services)
        updated = services.jobs.get(job.id, CallerIdentity("host_assistant", "admin", True))
        audit = services.artifacts.conn.execute("SELECT status, error_code FROM audit_events WHERE id = ?", (audit_id,)).fetchone()

        self.assertEqual(reconciled, [job.id])
        self.assertEqual(updated.status, "failed")
        self.assertEqual(updated.error_code, PROVIDER_TIMEOUT)
        self.assertEqual(audit["status"], "failed")
        self.assertEqual(audit["error_code"], PROVIDER_TIMEOUT)

    def _start_tts_provider(self, handler):
        self._tts_server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._tts_thread = threading.Thread(target=self._tts_server.serve_forever, daemon=True)
        self._tts_thread.start()
        return self._tts_server.server_address

    def _stop_tts_provider(self):
        self._tts_server.shutdown()
        self._tts_thread.join(timeout=2)
        self._tts_server.server_close()


class TTSProviderHTTPRequestHandler(BaseHTTPRequestHandler):
    request_body = {}
    auth_header = ""
    response_status = 200
    response_mime = "audio/wav"

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).request_body = json.loads(body.decode("utf-8"))
        type(self).auth_header = self.headers.get("Authorization", "")
        self.send_response(type(self).response_status)
        self.send_header("Content-Type", type(self).response_mime)
        self.end_headers()
        self.wfile.write(AUDIO_BYTES)

    def log_message(self, format, *args):
        return


class AsyncTTSProviderHTTPRequestHandler(BaseHTTPRequestHandler):
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
        self.send_header("Content-Type", "audio/wav")
        self.end_headers()
        self.wfile.write(AUDIO_BYTES)

    def log_message(self, format, *args):
        return


class TTSProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        TTSProviderHTTPRequestHandler.request_body = {}
        TTSProviderHTTPRequestHandler.auth_header = ""
        TTSProviderHTTPRequestHandler.response_status = 200
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), TTSProviderHTTPRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.provider = LocalHttpTTSProvider(
            url=f"http://{host}:{port}/synthesize",
            timeout_seconds=2,
            api_key="test-tts-token",
        )

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_local_http_provider_sends_json_and_auth_header(self) -> None:
        response = self.provider.synthesize(text="hello", voice="calm", language="en-US", format="wav", speed=1.0)

        self.assertEqual(response.mime_type, "audio/wav")
        self.assertEqual(response.data, AUDIO_BYTES)
        self.assertEqual(TTSProviderHTTPRequestHandler.request_body["text"], "hello")
        self.assertEqual(TTSProviderHTTPRequestHandler.auth_header, "Bearer test-tts-token")


class MatrixHTTPRequestHandler(BaseHTTPRequestHandler):
    requests = []

    def do_POST(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).requests.append(
            {
                "method": "POST",
                "path": self.path,
                "body": body,
                "content_type": self.headers.get("Content-Type", ""),
                "auth": self.headers.get("Authorization", ""),
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"content_uri": "mxc://example.test/media"}).encode("utf-8"))

    def do_PUT(self) -> None:
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).requests.append(
            {
                "method": "PUT",
                "path": self.path,
                "body": body,
                "content_type": self.headers.get("Content-Type", ""),
                "auth": self.headers.get("Authorization", ""),
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"event_id": "$event123"}).encode("utf-8"))

    def log_message(self, format, *args):
        return


class MatrixProviderAndWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        MatrixHTTPRequestHandler.requests = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), MatrixHTTPRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.homeserver = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_matrix_http_client_uploads_and_sends_audio(self) -> None:
        client = MatrixHttpClient(homeserver=self.homeserver, access_token="test-matrix-token", timeout_seconds=2)
        upload = client.upload_media(data=AUDIO_BYTES, mime_type="audio/wav", filename="test.wav")
        sent = client.send_audio(
            room_id="!allowed:example.test",
            body="test.wav",
            content_uri=upload.content_uri,
            mime_type="audio/wav",
            size_bytes=len(AUDIO_BYTES),
        )

        self.assertEqual(sent.event_id, "$event123")
        self.assertEqual(MatrixHTTPRequestHandler.requests[0]["auth"], "Bearer test-matrix-token")
        self.assertEqual(MatrixHTTPRequestHandler.requests[0]["content_type"], "audio/wav")
        self.assertIn("/_matrix/media/v3/upload", MatrixHTTPRequestHandler.requests[0]["path"])
        send_path = unquote(MatrixHTTPRequestHandler.requests[1]["path"])
        self.assertIn("/rooms/!allowed:example.test/send/m.room.message/", send_path)
        send_body = json.loads(MatrixHTTPRequestHandler.requests[1]["body"].decode("utf-8"))
        self.assertEqual(send_body["msgtype"], "m.audio")
        self.assertEqual(send_body["url"], "mxc://example.test/media")

    def test_matrix_http_client_uploads_and_sends_image(self) -> None:
        client = MatrixHttpClient(homeserver=self.homeserver, access_token="test-matrix-token", timeout_seconds=2)
        upload = client.upload_media(data=IMAGE_BYTES, mime_type="image/png", filename="test.png")
        sent = client.send_image(
            room_id="!allowed:example.test",
            body="test.png",
            content_uri=upload.content_uri,
            mime_type="image/png",
            size_bytes=len(IMAGE_BYTES),
            width=640,
            height=480,
        )

        self.assertEqual(sent.event_id, "$event123")
        self.assertEqual(MatrixHTTPRequestHandler.requests[0]["content_type"], "image/png")
        send_body = json.loads(MatrixHTTPRequestHandler.requests[1]["body"].decode("utf-8"))
        self.assertEqual(send_body["msgtype"], "m.image")
        self.assertEqual(send_body["url"], "mxc://example.test/media")
        self.assertEqual(send_body["info"]["mimetype"], "image/png")
        self.assertEqual(send_body["info"]["size"], len(IMAGE_BYTES))
        self.assertEqual(send_body["info"]["w"], 640)
        self.assertEqual(send_body["info"]["h"], 480)

    def test_dispatcher_room_allowlist_audio_permissions_and_secret_redaction(self) -> None:
        services, _, dispatcher = fresh_phase4_gateway()
        services.config.raw["modules"]["matrix"]["homeserver"] = self.homeserver
        audio = services.artifacts.create_from_bytes(
            kind="audio",
            mime_type="audio/wav",
            extension="wav",
            data=AUDIO_BYTES,
            owner="host_assistant",
            source_tool="test",
        )
        forbidden_audio = services.artifacts.create_from_bytes(
            kind="audio",
            mime_type="audio/wav",
            extension="wav",
            data=AUDIO_BYTES,
            owner="host_assistant",
            source_tool="test",
        )
        document = services.artifacts.create_from_bytes(
            kind="document",
            mime_type="text/plain",
            extension="txt",
            data=b"text",
            owner="host_assistant",
            source_tool="test",
        )

        sent = asyncio.run(
            dispatcher.dispatch(
                "matrix_send_audio",
                {"room_id": "!allowed:example.test", "audio_artifact_id": audio.id, "body": "voice note"},
                authorization="Bearer test-host-token",
            )
        )
        bad_room = asyncio.run(
            dispatcher.dispatch(
                "matrix_send_text",
                {"room_id": "!denied:example.test", "text": "hello"},
                authorization="Bearer test-host-token",
            )
        )
        forbidden = asyncio.run(
            dispatcher.dispatch(
                "matrix_send_audio",
                {"room_id": "!allowed:example.test", "audio_artifact_id": forbidden_audio.id},
                authorization="Bearer test-role-token",
            )
        )
        bad_mime = asyncio.run(
            dispatcher.dispatch(
                "matrix_send_audio",
                {"room_id": "!allowed:example.test", "audio_artifact_id": document.id},
                authorization="Bearer test-host-token",
            )
        )
        rows = services.artifacts.conn.execute("SELECT input_summary_json, error_message FROM audit_events").fetchall()

        self.assertTrue(sent["ok"])
        self.assertEqual(sent["event_id"], "$event123")
        self.assertEqual(sent["media"]["artifact_id"], audio.id)
        self.assertEqual(bad_room["error"]["code"], POLICY_DENIED)
        self.assertEqual(forbidden["error"]["code"], ARTIFACT_FORBIDDEN)
        self.assertEqual(bad_mime["error"]["code"], UNSUPPORTED_MEDIA_TYPE)
        self.assertNotIn("test-matrix-token", str(sent))
        self.assertNotIn("test-matrix-token", str([tuple(row) for row in rows]))

    def test_dispatcher_sends_image_artifact_to_matrix(self) -> None:
        services, _, dispatcher = fresh_phase4_gateway()
        services.config.raw["modules"]["matrix"]["homeserver"] = self.homeserver
        image = services.artifacts.create_from_bytes(
            kind="image",
            mime_type="image/png",
            extension="png",
            data=IMAGE_BYTES,
            owner="host_assistant",
            source_tool="test",
            metadata={"width": 320, "height": 240},
        )
        document = services.artifacts.create_from_bytes(
            kind="document",
            mime_type="text/plain",
            extension="txt",
            data=b"text",
            owner="host_assistant",
            source_tool="test",
        )

        sent = asyncio.run(
            dispatcher.dispatch(
                "matrix_send_image",
                {"room_id": "!allowed:example.test", "image_artifact_id": image.id, "body": "preview.png"},
                authorization="Bearer test-host-token",
            )
        )
        bad_mime = asyncio.run(
            dispatcher.dispatch(
                "matrix_send_image",
                {"room_id": "!allowed:example.test", "image_artifact_id": document.id},
                authorization="Bearer test-host-token",
            )
        )
        bad_room = asyncio.run(
            dispatcher.dispatch(
                "matrix_send_image",
                {"room_id": "!denied:example.test", "image_artifact_id": image.id},
                authorization="Bearer test-role-token",
            )
        )
        send_body = json.loads(MatrixHTTPRequestHandler.requests[1]["body"].decode("utf-8"))

        self.assertTrue(sent["ok"])
        self.assertEqual(sent["event_id"], "$event123")
        self.assertEqual(sent["media"]["artifact_id"], image.id)
        self.assertEqual(sent["media"]["width"], 320)
        self.assertEqual(sent["media"]["height"], 240)
        self.assertEqual(send_body["msgtype"], "m.image")
        self.assertEqual(send_body["body"], "preview.png")
        self.assertEqual(send_body["info"]["w"], 320)
        self.assertEqual(send_body["info"]["h"], 240)
        self.assertEqual(bad_mime["error"]["code"], UNSUPPORTED_MEDIA_TYPE)
        self.assertEqual(bad_room["error"]["code"], POLICY_DENIED)


if __name__ == "__main__":
    unittest.main()
