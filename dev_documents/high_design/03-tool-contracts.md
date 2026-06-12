# 03. MCP Tool Contracts

## Naming and Common Rules

- Tool names use domain prefixes, such as `image_generate` and `tts_synthesize`.
- In ZeroClaw, full tool names are prefixed by the MCP server name, such as `home__image_generate`.
- Arguments use `snake_case`.
- Provider name, base URL, API key, Matrix token, and printer permissions are not tool arguments.
- File outputs return artifact metadata, not large binary payloads.

## Common Success Response

```json
{
  "ok": true,
  "request_id": "req_...",
  "job_id": "job_...",
  "status": "succeeded",
  "artifact": {
    "id": "art_...",
    "kind": "image",
    "mime_type": "image/png",
    "filename": "art_....png",
    "url": "http://127.0.0.1:8787/artifacts/art_...",
    "size_bytes": 123456,
    "metadata": {}
  }
}
```

## Common Failure Response

```json
{
  "ok": false,
  "request_id": "req_...",
  "job_id": "job_...",
  "status": "failed",
  "error": {
    "code": "POLICY_DENIED",
    "message": "room_id is not allowed",
    "retryable": false
  }
}
```

## Stable Error Codes

| Code | Description | Retryable |
| --- | --- | --- |
| `INVALID_ARGUMENT` | Argument validation failed | false |
| `AUTH_REQUIRED` | Caller identity is missing or invalid | false |
| `POLICY_DENIED` | Gateway policy denied the call | false |
| `RATE_LIMITED` | Concurrency, frequency, or budget limit exceeded | true |
| `ARTIFACT_NOT_FOUND` | Artifact does not exist | false |
| `ARTIFACT_FORBIDDEN` | Caller cannot read the artifact | false |
| `PROVIDER_UNAVAILABLE` | Provider is unavailable | true |
| `PROVIDER_REJECTED` | Provider rejected the request, such as content or size rejection | false |
| `PROVIDER_TIMEOUT` | Provider timed out | true |
| `UNSUPPORTED_MEDIA_TYPE` | File type is unsupported | false |
| `INTERNAL_ERROR` | Unclassified internal error | true |

## Tool List

| Tool | Risk | Default Auto Approval | Description |
| --- | --- | --- | --- |
| `health_check` | Low | Can enable | Query Gateway and module health |
| `job_status` | Low | Can enable | Query long-running task status |
| `artifact_get` | Low to medium | Can enable with permission checks | Query artifact metadata and download URL |
| `image_generate` | Medium | Enable carefully | Text-to-image |
| `image_edit` | Medium | Enable carefully | Artifact-based image editing |
| `tts_synthesize` | Low to medium | Can enable in private local use | Text-to-speech |
| `matrix_send_text` | High | Disabled by default | Send text to an allowlisted Matrix room |
| `matrix_send_audio` | High | Disabled by default | Send an audio artifact to an allowlisted Matrix room |
| `printer_list` | Low | Can enable | List available printers |
| `printer_print_file` | High | Disabled by default | Print an artifact |

## `image_generate`

Purpose: generate an image from a prompt.

Input:

```json
{
  "prompt": "string",
  "size": "auto | 1024x1024 | 1536x1024 | 1024x1536 | 3840x2160 | 2160x3840",
  "quality": "low | medium | high | auto",
  "output_format": "png | jpeg | webp",
  "n": 1
}
```

Constraints:

- `prompt` maximum length is configurable. Recommended version 1 value: 4000 characters.
- `n` defaults to and is limited to 1 in version 1. It can be expanded later if the provider supports it.
- `size` must be in the allowlist. The iKun reference says non-standard sizes may fail, so arbitrary dimensions are not accepted.
- The Gateway should not automatically append prompt enhancers such as `8K`. The iKun reference lists this kind of wording as a possible failure factor.
- `output_format` defaults to `png`.

Provider mapping:

