# home_mcp_gateway

`home_mcp_gateway` is a local HTTP/SSE MCP gateway for ZeroClaw and other MCP clients. It centralizes tool calls, policy checks, artifact storage, jobs, and audit records behind one local MCP endpoint.

Normal users edit YAML under `config/`. The committed `config/config.main.yaml` is the application baseline, and the ignored `config/config.yaml` is your local runtime config.

## Quick Start

Requirements:

- Docker with Docker Compose
- PowerShell on Windows for the helper scripts

Edit `config/config.yaml` and set at least `callers.host_assistant.token`, `callers.role_default.token`, and `artifacts.signed_url_secret`.

Build and run with Docker Compose:

```powershell
docker compose up -d --build
```

The default endpoint is `http://127.0.0.1:8787`.

Check health:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/healthz
Invoke-RestMethod http://127.0.0.1:8787/readyz
```

## MCP Client

Use the SSE transport URL:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

When another Docker Compose service connects to this gateway on the same Docker network, use:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

## Local Python Development

```powershell
python -m pip install -e .
python -m app.main
```

The default path is Docker Compose. Use local Python runs for development only.

## Agents

Set `agents.enabled` in `config/config.yaml`, then run the root helper:

```powershell
.\apply_agent.bat
```

The helper calls `tools/apply_agent.ps1` and manages `config/agent/config.agent.<name>.yaml` files.

## Tests

```powershell
.\tests\run_tests.ps1
```

## Documentation

- Documentation index: [docs/README.md](docs/README.md)
- User guide: [docs/user/README.md](docs/user/README.md)
- Current developer docs: [docs/developer/README.md](docs/developer/README.md)
- Original development docs: [docs/original/README.md](docs/original/README.md)
- Chinese quick start: [README.zh-cn.md](README.zh-cn.md)
