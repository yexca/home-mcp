from __future__ import annotations

import inspect
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from core.errors import GatewayError, INVALID_ARGUMENT

FORBIDDEN_SCHEMA_KEYS = {"api_key", "token", "base_url", "authorization", "access_token", "path"}
TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")
RISK_LEVELS = {"low", "medium", "high"}

ToolHandler = Callable[..., Awaitable[dict[str, Any]] | dict[str, Any]]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None
    risk_level: str
    handler: ToolHandler
    creates_job: bool = False
    background_handler: ToolHandler | None = None


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        _validate_definition(definition)
        if definition.name in self._tools:
            raise GatewayError(INVALID_ARGUMENT, f"duplicate tool registered: {definition.name}")
        self._tools[definition.name] = definition

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise GatewayError(INVALID_ARGUMENT, f"unknown tool: {name}") from exc

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": item.name,
                "title": item.title,
                "description": item.description,
                "input_schema": item.input_schema,
                "output_schema": item.output_schema,
                "risk_level": item.risk_level,
                "creates_job": item.creates_job,
            }
            for item in sorted(self._tools.values(), key=lambda tool: tool.name)
        ]


def _validate_definition(definition: ToolDefinition) -> None:
    if not TOOL_NAME_RE.match(definition.name):
        raise GatewayError(INVALID_ARGUMENT, "tool name must be snake_case")
    if definition.risk_level not in RISK_LEVELS:
        raise GatewayError(INVALID_ARGUMENT, "tool risk_level is invalid")
    if definition.input_schema.get("type") != "object":
        raise GatewayError(INVALID_ARGUMENT, "tool input_schema root must be object")
    bad = _find_forbidden_schema_key(definition.input_schema)
    if bad:
        raise GatewayError(INVALID_ARGUMENT, f"forbidden schema field: {bad}")
    if not callable(definition.handler):
        raise GatewayError(INVALID_ARGUMENT, "tool handler must be callable")
    if definition.background_handler is not None:
        if not definition.creates_job:
            raise GatewayError(INVALID_ARGUMENT, "background tools must create jobs")
        if not callable(definition.background_handler):
            raise GatewayError(INVALID_ARGUMENT, "background_handler must be callable")


def _find_forbidden_schema_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered in FORBIDDEN_SCHEMA_KEYS:
                return str(key)
            if key == "properties" and isinstance(item, dict):
                for prop in item:
                    prop_lower = str(prop).lower()
                    if prop_lower in FORBIDDEN_SCHEMA_KEYS or any(token in prop_lower for token in FORBIDDEN_SCHEMA_KEYS):
                        return str(prop)
            found = _find_forbidden_schema_key(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_forbidden_schema_key(item)
            if found:
                return found
    return None


async def call_handler(handler: ToolHandler, *args: Any, **kwargs: Any) -> dict[str, Any]:
    result = handler(*args, **kwargs)
    if inspect.isawaitable(result):
        result = await result
    return result
