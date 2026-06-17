# Local SSE MCP Gateway Requirements

## Goal

Build a Docker-deployable local MCP service for the host ZeroClaw assistant and multiple Docker-based role play ZeroClaw instances. The first version uses a single Gateway service. It exposes tools through SSE MCP and connects internal capability/skill modules for third-party OpenAI image2-compatible image generation/editing APIs, local TTS, Matrix voice messaging, local printers, and future capabilities.

## Core Decisions

- The MCP service can be deployed with Docker.
- The first version should be a single `home_mcp_gateway` service using SSE transport.
- The external contract is MCP protocol plus stable tool schemas.
- Internal capabilities are split into domain modules to keep high cohesion and low coupling.
- Third-party image API keys, Matrix tokens, and high-risk system permissions stay inside the MCP Gateway and are not distributed to ZeroClaw containers.
- File-based outputs are stored in the artifact store. Tools return `artifact_id`, path, URL, and metadata.
- Tools with external side effects, such as printing and Matrix sending, should not be auto-approved by default.

## Scope

### Included In The First Stage

- SSE MCP service entrypoint.
- Tool registration and discovery.
- Artifact storage.
- Image generation module, with first-class support for third-party OpenAI image2-compatible/proxy APIs and future provider replacement.
- TTS synthesis module.
- Matrix text/audio sending module.
- Printer module requirements and interface reservation.
- Docker Compose deployment plan.
- Configuration, secrets, logging, audit, and permission policy.

### Not Included In The First Stage

- Public multi-tenant service.
- Web admin console.
- Full billing system.
- Complex clustered queue system.
- Multi-machine distributed deployment.
- Complete compatibility with every printer format.

## Document Index

- [01-overview.md](01-overview.md): Product goals, user scenarios, and runtime boundaries.
- [02-architecture.md](02-architecture.md): Overall architecture, module boundaries, and data flow.
- [03-modules.md](03-modules.md): Capability/skill module model and extension rules.
- [04-tools.md](04-tools.md): MCP tool list and parameter drafts.
- [05-deployment.md](05-deployment.md): Docker, SSE, and ZeroClaw configuration plan.
- [06-security.md](06-security.md): Permissions, secrets, approval, and audit.
- [07-milestones.md](07-milestones.md): MVP phases and acceptance criteria.

