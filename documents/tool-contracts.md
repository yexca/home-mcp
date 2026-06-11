# Tool Contracts

Tool schemas are the external MCP contract. They must never expose provider
base URLs, API keys, tokens, authorization headers, access tokens, local file
paths, or system paths.

All tool handlers return a dictionary. Success responses include:

```json
{
  "ok": true,
  "status": "succeeded",
  "request_id": "req_..."
}
```

Failure responses include:

```json
{
  "ok": false,
  "status": "failed",
  "request_id": "req_...",
  "error": {
    "code": "POLICY_DENIED",
    "message": "anonymous caller is not allowed for this tool",
    "retryable": false
  }
}
```

When a synchronous tool has `creates_job=True`, the dispatcher creates a job,
waits for the handler to finish, and adds `job_id` to the final result.

Some long-running tools use a background contract. These tools still have
`creates_job=True`, but return quickly with an accepted job response:

```json
{
  "ok": true,
  "status": "accepted",
  "request_id": "req_...",
  "job_id": "job_...",
  "job": {
    "id": "job_...",
    "status": "running",
    "progress": 0
  }
}
```

Callers should poll `job_status` until the job reaches a terminal state. On
success, the job record includes artifact IDs and a result summary; callers can
then fetch artifact metadata with `artifact_get`.

## Built-In Tools

### `health_check`

Risk: `low`

Input:

```json
{}
```

Output includes the server name, version, and enabled modules.

### `artifact_get`

Risk: `low`

Input:

```json
{
  "artifact_id": "art_..."
}
```

Output includes artifact metadata and a short-lived signed `download_url` when
the caller may read the artifact. The signed URL can be fetched with a direct
GET and does not require the MCP Bearer token. `artifact_get` does not inline
artifact bytes; clients should use `download_url` to fetch the file.

### `artifact_get_image`

Risk: `low`

Input:

```json
{
  "artifact_id": "art_..."
}
```

Compatibility helper for clients that explicitly want a strict image-only
inline fetch. It returns readable image artifact metadata and, for MCP JSON-RPC
clients, an additional `type: image` content item containing base64 image bytes.
Prefer `artifact_get` for new clients that can use signed downloads. The
artifact must be `image/png`, `image/jpeg`, or `image/webp`, and its raw size
must not exceed `artifacts.max_inline_artifact_bytes`.

### `artifact_upload_image`

Risk: `low`

Input:

```json
{
  "filename": "input.png",
  "mime_type": "image/png",
  "b64_data": "<base64 image bytes>"
}
```

Use this tool to import caller-provided image bytes into the gateway artifact
store before passing them to tools such as `image_edit`. The public contract
does not accept local file paths or remote image URLs for this import step.

Rules:

- The caller must be authenticated.
- `mime_type` must be `image/png`, `image/jpeg`, or `image/webp`, and must also
  be allowed by `modules.image.allowed_edit_input_mime_types` when configured.
- `b64_data` must be valid non-empty base64.
- Decoded bytes must not exceed `artifacts.max_artifact_bytes`.
- The stored artifact filename is derived from the generated artifact id. The
  caller-provided filename is stored only as metadata.

Output contains `artifact` metadata, including `id`, `mime_type`, `size_bytes`,
`sha256`, and `download_url`.

### `job_status`

Risk: `low`

Input:

```json
{
  "job_id": "job_..."
}
```

Output includes the visible job record. Non-admin callers can only read their
own jobs. Non-terminal responses include a `polling` object with
`next_poll_after_seconds`, backoff guidance, and `avoid_concurrent_polls`.
Terminal responses include `polling.terminal: true`; callers should stop
polling and use returned artifact ids with `artifact_get` when applicable.

## Image Tools

Registered only when `modules.image.enabled` is true.

### `image_generate`

Risk: `medium`; creates a background job.

Input:

```json
{
  "prompt": "A clean product photo of a small desk lamp",
  "size": "1920x1080",
  "quality": "auto",
  "output_format": "png",
  "n": 1
}
```

Required fields:

- `prompt`

Rules:

- `n` must be `1`.
- `size` must be `auto` or one of the configured `allowed_sizes`.
- `quality` must be one of the configured `allowed_qualities`.
- `output_format` must be one of the configured `allowed_output_formats`.

