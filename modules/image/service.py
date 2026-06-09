from __future__ import annotations

import base64
import binascii
import socket
from dataclasses import dataclass
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from core.errors import GatewayError, INVALID_ARGUMENT, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE, UNSUPPORTED_MEDIA_TYPE
from modules.image.providers.ikun_openai_compatible import IkunOpenAICompatibleProvider, ProviderImageOutput
from tools.result import success
from transport.request_context import RequestContext

MIME_BY_FORMAT = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
EXTENSION_BY_MIME = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


@dataclass(frozen=True, slots=True)
class DownloadedImage:
    data: bytes
    mime_type: str
    source_host: str


class ImageGenerationService:
    def __init__(self, provider: IkunOpenAICompatibleProvider, downloader: Any | None = None) -> None:
        self.provider = provider
        self.downloader = downloader or download_image_url

    async def generate(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        image_config = ctx.config.modules.get("image", {})
        prompt = _validated_prompt(arguments.get("prompt", ""), int(image_config.get("max_prompt_chars", 4000)))
        n = int(arguments.get("n", 1))
        if n != 1:
            raise GatewayError(INVALID_ARGUMENT, "n must be 1 for image_generate")
        size = _validated_size(arguments.get("size", "auto"), image_config)
        quality = _validated_member(arguments.get("quality", "auto"), image_config.get("allowed_qualities", ["auto"]), "quality")
        output_format = _validated_member(
            arguments.get("output_format", "png"),
            image_config.get("allowed_output_formats", ["png", "jpeg", "webp"]),
            "output_format",
        )

        ctx.limits.check(
            f"image_generate:{ctx.caller.caller_id}:day",
            limit=int(ctx.config.limits.get("image_jobs_per_caller_per_day", 20)),
            window_seconds=24 * 60 * 60,
        )
        response = self.provider.generate(
            prompt=prompt,
            n=n,
            size=size,
            quality=quality,
            output_format=output_format,
        )

        artifacts = []
        response_types: list[str] = []
        for item in response.outputs:
            downloaded = _resolve_output(item, output_format, image_config, self.downloader)
            metadata = {
                "provider": "ikun",
                "model": self.provider.model,
                "size": size,
                "quality": quality,
                "output_format": output_format,
                "provider_output": {
                    "type": item.response_type,
                    "host": downloaded.source_host,
                },
            }
            if response.usage:
                metadata["usage"] = response.usage
            if item.revised_prompt:
                metadata["revised_prompt"] = item.revised_prompt
            artifact = ctx.artifacts.create_from_bytes(
                kind="image",
                mime_type=downloaded.mime_type,
                extension=EXTENSION_BY_MIME[downloaded.mime_type],
                data=downloaded.data,
                owner=ctx.caller,
                source_tool="image_generate",
                source_job_id=ctx.job_id,
                metadata=metadata,
            )
            artifacts.append(artifact.to_metadata(ctx.config.artifacts.get("public_base_url")))
            response_types.append(item.response_type)

        return success(
            request_id=ctx.request_id,
            artifact=artifacts[0],
            artifacts=artifacts,
            provider_output={"types": response_types, "count": len(artifacts)},
        )


async def image_generate(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    provider = IkunOpenAICompatibleProvider.from_settings(ctx.config)
    return await ImageGenerationService(provider).generate(arguments, ctx)


def download_image_url(url: str, image_config: dict[str, Any]) -> DownloadedImage:
    parsed = urlparse(url)
    allowed_hosts = set(image_config.get("ikun", {}).get("allowed_image_url_hosts") or [])
    allow_http = bool(image_config.get("allow_http_image_urls", False))
    if parsed.scheme != "https" and not (allow_http and parsed.scheme == "http"):
        raise GatewayError(PROVIDER_UNAVAILABLE, "provider image URL scheme is not allowed", retryable=False)
    if not parsed.hostname or parsed.hostname not in allowed_hosts:
        raise GatewayError(PROVIDER_UNAVAILABLE, "provider image URL host is not allowed", retryable=False)

    max_bytes = int(image_config.get("max_download_bytes", 10 * 1024 * 1024))
    req = request.Request(url, method="GET", headers={"Accept": "image/png,image/jpeg,image/webp"})
    try:
        with request.urlopen(req, timeout=int(image_config.get("ikun", {}).get("timeout_seconds", 60))) as response:
            mime_type = _normalize_mime(response.headers.get("Content-Type", ""))
            if mime_type not in EXTENSION_BY_MIME:
                raise GatewayError(UNSUPPORTED_MEDIA_TYPE, "provider image MIME type is not supported", retryable=False)
            chunks: list[bytes] = []
            size = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise GatewayError(PROVIDER_UNAVAILABLE, "provider image exceeds max size", retryable=False)
                chunks.append(chunk)
    except GatewayError:
        raise
    except (TimeoutError, socket.timeout) as exc:
        raise GatewayError(PROVIDER_TIMEOUT, "provider image download timed out", retryable=True) from exc
    except error.URLError as exc:
        if isinstance(exc.reason, (TimeoutError, socket.timeout)):
            raise GatewayError(PROVIDER_TIMEOUT, "provider image download timed out", retryable=True) from exc
        raise GatewayError(PROVIDER_UNAVAILABLE, "provider image download failed", retryable=True) from exc

    return DownloadedImage(data=b"".join(chunks), mime_type=mime_type, source_host=parsed.hostname)


def _resolve_output(
    item: ProviderImageOutput,
    output_format: str,
    image_config: dict[str, Any],
    downloader: Any,
) -> DownloadedImage:
    if item.response_type == "url" and item.url:
        return downloader(item.url, image_config)
    if item.response_type == "b64_json" and item.b64_json:
        max_bytes = int(image_config.get("max_download_bytes", 10 * 1024 * 1024))
        estimated = (len(item.b64_json) * 3) // 4
        if estimated > max_bytes:
            raise GatewayError(PROVIDER_UNAVAILABLE, "provider image exceeds max size", retryable=False)
        try:
            data = base64.b64decode(item.b64_json, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "provider returned invalid base64 image", retryable=True) from exc
        if len(data) > max_bytes:
            raise GatewayError(PROVIDER_UNAVAILABLE, "provider image exceeds max size", retryable=False)
        return DownloadedImage(data=data, mime_type=MIME_BY_FORMAT[output_format], source_host="inline")
    raise GatewayError(PROVIDER_UNAVAILABLE, "image provider returned unsupported image data", retryable=True)


def _validated_prompt(prompt: str, max_chars: int) -> str:
    if not isinstance(prompt, str) or not prompt.strip():
        raise GatewayError(INVALID_ARGUMENT, "prompt is required")
    if len(prompt) > max_chars:
        raise GatewayError(INVALID_ARGUMENT, "prompt is too long")
    return prompt


def _validated_size(size: str, image_config: dict[str, Any]) -> str:
    allowed = set(image_config.get("allowed_sizes") or [])
    selected = image_config.get("default_size") if size == "auto" else size
    if not isinstance(selected, str) or selected not in allowed:
        raise GatewayError(INVALID_ARGUMENT, "size is not allowed")
    return selected


def _validated_member(value: str, allowed_values: list[str], field: str) -> str:
    if not isinstance(value, str) or value not in set(allowed_values):
        raise GatewayError(INVALID_ARGUMENT, f"{field} is not allowed")
    return value


def _normalize_mime(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()
