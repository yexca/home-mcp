# Configuration

Configuration starts from `config/config.example.yaml`. The local runtime
override is `config/config.yaml`. If `CONFIG_PATH` is set, that file is loaded
instead of `config/config.yaml` and deep-merged over the base configuration.
Root `.env` values are loaded into the process environment without overriding
existing variables, then `${NAME}` placeholders are substituted after merging.

For normal local use, create a user config file:

```powershell
Copy-Item config/config.example.yaml config/config.yaml
Copy-Item .env.example .env
python -m app.main
```

Do not use `env/test.config.yaml` as the user config. It is intentionally small
and is owned by the test runner.

## Configuration Files

| File | Owner | Purpose |
| --- | --- | --- |
| `config/config.example.yaml` | Repository | Template/base config loaded before runtime overrides. |
| `config/config.yaml` | User | Local runtime overrides used by both Python and Docker Compose. Created from `config/config.example.yaml` and ignored by git. |
| `.env.example` | Repository | Environment template with placeholder token/provider variables. |
| `.env` | User | Local environment values for Python and Docker Compose. Created from `.env.example` and ignored by git. |
| `env/test.config.yaml` | Tests | Test-only config used by `env/run_tests.ps1`. |

Load order:

0. Load root `.env` into the process environment without overriding existing variables.
1. Load `config/config.example.yaml`.
2. If `CONFIG_PATH` is set, merge that file.
3. Otherwise, if `config/config.yaml` exists, merge it.
4. Substitute environment placeholders.

## Required Sections

The loader requires these sections:

- `server`
- `artifacts`
- `database`
- `limits`

The loader also validates module-specific settings when a module is enabled.
`artifacts.root` is created during validation.

## Server

```yaml
server:
  name: home_mcp_gateway
  version: 0.1.0
  host: 127.0.0.1
  port: 8787
  mcp_path: /mcp
  artifact_path: /artifacts
```

`host` and `port` are passed directly to `ThreadingHTTPServer`. Because the
same config is used by Docker Compose, use `0.0.0.0` when the service must be
reachable through the published Docker port. Local clients can still connect to
`http://127.0.0.1:8787`.

## Artifacts And Database

```yaml
artifacts:
  root: ./artifacts
  public_base_url: http://127.0.0.1:8787/artifacts
  signed_url_secret_env: ARTIFACT_SIGNING_SECRET
  signed_url_ttl_seconds: 300
  max_artifact_bytes: 52428800
  max_inline_artifact_bytes: 5242880

database:
  path: ./artifacts/metadata.sqlite3
  wal: true
  busy_timeout_ms: 5000
```

Artifact `download_url` values are derived from the incoming HTTP request Host
header when available. For example, a caller using
`http://127.0.0.1:8787/mcp` receives `http://127.0.0.1:8787/artifacts/...`,
while a caller using `http://192.168.1.23:8787/mcp` receives
`http://192.168.1.23:8787/artifacts/...`.

`public_base_url` is the fallback used when no request-derived base URL is
available. `ARTIFACT_PUBLIC_BASE_URL` can override this fallback at runtime
without editing YAML. Docker Compose passes this environment variable to the
container and defaults it to `http://127.0.0.1:8787/artifacts`, matching local
host use. For mixed host/container access, set it in `.env` to one unified
address that both sides can fetch, such as the Docker host LAN IP:

```dotenv
ARTIFACT_PUBLIC_BASE_URL=http://192.168.1.23:8787/artifacts
```

`artifact.download_url` values are short-lived signed URLs in the form
`/artifacts/{artifact_id}?expires=...&signature=...`. MCP calls still use
Bearer-token authentication, but artifact downloads can be fetched directly by
clients that only know the signed URL. Set `ARTIFACT_SIGNING_SECRET` to a strong
random value and keep `artifacts.signed_url_ttl_seconds` short enough for your
ZeroClaw workflow. If `ARTIFACT_SIGNING_SECRET` is not set, the gateway falls
back to `GATEWAY_TOKEN_HOST` for compatibility.

`artifacts.max_artifact_bytes` applies to generated artifacts and caller
uploads, including images imported through `artifact_upload_image`.
`artifacts.max_inline_artifact_bytes` limits image bytes returned inline through
`artifact_get`; inline content is base64-encoded in the MCP response and
therefore grows by roughly one third over the raw file size.

Retention is configured by artifact kind:

```yaml
artifacts:
  retention_days:
    image: 30
    audio: 30
    document: 30
    print: 7
    temp: 1
```

The current code checks expiry during reads. It does not include a background
cleanup worker.

## Callers And Tokens

```yaml
callers:
  host_assistant:
    role: admin
    token_env: GATEWAY_TOKEN_HOST
    shared_artifact_read: true
  role_default:
    role: role_play
    token_env: GATEWAY_TOKEN_ROLE_DEFAULT
    shared_artifact_read: false
```

At request time, bearer tokens are compared against the environment variable
named by `token_env`.

```text
Authorization: Bearer <token>
```

No token values should appear in YAML files, logs, tests, or documentation.

Copy `.env.example` to `.env` in the repository root and set the local values
there:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Docker Compose reads `.env` for `${NAME}` substitutions in
`docker-compose.yml`, then passes those values into the container environment.
Local Python runs also load `.env` directly before configuration placeholders
are substituted.

## Policy

```yaml
policy:
  default_allow: false
  anonymous_allowed_tools:
    - health_check
  high_risk_allowed_callers: {}
  allowed_matrix_rooms: []
  allowed_printers: []
```

Important behavior:

- `health_check` is always allowed.
- Anonymous callers may only call tools listed in `anonymous_allowed_tools`.
- High-risk tools need `high_risk_allowed_callers`.
- `matrix_send_text` and `matrix_send_audio` require an allowlisted `room_id`.
- `printer_print_file` requires an allowlisted `printer_id`.

