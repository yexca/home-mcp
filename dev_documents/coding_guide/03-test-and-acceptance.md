# 03. Tests and Acceptance

## Test Layers

Each phase should cover the risk surface it introduces:

| Layer | Purpose |
| --- | --- |
| Unit tests | Validate config, registry, dispatcher, IDs, policy, limits, and provider adapters |
| Integration tests | Validate SQLite, artifact file writes/downloads, job state, and audit consistency |
| MCP contract tests | Keep tool schemas, success responses, failure responses, and error codes stable |
| Provider mock tests | Validate iKun, TTS, Matrix, and printer bridge requests and error mapping |
| Security tests | Validate secret redaction, path safety, permissions, allowlists, and limits |
| E2E/manual tests | Validate Gateway startup, ZeroClaw tool discovery, and real or mock provider flows |

Real iKun tokens, Matrix tokens, and physical printer tests are local manual tests only. They must not run in default CI.

## Phase 0 Acceptance

Required checks:

- HTTP health check.
- MCP `health_check` contract test.
- Host ZeroClaw SSE manual integration.

Checklist:

- `/healthz` returns 200.
- `/readyz` does not leak secrets.
- ZeroClaw can discover the `home` MCP server.
- `home__health_check` succeeds.
- Tool schemas can be loaded on demand when `deferred_loading = true`.

## Phase 1 Acceptance

Required checks:

- Config loader unit tests.
- Tool registry unit tests.
- Dispatcher unit tests.
- ArtifactStore integration tests.
- JobManager unit tests.
- AuditLogger unit tests.
- PolicyEngine unit tests.
- MCP contract tests.

Key assertions:

- Duplicate tool registration fails.
- Handler exceptions return `INTERNAL_ERROR`.
- Non-owner artifact reads return `ARTIFACT_FORBIDDEN`.
- Reads succeed after an explicit grant.
- Expired artifacts cannot be read by normal callers.
- `audit_start` and `audit_finish` are paired.
- prompt/text summaries are redacted.
- Schemas do not include `api_key`, `token`, `base_url`, or local path fields.

## Phase 2 Acceptance

Required checks:

- iKun image provider mock unit tests.
- `image_generate` service tests.
- Artifact persistence tests.
- Provider URL download safety tests.
- Secret redaction tests.

Key assertions:

- JSON body includes `model`, `prompt`, `n`, `size`, `quality`, and `output_format`.
- Authorization header is sent but does not enter logs or audit records.
- URL responses are persisted as image artifacts.
- `b64_json` responses are persisted as image artifacts.
- MCP responses do not include large base64 payloads.
- Provider URL hosts outside the allowlist return `PROVIDER_UNAVAILABLE`.
- HTTP provider URLs return `PROVIDER_UNAVAILABLE` unless explicitly allowed.
- Provider 401/403 maps to `PROVIDER_REJECTED`.
- Provider 429 maps to `RATE_LIMITED`.
- Provider timeout maps to `PROVIDER_TIMEOUT`.

Manual integration:

- Generate one small test image with a real iKun token.
- Record `request_id`, `job_id`, `artifact_id`, and `provider_output`.
- Verify the artifact download URL still works after the provider URL expires.
- Do not record token values.

## Phase 3 Acceptance

Required checks:

- `image_edit` input schema tests.
- Multipart provider mock tests.
- Artifact permission tests.
- MIME and size limit tests.

Key assertions:

- `image_artifact_id` is accepted as a single-image compatibility form.
- Local path and URL inputs are rejected by schema validation.
- Missing artifacts return `ARTIFACT_NOT_FOUND`.
- Forbidden artifacts return `ARTIFACT_FORBIDDEN`.
- Non-image MIME types return `UNSUPPORTED_MEDIA_TYPE`.
- Multipart requests include one or more `image[]` fields.
- Output images are stored in ArtifactStore.

## Phase 4 Acceptance

Required checks:

- TTS provider mock tests.
- Matrix provider mock tests.
- Room allowlist security tests.
- Audio artifact permission and MIME tests.

Key assertions:

- `tts_synthesize` outputs an audio artifact.
- Overlong text returns `INVALID_ARGUMENT`.
- Out-of-range speed returns `INVALID_ARGUMENT`.
- Non-allowlisted rooms return `POLICY_DENIED`.
- `matrix_send_audio` returns `ARTIFACT_FORBIDDEN` for unreadable artifacts.
- Matrix tokens do not appear in responses, logs, or audit records.

Manual integration:

- ZeroClaw calls `tts_synthesize` to create audio.
- ZeroClaw calls `matrix_send_audio` to send the audio to an allowlisted room.
- Verify that Matrix returns an event ID.

## Phase 5 Acceptance

Required checks:

- Printer bridge mock tests.
- Printer allowlist tests.
- Printable MIME tests.
- Copies limit tests.

Key assertions:

- `printer_list` returns only allowlisted printers.
- Non-allowlisted printers return `POLICY_DENIED`.
- Unsupported MIME types return `UNSUPPORTED_MEDIA_TYPE`.
- `printer_print_file` does not accept local paths.
- Print actions create job and audit records.

Manual integration:

- Print one test PDF or image artifact.
- Verify printer status, job record, and audit record.

## Regression Gate

Every merge should run at least:

```text
unit tests
contract tests
artifact integration tests
image provider mock tests
security policy tests
```

Before release, also run:

```text
ZeroClaw host SSE integration
Docker or compose startup test
manual iKun smoke test
secret scan
artifact permission regression
```

## Secret Scan Checklist

Before release, verify:

- The repository contains no real `IMAGE_API_KEY`, `MATRIX_ACCESS_TOKEN`, or caller token.
- The content of `dev_documents/ikun/key.txt` was not copied into any new file.
- Test fixtures do not contain real provider URL query strings, Authorization headers, or tokens.
- Log examples only contain `present: true/false`.
- Failure responses do not contain stack traces, sensitive absolute paths, or full provider error bodies.

