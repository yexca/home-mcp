from __future__ import annotations

from typing import Any

from core.artifacts import artifact_download_url
from core.errors import GatewayError, INVALID_ARGUMENT, UNSUPPORTED_MEDIA_TYPE
from modules.tts.providers.local_http import LocalHttpTTSProvider, MockTTSProvider
from tools.result import success
from transport.request_context import RequestContext

EXTENSION_BY_MIME = {
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
}
MIME_BY_FORMAT = {
    "ogg": "audio/ogg",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
}


class TTSSynthesisService:
    def __init__(self, provider: Any) -> None:
        self.provider = provider

    async def synthesize(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        tts_config = ctx.config.modules.get("tts", {})
        text = _validated_text(arguments.get("text", ""), int(tts_config.get("max_text_chars", 4000)))
        voice = _validated_member(arguments.get("voice", tts_config.get("default_voice")), tts_config.get("voices", []), "voice")
        language = _validated_member(
            arguments.get("language", tts_config.get("default_language")),
            tts_config.get("languages", []),
            "language",
        )
        output_format = _validated_member(
            arguments.get("format", tts_config.get("default_format", "wav")),
            tts_config.get("allowed_formats", ["ogg", "mp3", "wav"]),
            "format",
        )
        speed = _validated_speed(arguments.get("speed", tts_config.get("default_speed", 1.0)), tts_config)

        ctx.limits.check(
            f"tts_synthesize:{ctx.caller.caller_id}:day",
            limit=int(ctx.config.limits.get("tts_jobs_per_caller_per_day", 100)),
            window_seconds=24 * 60 * 60,
        )
        response = self.provider.synthesize(
            text=text,
            voice=voice,
            language=language,
            format=output_format,
            speed=speed,
        )
        allowed_mimes = set(tts_config.get("allowed_mime_types") or ctx.config.policy.get("audio_mime_types") or EXTENSION_BY_MIME)
        if response.mime_type not in allowed_mimes or response.mime_type not in EXTENSION_BY_MIME:
            raise GatewayError(UNSUPPORTED_MEDIA_TYPE, "tts audio MIME type is not supported", retryable=False)
        if response.mime_type != MIME_BY_FORMAT[output_format]:
            raise GatewayError(UNSUPPORTED_MEDIA_TYPE, "tts provider returned a different audio format", retryable=False)

        artifact = ctx.artifacts.create_from_bytes(
            kind="audio",
            mime_type=response.mime_type,
            extension=EXTENSION_BY_MIME[response.mime_type],
            data=response.data,
            owner=ctx.caller,
            source_tool="tts_synthesize",
            source_job_id=ctx.job_id,
            metadata={
                "provider": response.provider,
                "voice": response.voice,
                "language": response.language,
                "format": response.format,
                "speed": speed,
            },
        )
        return success(
            request_id=ctx.request_id,
            artifact=artifact.to_metadata(download_url=artifact_download_url(ctx.config, artifact, ctx.metadata)),
            provider_output={"type": "audio", "mime_type": response.mime_type},
        )


async def tts_synthesize(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    tts_config = ctx.config.modules.get("tts", {})
    provider_name = tts_config.get("provider", "mock")
    if provider_name == "local_http":
        local_http = tts_config.get("local_http", {})
        provider = LocalHttpTTSProvider(
            url=str(local_http["url"]),
            timeout_seconds=int(local_http.get("timeout_seconds", 30)),
            api_key=str(local_http.get("api_key", "")),
        )
    elif provider_name == "mock":
        provider = MockTTSProvider()
    else:
        raise GatewayError(INVALID_ARGUMENT, "tts provider is not supported")
    return await TTSSynthesisService(provider).synthesize(arguments, ctx)


def _validated_text(text: str, max_chars: int) -> str:
    if not isinstance(text, str) or not text.strip():
        raise GatewayError(INVALID_ARGUMENT, "text is required")
    if len(text) > max_chars:
        raise GatewayError(INVALID_ARGUMENT, "text is too long")
    return text


def _validated_member(value: Any, allowed_values: list[str], field: str) -> str:
    if not isinstance(value, str) or value not in set(allowed_values):
        raise GatewayError(INVALID_ARGUMENT, f"{field} is not allowed")
    return value


def _validated_speed(value: Any, tts_config: dict[str, Any]) -> float:
    if not isinstance(value, (int, float)):
        raise GatewayError(INVALID_ARGUMENT, "speed must be a number")
    speed = float(value)
    min_speed = float(tts_config.get("min_speed", 0.5))
    max_speed = float(tts_config.get("max_speed", 2.0))
    if speed < min_speed or speed > max_speed:
        raise GatewayError(INVALID_ARGUMENT, "speed is out of range")
    return speed