Example high-risk allowlist:

```yaml
policy:
  high_risk_allowed_callers:
    host_assistant:
      - matrix_send_text
      - matrix_send_audio
      - printer_print_file
```

## Limits

The current in-memory limiter supports per-process windows. Counters reset when
the process restarts.

```yaml
limits:
  sync_tool_timeout_seconds: 120
  image_jobs_per_caller_per_day: 20
  tts_jobs_per_caller_per_day: 100
  print_jobs_per_caller_per_day: 20
  matrix_messages_per_room_per_minute: 5
```

Some configured global concurrency keys exist in config for future hardening,
but the current implementation applies the per-caller/per-room checks shown in
service code.

## Image Module

Enable with:

```yaml
modules:
  image:
    enabled: true
    provider: ikun
    default_size: 1024x1024
    allowed_sizes:
      - 1024x1024
      - 1024x1536
      - 1536x1024
    allowed_qualities:
      - auto
      - low
      - medium
      - high
    allowed_output_formats:
      - png
      - jpeg
      - webp
    total_timeout_seconds: 600
    stale_job_grace_seconds: 30
    ikun:
      base_url: ${IMAGE_API_BASE_URL}
      model: ${IMAGE_API_MODEL}
      api_key: ${IMAGE_API_KEY}
      timeout_seconds: 60
      allowed_image_url_hosts:
        - img.opcheiben.cn
```

Validation requires `provider: ikun`, a configured base URL, model, API key, and
a `default_size` that appears in `allowed_sizes`. `base_url` must be the
OpenAI-compatible API root, for example `https://api.monkey-tools.cn`; do not
include `/v1/images`, because the gateway appends the image endpoints itself.

The provider calls:

- `POST {base_url}/v1/images/generations`
- `POST {base_url}/v1/images/edits`

Provider responses may contain `url` or `b64_json`; both are persisted as local
image artifacts. URL downloads require an allowed HTTPS host unless
`allow_http_image_urls` is explicitly true. `allowed_image_url_hosts` should
list the hosts found in provider response image URLs, such as CDN hosts, and
should remain explicit rather than allowing arbitrary hosts.

`image_generate` uses a background job contract. `total_timeout_seconds`
defines the gateway-owned wall-clock deadline for provider generation, provider
response decoding, provider image URL download, and artifact persistence.
`ikun.timeout_seconds` remains the per-socket timeout passed to the provider
HTTP adapter. On gateway deadline expiry, the job is marked failed with
`PROVIDER_TIMEOUT`. `stale_job_grace_seconds` is added to the deadline when
startup reconciliation decides whether an old non-terminal image job was
abandoned during restart.

For editing existing local images, callers must first import the image bytes
with `artifact_upload_image`:

```json
{
  "filename": "input.png",
  "mime_type": "image/png",
  "b64_data": "<base64 image bytes>"
}
```

The upload tool stores the bytes as an image artifact owned by the authenticated
caller. Then pass the returned `artifact.id` as `image_artifact_id` or inside
`image_artifact_ids` for `image_edit`. The edit inputs are gateway artifact ids,
not local file paths or public URLs.

`artifact_upload_image` accepts only `image/png`, `image/jpeg`, and
`image/webp`, and also respects `modules.image.allowed_edit_input_mime_types`
when that list is configured.

## TTS Module

Enable with `provider: local_http` or `provider: mock`.

```yaml
modules:
  tts:
    enabled: true
    provider: local_http
    default_voice: default
    voices: [default]
    default_language: ja-JP
    languages: [ja-JP, en-US]
    default_format: wav
    allowed_formats: [ogg, mp3, wav]
    total_timeout_seconds: 120
    stale_job_grace_seconds: 30
    local_http:
      url: ${TTS_LOCAL_HTTP_URL}
      api_key: ${TTS_API_KEY}
      timeout_seconds: 30
```

`local_http` sends JSON to the configured URL and expects an audio response with
a supported MIME type. `mock` returns deterministic local test audio.

`tts_synthesize` uses a background job contract. It returns an accepted
`job_id` before calling the provider, and callers should poll `job_status` then
fetch completed audio with `artifact_get`. `total_timeout_seconds` is the
gateway-owned wall-clock deadline for synthesis and artifact persistence.
`local_http.timeout_seconds` remains the per-socket provider timeout. On
gateway deadline expiry, the job is marked failed with `PROVIDER_TIMEOUT`.
`stale_job_grace_seconds` is added to the deadline when startup reconciliation
decides whether an old non-terminal TTS job was abandoned during restart.

## Matrix Module

```yaml
modules:
  matrix:
    enabled: true
    homeserver: ${MATRIX_HOMESERVER}
    access_token: ${MATRIX_ACCESS_TOKEN}
    timeout_seconds: 30
```

Matrix tools are high risk. Configure room allowlists through
`policy.allowed_matrix_rooms` or `modules.matrix.allowed_rooms`, and configure
high-risk caller access in `policy.high_risk_allowed_callers`.

## Printer Module

```yaml
modules:
  printer:
    enabled: true
    provider: bridge_http
    allowed_printers:
      - test-printer
    allowed_mime_types:
      - application/pdf
      - image/png
      - image/jpeg
    max_copies: 2
    bridge_http:
      url: ${PRINTER_BRIDGE_URL}
      api_key: ${PRINTER_BRIDGE_API_KEY}
      timeout_seconds: 30
```

The provider calls:

- `GET {url}/printers`
- `POST {url}/print`

Only allowlisted printers are returned by `printer_list` and accepted by
`printer_print_file`.
