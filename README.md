# home_mcp_gateway

`home_mcp_gateway` is a local HTTP/SSE MCP gateway for ZeroClaw and other MCP clients. It centralizes tool calls, policy checks, artifact storage, jobs, and audit records behind one local MCP endpoint.

Manage settings, agents and LLM providers/models in the WebUI. Management data is stored in SQLite (default: `artifacts/metadata.sqlite3`). The first startup imports existing YAML and remote image settings; YAML remains the bootstrap configuration source.

## Quick Start

Requirements:

- Docker with Docker Compose
- PowerShell on Windows for the helper scripts

Edit `config/config.yaml` and set at least `callers.host_assistant.token`, `callers.role_default.token`, and `artifacts.signed_url_secret`.

Build and run with Docker Compose:

```powershell
$env:HOME_MCP_LOGIN_KEY = "your-login-key"
docker compose up -d --build
```

The default endpoint is `http://127.0.0.1:8787`.

Log in to the WebUI with `HOME_MCP_LOGIN_KEY`, independent of MCP caller tokens. Compose also accepts this variable from `.env`. In LLM Management, configure an OpenAI-compatible provider URL and API key, fetch models, select models to add, and assign `text` / `image` tags. URLs with `/v1` are accepted. Remote Image selects an added model tagged `image`.

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
$env:HOME_MCP_DEV_MODE = "true"
python -m app.main
```

`HOME_MCP_DEV_MODE=true` opens management without login. MCP caller authentication and policy still apply. Use `HOME_MCP_LOGIN_KEY` with dev mode off for normal operation. Module switches and agent changes require a restart; switching an existing remote image tool's selected model takes effect immediately.

The default path is Docker Compose. Use local Python runs for development only.

## Agents

Manage agents in the WebUI; caller and Matrix tokens are saved to SQLite. After migration, YAML edits do not override saved management data. Back up the database together with artifacts.

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
