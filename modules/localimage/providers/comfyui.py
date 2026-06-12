from __future__ import annotations

import json
import socket
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from app.config import Settings
from core.errors import GatewayError, PROVIDER_REJECTED, PROVIDER_TIMEOUT, PROVIDER_UNAVAILABLE


@dataclass(frozen=True, slots=True)
class ComfyUIImage:
    data: bytes
    mime_type: str
    filename: str
    subfolder: str
    image_type: str


@dataclass(frozen=True, slots=True)
class ComfyUIResponse:
    prompt_id: str
    outputs: list[ComfyUIImage]


class ComfyUIProvider:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = 30,
        poll_interval_seconds: float = 1.0,
        max_wait_seconds: float = 900,
        opener: Any | None = None,
        sleeper: Any | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds
        self.opener = opener or request.urlopen
        self.sleeper = sleeper or time.sleep

    @classmethod
    def from_settings(cls, settings: Settings) -> "ComfyUIProvider":
        localimage_config = settings.modules.get("localimage", {})
        comfyui = localimage_config.get("comfyui", {})
        base_url = str(comfyui["base_url"])
        parsed = parse.urlparse(base_url)
        allowed_hosts = set(str(item) for item in comfyui.get("allowed_hosts", []))
        if not parsed.hostname or parsed.hostname not in allowed_hosts:
            raise GatewayError(PROVIDER_REJECTED, "ComfyUI host is not allowed", retryable=False)
        return cls(
            base_url=base_url,
            timeout_seconds=int(comfyui.get("timeout_seconds", 30)),
            poll_interval_seconds=float(comfyui.get("poll_interval_seconds", 1)),
            max_wait_seconds=float(comfyui.get("max_wait_seconds", localimage_config.get("total_timeout_seconds", 900))),
        )

    def generate(self, workflow: dict[str, Any]) -> ComfyUIResponse:
        prompt_id = self._queue_prompt(workflow)
        history = self._wait_for_history(prompt_id)
        images = self._download_outputs(history, prompt_id)
        if not images:
            raise GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI returned no image outputs", retryable=True)
        return ComfyUIResponse(prompt_id=prompt_id, outputs=images)

    def _queue_prompt(self, workflow: dict[str, Any]) -> str:
        client_id = uuid.uuid4().hex
        body = json.dumps({"prompt": workflow, "client_id": client_id}, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}/prompt",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        decoded = self._send_json(req)
        prompt_id = decoded.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI did not return a prompt id", retryable=True)
        return prompt_id

    def _wait_for_history(self, prompt_id: str) -> dict[str, Any]:
        deadline = time.monotonic() + self.max_wait_seconds
        while time.monotonic() < deadline:
            req = request.Request(f"{self.base_url}/history/{parse.quote(prompt_id)}", method="GET", headers={"Accept": "application/json"})
            decoded = self._send_json(req)
            item = decoded.get(prompt_id)
            if isinstance(item, dict):
                if _has_execution_error(item):
                    raise GatewayError(PROVIDER_REJECTED, "ComfyUI workflow execution failed", retryable=False)
                outputs = item.get("outputs")
                if isinstance(outputs, dict) and outputs:
                    return item
            self.sleeper(max(0.01, self.poll_interval_seconds))
        raise GatewayError(PROVIDER_TIMEOUT, "ComfyUI generation timed out", retryable=True)

    def _download_outputs(self, history_item: dict[str, Any], prompt_id: str) -> list[ComfyUIImage]:
        outputs = history_item.get("outputs")
        if not isinstance(outputs, dict):
            return []
        images: list[ComfyUIImage] = []
        for node_output in outputs.values():
            if not isinstance(node_output, dict):
                continue
            raw_images = node_output.get("images")
            if not isinstance(raw_images, list):
                continue
            for image in raw_images:
                if not isinstance(image, dict):
                    continue
                filename = image.get("filename")
                if not isinstance(filename, str) or not filename:
                    continue
                subfolder = image.get("subfolder") if isinstance(image.get("subfolder"), str) else ""
                image_type = image.get("type") if isinstance(image.get("type"), str) else "output"
                data, mime_type = self._view_image(filename=filename, subfolder=subfolder, image_type=image_type)
                images.append(
                    ComfyUIImage(
                        data=data,
                        mime_type=mime_type,
                        filename=filename,
                        subfolder=subfolder,
                        image_type=image_type,
                    )
                )
        return images

    def _view_image(self, *, filename: str, subfolder: str, image_type: str) -> tuple[bytes, str]:
        query = parse.urlencode({"filename": filename, "subfolder": subfolder, "type": image_type})
        req = request.Request(
            f"{self.base_url}/view?{query}",
            method="GET",
            headers={"Accept": "image/png,image/jpeg,image/webp,*/*"},
        )
        try:
            with self.opener(req, timeout=self.timeout_seconds) as response:
                mime_type = _normalize_mime(response.headers.get("Content-Type", ""))
                data = response.read()
        except error.HTTPError as exc:
            gateway_error = _map_http_error(exc)
            exc.close()
            raise gateway_error from exc
        except (TimeoutError, socket.timeout) as exc:
            raise GatewayError(PROVIDER_TIMEOUT, "ComfyUI image download timed out", retryable=True) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise GatewayError(PROVIDER_TIMEOUT, "ComfyUI image download timed out", retryable=True) from exc
            raise GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI image download failed", retryable=True) from exc
        except OSError as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI image download failed", retryable=True) from exc
        if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
            mime_type = _mime_from_filename(filename)
        return data, mime_type

    def _send_json(self, req: request.Request) -> dict[str, Any]:
        try:
            with self.opener(req, timeout=self.timeout_seconds) as response:
                body = response.read()
        except error.HTTPError as exc:
            gateway_error = _map_http_error(exc)
            exc.close()
            raise gateway_error from exc
        except (TimeoutError, socket.timeout) as exc:
            raise GatewayError(PROVIDER_TIMEOUT, "ComfyUI request timed out", retryable=True) from exc
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise GatewayError(PROVIDER_TIMEOUT, "ComfyUI request timed out", retryable=True) from exc
            raise GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI is unavailable", retryable=True) from exc
        except OSError as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI is unavailable", retryable=True) from exc

        try:
            decoded = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI returned non-json response", retryable=True) from exc
        if not isinstance(decoded, dict):
            raise GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI returned invalid response", retryable=True)
        return decoded


def _map_http_error(exc: error.HTTPError) -> GatewayError:
    if exc.code in {400, 401, 403}:
        return GatewayError(PROVIDER_REJECTED, "ComfyUI rejected the request", retryable=False)
    if exc.code >= 500:
        return GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI is unavailable", retryable=True)
    return GatewayError(PROVIDER_UNAVAILABLE, "ComfyUI request failed", retryable=True)


def _has_execution_error(history_item: dict[str, Any]) -> bool:
    status = history_item.get("status")
    if not isinstance(status, dict):
        return False
    status_str = status.get("status_str")
    completed = status.get("completed")
    return status_str in {"error", "failed"}


def _normalize_mime(content_type: str) -> str:
    return content_type.split(";", 1)[0].strip().lower()


def _mime_from_filename(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lowered.endswith(".webp"):
        return "image/webp"
    return "image/png"
