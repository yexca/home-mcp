from __future__ import annotations

from typing import Any

from app.config import Settings
from core.errors import GatewayError, INVALID_ARGUMENT
from modules.localimage.providers.comfyui import ComfyUIProvider

LocalImageProvider = Any

_PROVIDER_FACTORIES = {
    "comfyui": ComfyUIProvider.from_settings,
}


def create_localimage_provider(settings: Settings) -> LocalImageProvider:
    localimage_config = settings.modules.get("localimage", {})
    provider_name = str(localimage_config.get("provider", "comfyui"))
    try:
        factory = _PROVIDER_FACTORIES[provider_name]
    except KeyError as exc:
        raise GatewayError(INVALID_ARGUMENT, f"unsupported localimage provider: {provider_name}") from exc
    return factory(settings)
