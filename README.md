# home_mcp_gateway

`home_mcp_gateway` is a local MCP gateway for ZeroClaw and other MCP clients.
It exposes one local HTTP/SSE MCP endpoint, routes tool calls through a policy
engine, stores generated files as artifacts, and records jobs and audit events
in SQLite.

The important configuration rule is:

**Users edit `config/config.yaml` and `.env`.**

`config/config.example.yaml` is the template/base configuration. For local use,
copy it to `config/config.yaml`. Both local Python runs and Docker Compose use
that same file. Root-level `.env` keeps tokens, provider secrets, service
startup settings, timeouts, and size limits.

## Quick Start

Requirements:

- Python 3.11 or newer.
- `PyYAML`.

Create your local user config:

```powershell
Copy-Item config/config.example.yaml config/config.yaml
Copy-Item .env.example .env
```

Edit `config/config.yaml` and `.env`, then run:

```powershell
python -m pip install -e .
python -m app.main
```

The default local endpoint is `http://127.0.0.1:8787`.

Check the process:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/healthz
Invoke-RestMethod http://127.0.0.1:8787/readyz
```

## Where User Settings Live

Use these files for different purposes:

| File | Purpose |
| --- | --- |
| `config/config.example.yaml` | Template/base config. Copy it to `config/config.yaml`. |
| `config/config.yaml` | Your local runtime config. Used by both Python and Docker Compose. It is git-ignored. |
| `.env.example` | Environment template. Copy it to `.env` for tokens and provider secrets. |
| `.env` | Local environment variables for Python and Docker Compose. It is git-ignored. |
| `tests/config/test.config.yaml` | Test-only config used by `tests/run_tests.ps1`. |

The application loads settings in this order, with earlier files winning over
later defaults:

1. Load root `.env` into the process environment without overriding existing variables.
2. Load root `.env.example` for missing environment defaults.
3. If `CONFIG_PATH` is set, load that YAML as the user config.
4. If `CONFIG_PATH` is not set and `config/config.yaml` exists, load that YAML as the user config.
5. Fill missing YAML keys from `config/config.example.yaml`.
6. Replace placeholders such as `${SERVER_PORT}` and `${IMAGE_API_KEY}`.
7. Apply explicit environment overrides for module switches and timeout values.

Common user-editable sections are:

- `SERVER_HOST`, `SERVER_PORT`
- `ARTIFACT_ROOT`, `ARTIFACT_PUBLIC_BASE_URL`, artifact size and URL TTL limits
- `DATABASE_PATH`, `DATABASE_BUSY_TIMEOUT_MS`
- tool timeout and rate limit variables such as `SYNC_TOOL_TIMEOUT_SECONDS` and `MATRIX_MESSAGES_PER_ROOM_PER_MINUTE`
- module runtime switches such as `IMAGE_MODULE_ENABLED`, `LOCAL_IMAGE_MODULE_ENABLED`, `TTS_MODULE_ENABLED`, `MATRIX_MODULE_ENABLED`, and `PRINTER_MODULE_ENABLED`
- `callers.*.token_env`
- `policy.high_risk_allowed_callers`
- `modules.image`, `modules.localimage`, `modules.tts`, `modules.matrix`, `modules.printer`

Secrets should stay in environment variables, not YAML files. Copy
`.env.example` to `.env` and put local token/provider values there.

For a custom config file outside the default location, set `CONFIG_PATH`
explicitly:

```powershell
$env:CONFIG_PATH = "path/to/your.config.yaml"
python -m app.main
```

## MCP Client Setup

Use the SSE transport URL:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

When the gateway is used from another Compose service on the same network, use:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

## Available Tools

Built-in tools:

- `health_check`: returns server and enabled-module status.
- `artifact_get`: returns artifact metadata and a signed download URL.
- `artifact_get_image`: compatibility helper that requires an inline-readable image artifact.
- `job_status`: returns a job visible to the caller.

Currently used module tools:

- `image_generate`, `image_edit`: generate or edit images and store results as image artifacts.
- `localimage_generate`: generate images through a local ComfyUI workflow and store results as image artifacts.
- `tts_synthesize`: synthesize text into an audio artifact.
- `matrix_send_text`, `matrix_send_audio`, `matrix_send_image`: send to Matrix rooms allowed by policy.
- `printer_print_file`: send allowlisted artifacts to configured printers.

Matrix sender accounts are configured server-side. The tools do not accept a
Matrix `access_token` argument. To let different MCP callers send as different
Matrix users, configure optional caller mappings and accounts:

```yaml
modules:
  matrix:
    enabled: true
    homeserver: ${MATRIX_HOMESERVER}
    access_token: ${MATRIX_ACCESS_TOKEN}
    caller_accounts:
      role_default: agent1
      agent1: agent1
      agent2: agent2
    accounts:
      agent1:
        homeserver: ${MATRIX_HOMESERVER}
        access_token: ${AGENT1_MATRIX_ACCESS_TOKEN}
      agent2:
        access_token: ${AGENT2_MATRIX_ACCESS_TOKEN}