```json
{
  "model": "${IMAGE_API_MODEL}",
  "prompt": "...",
  "n": 1,
  "size": "3840x2160",
  "quality": "auto",
  "output_format": "png"
}
```

Output:

```json
{
  "ok": true,
  "request_id": "req_...",
  "job_id": "job_...",
  "status": "succeeded",
  "artifact": {
    "id": "art_...",
    "kind": "image",
    "mime_type": "image/png",
    "url": "http://127.0.0.1:8787/artifacts/art_..."
  },
  "image": {
    "revised_prompt": "...",
    "provider_item_id": "compat-generate-...",
    "provider_output": "url | b64_json"
  }
}
```

## `image_edit`

Purpose: generate or edit a new image based on existing image artifacts.

Input:

```json
{
  "image_artifact_ids": ["art_..."],
  "prompt": "string",
  "size": "auto | 1024x1024 | 1536x1024 | 1024x1536 | 3840x2160 | 2160x3840",
  "quality": "low | medium | high | auto",
  "output_format": "png | jpeg | webp"
}
```

Compatible shorthand:

```json
{
  "image_artifact_id": "art_...",
  "prompt": "string"
}
```

Constraints:

- Version 1 accepts only artifact inputs, not arbitrary URLs or local paths.
- Input image maximum size is configurable.
- Artifact MIME type must be `image/png`, `image/jpeg`, or `image/webp`.
- The iKun edits endpoint supports `stream` and `partial_images`; version 1 does not expose these provider parameters through MCP. They are fixed to provider defaults or configuration values.

## `tts_synthesize`

Input:

```json
{
  "text": "string",
  "voice": "default",
  "language": "zh-CN | ja-JP | en-US | auto",
  "format": "ogg_opus | mp3 | wav",
  "speed": 1.0
}
```

Constraints:

- `text` maximum length is configurable. Recommended version 1 value: 2000 characters.
- `speed` should be limited to `0.5` through `2.0`.
- Output is stored as an audio artifact.

## `matrix_send_text`

Input:

```json
{
  "room_id": "!room:server",
  "text": "string",
  "formatted": false
}
```

Constraints:

- `room_id` must match the Gateway allowlist.
- `text` maximum length is configurable.
- This is a high-risk tool and should not be auto-approved by default in ZeroClaw.

## `matrix_send_audio`

Input:

```json
{
  "room_id": "!room:server",
  "audio_artifact_id": "art_...",
  "caption": "string"
}
```

Constraints:

- `room_id` must match the allowlist.
- `audio_artifact_id` must exist and be readable by the caller.
- MIME type must be an allowed audio type.

## `printer_list`

Input:

```json
{}
```

Response:

```json
{
  "ok": true,
  "request_id": "req_...",
  "printers": [
    {
      "id": "Home_Printer",
      "name": "Home Printer",
      "status": "idle",
      "allowed": true
    }
  ]
}
```

## `printer_print_file`

Input:

```json
{
  "printer_id": "Home_Printer",
  "artifact_id": "art_...",
  "copies": 1,
  "duplex": false,
  "color": false
}
```

Constraints:

- `printer_id` must match the allowlist.
- `copies` defaults to 1. The maximum is configurable; recommended version 1 value: 3.
- Version 1 prints only artifacts and does not accept arbitrary local paths.
- File MIME type must be in the printable allowlist.

## `artifact_get`

Input:

```json
{
  "artifact_id": "art_..."
}
```

Returns artifact metadata and a download URL. In version 1 the URL may be an internal static route. If the service is exposed beyond the local network later, signed URLs with expiration must be added.

## `job_status`

Input:

```json
{
  "job_id": "job_..."
}
```

Response:

```json
{
  "ok": true,
  "request_id": "req_...",
  "job": {
    "id": "job_...",
    "tool_name": "image_generate",
    "status": "running | succeeded | failed | canceled",
    "progress": 0.5,
    "created_at": "2026-06-10T00:00:00Z",
    "updated_at": "2026-06-10T00:00:10Z",
    "artifact_ids": []
  }
}
```
