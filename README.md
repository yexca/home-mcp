# home_mcp_gateway

Local MCP gateway for ZeroClaw integrations. It provides HTTP MCP endpoints,
tool dispatch, SQLite-backed jobs/audit/artifacts, module-based integrations,
and Docker/Compose deployment support.

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

## Docker

```powershell
docker compose up --build
```

Compose mounts `env/compose.config.yaml` and stores artifacts in the
`home-mcp-artifacts` volume.

## Test

```powershell
.\env\run_tests.ps1
```