```

Selection order is: `caller_accounts[caller_id]`, then direct `caller_id`, then
the matching `accounts[account_key]`, then legacy `modules.matrix.access_token`
as the default/fallback sender. Room allowlists and high-risk caller policy
still apply before any Matrix send.

To add another Matrix-capable caller automatically:

```powershell
python tools/add_matrix_agent.py agent3 --matrix-access-token <matrix-access-token>
```

The script updates `config/config.yaml` and `.env`, creates a generated MCP
Bearer token under `GATEWAY_TOKEN_AGENT3`, maps `agent3` to
`${AGENT3_MATRIX_ACCESS_TOKEN}`, and grants the Matrix send tools to that
caller. Use `--allow-all-rooms` when you want `policy.allowed_matrix_rooms: []`.
An empty Matrix room allowlist means all rooms are allowed; a non-empty list
restricts sends to those room IDs.

`docker-compose.yml` loads `.env` with `env_file`, so generated agent token
variables are available in Docker without editing the Compose file.

## Authentication And Policy

Callers authenticate with a bearer token:

```text
Authorization: Bearer <token>
```

Tokens are compared against the environment variable named by each caller entry
in configuration. Anonymous callers can only use tools listed in
`policy.anonymous_allowed_tools`; by default that is `health_check`.

Artifacts and jobs are scoped to the caller that created them. Admin callers can
read shared artifacts only when their configured caller has
`shared_artifact_read: true`.

## Docker

Docker Compose uses the same `config/config.yaml` as local Python runs:

```powershell
Copy-Item config/config.example.yaml config/config.yaml
Copy-Item .env.example .env
# Edit config/config.yaml and .env.
docker compose up --build
```

Compose automatically reads `.env`, mounts `config/config.yaml`, and stores
artifacts plus SQLite metadata under `./artifacts`.

For Docker, keep `SERVER_HOST=0.0.0.0` in `.env` so the published port can
accept host connections. Clients can still use `http://127.0.0.1:8787/mcp`
from the host machine.

When ZeroClaw also runs in Docker, artifact `download_url` values must point to
an address reachable from the ZeroClaw container. The gateway derives download
URLs from the address used to call MCP when possible, so a ZeroClaw MCP URL of
`http://192.168.1.23:8787/mcp` yields artifact URLs under
`http://192.168.1.23:8787/artifacts`. `ARTIFACT_PUBLIC_BASE_URL` remains the
fallback and defaults to `http://127.0.0.1:8787/artifacts` for host-local use.
Artifact `download_url` values are short-lived signed URLs, so clients can fetch
them directly without knowing the MCP Bearer token.

## Tests

Tests use `tests/config/test.config.yaml`; that file is not the user config.

```powershell
.\tests\run_tests.ps1
```

The test script sets `CONFIG_PATH=tests/config/test.config.yaml` and local test
tokens, then runs the Python `unittest` suite.

## Documentation

- Developer documentation: [`documents/`](documents/README.md)
- Deployment notes: [`deploy/README.md`](deploy/README.md)
- Module extension notes: [`dev_documents/module-extension.md`](dev_documents/module-extension.md)
- Chinese README: [`README.zh-cn.md`](README.zh-cn.md)
