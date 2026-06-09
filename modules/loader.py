from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType
from typing import Callable

from app.config import Settings
from core.errors import GatewayError, INVALID_ARGUMENT
from tools.registry import ToolRegistry

RegisterTools = Callable[[ToolRegistry, Settings], None]


def register_configured_module_tools(
    registry: ToolRegistry,
    settings: Settings,
    *,
    package_name: str = "modules",
) -> None:
    """Discover enabled module manifests and let each one register its tools."""
    package = importlib.import_module(package_name)
    module_names = _discover_module_names(package)
    for module_name in sorted(_enabled_module_names(settings)):
        if module_name not in module_names:
            raise GatewayError(INVALID_ARGUMENT, f"enabled module has no package: {module_name}")
        manifest = importlib.import_module(f"{package_name}.{module_name}.manifest")
        register = _register_function(manifest, module_name)
        register(registry, settings)


def _enabled_module_names(settings: Settings) -> list[str]:
    return [
        name
        for name, spec in settings.modules.items()
        if isinstance(spec, dict) and bool(spec.get("enabled", False))
    ]


def _discover_module_names(package: ModuleType) -> set[str]:
    package_paths = getattr(package, "__path__", None)
    if package_paths is None:
        raise GatewayError(INVALID_ARGUMENT, f"module package is not discoverable: {package.__name__}")
    return {
        item.name
        for item in pkgutil.iter_modules(package_paths)
        if item.ispkg and not item.name.startswith("_")
    }


def _register_function(manifest: ModuleType, module_name: str) -> RegisterTools:
    register = getattr(manifest, "register_tools", None)
    if not callable(register):
        raise GatewayError(INVALID_ARGUMENT, f"module manifest missing register_tools: {module_name}")
    return register
