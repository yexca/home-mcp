from __future__ import annotations

import base64
import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib import error, request

from core.errors import GatewayError, PROVIDER_REJECTED, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE, RATE_LIMITED


@dataclass(frozen=True, slots=True)
class BridgePrinter:
    id: str
    name: str
    status: str | None = None
    capabilities: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class BridgePrintResponse:
    bridge_job_id: str
    status: str
    printer_id: str


class BridgeHttpPrinterProvider:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = 30,
        api_key: str | None = None,
        opener: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.api_key = api_key or ""
        self.opener = opener or request.urlopen

    def list_printers(self) -> list[BridgePrinter]:
        req = self._request("/printers", method="GET")
        decoded = self._send_json(req)
        raw_printers = decoded.get("printers")
        if not isinstance(raw_printers, list):
            raise GatewayError(PROVIDER_UNAVAILABLE, "printer bridge returned invalid printer list", retryable=True)
        printers: list[BridgePrinter] = []
        for item in raw_printers:
            if not isinstance(item, dict):
                continue
            printer_id = item.get("id")
            name = item.get("name", printer_id)
            if isinstance(printer_id, str) and printer_id and isinstance(name, str):
                capabilities = item.get("capabilities") if isinstance(item.get("capabilities"), dict) else None
                status = item.get("status") if isinstance(item.get("status"), str) else None
                printers.append(BridgePrinter(id=printer_id, name=name, status=status, capabilities=capabilities))
        return printers

    def print_file(
        self,
        *,
        printer_id: str,
        filename: str,
        mime_type: str,
        data: bytes,
        copies: int,
        duplex: str,
        color: str,
        artifact_id: str,
    ) -> BridgePrintResponse:
        payload = {
            "printer_id": printer_id,
            "artifact_id": artifact_id,
            "filename": filename,
            "mime_type": mime_type,
            "data_b64": base64.b64encode(data).decode("ascii"),
            "options": {
                "copies": copies,
                "duplex": duplex,
                "color": color,
            },
        }
        req = self._request(
            "/print",
            method="POST",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
        )
        decoded = self._send_json(req)
        bridge_job_id = decoded.get("job_id")
        status = decoded.get("status", "submitted")
        if not isinstance(bridge_job_id, str) or not bridge_job_id:
            raise GatewayError(PROVIDER_UNAVAILABLE, "printer bridge returned no job ID", retryable=True)
        if not isinstance(status, str) or not status:
            status = "submitted"
        return BridgePrintResponse(bridge_job_id=bridge_job_id, status=status, printer_id=printer_id)

    def _request(
        self,
        path: str,
        *,
        method: str,
        data: bytes | None = None,
        content_type: str | None = None,
    ) -> request.Request:
        headers = {"Accept": "application/json"}
        if content_type:
            headers["Content-Type"] = content_type
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return request.Request(f"{self.base_url}{path}", data=data, method=method, headers=headers)

    def _send_json(self, req: request.Request) -> dict[str, Any]:
        try:
            with self.opener(req, timeout=self.timeout_seconds) as response:
                data = response.read()
        except error.HTTPError as exc:
            raise _map_http_error(exc) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise GatewayError(PROVIDER_TIMEOUT, "printer bridge timed out", retryable=True) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise GatewayError(PROVIDER_TIMEOUT, "printer bridge timed out", retryable=True) from exc
            raise GatewayError(PROVIDER_UNAVAILABLE, "printer bridge is unavailable", retryable=True) from exc
        except OSError as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "printer bridge is unavailable", retryable=True) from exc

        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "printer bridge returned non-json response", retryable=True) from exc
        if not isinstance(decoded, dict):
            raise GatewayError(PROVIDER_UNAVAILABLE, "printer bridge returned invalid response", retryable=True)
        return decoded


def _map_http_error(exc: error.HTTPError) -> GatewayError:
    if exc.code in {401, 403}:
        return GatewayError(PROVIDER_REJECTED, "printer bridge rejected the request", retryable=False)
    if exc.code == 429:
        return GatewayError(RATE_LIMITED, "printer bridge rate limit exceeded", retryable=True)
    if exc.code >= 500:
        return GatewayError(PROVIDER_UNAVAILABLE, "printer bridge is unavailable", retryable=True)
    return GatewayError(PROVIDER_REJECTED, "printer bridge rejected the request", retryable=False)
