from __future__ import annotations

from typing import Any

from app.config import Settings
from core.errors import GatewayError, INVALID_ARGUMENT
from modules.image.providers.ikun_openai_compatible import IkunOpenAICompatibleProvider

ImageProvider = Any

_PROVIDER_FACTORIES = {
    "ikun": IkunOpenAICompatibleProvider.from_settings,
}


def create_image_provider(settings: Settings) -> ImageProvider:
    image_config = settings.modules.get("image", {})
    provider_name = str(image_config.get("provider", "ikun"))
    try:
        factory = _PROVIDER_FACTORIES[provider_name]
    except KeyError as exc:
        raise GatewayError(INVALID_ARGUMENT, f"unsupported image provider: {provider_name}") from exc
    return factory(settings)
