from __future__ import annotations

import asyncio
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote

from core.errors import ARTIFACT_FORBIDDEN, INVALID_ARGUMENT, POLICY_DENIED, UNSUPPORTED_MEDIA_TYPE
from core.ids import new_request_id
from core.policy import CallerIdentity
from modules.matrix.providers.http_client import MatrixHttpClient
from modules.tts.providers.local_http import LocalHttpTTSProvider, ProviderAudioResponse
from modules.tts.service import TTSSynthesisService
from tests.helpers import fresh_phase4_gateway
from transport.request_context import RequestContext

AUDIO_BYTES = b"RIFFphase4-audio"


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


if __name__ == "__main__":
    unittest.main()
