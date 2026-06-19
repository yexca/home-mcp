---
name: mcp-image-send
description: Generate or edit images through the local MCP gateway, then send the resulting image artifact to Matrix with matrix_send_image.
version: 0.2.2
author: yexca
tags: [matrix, image, mcp, python]
---

# MCP Image Send

Use this skill when the user asks you to generate an image, send a generated image to Matrix, or edit an image that arrived from Matrix.

This package is intended to be copied as `skills/mcp-image-send/` inside each ZeroClaw agent workspace. The runtime files are `SKILL.md` and `mcp_image_send.py`; `test_mcp_image_send.py` is kept with the package as contract documentation and regression coverage.

The helper submits the image job through MCP, polls `job_status`, selects the generated artifact id, and calls MCP `matrix_send_image` itself. The LLM should not send a separate Matrix image marker after success.

Do not output `[IMAGE:/...]` after this skill succeeds. The old marker flow can trigger ZeroClaw visual-model token issues, and this skill no longer returns `image_markers` or `send_text`.

Matrix access tokens are selected by the MCP server from the resolved MCP caller identity. This skill only uses `MCP_GATEWAY_TOKEN` to call MCP. Do not read, pass, or ask for a Matrix `access_token`, and do not pass `matrix_account`.

## Entry Points

Run the helper with the built-in `shell` tool from the ZeroClaw workspace. Use `approved=true` when the risk profile requires it.

### local_text_to_image

Default choice for local text-to-image. Uses MCP tool `local_image_generate`, then sends the first resulting artifact to Matrix unless `send_all=true`.

```sh
python3 /zeroclaw-data/workspace/skills/mcp-image-send/mcp_image_send.py local_text_to_image '{"prompt":"...","room_id":"!room:example.org"}'
```

Common payload fields:

- `prompt` required.
- `room_id` required unless `MATRIX_DEFAULT_ROOM_ID` is set.
- `body` optional filename/caption for `matrix_send_image`.
- `negative_prompt` optional.
- `size` default `1024x1024`.
- `style` default `default`; can be `anime`, `realistic`, or `illustration` when allowed by the MCP server.
- `quality` default `standard`.
- `output_format` default `png`.
- `seed` optional integer.
- `poll_interval_seconds` default `10`.
- `max_wait_seconds` default `900`.
- `send_all` default `false`.
- `download_copy` default `false`; when true, save debug copies under `/zeroclaw-data/workspace/imgs` and return `files`.

### remote_text_to_image

Use when the LLM decides the remote image pipeline is more appropriate. Uses MCP tool `image_generate`, then sends via `matrix_send_image`.

```sh
python3 /zeroclaw-data/workspace/skills/mcp-image-send/mcp_image_send.py remote_text_to_image '{"prompt":"...","room_id":"!room:example.org"}'
```

Common payload fields:

- `prompt` required.
- `room_id` required unless `MATRIX_DEFAULT_ROOM_ID` is set.
- `body` optional filename/caption for `matrix_send_image`.
- `size` default `auto`.
- `quality` default `auto`.
- `output_format` default `png`.
- `n` forced to `1` unless the MCP server accepts another value.
- `poll_interval_seconds` default `60`.
- `max_wait_seconds` default `1800`.
- `send_all` default `false`.
- `download_copy` default `false`.

### remote_image_to_image

Use when editing a local Matrix image file. The helper uploads the local file with `artifact_upload_image`, calls `image_edit`, then sends the output artifact via `matrix_send_image`.

```sh
python3 /zeroclaw-data/workspace/skills/mcp-image-send/mcp_image_send.py remote_image_to_image '{"prompt":"make it watercolor","image_path":"/zeroclaw-data/workspace/matrix_files/input.png","room_id":"!room:example.org"}'
```

Common payload fields:

- `prompt` required.
- `room_id` required unless `MATRIX_DEFAULT_ROOM_ID` is set.
- `body` optional filename/caption for `matrix_send_image`.
- `image_path` required unless `image_paths` is provided.
- `image_paths` optional array of local image paths.
- `size` default `auto`.
- `quality` default `auto`.
- `output_format` default `png`.
- `n` forced to `1` unless the MCP server accepts another value.
- `poll_interval_seconds` default `60`.
- `max_wait_seconds` default `1800`.
- `send_all` default `false`.
- `download_copy` default `false`.

## Matrix Room Selection

Pass `room_id` in the JSON payload whenever possible. If the payload omits it, the helper uses `MATRIX_DEFAULT_ROOM_ID`.

If neither the payload nor the environment provides a room id, the script returns structured JSON with `stage: "parse_args"` and `error.type: "missing_room_id"`. It does not send a failure Matrix message.

The room must still be allowlisted by MCP policy.

## Return Contract

The script prints exactly one JSON object.

On success:

```json
{
  "ok": true,
  "status": "sent",
  "tool": "local_image_generate",
  "job_id": "job_...",
  "artifact_ids": ["art_..."],
  "selected_artifact_ids": ["art_..."],
  "room_id": "!room:example.org",
  "matrix_events": [
    {
      "event_id": "$...",
      "room_id": "!room:example.org",
      "artifact_id": "art_...",
      "media": {
        "artifact_id": "art_...",
        "content_uri": "mxc://...",
        "mime_type": "image/png",
        "size_bytes": 12345,
        "filename": "image.png"
      }
    }
  ],
  "files": []
}
```

By default `files` is empty because the helper sends MCP artifacts directly and does not download a workspace copy. With `download_copy=true`, `files` contains debug copies saved under `/zeroclaw-data/workspace/imgs`.

On failure:

```json
{
  "ok": false,
  "status": "failed",
  "stage": "poll_job",
  "error": {
    "type": "timeout",
    "message": "job timed out after 900 seconds",
    "retryable": true
  }
}
```

Do not pretend the character successfully sent an image after a failure. Explain the failure in your own voice/personality, using the structured `stage` and `error.message`. Do not directly send a failure Matrix message from this helper.

## Environment

Defaults are tuned for docker_new_6:

- `MCP_URL`: defaults to `http://host.docker.internal:8787/mcp`.
- `MCP_GATEWAY_TOKEN`: required bearer token for the gateway. Each agent should use its own token so MCP can resolve the caller and select the correct Matrix account.
- `MATRIX_DEFAULT_ROOM_ID`: optional fallback when payload `room_id` is omitted.
- `ZEROCLAW_AGENT_WORKSPACE`: defaults to `/zeroclaw-data/workspace`; used only when `download_copy=true`.
- Debug output directory: `/zeroclaw-data/workspace/imgs`.

If the script is run outside the container, set `MCP_URL`, `MCP_GATEWAY_TOKEN`, and optionally `MATRIX_DEFAULT_ROOM_ID` and `ZEROCLAW_AGENT_WORKSPACE`.

Current docker_new_6 containers must also have `python3` available. If the base ZeroClaw image does not include Python, add it to the runtime image before using this helper.

## Source Layout

In this repository the package lives at `mcp_python_skills/mcp-image-send/`.
Keep the directory self-contained so it can be copied directly to a ZeroClaw
workspace. Do not commit `__pycache__/` or local output files.
