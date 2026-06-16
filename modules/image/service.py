from __future__ import annotations

import base64
import binascii
import logging
import socket
import time
from dataclasses import dataclass
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from core.artifacts import artifact_download_url
from core.errors import GatewayError, INVALID_ARGUMENT, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE, UNSUPPORTED_MEDIA_TYPE
from modules.image.providers import ImageProvider, create_image_provider
from modules.image.providers.openai_compatible import (
    ProviderEditImage,
    ProviderImageOutput,
    ProviderImageResponse,
)
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

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DownloadedImage:
    data: bytes
    mime_type: str
    source_host: str


@dataclass(frozen=True, slots=True)
class PreparedImageGenerate:
    prompt: str
    n: int
    size: str
    quality: str
    output_format: str


@dataclass(frozen=True, slots=True)
class ImageDeadline:
    expires_at: float

    @classmethod
    def after(cls, seconds: float) -> "ImageDeadline":
        return cls(time.monotonic() + seconds)

    def remaining_seconds(self) -> float:
        return self.expires_at - time.monotonic()

    def check(self) -> None:
        if self.remaining_seconds() <= 0:
            raise GatewayError(
                PROVIDER_TIMEOUT,
                "image job exceeded gateway deadline or was abandoned during restart",
                retryable=True,
            )


