# Deployment

## Local Compose

Start the Gateway:

```powershell
$env:HOME_MCP_LOGIN_KEY = "your-login-key"
docker compose up --build
```

Open the local WebUI:

```text
http://127.0.0.1:8787
```

The root URL redirects to `/webui/`. Log in with `HOME_MCP_LOGIN_KEY`, or use `HOME_MCP_DEV_MODE=true` for development management without login. Compose accepts these variables from the shell or `.env`. The WebUI writes management settings, agents and LLM providers/models to SQLite. Docker Compose persists the database and artifacts under `./artifacts`.

The host can connect ZeroClaw to:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

Another compose service on the same network can use:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

Artifact download links are normally derived from the address used to call the MCP endpoint. When the gateway cannot derive a request base URL, it falls back to `artifacts.public_base_url` in YAML.

## Configuration

- Compose mounts `./config:/app/config` read-write.
- `config/config.main.yaml` is the project baseline.
- `config/config.yaml` and agent fragments supply optional legacy bootstrap configuration, imported once.
- Saved management configuration and agent tokens live in SQLite; use the WebUI after import.
- `artifacts.signed_url_secret` signs short-lived artifact download URLs.
- Artifacts and SQLite metadata live under `./artifacts` by default.
- Keep high-risk tools out of ZeroClaw auto approve by default.

## Health Checks

- `GET /healthz` confirms the process is alive.
- `GET /readyz` shows enabled modules without exposing provider secrets.
- The Dockerfile and Compose service both use `/healthz` health checks.
