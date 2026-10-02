# User Guide

This guide is for running `home_mcp_gateway` as a local MCP gateway. Manage settings, agents and LLM models through the WebUI; management data is persisted in SQLite.

## Files You Touch

| File | Purpose |
| --- | --- |
| `artifacts/metadata.sqlite3` | Saved management settings, agents, providers/models, jobs, artifacts and audit records. |
| `config/config.yaml` | Optional bootstrap settings imported on the first startup. Ignored by git. |
| `config/agent/config.agent.<name>.yaml` | Legacy agent settings imported on the first startup. Ignored by git. |
| `config/comfyui/` | ComfyUI workflow JSON files used by local image generation. |

`config/config.main.yaml` is the committed bootstrap baseline. Once imported, saved SQLite settings take precedence over YAML values. Back up the database together with the artifact files.

## Install And Run

Set these values in `config/config.yaml` before exposing the gateway to real clients:

```yaml
artifacts:
  signed_url_secret: replace-with-a-strong-signing-secret

callers:
  host_assistant:
    token: replace-with-a-strong-token
  role_default:
    token: replace-with-a-strong-role-token
```

Run locally:

```powershell
python -m pip install -e .
$env:HOME_MCP_LOGIN_KEY = "your-login-key"
python -m app.main
```

Or with Docker Compose:

```powershell
$env:HOME_MCP_LOGIN_KEY = "your-login-key"
docker compose up --build
```

Compose mounts `./config` read-write into the container and stores artifacts under `./artifacts`.

## WebUI Configuration

Open:

```text
http://127.0.0.1:8787
```

Log in with the key in `HOME_MCP_LOGIN_KEY`. This key is independent of MCP caller tokens and is never saved to SQLite. The browser remembers it for the current tab session. Compose accepts the variable from the shell or `.env`.

For local development, set `$env:HOME_MCP_DEV_MODE = "true"` before starting the server. This bypasses WebUI management login; MCP caller authentication and policy continue to apply. With dev mode off and no login key configured, management APIs are unavailable.

Restart the service after changing module switches or agent settings so tool registration is refreshed.

## LLM Management And Remote Image

1. Open LLM Management and add a provider name, OpenAI-compatible API address and API key. Either `https://example.com` or `https://example.com/v1` is accepted.
2. Click Save & fetch models to request the provider's model list. Search the returned list, check the models to add, and assign `text` and/or `image` tags. Model IDs can also be entered manually.
3. Save model selection & tags. Tag `image` means the model supports image generation through the provider's Images API; the tag is selected manually because model lists do not reliably declare this capability.
4. Open Remote Image, select an added model tagged `image`, and save. URL, API key and upstream model name come from the selected provider/model.

Keys are stored in SQLite and are never returned by the model management API. Leave a provider's key field blank when editing to retain its current key. Existing image tools pick up model selections and provider credential edits immediately. Change the Remote Image selection before deleting its model/provider or removing its `image` tag.

## MCP Client URL

Host-local clients:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

Docker clients on the same Compose network:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

## Agent Setup

Use the WebUI Matrix page to add, remove, and edit agents. Caller tokens, Matrix account credentials and permissions are stored in SQLite.

For legacy configuration import on the first startup, `config/config.yaml` can declare:

```yaml
agents:
  enabled:
    - agent1
    - agent2

modules:
  matrix:
    enabled: true
```

Then create or edit each `config/agent/config.agent.<name>.yaml` and fill `caller.token` plus `matrix.access_token` if that agent sends Matrix messages.

## Advanced YAML Override

`CONFIG_PATH` is still supported for tests and advanced development. It supplies bootstrap values and the database path, with missing defaults filled from `config/config.main.yaml`. Saved management settings in that database then take precedence.
