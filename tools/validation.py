from __future__ import annotations

from typing import Any

from core.errors import GatewayError, INVALID_ARGUMENT

_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
}


def validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise GatewayError(INVALID_ARGUMENT, "tool arguments must be an object")
    if schema.get("type") and schema.get("type") != "object":
        raise GatewayError(INVALID_ARGUMENT, "tool schema root must be object")
    required = schema.get("required", [])
    for field in required:
        if field not in arguments:
            raise GatewayError(INVALID_ARGUMENT, f"missing required argument: {field}")
    properties = schema.get("properties", {})
    additional = schema.get("additionalProperties", True)
    if not additional:
        for field in arguments:
            if field not in properties:
                raise GatewayError(INVALID_ARGUMENT, f"unknown argument: {field}")
    for field, spec in properties.items():
        if field not in arguments:
            continue
        _validate_value(field, arguments[field], spec)
    return arguments


def _validate_value(field: str, value: Any, spec: dict[str, Any]) -> None:
    expected = spec.get("type")
    if expected:
        types = expected if isinstance(expected, list) else [expected]
        if not any(isinstance(value, _TYPE_MAP[item]) for item in types if item in _TYPE_MAP):
            raise GatewayError(INVALID_ARGUMENT, f"invalid type for argument: {field}")
    if "enum" in spec and value not in spec["enum"]:
        raise GatewayError(INVALID_ARGUMENT, f"invalid value for argument: {field}")
    if isinstance(value, str):
        if "minLength" in spec and len(value) < int(spec["minLength"]):
            raise GatewayError(INVALID_ARGUMENT, f"argument too short: {field}")
        if "maxLength" in spec and len(value) > int(spec["maxLength"]):
            raise GatewayError(INVALID_ARGUMENT, f"argument too long: {field}")
