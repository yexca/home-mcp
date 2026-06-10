# Deployment Notes

## Local Compose

Start the Gateway:

```powershell
Copy-Item .env.example .env
# Edit .env and set GATEWAY_TOKEN_HOST, GATEWAY_TOKEN_ROLE_DEFAULT,
# and ARTIFACT_SIGNING_SECRET.
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

Artifact download links are normally derived from the address used to call the
MCP endpoint. A client using `http://127.0.0.1:8787/mcp` receives
`http://127.0.0.1:8787/artifacts/...`; a client using
`http://192.168.1.23:8787/mcp` receives
`http://192.168.1.23:8787/artifacts/...`.
The returned artifact URLs include `expires` and `signature` query parameters
and can be fetched directly without the MCP Bearer token until they expire.

When the gateway cannot derive a request base URL, it falls back to
`ARTIFACT_PUBLIC_BASE_URL`. The default matches host-local use:

```dotenv
ARTIFACT_PUBLIC_BASE_URL=http://127.0.0.1:8787/artifacts
```

For mixed host/container access, either make both clients call MCP through the
same reachable base URL or set `ARTIFACT_PUBLIC_BASE_URL` in `.env` to that
unified gateway URL:

```dotenv
ARTIFACT_PUBLIC_BASE_URL=http://192.168.1.23:8787/artifacts
```

Use the same base for the ZeroClaw MCP URL, replacing `/artifacts` with `/mcp`.

## Configuration

- Compose mounts `config/config.yaml` into the container.
- Compose reads local values from the project-root `.env`, created from
  `.env.example`.
- `ARTIFACT_SIGNING_SECRET` signs short-lived artifact download URLs.
- Artifacts and SQLite metadata live under the project-root `./artifacts`
  directory, matching the default user config.
- Secrets are supplied only through environment variables, never through checked-in YAML.
- Keep high-risk tools out of ZeroClaw auto approve by default.

## Health Checks

- `GET /healthz` confirms the process is alive.
- `GET /readyz` shows enabled modules without exposing provider secrets.
- The Dockerfile and Compose service both use `/healthz` health checks.
