from __future__ import annotations

from typing import Any

from core.errors import GatewayError, INVALID_ARGUMENT, POLICY_DENIED, UNSUPPORTED_MEDIA_TYPE
from modules.matrix.providers.http_client import MatrixHttpClient
from tools.result import success
from transport.request_context import RequestContext


class MatrixService:
    def __init__(self, client: MatrixHttpClient) -> None:
        self.client = client

    async def send_text(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        matrix_config = ctx.config.modules.get("matrix", {})
        room_id = _validated_room(arguments.get("room_id"), ctx)
        text = _validated_text(arguments.get("text", ""), int(matrix_config.get("max_text_chars", 4000)), "text")
        _check_room_rate_limit(room_id, ctx)
        response = self.client.send_text(room_id=room_id, body=text)
        return success(request_id=ctx.request_id, event_id=response.event_id, room_id=room_id)

    async def send_audio(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        room_id = _validated_room(arguments.get("room_id"), ctx)
        artifact_id = arguments.get("audio_artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise GatewayError(INVALID_ARGUMENT, "audio_artifact_id is required")
        artifact = ctx.artifacts.get(artifact_id, ctx.caller)
        allowed_mimes = set(ctx.config.modules.get("tts", {}).get("allowed_mime_types") or ctx.config.policy.get("audio_mime_types") or [])
        if artifact.kind != "audio" or artifact.mime_type not in allowed_mimes:
            raise GatewayError(UNSUPPORTED_MEDIA_TYPE, "audio artifact MIME type is not supported", retryable=False)
        body = arguments.get("body") or artifact.filename
        body = _validated_text(body, 512, "body")
        data = ctx.artifacts.safe_path(artifact).read_bytes()
        _check_room_rate_limit(room_id, ctx)
        uploaded = self.client.upload_media(data=data, mime_type=artifact.mime_type, filename=artifact.filename)
        sent = self.client.send_audio(
            room_id=room_id,
            body=body,
            content_uri=uploaded.content_uri,
            mime_type=artifact.mime_type,
            size_bytes=artifact.size_bytes,
        )
        media = {
            "artifact_id": artifact.id,
            "content_uri": uploaded.content_uri,
            "mime_type": artifact.mime_type,
            "size_bytes": artifact.size_bytes,
            "filename": artifact.filename,
        }
        return success(request_id=ctx.request_id, event_id=sent.event_id, room_id=room_id, media=media)


async def matrix_send_text(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    return await MatrixService(_client_from_settings(ctx)).send_text(arguments, ctx)


async def matrix_send_audio(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    return await MatrixService(_client_from_settings(ctx)).send_audio(arguments, ctx)


def _client_from_settings(ctx: RequestContext) -> MatrixHttpClient:
    matrix_config = ctx.config.modules.get("matrix", {})
    homeserver = matrix_config.get("homeserver")
    access_token = matrix_config.get("access_token")
    if not isinstance(homeserver, str) or not homeserver or not isinstance(access_token, str) or not access_token:
        raise GatewayError(INVALID_ARGUMENT, "matrix module is not configured")
    return MatrixHttpClient(
        homeserver=homeserver,
        access_token=access_token,
        timeout_seconds=int(matrix_config.get("timeout_seconds", 30)),
    )


def _validated_room(room_id: Any, ctx: RequestContext) -> str:
    if not isinstance(room_id, str) or not room_id:
        raise GatewayError(INVALID_ARGUMENT, "room_id is required")
    allowed_rooms = set(ctx.config.policy.get("allowed_matrix_rooms") or ctx.config.modules.get("matrix", {}).get("allowed_rooms") or [])
    if room_id not in allowed_rooms:
        raise GatewayError(POLICY_DENIED, "matrix room is not allowlisted", retryable=False)
    return room_id


def _validated_text(text: Any, max_chars: int, field: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise GatewayError(INVALID_ARGUMENT, f"{field} is required")
    if len(text) > max_chars:
        raise GatewayError(INVALID_ARGUMENT, f"{field} is too long")
    return text


def _check_room_rate_limit(room_id: str, ctx: RequestContext) -> None:
    ctx.limits.check(
        f"matrix:{room_id}:minute",
        limit=int(ctx.config.limits.get("matrix_messages_per_room_per_minute", 5)),
        window_seconds=60,
    )
