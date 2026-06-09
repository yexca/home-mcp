from __future__ import annotations

import asyncio
import base64
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.errors import ARTIFACT_FORBIDDEN, ARTIFACT_NOT_FOUND, INVALID_ARGUMENT, UNSUPPORTED_MEDIA_TYPE
from core.ids import new_request_id
from core.policy import CallerIdentity
from modules.image.providers.ikun_openai_compatible import (
    IkunOpenAICompatibleProvider,
    ProviderEditImage,
    ProviderImageOutput,
    ProviderImageResponse,
)
from modules.image.service import DownloadedImage, ImageGenerationService
from tests.helpers import fresh_image_gateway
from transport.request_context import RequestContext

PNG_BYTES = b"\x89PNG\r\n\x1a\nedit-test-image"
WEBP_BYTES = b"RIFFwebp-test"
OUTPUT_BYTES = b"\x89PNG\r\n\x1a\nedit-output"


class FakeEditProvider:
    model = "test-image-model"

    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []

    def edit(self, **kwargs):
        self.calls.append(kwargs)
        return ProviderImageResponse(outputs=self.outputs, usage={"total_tokens": 2})


def fake_downloader(url, image_config):
    return DownloadedImage(data=OUTPUT_BYTES, mime_type="image/png", source_host="cdn.example.test")


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


def create_image_artifact(services, owner: str = "host_assistant", data: bytes = PNG_BYTES, mime_type: str = "image/png"):
    extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}.get(mime_type, "bin")
    return services.artifacts.create_from_bytes(
        kind="image",
        mime_type=mime_type,
        extension=extension,
        data=data,
        owner=owner,
        source_tool="test",
    )