The tool schema exposes the configured `size`, `quality`, and `output_format`
values as enums so clients can select valid values without reading local config.
With the default config, `size` is one of `auto`, `1024x1024`,
`1024x1536`, `1536x1024`, `1280x720`, `720x1280`, `1920x1080`,
`1080x1920`, `2560x1440`, `1440x2560`, `3840x2160`, or `2160x3840`;
`quality` is one of `auto`, `low`, `medium`, or `high`.

Immediate output uses the background contract and contains `job_id` plus a
running job summary. Poll `job_status` for completion. When the job succeeds,
its `artifact_ids` and `result_summary` reference the persisted image artifact.

### `image_edit`

Risk: `medium`; creates a synchronous job.

Input:

```json
{
  "prompt": "Make the background white and keep the product unchanged",
  "image_artifact_id": "art_...",
  "size": "1920x1080",
  "quality": "auto",
  "output_format": "png",
  "n": 1
}
```

Use either `image_artifact_id` or `image_artifact_ids`. The current service
requires at least one readable image artifact and enforces configured MIME,
count, per-image size, and total-size limits. These values are gateway artifact
ids, not local paths, public URLs, or raw image bytes. To edit an existing local
image, first import it with `artifact_upload_image`, then pass the returned
`artifact.id` to `image_edit`.

## TTS Tool

Registered only when `modules.tts.enabled` is true.

### `tts_synthesize`

Risk: `medium`; creates a background job.

Input:

```json
{
  "text": "Hello from the gateway.",
  "voice": "default",
  "language": "en-US",
  "format": "wav",
  "speed": 1.0
}
```

Required fields:

- `text`

Rules:

- `voice`, `language`, and `format` must be allowed by config.
- `speed` must be within `min_speed` and `max_speed`.
- Provider MIME type must match the requested format.

Immediate output uses the background contract and contains `job_id` plus a
running job summary. It does not include an audio artifact. Poll `job_status`
until completion; when the job succeeds, its `artifact_ids` and compact
`result_summary` reference the generated audio artifact. Use `artifact_get` to
retrieve audio metadata and a signed `download_url`.

Polling guidance:

- Wait about `1-2` seconds after receiving `job_id` before the first
  `job_status` call.
- Poll every `2-5` seconds for normal TTS jobs.
- If the job remains `running`, back off to `5-10` seconds.
- Avoid sub-second polling and concurrent polls for the same job.
- Stop polling once the job reaches `succeeded` or `failed`.

## Matrix Tools

Registered only when `modules.matrix.enabled` is true.

### `matrix_send_text`

Risk: `high`; creates a job.

Input:

```json
{
  "room_id": "!room:example.org",
  "text": "Message text"
}
```

Rules:

- `room_id` must be allowlisted.
- Caller must be allowed to use this high-risk tool.
- The room is subject to `matrix_messages_per_room_per_minute`.

### `matrix_send_audio`

Risk: `high`; creates a job.

Input:

```json
{
  "room_id": "!room:example.org",
  "audio_artifact_id": "art_...",
  "body": "audio.wav"
}
```

The audio artifact must be readable by the caller, have kind `audio`, and use an
allowed audio MIME type. The service uploads it to Matrix media, then sends an
`m.audio` message.

## Printer Tools

Registered only when `modules.printer.enabled` is true.

### `printer_list`

Risk: `low`

Input:

```json
{}
```

Output contains only printers returned by the bridge whose IDs are in the
configured allowlist.

### `printer_print_file`

Risk: `high`; creates a job.

Input:

```json
{
  "printer_id": "test-printer",
  "artifact_id": "art_...",
  "copies": 1,
  "duplex": "none",
  "color": "auto"
}
```

Rules:

- `printer_id` must be allowlisted.
- Caller must be allowed to use this high-risk tool.
- Artifact MIME type must be printable.
- Artifact size must not exceed `max_file_bytes`.
- `copies`, `duplex`, and `color` must pass configured constraints.

## Stable Error Codes

The stable error code set is defined in `core.errors`:

- `INVALID_ARGUMENT`
- `AUTH_REQUIRED`
- `POLICY_DENIED`
- `RATE_LIMITED`
- `ARTIFACT_NOT_FOUND`
- `ARTIFACT_FORBIDDEN`
- `PROVIDER_UNAVAILABLE`
- `PROVIDER_REJECTED`
- `PROVIDER_TIMEOUT`
- `UNSUPPORTED_MEDIA_TYPE`
- `INTERNAL_ERROR`

Provider adapters map external HTTP errors into these gateway codes.
