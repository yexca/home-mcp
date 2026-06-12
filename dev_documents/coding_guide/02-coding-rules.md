# 02. Coding Rules

## Directory and Responsibilities

Use the directory layout from the detailed design:

```text
mcp_1/
  app/
    main.py
    config.py
    logging.py
  transport/
    mcp_server.py
    artifact_routes.py
    request_context.py
  tools/
    registry.py
    dispatcher.py
    result.py
    validation.py
  core/
    artifacts.py
    jobs.py
    policy.py
    audit.py
    errors.py
    limits.py
    ids.py
    time.py
  modules/
    image/
    tts/
    matrix/
    printer/
  config/
    config.example.yaml
  deploy/
  tests/
```

Layering rules:

- `transport/` handles MCP/SSE, HTTP routes, download responses, and connection context. It must not call providers directly.
- `tools/` is the ZeroClaw-visible contract layer. It owns schemas, registry, dispatch, and result normalization.
- `core/` must not depend on capability modules.
- `modules/*/service.py` may depend on `core` interfaces, but modules must not import each other directly.
- `modules/*/providers/` handles external APIs or local service adapters. Provider response formats must not leak into MCP tool outputs.
- Cross-module workflows are composed by ZeroClaw or the application orchestration layer. For example, TTS must not directly call the Matrix module.

## ToolDefinition Rules

Every tool must register a consistent structure:

```text
ToolDefinition
  name: string
  title: string
  description: string
  input_schema: JSON schema
  output_schema: JSON schema | null
  risk_level: low | medium | high
  handler: async function
  creates_job: boolean
```

Registration rules:

- Tool names are globally unique and use snake_case with a domain prefix.
- ZeroClaw tool names are prefixed by the MCP server name, for example `home__image_generate`.
- Schema fields use snake_case.
- `input_schema` must not include provider `base_url`, `api_key`, Matrix token, caller token, local absolute paths, or printer system paths.
- High-risk tools must declare `risk_level = high`.
- File outputs return artifact metadata only. Do not return large base64 strings or binary payloads.

## Results and Errors

Successful results must include:

- `ok: true`
- `request_id`
- `status`
- `job_id` when a job is created
- `artifact` or `artifacts` when files are produced

Failed results must include:

- `ok: false`
- `request_id`
- `status: failed`
- `error.code`
- `error.message`
- `error.retryable`

Stable error codes:

```text
INVALID_ARGUMENT
AUTH_REQUIRED
POLICY_DENIED
RATE_LIMITED
ARTIFACT_NOT_FOUND
ARTIFACT_FORBIDDEN
PROVIDER_UNAVAILABLE
PROVIDER_REJECTED
PROVIDER_TIMEOUT
UNSUPPORTED_MEDIA_TYPE
INTERNAL_ERROR
```

Implementation rules:

- The dispatcher catches all exceptions and maps them to stable error codes.
- Error messages should be readable, but must not contain tokens, full Authorization headers, sensitive paths, or provider stack traces.
- Provider network timeouts and 5xx errors may be retried with a small limit. Policy failures, invalid arguments, content rejection, and auth failures must not be retried automatically.

## RequestContext

Handlers receive `RequestContext`. They should not read runtime services from globals.

```text
RequestContext
  request_id
  caller
  config
  artifacts
  jobs
  policy
  audit
  limits
  http_client
  now
```

Caller identity resolution order:

1. `Authorization: Bearer <gateway caller token>` mapped to a configured caller.
2. Caller metadata from the MCP connection.
3. Source IP or Docker network mapping.
4. Fallback to `anonymous`.

`anonymous` may only call `health_check` by default and must not read artifacts.

## Artifact Rules

ArtifactStore must:

- Use external IDs with the `art_` prefix. IDs must not include paths, caller names, or provider IDs.
- Write first to `${ARTIFACT_ROOT}/tmp/{artifact_id}.part`, validate size and sha256, then move atomically.
- Store metadata in SQLite and file bytes on the local filesystem.
- Canonicalize paths before opening files and ensure they are under canonical `ARTIFACT_ROOT`.
- Reject `../`, UNC paths, Windows drive paths, and symlink escapes.
- Allow normal callers to read only owned artifacts or explicitly granted artifacts.
- Treat admin access as config-controlled.
- Reject normal reads for expired artifacts.

Directory mapping:

| Kind | Path | Default retention |
| --- | --- | --- |
| `image` | `images/YYYY/MM/` | 30 days |
| `audio` | `audio/YYYY/MM/` | 30 days |
| `document` | `documents/YYYY/MM/` | 30 days |
| `print` | `print/YYYY/MM/` | 7 days |
| `temp` | `tmp/` | 24 hours |

## Job and Audit Rules

Job state machine:

```text
pending -> running -> succeeded
pending -> running -> failed
pending -> canceled
running -> canceled
```

Rules:

- `progress` is between `0.0` and `1.0`.
- Terminal states are immutable.
- Normal callers can read only their own jobs.
- Slow or side-effecting tools create jobs, even when the call finishes synchronously.

Audit rules:

- Every tool call writes `audit_start` and `audit_finish`.
- prompt/text/caption summaries store only the first 200 characters and the original length.
- artifact_id, room_id, and printer_id may be recorded.
- Authorization headers, access tokens, and API keys are never recorded.
- Provider URLs are redacted by default. Store only host and response type unless an explicit temporary debug setting is enabled.

## Config and Secrets

Config loading order:

1. `config.example.yaml` provides structure and non-sensitive defaults.
2. `CONFIG_PATH` points to the real `config.yaml`.
3. Environment variables replace `${VAR}` placeholders.
4. Startup validation produces typed settings.

Rules:

- Secrets come only from environment variables or a local secret store.
- Startup logs only record whether a secret is present, for example `{"secret":"IMAGE_API_KEY","present":true}`.
- `dev_documents/ikun/key.txt` must not be loaded into runtime config, test fixtures, logs, or documentation body.
- Provider secrets for disabled modules are not required.
- Missing required secrets for enabled modules fail startup. The error must not include the secret value.

## iKun Provider Rules

`image_generate`:

- Send `POST {base_url}/v1/images/generations`.
- Use a JSON request body.
- Read `model`, `base_url`, and `api_key` from config.
- Pass `prompt` as-is. Do not auto-append quality enhancer terms.
- Keep `n = 1` for the first version.
- Require `size` to match the configured allowlist. Map `auto` to the default size.

`image_edit`:

- Send `POST {base_url}/v1/images/edits`.
- Use `multipart/form-data`.
- Use `image[]` for input image fields.
- Do not expose `stream` or `partial_images` in the MCP schema for the first version.

Response handling:

- `data` must be a non-empty array.
- Each item must contain either `url` or `b64_json`.
- iKun image URLs are short-lived. Download and persist them immediately.
- URL downloads require HTTPS and configured allowed hosts by default.
- Estimate base64 size before decoding, then validate actual decoded bytes.
- Do not include `source_account_id` in normal tool output.
- `usage`, actual `size`, actual `quality`, and actual `output_format` may be stored in artifact metadata and job summaries.

## ZeroClaw Compatibility Rules

- Recommended ZeroClaw MCP server name: `home`.
- Recommended transport: `sse`.
- Recommended endpoint path: `/mcp`.
- Keep `deferred_loading = true`.
- Low-risk tools may be added to auto approve: `home__health_check`, `home__job_status`, `home__artifact_get`, and `home__printer_list`.
- Do not include `home__image_generate`, `home__image_edit`, Matrix tools, or print actions in the default auto approve list.
- Gateway policy is the final permission source. Do not rely on ZeroClaw auto approve as the only safety layer.

