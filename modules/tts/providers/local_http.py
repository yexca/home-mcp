from __future__ import annotations

import json
import socket
import wave
from dataclasses import dataclass
from io import BytesIO
from typing import Any
from urllib import error, request

from core.errors import GatewayError, PROVIDER_REJECTED, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE, RATE_LIMITED


@dataclass(frozen=True, slots=True)
class ProviderAudioResponse:
    data: bytes
    mime_type: str
    provider: str
    voice: str
    language: str
    format: str


class LocalHttpTTSProvider:
    def __init__(
        self,
        *,
        url: str,
        timeout_seconds: int = 30,
        api_key: str | None = None,
        opener: Any | None = None,
    ) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or ""
        self.opener = opener or request.urlopen

    def synthesize(
        self,
        *,
        text: str,
        voice: str,
        language: str,
        format: str,
        speed: float,
    ) -> ProviderAudioResponse:
        payload = {
            "text": text,
            "voice": voice,
            "language": language,
            "format": format,
            "speed": speed,
        }
        headers = {"Content-Type": "application/json", "Accept": "audio/ogg,audio/mpeg,audio/wav"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = request.Request(
            self.url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            method="POST",
            headers=headers,
        )
        try:
            with self.opener(req, timeout=self.timeout_seconds) as response:
                mime_type = _normalize_mime(response.headers.get("Content-Type", ""))
                return ProviderAudioResponse(
                    data=response.read(),
                    mime_type=mime_type,
                    provider="local_http",
                    voice=voice,
                    language=language,
                    format=format,
                )
        except error.HTTPError as exc:
            gateway_error = _map_http_error(exc)
            exc.close()
            raise gateway_error from exc
        except (TimeoutError, socket.timeout) as exc:
            raise GatewayError(PROVIDER_TIMEOUT, "tts provider timed out", retryable=True) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise GatewayError(PROVIDER_TIMEOUT, "tts provider timed out", retryable=True) from exc
            raise GatewayError(PROVIDER_UNAVAILABLE, "tts provider is unavailable", retryable=True) from exc
        except OSError as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "tts provider is unavailable", retryable=True) from exc


class MockTTSProvider:
    def synthesize(
        self,
        *,
        text: str,
        voice: str,
        language: str,
        format: str,
        speed: float,
    ) -> ProviderAudioResponse:
        mime_type = {"ogg": "audio/ogg", "mp3": "audio/mpeg", "wav": "audio/wav"}[format]
        data = _tiny_wav() if format == "wav" else f"mock-audio:{voice}:{language}:{speed}:{text}".encode("utf-8")
        return ProviderAudioResponse(
            data=data,
            mime_type=mime_type,
            provider="mock",
            voice=voice,
            language=language,
            format=format,
        )


def _map_http_error(exc: error.HTTPError) -> GatewayError:
    if exc.code in {401, 403}:
        return GatewayError(PROVIDER_REJECTED, "tts provider rejected the request", retryable=False)
    if exc.code == 429:
        return GatewayError(RATE_LIMITED, "tts provider rate limit exceeded", retryable=True)
    if exc.code >= 500:
        return GatewayError(PROVIDER_UNAVAILABLE, "tts provider is unavailable", retryable=True)
    return GatewayError(PROVIDER_REJECTED, "tts provider rejected the request", retryable=False)


def _normalize_mime(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _tiny_wav() -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\x00\x00" * 80)
    return buf.getvalue()
