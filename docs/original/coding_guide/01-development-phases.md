# 01. Development Phases

## Phase 0: Skeleton and Technical Validation

Goals:

- Create the Python 3.11+ project skeleton.
- Start an HTTP service exposing `/healthz`, `/readyz`, and `/mcp`.
- Register the minimal `health_check` tool.
- Verify that ZeroClaw can discover and call `home__health_check` through SSE MCP.

Suggested tasks:

- Create the baseline directories: `app/`, `transport/`, `tools/`, `core/`, `modules/`, `config/`, `deploy/`, and `tests/`.
- Implement minimal config loading with `CONFIG_PATH` and environment variable placeholders.
- Choose the MCP over SSE implementation. If the SDK is unstable, first implement the smallest compatible SSE/HTTP MCP adapter that ZeroClaw can call.
- Keep the Gateway server name as `home_mcp_gateway`; keep the ZeroClaw MCP server `name` as `home`.
- Add a local development start command and a draft Dockerfile.

Exit criteria:

- `GET /healthz` returns 200 and does not include secrets or provider details.
- `GET /readyz` returns an enabled/disabled module summary.
- Host ZeroClaw can call `home__health_check` through `http://127.0.0.1:8787/mcp`.
- Tool schemas can be loaded on demand when `deferred_loading = true`.

Deliverables:

- Runnable service skeleton.
- Contract test for `health_check`.
- Local development startup notes.

## Phase 1: Core Infrastructure

Goals:

- Build the shared execution base for the Gateway.
- Make all later tools reuse the same request, job, artifact, audit, policy, limit, and error model.

Suggested tasks:

- `tools/registry.py`: register `ToolDefinition` and reject duplicate names, missing risk levels, or invalid schemas.
- `tools/dispatcher.py`: create `request_id`, validate input, resolve caller identity, evaluate policy, call the handler, and normalize errors.
- `tools/result.py`: implement common success and failure result structures.
- `core/ids.py`: generate `req_`, `job_`, `art_`, and `aud_` IDs. ULID is recommended.
- `core/artifacts.py`: implement atomic file writes, sha256, size limits, metadata, permission checks, and expiration.
- `core/jobs.py`: implement the job state machine: `pending -> running -> succeeded/failed/canceled`.
- `core/audit.py`: write paired `audit_start` and `audit_finish` events with redacted input summaries.
- `core/policy.py`: implement default policies, caller permissions, artifact permissions, room allowlists, and printer allowlists.
- `core/limits.py`: implement in-process limits for image, TTS, Matrix, and printer tools.
- Initialize SQLite with WAL, foreign keys, busy timeout, and idempotent migrations.
- Implement `artifact_get` and `job_status`.

Exit criteria:

- `artifact_get` can return metadata and a download URL for a test artifact.
- `job_status` lets a caller read only its own jobs; admin access is controlled by config.
- Every tool call has a `request_id`, an audit record, and a stable error code.
- Unhandled handler exceptions return `INTERNAL_ERROR`. Logs may contain tracebacks, but MCP responses must not contain stack traces or secrets.
- Tool schemas do not include `api_key`, `token`, `base_url`, or local path parameters.

Deliverables:

- Unit tests for core services.
- Artifact integration tests.
- MCP contract fixtures.
- `config/config.example.yaml` aligned with the detailed design sample.

## Phase 2: iKun `image_generate`

Goals:

- Implement text-to-image generation through the iKun OpenAI-compatible `/v1/images/generations` endpoint.
- Support provider responses containing either `data[].url` or `data[].b64_json`.
- Persist every output image immediately as an image artifact.

Suggested tasks:

- `modules/image/schemas.py`: define `image_generate` input validation for prompt, size, quality, output_format, and n.
- `modules/image/providers/ikun_openai_compatible.py`: implement JSON requests, auth headers, response normalization, and error mapping.
- `modules/image/service.py`: call the provider, download URLs or decode base64, create artifacts, and build tool output.
- Restrict `n` to 1 for the first version.
- Require `size` to match the configured allowlist. Map `auto` to the default configured size.
- Read provider `model`, `base_url`, and `api_key` only from config.
- Allow provider image URL downloads only from HTTPS and configured hosts.
- Validate downloaded MIME type and size before persisting.
- Store provider URLs only in redacted metadata by default.

Exit criteria:

- Mock iKun URL responses create image artifacts.
- Mock iKun base64 responses create image artifacts.
- Local artifacts remain downloadable after the provider URL expires.
- The iKun token does not appear in ZeroClaw, MCP responses, app logs, audit records, or test fixtures.
- Invalid size, empty prompt, and overlong prompt return `INVALID_ARGUMENT`.
- Provider 401/403, 429, 5xx, timeout, non-JSON response, and empty `data` map to stable error codes.

