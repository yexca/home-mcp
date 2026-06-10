from __future__ import annotations

from typing import Any

from core.artifacts import artifact_download_url
from core.errors import GatewayError, INVALID_ARGUMENT, POLICY_DENIED, UNSUPPORTED_MEDIA_TYPE
from modules.printer.providers.bridge_http import BridgeHttpPrinterProvider
from tools.result import success
from transport.request_context import RequestContext

EXTENSION_BY_MIME = {
    "application/pdf": "pdf",
    "image/png": "png",
    "image/jpeg": "jpg",
}


class PrinterService:
    def __init__(self, provider: BridgeHttpPrinterProvider) -> None:
        self.provider = provider

    async def list_printers(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        allowed = _allowed_printers(ctx)
        printers = []
        for printer in self.provider.list_printers():
            if printer.id not in allowed:
                continue
            printers.append(
                {
                    "id": printer.id,
                    "name": printer.name,
                    "status": printer.status,
                    "allowed": True,
                    "capabilities": printer.capabilities or {},
                }
            )
        return success(request_id=ctx.request_id, printers=printers)

    async def print_file(self, arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
        printer_config = ctx.config.modules.get("printer", {})
        printer_id = _validated_printer_id(arguments.get("printer_id"), ctx)
        artifact_id = arguments.get("artifact_id")
        if not isinstance(artifact_id, str) or not artifact_id:
            raise GatewayError(INVALID_ARGUMENT, "artifact_id is required")
        artifact = ctx.artifacts.get(artifact_id, ctx.caller)
        allowed_mimes = set(printer_config.get("allowed_mime_types") or ctx.config.policy.get("printable_mime_types") or [])
        if artifact.mime_type not in allowed_mimes or artifact.mime_type not in EXTENSION_BY_MIME:
            raise GatewayError(UNSUPPORTED_MEDIA_TYPE, "artifact MIME type is not printable", retryable=False)
        max_file_bytes = int(printer_config.get("max_file_bytes", ctx.config.artifacts.get("max_artifact_bytes", 50 * 1024 * 1024)))
        if artifact.size_bytes > max_file_bytes:
            raise GatewayError(INVALID_ARGUMENT, "print artifact exceeds max size")

        copies = _validated_copies(arguments.get("copies", 1), int(printer_config.get("max_copies", 1)))
        duplex = _validated_option(arguments.get("duplex", printer_config.get("default_duplex", "none")), "duplex", printer_config)
        color = _validated_option(arguments.get("color", printer_config.get("default_color", "auto")), "color", printer_config)

        ctx.limits.check(
            f"printer_print_file:{ctx.caller.caller_id}:day",
            limit=int(ctx.config.limits.get("print_jobs_per_caller_per_day", 20)),
            window_seconds=24 * 60 * 60,
        )
        data = ctx.artifacts.safe_path(artifact).read_bytes()
        response = self.provider.print_file(
            printer_id=printer_id,
            filename=artifact.filename,
            mime_type=artifact.mime_type,
            data=data,
            copies=copies,
            duplex=duplex,
            color=color,
            artifact_id=artifact.id,
        )
        print_job = {
            "bridge_job_id": response.bridge_job_id,
            "status": response.status,
            "printer_id": response.printer_id,
            "copies": copies,
            "duplex": duplex,
            "color": color,
        }
        return success(
            request_id=ctx.request_id,
            print_job=print_job,
            artifact=artifact.to_metadata(download_url=artifact_download_url(ctx.config, artifact, ctx.metadata)),
        )


async def printer_list(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    return await PrinterService(_provider_from_settings(ctx)).list_printers(arguments, ctx)


async def printer_print_file(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    return await PrinterService(_provider_from_settings(ctx)).print_file(arguments, ctx)


def _provider_from_settings(ctx: RequestContext) -> BridgeHttpPrinterProvider:
    printer_config = ctx.config.modules.get("printer", {})
    if printer_config.get("provider", "bridge_http") != "bridge_http":
        raise GatewayError(INVALID_ARGUMENT, "printer provider is not supported")
    bridge_config = printer_config.get("bridge_http", {})
    base_url = bridge_config.get("url")
    if not isinstance(base_url, str) or not base_url:
        raise GatewayError(INVALID_ARGUMENT, "printer bridge is not configured")
    return BridgeHttpPrinterProvider(
        base_url=base_url,
        timeout_seconds=int(bridge_config.get("timeout_seconds", 30)),
        api_key=str(bridge_config.get("api_key", "")),
    )


def _allowed_printers(ctx: RequestContext) -> set[str]:
    return set(ctx.config.policy.get("allowed_printers") or ctx.config.modules.get("printer", {}).get("allowed_printers") or [])


def _validated_printer_id(value: Any, ctx: RequestContext) -> str:
    if not isinstance(value, str) or not value:
        raise GatewayError(INVALID_ARGUMENT, "printer_id is required")
    if value not in _allowed_printers(ctx):
        raise GatewayError(POLICY_DENIED, "printer is not allowlisted", retryable=False)
    return value


def _validated_copies(value: Any, max_copies: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise GatewayError(INVALID_ARGUMENT, "copies must be an integer")
    if value < 1 or value > max_copies:
        raise GatewayError(INVALID_ARGUMENT, "copies is out of range")
    return value


def _validated_option(value: Any, field: str, printer_config: dict[str, Any]) -> str:
    allowed_key = "duplex_modes" if field == "duplex" else "color_modes"
    allowed = set(printer_config.get(allowed_key) or [])
    if not isinstance(value, str) or value not in allowed:
        raise GatewayError(INVALID_ARGUMENT, f"{field} is not allowed")
    return value
