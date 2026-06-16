from __future__ import annotations

import json
import socket
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from app.config import Settings
from core.errors import (
    GatewayError,
    PROVIDER_REJECTED,
    PROVIDER_TIMEOUT,
    PROVIDER_UNAVAILABLE,
    RATE_LIMITED,
)


@dataclass(frozen=True, slots=True)
class ProviderImageOutput:
    response_type: str
    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderImageResponse:
    outputs: list[ProviderImageOutput]
    usage: dict[str, Any] | None = None
    raw_size: str | None = None
    raw_quality: str | None = None
    raw_output_format: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderEditImage:
    filename: str
    mime_type: str
    data: bytes


class OpenAICompatibleImageProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout_seconds: int = 60,
        opener: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.opener = opener or request.urlopen

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAICompatibleImageProvider":
        image_config = settings.modules.get("image", {})
        provider_config = image_config.get("openai_compatible", {})
        return cls(
            base_url=str(provider_config["base_url"]),
            model=str(provider_config["model"]),
            api_key=str(provider_config["api_key"]),
            timeout_seconds=int(provider_config.get("timeout_seconds", 60)),
        )

    def generate(
        self,
        *,
        prompt: str,
        n: int,
        size: str,
        quality: str,
        output_format: str,
    ) -> ProviderImageResponse:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
            "output_format": output_format,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/v1/images/generations",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        return _decode_image_response(self._send(req))

    def edit(
        self,
        *,
        prompt: str,
        images: list[ProviderEditImage],
        n: int,
        size: str,
        quality: str,
        output_format: str,
    ) -> ProviderImageResponse:
        fields: list[tuple[str, str]] = [
            ("model", self.model),
            ("prompt", prompt),
            ("n", str(n)),
            ("size", size),
            ("quality", quality),
            ("output_format", output_format),
        ]
        files = [("image[]", image.filename, image.mime_type, image.data) for image in images]
        body, content_type = _encode_multipart(fields, files)
        req = request.Request(
            f"{self.base_url}/v1/images/edits",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": content_type,
                "Accept": "application/json",
            },
        )
        return _decode_image_response(self._send(req))

    def _send(self, req: request.Request) -> bytes:
        try:
            with self.opener(req, timeout=self.timeout_seconds) as response:
                return response.read()
        except error.HTTPError as exc:
            gateway_error = _map_http_error(exc)
            exc.close()
            raise gateway_error from exc
        except (TimeoutError, socket.timeout) as exc:
            raise GatewayError(PROVIDER_TIMEOUT, "image provider timed out", retryable=True) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise GatewayError(PROVIDER_TIMEOUT, "image provider timed out", retryable=True) from exc
            raise GatewayError(PROVIDER_UNAVAILABLE, "image provider is unavailable", retryable=True) from exc
        except OSError as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "image provider is unavailable", retryable=True) from exc


def _map_http_error(exc: error.HTTPError) -> GatewayError:
    if exc.code in {401, 403}:
        return GatewayError(PROVIDER_REJECTED, "image provider rejected the request", retryable=False)
    if exc.code == 429:
        return GatewayError(RATE_LIMITED, "image provider rate limit exceeded", retryable=True)
    if exc.code >= 500:
        return GatewayError(PROVIDER_UNAVAILABLE, "image provider is unavailable", retryable=True)
    return GatewayError(PROVIDER_REJECTED, "image provider rejected the request", retryable=False)


def _decode_image_response(response_body: bytes) -> ProviderImageResponse:
    try:
        decoded = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise GatewayError(PROVIDER_UNAVAILABLE, "image provider returned non-json response", retryable=True) from exc

    data = decoded.get("data")
    if not isinstance(data, list) or not data:
        raise GatewayError(PROVIDER_UNAVAILABLE, "image provider returned no image data", retryable=True)

    outputs: list[ProviderImageOutput] = []
    for item in data:
        if not isinstance(item, dict):
            raise GatewayError(PROVIDER_UNAVAILABLE, "image provider returned invalid image data", retryable=True)
        if isinstance(item.get("url"), str) and item["url"]:
            outputs.append(
                ProviderImageOutput(
                    response_type="url",
                    url=item["url"],
                    revised_prompt=item.get("revised_prompt") if isinstance(item.get("revised_prompt"), str) else None,
                )
            )
        elif isinstance(item.get("b64_json"), str) and item["b64_json"]:
            outputs.append(
                ProviderImageOutput(
                    response_type="b64_json",
                    b64_json=item["b64_json"],
                    revised_prompt=item.get("revised_prompt") if isinstance(item.get("revised_prompt"), str) else None,
                )
            )
        else:
            raise GatewayError(PROVIDER_UNAVAILABLE, "image provider returned unsupported image data", retryable=True)

    return ProviderImageResponse(
        outputs=outputs,
        usage=decoded.get("usage") if isinstance(decoded.get("usage"), dict) else None,
    )


def _encode_multipart(
    fields: list[tuple[str, str]],
    files: list[tuple[str, str, str, bytes]],
) -> tuple[bytes, str]:
    boundary = f"----home-mcp-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, filename, mime_type, data in files:
        chunks.extend(
            [
                f"--{boundary}\r\n".encode("ascii"),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{_safe_filename(filename)}"\r\n'
                ).encode("utf-8"),
                f"Content-Type: {mime_type}\r\n\r\n".encode("ascii"),
                data,
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def _safe_filename(filename: str) -> str:
    return filename.replace("\\", "_").replace("/", "_").replace('"', "_")