class _ImageGenerationBase:
    def __init__(self, provider: ImageProvider, downloader: Any | None = None) -> None:
        self.provider = provider
        self.downloader = downloader or download_image_url

    async def generate(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        prepared = prepare_image_generate(arguments, ctx)
        return self.generate_prepared(prepared, ctx)

    def generate_prepared(
        self,
        prepared: PreparedImageGenerate,
        ctx: RequestContext,
        deadline: ImageDeadline | None = None,
    ) -> dict[str, Any]:
        image_config = ctx.config.modules.get("image", {})
        if deadline:
            deadline.check()
        response = self.provider.generate(
            prompt=prepared.prompt,
            n=prepared.n,
            size=prepared.size,
            quality=prepared.quality,
            output_format=prepared.output_format,
        )
        logger.info("image provider response received", extra={"request_id": ctx.request_id, "job_id": ctx.job_id})
        if deadline:
            deadline.check()
        return _persist_image_outputs(
            response=response,
            output_format=prepared.output_format,
            image_config=image_config,
            downloader=self.downloader,
            ctx=ctx,
            provider_model=self.provider.model,
            source_tool="image_generate",
            size=prepared.size,
            quality=prepared.quality,
            deadline=deadline,
        )


def prepare_image_generate(arguments: dict[str, Any], ctx: RequestContext) -> PreparedImageGenerate:
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
    return PreparedImageGenerate(
        prompt=prompt,
        n=n,
        size=size,
        quality=quality,
        output_format=output_format,
    )


class ImageGenerationService(_ImageGenerationBase):
    async def edit(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        image_config = ctx.config.modules.get("image", {})
        prompt = _validated_prompt(arguments.get("prompt", ""), int(image_config.get("max_prompt_chars", 4000)))
        n = int(arguments.get("n", 1))
        if n != 1:
            raise GatewayError(INVALID_ARGUMENT, "n must be 1 for image_edit")
        size = _validated_size(arguments.get("size", "auto"), image_config)
        quality = _validated_member(arguments.get("quality", "auto"), image_config.get("allowed_qualities", ["auto"]), "quality")
        output_format = _validated_member(
            arguments.get("output_format", "png"),
            image_config.get("allowed_output_formats", ["png", "jpeg", "webp"]),
            "output_format",
        )
        artifact_ids = _validated_image_artifact_ids(arguments, image_config)
        input_images = _load_edit_input_images(artifact_ids, ctx, image_config)

        ctx.limits.check(
            f"image_edit:{ctx.caller.caller_id}:day",
            limit=int(ctx.config.limits.get("image_jobs_per_caller_per_day", 20)),
            window_seconds=24 * 60 * 60,
        )
        response = self.provider.edit(
            prompt=prompt,
            images=input_images,
            n=n,
            size=size,
            quality=quality,
            output_format=output_format,
        )

        return _persist_image_outputs(
            response=response,
            output_format=output_format,
            image_config=image_config,
            downloader=self.downloader,
            ctx=ctx,
            provider_model=self.provider.model,
            source_tool="image_edit",
            size=size,
            quality=quality,
            extra_metadata={"input_artifact_ids": artifact_ids},
        )


async def image_generate(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    provider = create_image_provider(ctx.config)
    return await ImageGenerationService(provider).generate(arguments, ctx)


async def image_edit(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    provider = create_image_provider(ctx.config)
    return await ImageGenerationService(provider).edit(arguments, ctx)


def _persist_image_outputs(
    *,
    response: ProviderImageResponse,
    output_format: str,
    image_config: dict[str, Any],
    downloader: Any,
    ctx: RequestContext,
    provider_model: str,
    source_tool: str,
    size: str,
    quality: str,
    extra_metadata: dict[str, Any] | None = None,
    deadline: ImageDeadline | None = None,
) -> dict[str, Any]:
    artifacts = []
    response_types: list[str] = []
    for item in response.outputs:
        if deadline:
            deadline.check()
        downloaded = _resolve_output(item, output_format, image_config, downloader)
        if deadline:
            deadline.check()
        metadata = {
            "provider": "openai_compatible",
            "model": provider_model,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "provider_output": {
                "type": item.response_type,
                "host": downloaded.source_host,
            },
        }
        if extra_metadata:
            metadata.update(extra_metadata)
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
            source_tool=source_tool,
            source_job_id=ctx.job_id,
            metadata=metadata,
        )
        artifacts.append(artifact.to_metadata(download_url=artifact_download_url(ctx.config, artifact, ctx.metadata)))
        response_types.append(item.response_type)

    return success(
        request_id=ctx.request_id,
        artifact=artifacts[0],
        artifacts=artifacts,
        provider_output={"types": response_types, "count": len(artifacts)},
    )


def download_image_url(url: str, image_config: dict[str, Any]) -> DownloadedImage:
    parsed = urlparse(url)
    provider_config = image_config.get("openai_compatible", {})
    allowed_hosts = set(provider_config.get("allowed_image_url_hosts") or [])
    allow_http = bool(image_config.get("allow_http_image_urls", False))
    if parsed.scheme != "https" and not (allow_http and parsed.scheme == "http"):
        raise GatewayError(PROVIDER_UNAVAILABLE, "provider image URL scheme is not allowed", retryable=False)
    if not parsed.hostname or parsed.hostname not in allowed_hosts:
        raise GatewayError(PROVIDER_UNAVAILABLE, "provider image URL host is not allowed", retryable=False)

    logger.info("provider image URL download started", extra={"source_host": parsed.hostname})
    max_bytes = int(image_config.get("max_download_bytes", 10 * 1024 * 1024))
    req = request.Request(
        url,
        method="GET",
        headers={
            "Accept": "image/png,image/jpeg,image/webp,*/*",
            "User-Agent": "home-mcp-gateway/0.2.0",
        },
    )
    try:
        with request.urlopen(req, timeout=int(provider_config.get("timeout_seconds", 60))) as response:
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
    except error.HTTPError as exc:
        status = exc.code
        exc.close()
        raise GatewayError(PROVIDER_UNAVAILABLE, f"provider image download failed with HTTP {status}", retryable=True) from exc
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
    if size == "auto":
        return "auto"
    allowed = set(image_config.get("allowed_sizes") or [])
    if not isinstance(size, str) or size not in allowed:
        raise GatewayError(INVALID_ARGUMENT, "size is not allowed")
    return size


def _validated_member(value: str, allowed_values: list[str], field: str) -> str:
    if not isinstance(value, str) or value not in set(allowed_values):
        raise GatewayError(INVALID_ARGUMENT, f"{field} is not allowed")
    return value


def _validated_image_artifact_ids(arguments: dict[str, Any], image_config: dict[str, Any]) -> list[str]:
    artifact_ids: list[str] = []
    single_id = arguments.get("image_artifact_id")
    if single_id is not None:
        if not isinstance(single_id, str) or not single_id:
            raise GatewayError(INVALID_ARGUMENT, "image_artifact_id is invalid")
        artifact_ids.append(single_id)
    multi_ids = arguments.get("image_artifact_ids")
    if multi_ids is not None:
        if not isinstance(multi_ids, list) or not all(isinstance(item, str) and item for item in multi_ids):
            raise GatewayError(INVALID_ARGUMENT, "image_artifact_ids is invalid")
        artifact_ids.extend(multi_ids)
    if not artifact_ids:
        raise GatewayError(INVALID_ARGUMENT, "at least one image artifact is required")
    max_count = int(image_config.get("max_edit_input_images", 4))
    if len(artifact_ids) > max_count:
        raise GatewayError(INVALID_ARGUMENT, "too many input images")
    return artifact_ids


def _load_edit_input_images(
    artifact_ids: list[str],
    ctx: RequestContext,
    image_config: dict[str, Any],
) -> list[ProviderEditImage]:
    allowed_mimes = set(image_config.get("allowed_edit_input_mime_types") or EXTENSION_BY_MIME.keys())
    max_per_image = int(image_config.get("max_edit_input_image_bytes", image_config.get("max_download_bytes", 10 * 1024 * 1024)))
    max_total = int(image_config.get("max_edit_total_image_bytes", max_per_image * max(1, len(artifact_ids))))
    total_size = 0
    images: list[ProviderEditImage] = []
    for artifact_id in artifact_ids:
        artifact = ctx.artifacts.get(artifact_id, ctx.caller)
        if artifact.mime_type not in allowed_mimes:
            raise GatewayError(UNSUPPORTED_MEDIA_TYPE, "input artifact MIME type is not supported", retryable=False)
        if artifact.size_bytes > max_per_image:
            raise GatewayError(INVALID_ARGUMENT, "input image exceeds per-image size limit")
        total_size += artifact.size_bytes
        if total_size > max_total:
            raise GatewayError(INVALID_ARGUMENT, "input images exceed total size limit")
        data = ctx.artifacts.safe_path(artifact).read_bytes()
        images.append(ProviderEditImage(filename=artifact.filename, mime_type=artifact.mime_type, data=data))
    return images


def _normalize_mime(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()
