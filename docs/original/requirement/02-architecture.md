# 02. Architecture

## Recommended Architecture

```text
Host ZeroClaw assistant
Docker role ZeroClaw A
Docker role ZeroClaw B
Docker role ZeroClaw C
        |
        | SSE MCP
        v
home_mcp_gateway
        |
        +-- tool registry
        +-- auth and policy
        +-- job manager
        +-- artifact store
        +-- audit logger
        |
        +-- image module   -> third-party OpenAI image2-compatible API
        +-- tts module     -> local/remote TTS service
        +-- matrix module  -> Matrix homeserver
        +-- printer module -> OS printer service
```

## Deployment Shapes

### Docker Deployment

The MCP Gateway can be deployed with Docker. Most network-based capabilities fit well inside Docker, but the printer module depends on the actual host system:

- If the printer is reachable through a network protocol, Docker is usually viable.
- If the printer depends on host USB, Windows print queues, macOS CUPS, or mDNS discovery, run the Gateway on the host or provide a host-side `printer_module` sidecar.

### Host Deployment

Host deployment is suitable for the first debugging stage, especially when local printers, audio devices, or system credentials are involved.

### Hybrid Deployment

The `home_mcp_gateway` can run in Docker while a host-side `printer_bridge` handles printing. The Gateway calls `printer_bridge` over HTTP, while ZeroClaw still sees a single MCP service.

## Layers

### Transport Layer

Owns SSE MCP protocol handling, connection management, request parsing, responses, and event streaming. It does not contain business logic.

### MCP Tool Layer

Owns tool schemas, parameter validation, tool registration, unified error format, and dispatch. It does not call external APIs directly.

### Application Layer

Owns use case orchestration, such as creating jobs, calling modules, writing artifacts, and recording audit logs.

### Capability Module Layer

Owns a single domain capability, such as image, TTS, Matrix, or printer. Each module can contain provider adapters.

### Provider Adapter Layer

Owns integration with external APIs or local services, such as third-party OpenAI image2-compatible APIs, official OpenAI APIs, Piper, VOICEVOX, Matrix SDK, CUPS, and Windows Print Spooler.

### Infrastructure Layer

Owns configuration, secrets, logging, storage, queueing, HTTP clients, file system access, and security policy.

## Core Design Principles

- MCP tool schemas are external contracts; internal implementations can be replaced.
- Each capability module exposes a stable service interface.
- Modules do not call each other directly. Cross-module workflows are composed by the Application layer or by ZeroClaw.
- File-based outputs are written to the artifact store. MCP responses should not contain large binary payloads.
- High-risk actions are checked through a central policy engine instead of scattered module-level checks.

## Suggested Directory Layout

```text
mcp_1/
  app/
    main.py
    config.py
    logging.py
  transport/
    sse_server.py
    mcp_protocol.py
  tools/
    registry.py
    schemas.py
    dispatcher.py
  core/
    artifacts.py
    jobs.py
    policy.py
    audit.py
    errors.py
  modules/
    image/
      service.py
      providers/
        openai_compatible_provider.py
        official_openai_provider.py
      schemas.py
    tts/
      service.py
      providers/
      schemas.py
    matrix/
      service.py
      schemas.py
    printer/
      service.py
      providers/
      schemas.py
  deploy/
    Dockerfile
    docker-compose.yml
  requirement/
```

The implementation language can be decided later. Python with FastAPI/Starlette is a good fit for fast delivery; Rust is also suitable if long-term single-binary deployment and stronger typing are preferred.

