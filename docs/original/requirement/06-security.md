# 06. Security, Permissions, And Audit

## Risk Model

Project tools are grouped into three risk levels.

### Low Risk

- Query job status.
- Query artifact metadata.
- List printers.
- Synthesize short local TTS text.

### Medium Risk

- Third-party OpenAI image2-compatible/proxy image generation and editing.
- Generate long speech audio.
- Read artifact files.

Risks include API cost, content safety, storage usage, and privacy.

### High Risk

- Send Matrix messages or voice messages.
- Print files.
- Access arbitrary host paths.
- Call services that create real-world side effects.

## Permission Principles

- ZeroClaw containers do not directly hold third-party image API keys, Matrix tokens, or printer system permissions.
- All secrets live only in MCP Gateway environment variables or a secret store.
- Every tool call carries caller identity.
- High-risk tools must pass through the policy engine.
- Unknown rooms, unknown printers, and unknown external paths are denied by default.
- Printing is limited to artifacts or explicitly allowlisted directories.

## Auto-Approval Recommendation

Can be considered for auto approval:

```text
home__printer_list
home__job_status
home__artifact_get
home__tts_synthesize
```

Use caution for:

```text
home__image_generate
home__image_edit
```

Do not auto approve by default:

```text
home__matrix_send_text
home__matrix_send_audio
home__printer_print_file
```

Even if ZeroClaw-side auto approval is enabled, the Gateway should keep its own policy checks.

## Audit Log

Each tool call records:

- Request id.
- Caller id.
- Tool name.
- Parameter summary, excluding secrets and overly long text.
- Risk level.
- Policy decision.
- Start time, end time, and duration.
- Result status.
- Artifact id or job id.
- Error code.

## Input Limits

The first version should limit:

- TTS text length.
- Image prompt length.
- Third-party image API base URL must come from configuration; tool calls must not provide arbitrary runtime URLs.
- Matrix caption length.
- Single artifact size.
- Concurrent jobs per caller.
- Daily image generation count or budget.
- Maximum print copies.

## File Safety

- Do not accept arbitrary absolute paths by default.
- Prefer `artifact_id`.
- If paths are supported, canonicalize them and confirm they are inside allowlisted directories.
- Prevent path traversal.
- Upload and download URLs must expire or remain internal-only.

## Matrix Safety

- Room id must be allowlisted.
- Optionally restrict which caller can send to which room.
- Record audit logs before sending.
- High-risk content may require human confirmation from ZeroClaw.

## Printer Safety

- Printer id must be allowlisted.
- `copies` defaults to 1 and has a maximum value.
- Keep complex parameters disabled by default except color and duplex options when needed.
- Validate file type before printing.
- Record job id and printer status.

