# 07. MVP Phases And Acceptance Criteria

## Phase 0: Technical Validation

Goal:

- Start an SSE MCP service.
- ZeroClaw can discover tools.
- ZeroClaw can call `ping` or `health_check`.

Acceptance criteria:

- At least one of Docker mode or host mode works.
- Tool schemas load on demand with `deferred_loading = true`.

## Phase 1: Gateway Infrastructure

Goal:

- Implement tool registry.
- Implement unified error format.
- Implement artifact store.
- Implement audit logger.
- Implement basic configuration loading.

Acceptance criteria:

- `artifact_get` can return metadata for a test artifact.
- Every tool call has a request id and audit log.

## Phase 2: TTS And Matrix Voice Flow

Goal:

- `tts_synthesize` generates an audio artifact.
- `matrix_send_audio` sends the audio to an allowlisted room.

Acceptance criteria:

- ZeroClaw can send text and receive a Matrix voice message.
- TTS and Matrix modules do not directly depend on each other.
- Matrix room allowlist is enforced.

## Phase 3: Third-Party OpenAI Image2-Compatible Image Generation

Goal:

- `image_generate` generates an image artifact.
- The image provider supports configurable third-party API base URL, API key, and model.
- Support basic size, quality, and format parameters.
- Add concurrency and budget limits.

Acceptance criteria:

- ZeroClaw can generate an image and receive an artifact.
- Third-party image API key is not exposed to ZeroClaw containers.
- Limit violations return stable errors.

## Phase 4: Image Editing

Goal:

- `image_edit` edits an image based on an artifact.
- Support input image validation and output artifacts.

Acceptance criteria:

- Missing or unauthorized input is rejected.
- Output image is stored in the artifact store.

## Phase 5: Printer

Goal:

- `printer_list` lists printers.
- `printer_print_file` prints artifacts.
- Print status query is supported.

Acceptance criteria:

- Only allowlisted printers can be used.
- Only allowed artifact types can be printed.
- Print actions have audit records.

## Phase 6: Module Extension Standard

Goal:

- Finalize the new skill template.
- Every module has manifest, schema, service, provider, and tests.
- Documentation records auto-approval recommendation and risk level.

Acceptance criteria:

- Adding a dummy module does not require transport-layer changes.
- Adding a provider does not require MCP tool schema changes.

## MVP Priority

Recommended implementation order:

1. SSE MCP skeleton.
2. Tool registry and `health_check`.
3. Artifact store.
4. TTS.
5. Matrix audio.
6. Third-party OpenAI image2-compatible `image_generate`.
7. `image_edit`.
8. Printer.

Printer comes later because it depends most heavily on the host system environment and needs the strongest approval and audit handling.

