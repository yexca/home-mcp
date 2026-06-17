# 07. Next-Stage Detailed Design and MVP Plan

## Detailed Design Open Items

Before entering detailed design, finalize:

1. Whether to use a Python MCP SDK or implement the SSE MCP transport directly.
2. How ZeroClaw passes caller identity.
3. SQLite schema, migration mechanism, and WAL configuration.
4. Whether signed artifact URLs are required in version 1.
5. The concrete first TTS provider.
6. Matrix SDK versus direct Matrix HTTP API.
7. Whether the print bridge is included in the MVP or only reserved as an interface.

## MVP Implementation Order

### Phase 0: Skeleton

Goals:

- Start the Gateway.
- Expose the SSE MCP endpoint.
- Register `health_check`.
- Let ZeroClaw discover and call the tool.

Acceptance:

- Host ZeroClaw can call `http://127.0.0.1:8787/mcp`.
- Tool schemas load on demand with `deferred_loading = true`.

### Phase 1: Core Infrastructure

Goals:

- Tool registry.
- Common `ToolResult` and stable error codes.
- Artifact store.
- Job manager.
- Audit logger.
- Configuration loader.

Acceptance:

- `artifact_get` can query a test artifact.
- Every tool call has a `request_id` and audit record.
- Failure paths return stable error codes.

### Phase 2: iKun Image Generate

Goals:

- Implement `image_generate`.
- Call iKun `/v1/images/generations`.
- Support provider responses with either URL or `b64_json`.
- Persist generated output as image artifacts.

Acceptance:

- `gpt-image-2` can generate an image artifact.
- The iKun token is not exposed to ZeroClaw.
- Local artifacts remain readable after provider URLs expire.
- URL responses and `b64_json` responses are both persisted.
- Non-allowlisted sizes are rejected.

### Phase 3: Image Edit

Goals:

- Implement `image_edit`.
- Read input images from the artifact store.
- Call iKun `/v1/images/edits` with multipart/form-data.

Acceptance:

- Missing, unauthorized, or invalid-MIME input artifacts are rejected.
- Output images are stored in the artifact store.

### Phase 4: TTS

Goals:

- Implement `tts_synthesize`.
- Connect to a local or HTTP TTS provider.

Acceptance:

- Text generates an audio artifact.
- Text length, format, and speed limits work.

### Phase 5: Matrix

Goals:

- Implement `matrix_send_text`.
- Implement `matrix_send_audio`.
- Enforce the room allowlist.

Acceptance:

- Messages can be sent only to allowlisted rooms.
- Audio artifacts are uploaded and sent successfully.
- The Matrix token is not exposed to ZeroClaw.

### Phase 6: Printer

Goals:

- Implement `printer_list`.
- Depending on deployment, implement `printer_print_file` or a bridge adapter.

Acceptance:

- Only allowlisted printers can be used.
- Only artifacts with allowed MIME types can be printed.
- Print actions have job and audit records.

## Version 1 Non-Goals

- Public multi-tenant service.
- Web admin dashboard.
- Complete human approval UI.
- Complex clustered queue system.
- Arbitrary file download or arbitrary local path printing.
- Full parameter passthrough for every image provider.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| iKun returns expiring URLs | Download and save artifacts immediately after receiving the response |
| Token groups return URL/base64 differently | Adapter supports both `url` and `b64_json` |
| Non-standard image size causes failures | Use a configured `size` allowlist |
| ZeroClaw auto-approves high-risk tools by mistake | Gateway policy engine performs a second check |
| Printing depends on host environment | Defer the print module and design an HTTP bridge first |
| Docker access to host services is unstable | Document both `host.docker.internal` and same-compose-network options |

## Recommended Detailed Design Artifacts

Next stage should add the following under `dev_documents/detail_design/`:

- `01-mcp-transport-detail.md`
- `02-core-schema-detail.md`
- `03-image-provider-detail.md`
- `04-security-policy-detail.md`
- `05-test-plan.md`
- `config.example.yaml`
- `openapi-provider-notes.md`