Deliverables:

- Unit tests for `image_generate`.
- Provider mock tests.
- Artifact persistence tests.
- Security tests for URL download and secret redaction.
- Local manual iKun smoke test notes without token values.

## Phase 3: iKun `image_edit`

Goals:

- Implement image editing / image-to-image from one or more image artifacts.
- Integrate with the iKun `/v1/images/edits` multipart endpoint.

Suggested tasks:

- Support `image_artifact_ids` and keep compatibility with single `image_artifact_id`.
- Read input images from ArtifactStore only.
- Reject URL inputs, local paths, and arbitrary file parameters.
- Check that the caller can read each input artifact.
- Allow only `image/png`, `image/jpeg`, and `image/webp` as input MIME types.
- Enforce per-image size, total size, and max input image count.
- Use `image[]` as the multipart field name.
- Do not expose `stream` or `partial_images` in the MCP schema for the first version.
- Reuse the Phase 2 response normalization and artifact persistence flow.

Exit criteria:

- Missing, forbidden, expired, or invalid-MIME input artifacts are rejected.
- Mock edits responses in both URL and base64 forms are persisted as output artifacts.
- Multipart requests include one or more `image[]` fields.
- The output structure is consistent with `image_generate`.

Deliverables:

- Unit tests for `image_edit`.
- Multipart provider mock tests.
- Permission and MIME security tests.

## Phase 4: TTS and Matrix Audio Workflow

Goals:

- Implement `tts_synthesize` to generate audio artifacts.
- Implement `matrix_send_text` and `matrix_send_audio`.
- Allow ZeroClaw to compose the workflow: text -> audio artifact -> Matrix send.

Suggested tasks:

- Prefer a `local_http` TTS provider for the first implementation. If the real provider is not finalized, implement a mock provider and keep the interface stable.
- Validate TTS text length, voice allowlist, language, format, and speed.
- Store generated audio as artifacts.
- Allow only configured audio MIME types such as `audio/ogg`, `audio/mpeg`, and `audio/wav`.
- For Matrix, prefer a small HTTP API client wrapping homeserver, access token, media upload, and send event.
- Require room allowlist checks for both `matrix_send_text` and `matrix_send_audio`.
- Read Matrix tokens only from environment variables or a local secret store.

Exit criteria:

- TTS can generate an audio artifact from text.
- Matrix tools can send only to allowlisted rooms.
- `matrix_send_audio` uploads an audio artifact and returns `event_id`, `room_id`, and media summary.
- TTS and Matrix modules do not directly import each other.
- Matrix high-risk tools are not included in the default ZeroClaw auto approve list.

Deliverables:

- TTS provider mock tests.
- Matrix HTTP mock tests.
- Manual end-to-end notes for the audio workflow.

## Phase 5: Printer

Goals:

- Implement `printer_list`.
- Implement `printer_print_file` or an HTTP printer bridge depending on deployment shape.

Suggested tasks:

- Prefer `bridge_http` for the first version to avoid direct Docker dependency on the host print system.
- Return only allowlisted printers from `printer_list`, with an `allowed` flag.
- Accept only artifact inputs for `printer_print_file`.
- Reject local paths.
- Validate printer allowlist, MIME allowlist, file size, copies limit, duplex, and color options.
- Create job and audit records for print actions.

Exit criteria:

- Non-allowlisted printers return `POLICY_DENIED`.
- Invalid MIME types and oversized files are rejected.
- Print actions have job records, audit records, stable error codes, and observable status.
- Printer tools are not included in the default ZeroClaw auto approve list.

Deliverables:

- Printer bridge mock tests.
- Print security tests.
- Manual host printer acceptance notes.

## Phase 6: Module Extension Rules and Release Hardening

Goals:

- Stabilize the template for new modules and providers.
- Complete Docker/Compose support, local configuration, security baseline, and regression gates.

Suggested tasks:

- Each module should provide `manifest.py`, `schemas.py`, `service.py`, `providers/`, and `tests/`.
- Adding a module must not require changes in the transport layer.
- Adding a provider must not change the MCP tool schema unless the external contract is intentionally versioned.
- Complete Dockerfile, docker-compose, healthcheck, volume, and config mount notes.
- Add a release checklist for secret scanning, log redaction, artifact permissions, and ZeroClaw integration.

Exit criteria:

- A dummy module can be added without modifying the transport layer.
- A new image provider can be added without changing the external `image_generate` or `image_edit` schema.
- Full regression tests pass.
- Docker Compose can start the Gateway and ZeroClaw can connect from host or compose network.

Deliverables:

- Module template and extension notes.
- Release checklist.
- MVP version tag and changelog.

