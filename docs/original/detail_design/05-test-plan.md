# 05. Test Plan

## Objectives

Validate that the first version of `home_mcp_gateway` satisfies these requirements:

- ZeroClaw can discover and call tools through SSE MCP.
- Tool contracts and error codes are stable.
- artifact, job, and audit data remain consistent.
- iKun URL responses and base64 responses are both persisted into local artifacts.
- high-risk tools are correctly restricted by the Gateway policy engine.
- secrets never leak into responses, logs, or configuration examples.

## Unit Tests

| module | cases |
| --- | --- |
| config loader | environment substitution, missing required values, secrets not printed |
| tool registry | duplicate tool rejection, required schema, required risk level |
| dispatcher | invalid arguments, policy deny, handler exception, stable error mapping |
| id generator | correct prefix, sortable IDs, no obvious duplication |
| ArtifactStore | atomic writes, sha256, size limits, expiration, permissions |
| JobManager | state machine, terminal states immutable, caller read permissions |
| AuditLogger | start/finish pairing, input redaction, error recording |
| PolicyEngine | room/printer allowlists, role checks, artifact permissions |
| RateLimiter | global limits, caller limits, window reset |

## Image Provider Unit Tests

Use a mock HTTP client:

- `image_generate` sends the expected JSON body.
- Authorization header exists but never enters logs.
- URL response normalizes to `ProviderImageResult`.
- `b64_json` response normalizes to `ProviderImageResult`.
- empty `data` returns `PROVIDER_UNAVAILABLE`.
- non-JSON response returns `PROVIDER_UNAVAILABLE`.
- 401/403 maps to `PROVIDER_REJECTED`.
- 429 maps to `RATE_LIMITED`.
- 5xx maps to `PROVIDER_UNAVAILABLE`.
- timeout maps to `PROVIDER_TIMEOUT`.
- `image_edit` multipart contains one `image[]` field per artifact.
- `stream` and `partial_images` are absent by default.

## Artifact Integration Tests

Use a temporary `ARTIFACT_ROOT` and SQLite database:

1. write PNG bytes.
2. query metadata.
3. download the artifact.
4. verify MIME, length, and sha256.
5. read as a non-owner caller and expect `ARTIFACT_FORBIDDEN`.
6. grant read permission and verify success.
7. set an expiration time and verify normal read fails after expiration.

## MCP Contract Tests

Keep contract fixtures for each tool:

- input schema.
- success output example.
- failure output example.
- error code enum.

Requirements:

- schema fields use snake_case.
- tool arguments do not include `api_key`, `token`, `base_url`, or local paths.
- file outputs return artifact metadata only, never base64 payloads.
- `ok=false` responses include `error.code` and `retryable`.

## E2E Tests

### Phase 0: Gateway Startup

Steps:

1. copy `config.example.yaml` into a test config.
2. disable external providers.
3. start the Gateway.
4. request `/healthz` and `/readyz`.
5. call `health_check` through an MCP client.

Acceptance:

- process starts successfully.
- `health_check` returns enabled/disabled module summary.
- logs do not contain secrets.

### Phase 1: image_generate URL Response

Steps:

1. mock iKun `/v1/images/generations` to return `data[0].url`.
2. mock the image URL to return PNG bytes.
3. call `image_generate`.
4. call `artifact_get`.
5. download the artifact.

Acceptance:

- an image artifact is created.
- provider URL expiration does not affect local download.
- metadata records `provider_output = url`.

### Phase 2: image_generate Base64 Response

Steps:

1. mock iKun to return `data[0].b64_json` and `output_format = png`.
2. call `image_generate`.
3. download the artifact.

Acceptance:

- base64 is decoded and saved.
- MCP response does not contain the large base64 payload.
- metadata records `provider_output = b64_json`.

### Phase 3: image_edit

Steps:

1. create an input image artifact.
2. mock iKun `/v1/images/edits`.
3. call `image_edit`.

Acceptance:

- multipart includes artifact files.
- non-image artifacts are rejected.
- unauthorized artifacts are rejected.

## Security Tests

| case | expected |
| --- | --- |
| `image_generate` receives arbitrary `base_url` field | schema rejects or ignores it |
| `image_edit` receives local absolute path | schema rejects it |
| non-owner reads artifact | `ARTIFACT_FORBIDDEN` |
| Matrix room not in allowlist | `POLICY_DENIED` |
| printer not in allowlist | `POLICY_DENIED` |
| `copies` exceeds maximum | `INVALID_ARGUMENT` or `POLICY_DENIED` |
| provider returns http URL while http is disabled | `PROVIDER_UNAVAILABLE` |
| provider URL points to non-allowlisted host | `PROVIDER_UNAVAILABLE` |
| prompt exceeds length limit | `INVALID_ARGUMENT` |
| secret appears in exception message | test fails |

## ZeroClaw Integration Tests

Host configuration:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

Docker role-play configuration:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://host.docker.internal:8787/mcp"
deferred_loading = true
```

Acceptance:

- ZeroClaw shows tool names such as `home__health_check` and `home__image_generate`.
- `deferred_loading = true` keeps full schemas out of the initial context.
- low-risk tools can be auto-approved by configuration.
- Matrix and printing tools are not in the default auto-approval list.

## Regression Gate

After MVP implementation begins, every merge should run:

```text
unit tests
contract tests
artifact integration tests
image provider mock tests
security policy tests
```

Tests that use a real iKun token should remain manual/local tests and must not run in default CI, to avoid cost and secret exposure.

