#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_MCP_URL = "http://host.docker.internal:8787/mcp"
DEFAULT_WORKSPACE = "/zeroclaw-data/workspace"
IMAGE_MAGIC = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpg",
    b"RIFF": "webp",
}
TERMINAL_STATUSES = {"succeeded", "failed", "canceled", "cancelled"}


class SkillError(Exception):
    def __init__(
        self,
        stage: str,
        message: str,
        *,
        error_type: str = "skill_error",
        retryable: bool = False,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message
        self.error_type = error_type
        self.retryable = retryable
        self.details = details


def ok(**kwargs: Any) -> dict[str, Any]:
    return {"ok": True, **kwargs}


def fail(exc: SkillError) -> dict[str, Any]:
    data: dict[str, Any] = {
        "ok": False,
        "status": "failed",
        "stage": exc.stage,
        "error": {
            "type": exc.error_type,
            "message": exc.message,
            "retryable": exc.retryable,
        },
    }
    if exc.details is not None:
        data["details"] = exc.details
    return data


def fail_unexpected(exc: BaseException) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "failed",
        "stage": "unexpected",
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
            "retryable": False,
        },
    }


def print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, sort_keys=True))


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    return value if value is not None and value != "" else default


def normalize_mcp_url(url: str) -> str:
    return url.rstrip("/") or DEFAULT_MCP_URL


def bearer_token() -> str:
    return env("MCP_GATEWAY_TOKEN")


