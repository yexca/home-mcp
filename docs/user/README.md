# User Guide

This guide is for running `home_mcp_gateway` as a local MCP gateway. Normal users configure the gateway through YAML files under `config/`.

## Files You Touch

| File | Purpose |
| --- | --- |
| `config/config.yaml` | Local runtime settings, tokens, provider URLs, and module switches. Ignored by git. |
| `config/agent/config.agent.<name>.yaml` | Per-agent caller and Matrix settings, including local tokens. Ignored by git. |
| `config/comfyui/` | ComfyUI workflow JSON files used by local image generation. |

`config/config.main.yaml` is the committed baseline. Keep local values in `config/config.yaml` so project updates and personal settings stay separate.

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
python -m app.main
```

Or with Docker Compose:

```powershell
docker compose up --build
```

Compose mounts `./config` read-write into the container and stores artifacts under `./artifacts`.

## WebUI Configuration

Open:

```text
http://127.0.0.1:8787
```

Paste the value of `callers.host_assistant.token` as the Admin Token. The WebUI writes directly to `config/config.yaml` and `config/agent/*.yaml`. Restart the service after changing module switches or agent settings so tool registration is refreshed.

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

Use the WebUI Matrix page to add, remove, and edit agents. The WebUI writes `config/config.yaml` and `config/agent/config.agent.<name>.yaml` directly.

Manual setup is also possible. Edit `config/config.yaml`:

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

`CONFIG_PATH` is still supported for tests and advanced development. If set, the loader merges that YAML over `config/config.main.yaml` and does not use `config/config.yaml`.
