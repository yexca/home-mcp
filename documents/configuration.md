# Configuration

Configuration starts from `config/config.example.yaml`. If `CONFIG_PATH` is set,
that file is loaded and deep-merged over the base configuration. Environment
variables written as `${NAME}` are substituted after merging.

For normal local use, create a user config file:

```powershell
Copy-Item config/user.config.example.yaml config/user.config.yaml
python -m app.main
```

Do not use `env/test.config.yaml` as the user config. It is intentionally small
and is owned by the test runner.

## Configuration Files

| File | Owner | Purpose |
| --- | --- | --- |
| `config/user.config.yaml` | User | Local runtime overrides. Created from `config/user.config.example.yaml` and ignored by git. |
| `config/user.config.example.yaml` | Repository | User-facing template with common overrides. |
| `config/config.example.yaml` | Repository | Full base/default config loaded before `CONFIG_PATH`. |
| `.env.example` | Repository | Docker Compose environment template with placeholder token/provider variables. |
| `.env` | User | Local Docker Compose environment values. Created from `.env.example` and ignored by git. |
| `env/compose.config.yaml` | Repository/deployment | Config mounted by Docker Compose. |
| `env/test.config.yaml` | Tests | Test-only config used by `env/run_tests.ps1`. |

Load order:

1. Load `config/config.example.yaml`.
2. If `CONFIG_PATH` is set, merge that file.
3. Otherwise, if `config/user.config.yaml` exists, merge it.
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

`host` and `port` are passed directly to `ThreadingHTTPServer`. Compose uses
`0.0.0.0` inside the container and publishes port `8787` to the host.

## Artifacts And Database

```yaml
artifacts:
  root: ./artifacts
  public_base_url: http://127.0.0.1:8787/artifacts
  max_artifact_bytes: 52428800

database:
  path: ./artifacts/metadata.sqlite3
  wal: true
  busy_timeout_ms: 5000
```

`public_base_url` is used to build artifact `download_url` values. It should
match the address clients can reach.

`artifacts.max_artifact_bytes` applies to generated artifacts and caller
uploads, including images imported through `artifact_upload_image`.

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

For Docker Compose, copy `.env.example` to `.env` in the repository root and
set the local values there:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Docker Compose reads `.env` for `${NAME}` substitutions in
`docker-compose.yml`, then passes those values into the container environment.

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
    local_http:
      url: ${TTS_LOCAL_HTTP_URL}
      api_key: ${TTS_API_KEY}
      timeout_seconds: 30
```

`local_http` sends JSON to the configured URL and expects an audio response with
a supported MIME type. `mock` returns deterministic local test audio.

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
