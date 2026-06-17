# 05. Provider Adapter Design

## Adapter Principles

- MCP tool schemas are not bound to a specific provider.
- Adapters normalize provider requests, responses, and errors.
- Secrets are read only through the configuration/secrets reader inside adapters.
- Adapters do not write audit logs directly. They return enough metadata for the Application layer to audit.

## Image Provider: iKun OpenAI-Compatible

### Configuration

```yaml
modules:
  image:
    enabled: true
    provider: ikun_openai_compatible
    base_url: ${IMAGE_API_BASE_URL}
    api_key: ${IMAGE_API_KEY}
    model: ${IMAGE_API_MODEL}
    request_timeout_seconds: 180
    max_concurrent: 2
    allowed_sizes:
      - "1024x1024"
      - "1536x1024"
      - "1024x1536"
      - "3840x2160"
      - "2160x3840"
    default_size: "1024x1024"
    default_quality: "auto"
    default_output_format: "png"
    response_mode: auto
```

Recommended environment variables:

```text
IMAGE_API_BASE_URL=https://api.example.com
IMAGE_API_MODEL=gpt-image-2
IMAGE_API_KEY=<secret>
```

### Text-to-Image Endpoint

iKun reference endpoint:

```text
POST https://api.example.com/v1/images/generations
Authorization: Bearer <token>
Content-Type: application/json
```

Request body:

```json
{
  "model": "gpt-image-2",
  "prompt": "string",
  "n": 1,
  "size": "3840x2160"
}
```

Optional mapped fields:

```json
{
  "quality": "auto",
  "output_format": "png"
}
```

Response may contain:

```json
{
  "data": [
    {
      "id": "compat-generate-...",
      "url": "https://..."
    }
  ],
  "usage": {}
}
```

Or:

```json
{
  "data": [
    {
      "b64_json": "..."
    }
  ],
  "output_format": "png",
  "usage": {}
}
```

The iKun reference says response shape depends on the token group:

- The GPT-IMAGE-2 group returns `b64_json`.
- The text/image generation group returns `url`.
- Some URL-returning groups may downgrade 4K to 2K when 4K generation fails.

Therefore `response_mode` defaults to `auto`. The adapter must support both `url` and `b64_json` and use the actual response fields as the source of truth.

### Image Edit Endpoint

iKun reference endpoint:

```text
POST https://api.example.com/v1/images/edits
Authorization: Bearer <token>
Content-Type: multipart/form-data
```

Multipart fields:

```text
model=gpt-image-2
prompt=<prompt>
size=<allowed size>
output_format=png
moderation=auto
quality=auto
image[]=@<local input file>
```

Multiple input images use multiple `image[]` fields. Version 1 reads input files from the artifact store and uploads them to the provider.

`stream` and `partial_images` are provider-side parameters. Version 1 should not expose them through MCP tools, to avoid freezing provider details into the external contract. If needed, they can be controlled by provider configuration.

### Response Normalization

The adapter returns:

```text
ProviderImageResult
  provider_name
  model
  items[]
    provider_item_id
    revised_prompt
    output_type: url | b64_json
    url?
    b64_json?
    mime_hint?
  usage
  raw_metadata
```

The Application layer turns URL or base64 outputs into local artifacts.

### Provider Error Mapping

| Provider Condition | Gateway Error Code |
| --- | --- |
| 401/403 or invalid token | `PROVIDER_REJECTED` |
| Content policy rejection | `PROVIDER_REJECTED` |
| Upstream account or model unavailable | `PROVIDER_REJECTED` or `PROVIDER_UNAVAILABLE` |
| Invalid size | `INVALID_ARGUMENT` or `PROVIDER_REJECTED` |
| 429 | `RATE_LIMITED` |
| 5xx | `PROVIDER_UNAVAILABLE` |
| Timeout | `PROVIDER_TIMEOUT` |
| Response is not JSON | `PROVIDER_UNAVAILABLE` |
| Response has neither `url` nor `b64_json` | `PROVIDER_UNAVAILABLE` |

### iKun Failure Factors

The local iKun API reference lists common failure factors: invalid token, upstream account issues, policy-violating prompts, non-standard size formats, infringement-related content, and unsuitable quality-enhancement wording in prompts.

Gateway version 1 handling:

- Token and upstream account issues are normalized as provider errors without exposing secrets.
- Sizes are restricted to a configured allowlist.
- Prompts are passed through as provided; the Gateway does not automatically append style, quality, or resolution enhancers.
- Provider content rejection maps to `PROVIDER_REJECTED`.
- The documentation says failed generation may not charge the account, but the Gateway must not rely on that for retries. Automatic retries are limited to timeouts and 5xx responses.

## TTS Provider

Version 1 keeps provider replacement possible. The recommended first provider is `local_http`:

```yaml
modules:
  tts:
    enabled: true
    provider: local_http
    endpoint: http://tts:5000
    request_timeout_seconds: 60
    default_voice: default
    default_format: ogg_opus
```

Internal interface:

```text
synthesize(text, voice, language, format, speed) -> AudioBytesResult
```

The provider returns audio bytes, MIME type, and duration metadata. The Application layer writes an audio artifact.

## Matrix Provider

Configuration:

```yaml
modules:
  matrix:
    enabled: true
    homeserver: ${MATRIX_HOMESERVER}
    access_token: ${MATRIX_ACCESS_TOKEN}
    user_id: ${MATRIX_USER_ID}
    allowed_rooms:
      - "!example:matrix.org"
```

Internal interface:

```text
send_text(room_id, text, formatted) -> MatrixEventResult
send_audio(room_id, audio_artifact, caption) -> MatrixEventResult
send_image(room_id, image_artifact, caption) -> MatrixEventResult
```

Matrix send flow:

1. The Application layer checks the room allowlist.
2. The Matrix adapter uploads media.
3. The Matrix adapter sends the room event.
4. The adapter returns `event_id`, `room_id`, and a `media_uri` summary.

## Printer Provider

The print provider depends on deployment shape:

| Provider | Scenario |
| --- | --- |
| `bridge_http` | Gateway runs in Docker and print capability runs in a host sidecar |
| `os_print` | Gateway runs directly on the host |
| `cups_http` | Network CUPS or Linux CUPS is reachable |

Version 1 should design `bridge_http` first, while implementation can be deferred. The Gateway passes only allowlisted artifacts to the bridge and does not expose arbitrary paths.

Internal interface:

```text
list_printers() -> Printer[]
print_file(printer_id, file_path, options) -> PrintJobResult
get_print_job_status(print_job_id) -> PrintJobStatus
```

Pre-print checks:

- Printer allowlist.
- Artifact permission.
- MIME allowlist.
- Maximum `copies`.
- File size limit.

## Adding a New Provider

1. Add an adapter under the module's `providers/` directory.
2. Implement the module-defined provider interface.
3. Add configuration schema and secret declarations.
4. Add provider-level unit tests.
5. Do not modify MCP tool schemas unless the business capability itself changes.
