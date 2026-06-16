from __future__ import annotations

from typing import Any

from app.config import Settings
from core.errors import GatewayError, INVALID_ARGUMENT
from modules.image.providers.openai_compatible import OpenAICompatibleImageProvider

ImageProvider = Any

_PROVIDER_FACTORIES = {
    "openai_compatible": OpenAICompatibleImageProvider.from_settings,
}


def create_image_provider(settings: Settings) -> ImageProvider:
    image_config = settings.modules.get("image", {})
    provider_name = str(image_config.get("provider", "openai_compatible"))
    try:
        factory = _PROVIDER_FACTORIES[provider_name]
    except KeyError as exc:
        raise GatewayError(INVALID_ARGUMENT, f"unsupported image provider: {provider_name}") from exc
    return factory(settings)
