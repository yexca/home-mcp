# 04. Integration Playbook

## Host ZeroClaw Configuration

When the Gateway runs on the host:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

Expected tool names:

```text
home__health_check
home__job_status
home__artifact_get
home__image_generate
home__image_edit
home__tts_synthesize
home__matrix_send_text
home__matrix_send_audio
home__printer_list
home__printer_print_file
```

## Docker Role Play ZeroClaw Configuration

Docker Desktop connecting to a host Gateway:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://host.docker.internal:8787/mcp"
deferred_loading = true
```

For Linux Docker, add this to compose if needed:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Gateway and ZeroClaw in the same compose network:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

## Auto Approve Recommendations

Low-risk tools may be added when appropriate:

```toml
[risk_profiles.assistant]
auto_approve = [
  "home__health_check",
  "home__job_status",
  "home__artifact_get",
  "home__printer_list"
]
```

For a private local setup, `tts_synthesize` may also be added:

```toml
[risk_profiles.assistant]
auto_approve = [
  "home__health_check",
  "home__job_status",
  "home__artifact_get",
  "home__printer_list",
  "home__tts_synthesize"
]
```

Do not add these by default:

```text
home__image_generate
home__image_edit
home__matrix_send_text
home__matrix_send_audio
home__printer_print_file
```

Image tools have cost and content risk. Matrix tools send content outside the Gateway. Printer tools consume physical resources.

## Caller Token

If ZeroClaw supports custom headers for MCP servers, use:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true

[mcp.servers.headers]
Authorization = "Bearer ${GATEWAY_TOKEN_HOST}"
```

If custom headers are not available, the first version may map callers by source network or by a separate endpoint token. Document this as a lower-precision caller identity risk.

## iKun Image Integration

Environment variables:

```text
IMAGE_API_BASE_URL=https://api.example.com
IMAGE_API_MODEL=gpt-image-2
IMAGE_API_KEY=<secret>
```

Notes:

- Keep `IMAGE_API_KEY` only in environment variables or a local secret store.
- Do not copy the content of `dev_documents/ikun/key.txt` into config examples, test fixtures, logs, or integration notes.
- iKun image URLs are short-lived. The Gateway must download and persist URL outputs immediately.
- Different token groups may return URL or base64 outputs. The adapter must support both.
- Common provider failure causes include invalid token, unavailable upstream account, rejected prompt, invalid size format, copyright-sensitive content, and unsuitable prompt enhancer terms.
- The Gateway should not auto-append quality enhancer terms to prompts.

Recommended smoke test input:

```json
{
  "prompt": "A simple blue and white test card with the text MCP Gateway Smoke Test",
  "size": "1024x1024",
  "quality": "auto",
  "output_format": "png",
  "n": 1
}
```

Expected result:

- `image_generate` returns `ok = true`.
- The response includes `request_id`, `job_id`, and `artifact.id`.
- Artifact MIME is `image/png`, `image/jpeg`, or `image/webp`.
- Metadata records provider, model, size, quality, and provider_output.
- Downloading `/artifacts/{artifact_id}` returns image bytes.
- Logs and audit records do not contain `IMAGE_API_KEY`.

## Artifact Download Integration

For the internal-network first version, a plain download URL is acceptable:

```text
http://127.0.0.1:8787/artifacts/art_...
```

Recommended response headers:

```text
Content-Type: <mime_type>
Content-Length: <size_bytes>
Content-Disposition: inline; filename="<filename>"
X-Artifact-Id: <artifact_id>
Cache-Control: private, max-age=300
```

Checks:

- A non-owner caller cannot download the artifact unless admin or grant rules allow it.
- Expired artifacts cannot be downloaded.
- The canonical storage path must stay under `ARTIFACT_ROOT`.
- Before any cross-machine or public access, change artifact downloads to signed URLs bound to `expires`, `signature`, and `caller_id`.

## Troubleshooting Order

1. Check whether `/healthz` returns 200.
2. Check `/readyz` to confirm module enabled/disabled state.
3. Confirm ZeroClaw uses `name = "home"` and the tool prefix is `home__`.
4. Confirm schemas can load on demand with `deferred_loading = true`.
5. If a Docker role cannot reach the host, try `host.docker.internal`, `extra_hosts`, or a same-compose-network service name.
6. If image generation fails, reproduce with a mock provider first, then inspect real provider error mapping.
7. If artifact download fails, check caller identity, owner/grant, expiration time, canonical path, and file existence.
8. If any log contains a secret value, stop integration and fix redaction before continuing.