class ImageEditServiceTests(unittest.TestCase):
    def test_single_compatibility_id_creates_artifact_from_base64_response(self) -> None:
        services, _, _ = fresh_image_gateway()
        input_artifact = create_image_artifact(services)
        encoded = base64.b64encode(OUTPUT_BYTES).decode("ascii")
        provider = FakeEditProvider([ProviderImageOutput("b64_json", b64_json=encoded)])
        ctx = make_context(services)

        result = asyncio.run(
            ImageGenerationService(provider).edit(
                {
                    "prompt": "make it brighter",
                    "image_artifact_id": input_artifact.id,
                    "size": "1024x1024",
                    "quality": "auto",
                    "output_format": "png",
                },
                ctx,
            )
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["artifact"]["mime_type"], "image/png")
        self.assertEqual(provider.calls[0]["images"][0].filename, input_artifact.filename)
        self.assertEqual(provider.calls[0]["images"][0].data, PNG_BYTES)
        self.assertEqual(result["artifact"]["metadata"]["input_artifact_ids"], [input_artifact.id])
        self.assertNotIn(encoded, str(result))

    def test_multiple_ids_create_artifact_from_url_response(self) -> None:
        services, _, _ = fresh_image_gateway()
        first = create_image_artifact(services)
        second = create_image_artifact(services, data=WEBP_BYTES, mime_type="image/webp")
        provider = FakeEditProvider([ProviderImageOutput("url", url="https://cdn.example.test/edited.png")])

        result = asyncio.run(
            ImageGenerationService(provider, downloader=fake_downloader).edit(
                {"prompt": "combine them", "image_artifact_ids": [first.id, second.id]},
                make_context(services),
            )
        )

        self.assertTrue(result["ok"])
        self.assertEqual(len(provider.calls[0]["images"]), 2)
        self.assertNotIn("https://cdn.example.test/edited.png", str(result))

    def test_missing_forbidden_invalid_mime_and_size_limits(self) -> None:
        services, _, _ = fresh_image_gateway()
        provider = FakeEditProvider([ProviderImageOutput("b64_json", b64_json=base64.b64encode(OUTPUT_BYTES).decode("ascii"))])
        caller_ctx = make_context(services, CallerIdentity("role_default", "role_play"))
        forbidden = create_image_artifact(services, owner="host_assistant")
        expired_artifact = create_image_artifact(services, owner="role_default")
        with services.artifacts.conn:
            services.artifacts.conn.execute(
                "UPDATE artifacts SET expires_at = ? WHERE id = ?",
                ("2000-01-01T00:00:00.000Z", expired_artifact.id),
            )
        text_artifact = services.artifacts.create_from_bytes(
            kind="document",
            mime_type="text/plain",
            extension="txt",
            data=b"text",
            owner="role_default",
            source_tool="test",
        )
        large_artifact = create_image_artifact(services, owner="role_default", data=b"x" * 33)
        ok_artifact = create_image_artifact(services, owner="role_default", data=b"x" * 25)
        ok_artifact_two = create_image_artifact(services, owner="role_default", data=b"y" * 25)

        cases = [
            ("missing", "art_missing", ARTIFACT_NOT_FOUND),
            ("forbidden", forbidden.id, ARTIFACT_FORBIDDEN),
            ("expired", expired_artifact.id, ARTIFACT_FORBIDDEN),
            ("mime", text_artifact.id, UNSUPPORTED_MEDIA_TYPE),
            ("per_size", large_artifact.id, INVALID_ARGUMENT),
        ]
        for name, artifact_id, code in cases:
            with self.subTest(name=name), self.assertRaises(Exception) as raised:
                asyncio.run(ImageGenerationService(provider).edit({"prompt": "edit", "image_artifact_id": artifact_id}, caller_ctx))
            self.assertEqual(raised.exception.code, code)

        with self.assertRaises(Exception) as total_size:
            asyncio.run(
                ImageGenerationService(provider).edit(
                    {"prompt": "edit", "image_artifact_ids": [ok_artifact.id, ok_artifact_two.id]},
                    caller_ctx,
                )
            )
        self.assertEqual(total_size.exception.code, INVALID_ARGUMENT)

    def test_dispatcher_rejects_url_path_and_too_many_ids(self) -> None:
        services, _, dispatcher = fresh_image_gateway()
        too_many = ["art_one", "art_two", "art_three"]
        url_result = asyncio.run(
            dispatcher.dispatch(
                "image_edit",
                {"prompt": "edit", "image_url": "https://example.test/a.png"},
                authorization="Bearer test-host-token",
            )
        )
        path_result = asyncio.run(
            dispatcher.dispatch(
                "image_edit",
                {"prompt": "edit", "local_path": "C:/secret/a.png"},
                authorization="Bearer test-host-token",
            )
        )
        count_result = asyncio.run(
            dispatcher.dispatch(
                "image_edit",
                {"prompt": "edit", "image_artifact_ids": too_many},
                authorization="Bearer test-host-token",
            )
        )

        self.assertEqual(url_result["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(path_result["error"]["code"], INVALID_ARGUMENT)
        self.assertEqual(count_result["error"]["code"], INVALID_ARGUMENT)


class EditProviderHTTPRequestHandler(BaseHTTPRequestHandler):
    response_body = {"data": [{"b64_json": base64.b64encode(OUTPUT_BYTES).decode("ascii")}]}
    request_body = b""
    content_type = ""
    request_path = ""
    auth_header = ""

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        type(self).request_body = self.rfile.read(length)
        type(self).content_type = self.headers.get("Content-Type", "")
        type(self).request_path = self.path
        type(self).auth_header = self.headers.get("Authorization", "")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(type(self).response_body).encode("utf-8"))

    def log_message(self, format, *args):
        return


class IkunEditProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        EditProviderHTTPRequestHandler.request_body = b""
        EditProviderHTTPRequestHandler.content_type = ""
        EditProviderHTTPRequestHandler.request_path = ""
        EditProviderHTTPRequestHandler.auth_header = ""
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), EditProviderHTTPRequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.provider = IkunOpenAICompatibleProvider(
            base_url=f"http://{host}:{port}",
            model="test-image-model",
            api_key="test-image-api-key",
            timeout_seconds=2,
        )

    def tearDown(self) -> None:
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()

    def test_edit_sends_multipart_image_array_fields(self) -> None:
        response = self.provider.edit(
            prompt="edit",
            images=[
                ProviderEditImage(filename="one.png", mime_type="image/png", data=PNG_BYTES),
                ProviderEditImage(filename="two.webp", mime_type="image/webp", data=WEBP_BYTES),
            ],
            n=1,
            size="1024x1024",
            quality="auto",
            output_format="png",
        )

        self.assertEqual(response.outputs[0].response_type, "b64_json")
        self.assertEqual(EditProviderHTTPRequestHandler.request_path, "/v1/images/edits")
        self.assertIn("multipart/form-data", EditProviderHTTPRequestHandler.content_type)
        self.assertEqual(EditProviderHTTPRequestHandler.auth_header, "Bearer test-image-api-key")
        body = EditProviderHTTPRequestHandler.request_body
        self.assertEqual(body.count(b'name="image[]"'), 2)
        self.assertIn(b'name="model"', body)
        self.assertIn(b"test-image-model", body)


if __name__ == "__main__":
    unittest.main()
