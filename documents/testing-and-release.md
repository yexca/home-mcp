# Testing And Release

The repository uses Python `unittest`. The standard test entry point is:

```powershell
.\env\run_tests.ps1
```

The script sets:

```powershell
$env:CONFIG_PATH = "env/test.config.yaml"
$env:GATEWAY_TOKEN_HOST = "test-host-token"
$env:GATEWAY_TOKEN_ROLE_DEFAULT = "test-role-token"
python -m unittest discover -s tests
```

## Test Coverage Areas

Current tests cover:

- Configuration loading and module validation.
- Registry validation and duplicate protection.
- Dispatcher success/failure contracts.
- Artifact ownership, grants, expiry, and access checks.
- HTTP/MCP transport behavior.
- Image generation/edit provider flows.
- TTS behavior and Matrix audio workflow.
- Printer module behavior.
- High-risk policy checks and allowlists.
- Phase 6 module extension rules.

## Local Smoke Test

Start the server:

```powershell
$env:CONFIG_PATH = "env/test.config.yaml"
$env:GATEWAY_TOKEN_HOST = "test-host-token"
python -m app.main
```

Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/healthz
Invoke-RestMethod http://127.0.0.1:8787/readyz
```

Call a tool using the simple compatibility shape:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8787/mcp `
  -ContentType "application/json" `
  -Body '{"tool":"health_check","arguments":{}}'
```

Call JSON-RPC:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8787/mcp `
  -ContentType "application/json" `
  -Body '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

## Module Smoke Tests

Image:

- Enable `modules.image`.
- Set `IMAGE_API_BASE_URL`, `IMAGE_API_MODEL`, and `IMAGE_API_KEY`.
- Confirm `readyz` shows image enabled.
- Call `image_generate`.
- Verify the response contains `status: accepted` and `job_id`.
- Poll `job_status` until the job reaches `succeeded`.
- Verify the final job contains image artifact IDs.
- Call `artifact_get` for the artifact and verify `sha256` and signed
  `download_url`.
- Download the signed `download_url` without Bearer auth and verify the MIME
  type.

TTS:

- Enable `modules.tts` with `provider: mock` for local tests or `local_http`
  for integration tests.
- Call `tts_synthesize`.
- Download the returned artifact and verify the MIME type.

Matrix:

- Enable `modules.matrix`.
- Set `MATRIX_HOMESERVER` and `MATRIX_ACCESS_TOKEN`.
- Configure `policy.allowed_matrix_rooms`.
- Add the caller to `policy.high_risk_allowed_callers`.
- Send a short text message to an allowlisted test room.

Printer:

- Enable `modules.printer`.
- Set `PRINTER_BRIDGE_URL`.
- Configure `allowed_printers` and `policy.allowed_printers`.
- Add the caller to `policy.high_risk_allowed_callers`.
- Verify `printer_list`, then submit a small printable artifact to a test printer.

## Release Gate

Before releasing or deploying:

- Run `.\env\run_tests.ps1`.
- Create a local `.env` from `.env.example` and set non-empty local compose
  tokens.
- Build the container with `docker compose build`.
- Start it with `docker compose up`.
- Check `GET /healthz` and `GET /readyz`.
- Confirm enabled modules match the intended environment.
- Confirm no secrets are present in config files, docs, fixtures, logs, or test output.
- Confirm high-risk tools are not auto-approved by default in the MCP client.
- Confirm Matrix rooms and printer IDs are allowlisted explicitly.
- Confirm artifact downloads work from the address configured in `public_base_url`.

## Security Review Checklist

- Search for real tokens and API keys before committing.
- Confirm `.env` is not staged; commit `.env.example` only.
- Keep provider `base_url`, API keys, Matrix access tokens, printer API keys,
  and Authorization headers out of tool schemas.
- Keep provider secrets out of audit summaries and tool responses.
- Do not return binary payloads directly from MCP tools; return artifact metadata.
- Keep artifact reads scoped to owner, grant, or configured admin sharing.
- Map provider failures to stable gateway error codes.
