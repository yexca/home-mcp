# Deployment Notes

## Local Compose

Start the Gateway:

```powershell
Copy-Item .env.example .env
# Edit .env and set GATEWAY_TOKEN_HOST / GATEWAY_TOKEN_ROLE_DEFAULT.
docker compose up --build
```

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

## Configuration

- Compose mounts `env/compose.config.yaml` into the container.
- Compose reads local values from the project-root `.env`, created from
  `.env.example`.
- Artifacts and SQLite metadata live in the `home-mcp-artifacts` volume under `/data/artifacts`.
- Secrets are supplied only through environment variables, never through checked-in YAML.
- Keep high-risk tools out of ZeroClaw auto approve by default.

## Health Checks

- `GET /healthz` confirms the process is alive.
- `GET /readyz` shows enabled modules without exposing provider secrets.
- The Dockerfile and Compose service both use `/healthz` health checks.
