# 05. Deployment And Configuration

## Docker Feasibility

The MCP Gateway can be deployed with Docker. Docker is a good fit for network-based capabilities such as third-party OpenAI image2-compatible/proxy image APIs, TTS HTTP services, and Matrix. Local printers need host-system-specific decisions:

- Network printer: Usually viable from Docker.
- Linux CUPS: Can mount a CUPS socket or access CUPS over the network.
- Windows local printer: Prefer a host-side print bridge service.
- USB printer: Prefer a host-side sidecar; direct Docker access is more complex.

## Recommended Compose Shape

```yaml
services:
  home-mcp:
    build: .
    container_name: home-mcp
    ports:
      - "8787:8787"
    environment:
      MCP_HOST: "0.0.0.0"
      MCP_PORT: "8787"
      MCP_TRANSPORT: "sse"
      ARTIFACT_ROOT: "/artifacts"
      IMAGE_API_BASE_URL: "${IMAGE_API_BASE_URL}"
      IMAGE_API_KEY: "${IMAGE_API_KEY}"
      IMAGE_API_MODEL: "${IMAGE_API_MODEL}"
      MATRIX_HOMESERVER: "${MATRIX_HOMESERVER}"
      MATRIX_ACCESS_TOKEN: "${MATRIX_ACCESS_TOKEN}"
    volumes:
      - ./artifacts:/artifacts
      - ./config:/config:ro
    restart: unless-stopped
```

## ZeroClaw Configuration Draft

Host ZeroClaw:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

Docker ZeroClaw, when the Gateway runs on the host:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://host.docker.internal:8787/mcp"
deferred_loading = true
```

Linux Docker may need:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Docker ZeroClaw, when the Gateway runs in the same compose network:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://home-mcp:8787/mcp"
deferred_loading = true
```

## Configuration File Suggestion

```yaml
server:
  host: 0.0.0.0
  port: 8787
  transport: sse

artifacts:
  root: /artifacts
  public_base_url: http://home-mcp:8787/artifacts
  retention_days: 30

policy:
  default_allow: false
  allowed_matrix_rooms:
    - "!example:matrix.org"
  allowed_printers:
    - "Home_Printer"

modules:
  image:
    enabled: true
    provider: openai_compatible
    base_url: ${IMAGE_API_BASE_URL}
    model: ${IMAGE_API_MODEL}
    max_concurrent: 2
    daily_budget_usd: 5
  tts:
    enabled: true
    provider: local_http
    endpoint: http://tts:5000
  matrix:
    enabled: true
  printer:
    enabled: false
```

## Network Exposure

The first stage should only listen on localhost or Docker internal networks:

- Host debugging: `127.0.0.1:8787`
- Docker sharing: `0.0.0.0:8787`, but only within local firewall limits
- Direct public exposure is not recommended

If remote access is needed later, add:

- Reverse proxy.
- TLS.
- Bearer token or mTLS.
- IP allowlist.
- Tool-level permission policy.

## Artifact Mounts

Recommended host storage:

```text
mcp_1/artifacts/
  images/
  audio/
  print/
  tmp/
```

ZeroClaw does not need direct access to real file system paths. Prefer `artifact_id` and download URLs returned by MCP.

