from __future__ import annotations

import json
import socket
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from core.errors import GatewayError, PROVIDER_REJECTED, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE, RATE_LIMITED


@dataclass(frozen=True, slots=True)
class MatrixUploadResponse:
    content_uri: str


@dataclass(frozen=True, slots=True)
class MatrixSendResponse:
    event_id: str


class MatrixHttpClient:
    def __init__(
        self,
        *,
        homeserver: str,
        access_token: str,
        timeout_seconds: int = 30,
        opener: Any | None = None,
    ) -> None:
        self.homeserver = homeserver.rstrip("/")
        self.access_token = access_token
        self.timeout_seconds = timeout_seconds
        self.opener = opener or request.urlopen

    def upload_media(self, *, data: bytes, mime_type: str, filename: str) -> MatrixUploadResponse:
        url = f"{self.homeserver}/_matrix/media/v3/upload?filename={parse.quote(filename)}"
        req = request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": mime_type,
                "Accept": "application/json",
            },
        )
        decoded = self._send_json(req)
        content_uri = decoded.get("content_uri")
        if not isinstance(content_uri, str) or not content_uri:
            raise GatewayError(PROVIDER_UNAVAILABLE, "matrix media upload returned no content URI", retryable=True)
        return MatrixUploadResponse(content_uri=content_uri)

    def send_text(self, *, room_id: str, body: str) -> MatrixSendResponse:
        content = {"msgtype": "m.text", "body": body}
        return self.send_event(room_id=room_id, event_type="m.room.message", content=content)

    def send_audio(
        self,
        *,
        room_id: str,
        body: str,
        content_uri: str,
        mime_type: str,
        size_bytes: int,
    ) -> MatrixSendResponse:
        content = {
            "msgtype": "m.audio",
            "body": body,
            "url": content_uri,
            "info": {"mimetype": mime_type, "size": size_bytes},
        }
        return self.send_event(room_id=room_id, event_type="m.room.message", content=content)

    def send_image(
        self,
        *,
        room_id: str,
        body: str,
        content_uri: str,
        mime_type: str,
        size_bytes: int,
        width: int | None = None,
        height: int | None = None,
    ) -> MatrixSendResponse:
        info: dict[str, Any] = {"mimetype": mime_type, "size": size_bytes}
        if width is not None:
            info["w"] = width
        if height is not None:
            info["h"] = height
        content = {
            "msgtype": "m.image",
            "body": body,
            "url": content_uri,
            "info": info,
        }
        return self.send_event(room_id=room_id, event_type="m.room.message", content=content)

    def send_event(self, *, room_id: str, event_type: str, content: dict[str, Any]) -> MatrixSendResponse:
        txn_id = uuid.uuid4().hex
        encoded_room = parse.quote(room_id, safe="")
        encoded_event = parse.quote(event_type, safe="")
        url = f"{self.homeserver}/_matrix/client/v3/rooms/{encoded_room}/send/{encoded_event}/{txn_id}"
        req = request.Request(
            url,
            data=json.dumps(content, ensure_ascii=False).encode("utf-8"),
            method="PUT",
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        decoded = self._send_json(req)
        event_id = decoded.get("event_id")
        if not isinstance(event_id, str) or not event_id:
            raise GatewayError(PROVIDER_UNAVAILABLE, "matrix send returned no event ID", retryable=True)
        return MatrixSendResponse(event_id=event_id)

    def _send_json(self, req: request.Request) -> dict[str, Any]:
        try:
            with self.opener(req, timeout=self.timeout_seconds) as response:
                data = response.read()
        except error.HTTPError as exc:
            gateway_error = _map_http_error(exc)
            exc.close()
            raise gateway_error from exc
        except (TimeoutError, socket.timeout) as exc:
            raise GatewayError(PROVIDER_TIMEOUT, "matrix provider timed out", retryable=True) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise GatewayError(PROVIDER_TIMEOUT, "matrix provider timed out", retryable=True) from exc
            raise GatewayError(PROVIDER_UNAVAILABLE, "matrix provider is unavailable", retryable=True) from exc
        except OSError as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "matrix provider is unavailable", retryable=True) from exc

        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "matrix provider returned non-json response", retryable=True) from exc
        if not isinstance(decoded, dict):
            raise GatewayError(PROVIDER_UNAVAILABLE, "matrix provider returned invalid response", retryable=True)
        return decoded


def _map_http_error(exc: error.HTTPError) -> GatewayError:
    if exc.code in {401, 403}:
        return GatewayError(PROVIDER_REJECTED, "matrix provider rejected the request", retryable=False)
    if exc.code == 429:
        return GatewayError(RATE_LIMITED, "matrix provider rate limit exceeded", retryable=True)
    if exc.code >= 500:
        return GatewayError(PROVIDER_UNAVAILABLE, "matrix provider is unavailable", retryable=True)
    return GatewayError(PROVIDER_REJECTED, "matrix provider rejected the request", retryable=False)