def mcp_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    url = normalize_mcp_url(env("MCP_URL", DEFAULT_MCP_URL))
    payload = {
        "jsonrpc": "2.0",
        "id": f"skill-{int(time.time() * 1000)}",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    headers = {"Content-Type": "application/json"}
    token = bearer_token()
    if not token:
        raise SkillError(
            "mcp_call",
            "MCP_GATEWAY_TOKEN is required",
            error_type="missing_mcp_gateway_token",
            retryable=False,
        )
    headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SkillError(
            "mcp_call",
            f"MCP HTTP {exc.code} calling {tool_name}: {body}",
            error_type="mcp_http_error",
            retryable=500 <= exc.code < 600,
        ) from exc
    except urllib.error.URLError as exc:
        raise SkillError(
            "mcp_call",
            f"MCP connection failed calling {tool_name}: {exc.reason}",
            error_type="mcp_connection_error",
            retryable=True,
        ) from exc

    try:
        wrapper = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SkillError("mcp_call", f"MCP returned non-JSON for {tool_name}", details=raw) from exc

    if "error" in wrapper:
        raise SkillError("mcp_call", f"MCP JSON-RPC error calling {tool_name}", details=wrapper["error"])

    result = wrapper.get("result")
    if not isinstance(result, dict):
        raise SkillError("mcp_call", f"MCP returned malformed result for {tool_name}", details=wrapper)

    if "content" in result:
        return parse_mcp_content_result(tool_name, result)
    return result


def parse_mcp_content_result(tool_name: str, result: dict[str, Any]) -> dict[str, Any]:
    text_items = [
        item.get("text", "")
        for item in result.get("content", [])
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    merged: dict[str, Any] = {}
    for text in text_items:
        if not text:
            continue
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(decoded, dict):
            merged.update(decoded)
    if not merged:
        raise SkillError("mcp_call", f"MCP returned no parseable text payload for {tool_name}", details=result)
    if result.get("isError") or not merged.get("ok", False):
        message = extract_gateway_error_message(merged)
        raise SkillError(
            "mcp_call",
            f"{tool_name} failed: {message}",
            error_type="mcp_tool_error",
            retryable=bool((merged.get("error") or {}).get("retryable")),
            details=merged,
        )
    return merged


def extract_gateway_error_message(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or error.get("code") or error)
    if error:
        return str(error)
    return str(payload)


def poll_job(job_id: str, *, poll_interval_seconds: int, max_wait_seconds: int) -> dict[str, Any]:
    if max_wait_seconds <= 0:
        raise SkillError("poll_job", "max_wait_seconds must be greater than zero")
    if poll_interval_seconds <= 0:
        raise SkillError("poll_job", "poll_interval_seconds must be greater than zero")

    deadline = time.monotonic() + max_wait_seconds
    last_payload: dict[str, Any] | None = None
    while True:
        payload = mcp_call("job_status", {"job_id": job_id})
        last_payload = payload
        job = payload.get("job") if isinstance(payload.get("job"), dict) else payload
        status = str(job.get("status", "")).lower()
        if status == "succeeded":
            return job
        if status in {"failed", "canceled", "cancelled"}:
            raise SkillError(
                "poll_job",
                f"job ended with status {status}",
                error_type="job_terminal_failure",
                retryable=False,
                details=job,
            )
        now = time.monotonic()
        if now >= deadline:
            raise SkillError(
                "poll_job",
                f"job timed out after {max_wait_seconds} seconds",
                error_type="timeout",
                retryable=True,
                details=last_payload,
            )
        time.sleep(min(poll_interval_seconds, max(0.1, deadline - now)))


def first_present(data: Any, keys: tuple[str, ...]) -> Any:
    if isinstance(data, dict):
        for key in keys:
            if key in data and data[key]:
                return data[key]
    return None


def collect_artifact_ids(*values: Any) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()

    def add(value: Any) -> None:
        if isinstance(value, str) and value.startswith("art_") and value not in seen:
            seen.add(value)
            ids.append(value)

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            add(value.get("artifact_id"))
            add(value.get("id") if value.get("kind") == "image" or "mime_type" in value else None)
            for key in ("artifact_ids", "artifacts", "artifact", "result_summary", "provider_output"):
                if key in value:
                    walk(value[key])
        elif isinstance(value, list):
            for item in value:
                walk(item)
        else:
            add(value)

    for value in values:
        walk(value)
    return ids


def job_id_from_submit(payload: dict[str, Any]) -> str:
    job_id = first_present(payload, ("job_id",))
    if isinstance(job_id, str) and job_id:
        return job_id
    job = payload.get("job")
    if isinstance(job, dict) and isinstance(job.get("id"), str):
        return job["id"]
    raise SkillError("submit_job", "MCP response did not include a job_id", details=payload)


def artifact_get(artifact_id: str) -> dict[str, Any]:
    payload = mcp_call("artifact_get", {"artifact_id": artifact_id})
    artifact = payload.get("artifact")
    if not isinstance(artifact, dict):
        raise SkillError("artifact_get", "artifact_get returned no artifact metadata", details=payload)
    if not artifact.get("download_url"):
        raise SkillError("artifact_get", "artifact metadata has no download_url", details=artifact)
    return artifact


def workspace_dir() -> Path:
    return Path(env("ZEROCLAW_AGENT_WORKSPACE", DEFAULT_WORKSPACE))


def output_dir() -> Path:
    path = workspace_dir() / "imgs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def extension_from_artifact(artifact: dict[str, Any], fallback: str = "png") -> str:
    mime = str(artifact.get("mime_type") or "").lower()
    if mime == "image/png":
        return "png"
    if mime in {"image/jpeg", "image/jpg"}:
        return "jpg"
    if mime == "image/webp":
        return "webp"
    filename = str(artifact.get("filename") or "")
    suffix = Path(filename).suffix.lower().lstrip(".")
    return suffix or fallback


def download_url(url: str, destination: Path) -> None:
    request = urllib.request.Request(rewrite_download_host(url), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        raise SkillError(
            "download_artifact",
            f"artifact download HTTP {exc.code}",
            error_type="download_http_error",
            retryable=500 <= exc.code < 600,
        ) from exc
    except urllib.error.URLError as exc:
        raise SkillError(
            "download_artifact",
            f"artifact download failed: {exc.reason}",
            error_type="download_connection_error",
            retryable=True,
        ) from exc
    destination.write_bytes(data)


def rewrite_download_host(url: str) -> str:
    replacement = env("MCP_ARTIFACT_HOST_REWRITE", "")
    if replacement:
        parsed = urllib.parse.urlparse(url)
        if parsed.hostname == "host.docker.internal":
            return urllib.parse.urlunparse(parsed._replace(netloc=replacement))
    return url


def looks_like_image(path: Path) -> bool:
    head = path.read_bytes()[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n") or head.startswith(b"\xff\xd8\xff"):
        return True
    return head.startswith(b"RIFF") and path.read_bytes()[8:12] == b"WEBP"


def validate_downloaded_image(path: Path, *, min_size_bytes: int = 512) -> None:
    if not path.exists():
        raise SkillError("validate_image", f"downloaded file does not exist: {path}")
    size = path.stat().st_size
    if size < min_size_bytes:
        raise SkillError(
            "validate_image",
            f"downloaded file is too small to be a valid image: {size} bytes",
            details={"path": str(path), "size_bytes": size},
        )
    if not looks_like_image(path):
        raise SkillError("validate_image", "downloaded file does not look like png/jpeg/webp", details=str(path))


def fetch_artifact_to_workspace(artifact_id: str, *, index: int = 0) -> dict[str, Any]:
    artifact = artifact_get(artifact_id)
    ext = extension_from_artifact(artifact)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{index + 1}" if index else ""
    destination = output_dir() / f"{stamp}{suffix}.{ext}"
    download_url(str(artifact["download_url"]), destination)
    validate_downloaded_image(destination)
    return {
        "artifact_id": artifact_id,
        "file": destination.as_posix(),
        "artifact": artifact,
        "size_bytes": destination.stat().st_size,
    }


def bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def int_value(payload: dict[str, Any], key: str, default: int) -> int:
    value = payload.get(key, default)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SkillError("parse_args", f"{key} must be an integer") from exc


def room_id_from_payload(payload: dict[str, Any]) -> str:
    value = payload.get("room_id") or env("MATRIX_DEFAULT_ROOM_ID")
    if not isinstance(value, str) or not value.strip():
        raise SkillError(
            "parse_args",
            "room_id is required; provide payload room_id or MATRIX_DEFAULT_ROOM_ID",
            error_type="missing_room_id",
            retryable=False,
        )
    return value.strip()


def matrix_body_from_payload(payload: dict[str, Any]) -> str | None:
    value = payload.get("body")
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise SkillError("parse_args", "body must be a string")
    return value


def send_image_to_matrix(room_id: str, artifact_id: str, body: str | None) -> dict[str, Any]:
    args: dict[str, Any] = {"room_id": room_id, "image_artifact_id": artifact_id}
    if body is not None:
        args["body"] = body
    try:
        result = mcp_call("matrix_send_image", args)
    except SkillError as exc:
        raise SkillError(
            "matrix_send_image",
            exc.message,
            error_type=exc.error_type,
            retryable=exc.retryable,
            details={"artifact_id": artifact_id, "room_id": room_id, "tool_error": exc.details},
        ) from exc
    return {
        "event_id": result.get("event_id"),
        "room_id": result.get("room_id", room_id),
        "artifact_id": artifact_id,
        "media": result.get("media"),
        "request_id": result.get("request_id"),
        "job_id": result.get("job_id"),
        "status": result.get("status"),
    }


def submit_and_send(
    tool_name: str,
    tool_args: dict[str, Any],
    *,
    room_id: str,
    body: str | None,
    poll_interval_seconds: int,
    max_wait_seconds: int,
    send_all: bool,
    download_copy: bool,
) -> dict[str, Any]:
    submitted = mcp_call(tool_name, tool_args)
    job_id = job_id_from_submit(submitted)
    job = poll_job(job_id, poll_interval_seconds=poll_interval_seconds, max_wait_seconds=max_wait_seconds)
    artifact_ids = collect_artifact_ids(job, submitted)
    if not artifact_ids:
        raise SkillError("extract_artifact", "succeeded job did not expose any artifact_id", details=job)

    selected_ids = artifact_ids if send_all else artifact_ids[:1]
    matrix_events = [send_image_to_matrix(room_id, artifact_id, body) for artifact_id in selected_ids]
    downloads = (
        [fetch_artifact_to_workspace(artifact_id, index=i) for i, artifact_id in enumerate(selected_ids)]
        if download_copy
        else []
    )
    files = [item["file"] for item in downloads]
    return ok(
        status="sent",
        tool=tool_name,
        job_id=job_id,
        artifact_ids=artifact_ids,
        selected_artifact_ids=selected_ids,
        room_id=room_id,
        matrix_events=matrix_events,
        files=files,
        job=job,
    )


def local_text_to_image(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = require_string(payload, "prompt")
    room_id = room_id_from_payload(payload)
    body = matrix_body_from_payload(payload)
    args: dict[str, Any] = {
        "prompt": prompt,
        "size": payload.get("size", "1024x1024"),
        "quality": payload.get("quality", "standard"),
        "style": payload.get("style", "default"),
        "output_format": payload.get("output_format", "png"),
    }
    copy_optional(payload, args, "negative_prompt")
    copy_optional(payload, args, "seed")
    return submit_and_send(
        "local_image_generate",
        args,
        room_id=room_id,
        body=body,
        poll_interval_seconds=int_value(payload, "poll_interval_seconds", 10),
        max_wait_seconds=int_value(payload, "max_wait_seconds", 900),
        send_all=bool_value(payload.get("send_all"), False),
        download_copy=bool_value(payload.get("download_copy"), False),
    )


def remote_text_to_image(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = require_string(payload, "prompt")
    room_id = room_id_from_payload(payload)
    body = matrix_body_from_payload(payload)
    args: dict[str, Any] = {
        "prompt": prompt,
        "size": payload.get("size", "auto"),
        "quality": payload.get("quality", "auto"),
        "output_format": payload.get("output_format", "png"),
        "n": int(payload.get("n", 1)),
    }
    return submit_and_send(
        "image_generate",
        args,
        room_id=room_id,
        body=body,
        poll_interval_seconds=int_value(payload, "poll_interval_seconds", 60),
        max_wait_seconds=int_value(payload, "max_wait_seconds", 1800),
        send_all=bool_value(payload.get("send_all"), False),
        download_copy=bool_value(payload.get("download_copy"), False),
    )


def remote_image_to_image(payload: dict[str, Any]) -> dict[str, Any]:
    prompt = require_string(payload, "prompt")
    room_id = room_id_from_payload(payload)
    body = matrix_body_from_payload(payload)
    paths = image_paths_from_payload(payload)
    artifact_ids = [upload_local_image(path) for path in paths]
    args: dict[str, Any] = {
        "prompt": prompt,
        "size": payload.get("size", "auto"),
        "quality": payload.get("quality", "auto"),
        "output_format": payload.get("output_format", "png"),
        "n": int(payload.get("n", 1)),
    }
    if len(artifact_ids) == 1:
        args["image_artifact_id"] = artifact_ids[0]
    else:
        args["image_artifact_ids"] = artifact_ids
    result = submit_and_send(
        "image_edit",
        args,
        room_id=room_id,
        body=body,
        poll_interval_seconds=int_value(payload, "poll_interval_seconds", 60),
        max_wait_seconds=int_value(payload, "max_wait_seconds", 1800),
        send_all=bool_value(payload.get("send_all"), False),
        download_copy=bool_value(payload.get("download_copy"), False),
    )
    result["input_artifact_ids"] = artifact_ids
    return result


def require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SkillError("parse_args", f"{key} is required")
    return value


def copy_optional(source: dict[str, Any], target: dict[str, Any], key: str) -> None:
    if key in source and source[key] not in (None, ""):
        target[key] = source[key]


def image_paths_from_payload(payload: dict[str, Any]) -> list[Path]:
    raw_paths = payload.get("image_paths")
    if raw_paths is None:
        image_path = require_string(payload, "image_path")
        raw_paths = [image_path]
    if not isinstance(raw_paths, list) or not raw_paths:
        raise SkillError("parse_args", "image_paths must be a non-empty array")
    paths = [Path(str(item)) for item in raw_paths]
    for path in paths:
        if not path.exists() or not path.is_file():
            raise SkillError("upload_image", f"image file does not exist: {path}")
        validate_downloaded_image(path, min_size_bytes=16)
    return paths


def upload_local_image(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or sniff_mime(path)
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise SkillError("upload_image", f"unsupported image MIME type for {path}: {mime_type}")
    data = path.read_bytes()
    payload = {
        "filename": path.name,
        "mime_type": mime_type,
        "b64_data": base64.b64encode(data).decode("ascii"),
    }
    result = mcp_call("artifact_upload_image", payload)
    artifact = result.get("artifact")
    if not isinstance(artifact, dict) or not isinstance(artifact.get("id"), str):
        raise SkillError("upload_image", "artifact_upload_image returned no artifact id", details=result)
    return artifact["id"]


def sniff_mime(path: Path) -> str:
    head = path.read_bytes()[:16]
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    return "application/octet-stream"


def parse_payload(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SkillError("parse_args", f"payload must be valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SkillError("parse_args", "payload must be a JSON object")
    return payload


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] in {"-h", "--help"}:
        print_json(
            {
                "ok": False,
                "status": "failed",
                "stage": "usage",
                "error": {
                    "type": "usage",
                    "message": "usage: mcp_image_send.py <local_text_to_image|remote_text_to_image|remote_image_to_image> '<json-payload>'",
                    "retryable": False,
                },
            }
        )
        return 2

    action = argv[1]
    try:
        payload = parse_payload(argv[2])
        if action == "local_text_to_image":
            print_json(local_text_to_image(payload))
        elif action == "remote_text_to_image":
            print_json(remote_text_to_image(payload))
        elif action == "remote_image_to_image":
            print_json(remote_image_to_image(payload))
        else:
            raise SkillError("parse_args", f"unknown action: {action}")
        return 0
    except SkillError as exc:
        print_json(fail(exc))
        return 1
    except BaseException as exc:
        print_json(fail_unexpected(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
