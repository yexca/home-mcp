# 06. ZeroClaw Configuration Detailed Design

## Configuration Entry

The ZeroClaw MCP reference states:

- MCP servers are configured in `config.toml` under `[mcp]` and `[[mcp.servers]]`.
- `name` is required and becomes the tool prefix `name__tool_name`.
- `transport` supports `stdio`, `sse`, and `http`.
- `deferred_loading = true` loads tool schemas on demand and reduces initial token overhead; keep it enabled.
- Without auto approval, MCP tool execution requires manual approval by default unless the agent risk profile grants broader autonomy.

## Host ZeroClaw

When the Gateway runs on the same host:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

Example tool names:

```text
home__health_check
home__artifact_get
home__image_generate
home__matrix_send_text
```

## Docker Role-Play ZeroClaw To Host Gateway

Windows/macOS Docker Desktop:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://host.docker.internal:8787/mcp"
deferred_loading = true
```

On Linux Docker, add this to compose when needed:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

## Same Compose Network

When the Gateway and ZeroClaw role containers share one Docker Compose network:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

The recommended compose service name is `home-mcp`.

## Auto-Approval Guidance

Low-risk tools:

```toml
[risk_profiles.assistant]
auto_approve = [
  "home__health_check",
  "home__job_status",
  "home__artifact_get",
  "home__printer_list"
]
```

For private local usage, `tts_synthesize` may also be added:

```toml
[risk_profiles.assistant]
auto_approve = [
  "home__health_check",
  "home__job_status",
  "home__artifact_get",
  "home__printer_list",
  "home__tts_synthesize"
]
```

Do not auto-approve these by default:

```text
home__image_generate
home__image_edit
home__matrix_send_text
home__matrix_send_audio
home__printer_print_file
```

Reasons:

- image tools carry third-party API cost and content risk.
- Matrix tools send content to external rooms.
- printing consumes physical resources and produces real-world output.

Even if a user auto-approves high-risk tools in ZeroClaw, the Gateway still enforces its policy engine.

## Tool Filtering

For role-play ZeroClaw instances that should not see high-risk tools, use tool filtering in project configuration. Suggested groups:

| group | tools |
| --- | --- |
| `home_readonly` | `home__health_check`, `home__job_status`, `home__artifact_get` |
| `home_media` | `home__image_generate`, `home__image_edit`, `home__tts_synthesize` |
| `home_side_effects` | `home__matrix_send_text`, `home__matrix_send_audio`, `home__printer_print_file` |

Gateway caller identity and policy remain the final authorization source.

## Caller Token Passing

If ZeroClaw supports custom headers for an MCP server, use:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true

[mcp.servers.headers]
Authorization = "Bearer ${GATEWAY_TOKEN_HOST}"
```

If the current ZeroClaw version does not support custom headers, the first version can map callers by source network or a dedicated endpoint token. Mark this as a caller-identity precision risk in the security notes.

## Integration Checklist

1. Gateway `/healthz` returns 200.
2. ZeroClaw discovers the `home` MCP server.
3. `home__health_check` succeeds.
4. `home__image_generate` does not require ZeroClaw to hold the iKun token.
5. `deferred_loading = true` sends only tool names in the initial context.
6. role-play ZeroClaw cannot read artifacts owned by other callers.
7. Matrix and printing tools are not included in default auto approval.

