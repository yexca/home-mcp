# home_mcp_gateway

Phase 1 implementation of a local MCP gateway core. It provides a runnable
HTTP skeleton, core tool dispatch, SQLite-backed jobs/audit/artifacts, and
safe built-in tools for health, job status, and artifact metadata.

## Run

```powershell
$env:CONFIG_PATH = "env/test.config.yaml"
python -m app.main
```

Default local endpoint:

- `GET /healthz`
- `GET /readyz`
- `POST /mcp`
- `GET /artifacts/{artifact_id}`

## Test

```powershell
.\env\run_tests.ps1
```
