# home_mcp_gateway

`home_mcp_gateway` is a local MCP gateway for ZeroClaw and other MCP clients.
It exposes one local HTTP/SSE MCP endpoint, routes tool calls through a policy
engine, stores generated files as artifacts, and records jobs and audit events
in SQLite.

The important configuration rule is:

**Users edit `config/user.config.yaml`.**

`config/config.example.yaml` is the built-in base configuration. Do not treat it
as your personal config. For local use, copy
`config/user.config.example.yaml` to `config/user.config.yaml`. When
`CONFIG_PATH` is not set, the application automatically loads
`config/user.config.yaml` if it exists.

## Quick Start

Requirements:

- Python 3.11 or newer.
- `PyYAML`.

Create your local user config:

```powershell
Copy-Item config/user.config.example.yaml config/user.config.yaml
```

Edit `config/user.config.yaml`, then run:

```powershell
python -m pip install -e .
$env:GATEWAY_TOKEN_HOST = "change-me"
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
| `config/user.config.yaml` | Your local user config. Create it by copying `config/user.config.example.yaml`. It is git-ignored. |
| `config/user.config.example.yaml` | User-facing template with only common overrides. Safe to commit. |
| `config/config.example.yaml` | Full base/default config loaded by the program first. Mostly for maintainers. |
| `.env.example` | Docker Compose environment template. Copy it to `.env` for local secrets. |
| `.env` | Local Docker Compose environment variables. It is git-ignored. |
| `env/compose.config.yaml` | Config mounted by Docker Compose. |
| `env/test.config.yaml` | Test-only config used by `env/run_tests.ps1`. |

The application loads configuration in this order:

1. Load `config/config.example.yaml`.
2. If `CONFIG_PATH` is set, deep-merge that YAML over the base config.
3. If `CONFIG_PATH` is not set and `config/user.config.yaml` exists, deep-merge that file instead.
4. Replace placeholders such as `${IMAGE_API_KEY}` with environment variables.

Common user-editable sections are:

- `server.host`, `server.port`
- `artifacts.root`, `artifacts.public_base_url`
- `database.path`
- `callers.*.token_env`
- `policy.allowed_matrix_rooms`
- `policy.allowed_printers`
- `policy.high_risk_allowed_callers`
- `modules.image`, `modules.tts`, `modules.matrix`, `modules.printer`

Secrets should stay in environment variables, not YAML files. For Docker
Compose, copy `.env.example` to `.env` and put local token/provider values
there.

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
- `artifact_get`: returns artifact metadata and a download URL when access is allowed.
- `job_status`: returns a job visible to the caller.

Optional module tools:

- `image_generate`, `image_edit`: generate or edit images and store results as image artifacts.
- `tts_synthesize`: synthesize speech and store the audio as an artifact.
- `matrix_send_text`, `matrix_send_audio`: send allowlisted Matrix messages.
- `printer_list`, `printer_print_file`: list allowlisted printers and submit print jobs.

Matrix send and print submission are high-risk tools. They require an
authenticated caller and explicit policy allowlists.

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

Docker Compose uses `env/compose.config.yaml`:

```powershell
Copy-Item .env.example .env
# Edit .env and set GATEWAY_TOKEN_HOST / GATEWAY_TOKEN_ROLE_DEFAULT.
docker compose up --build
```

Compose automatically reads `.env`, mounts `env/compose.config.yaml`, and
stores artifacts plus SQLite metadata in the `home-mcp-artifacts` volume.

## Tests

Tests use `env/test.config.yaml`; that file is not the user config.

```powershell
.\env\run_tests.ps1
```

The test script sets `CONFIG_PATH=env/test.config.yaml` and local test tokens,
then runs the Python `unittest` suite.

## Documentation

- Developer documentation: [`dev_documents/documents/`](dev_documents/documents/README.md)
- Deployment notes: [`deploy/README.md`](deploy/README.md)
- Module extension notes: [`dev_documents/module-extension.md`](dev_documents/module-extension.md)
- Chinese README: [`README.zh-cn.md`](README.zh-cn.md)
