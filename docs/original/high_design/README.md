# Local SSE MCP Gateway High-Level Design

## Objective

This directory continues from the requirement analysis artifacts in `dev_documents/requirement/` and defines the high-level design for `home_mcp_gateway`. The goal is to deliver a local or Docker-deployable SSE MCP service that provides one shared tool entry point for the host ZeroClaw assistant and multiple Docker role-play ZeroClaw instances. The Gateway centralizes third-party image generation, TTS, Matrix messaging, printing, secrets, artifacts, policies, and audit logs.

## Design Conclusions

- Version 1 uses a modular monolithic Gateway instead of multiple independent MCP servers.
- The external MCP endpoint uses SSE, with `/mcp` as the default path.
- The ZeroClaw MCP server `name` should be `home`, so tools appear as `home__<tool_name>`.
- The Gateway is layered into transport, tool, application, capability module, provider adapter, and infrastructure layers.
- File outputs are stored in the artifact store. MCP responses return `artifact_id`, download URL, and metadata instead of large binary payloads.
- The first image provider targets the iKun OpenAI-compatible API. `base_url`, `api_key`, and `model` are configuration values; provider details are not exposed in the tool schema.
- iKun image responses may contain a temporary URL or `b64_json`; the Gateway must persist the image immediately as a local artifact.
- Matrix sending, printing, and external path access are high-risk actions and must pass the Gateway policy engine.

## Document Index

- [01-architecture.md](01-architecture.md): Overall architecture, layers, and module boundaries.
- [02-runtime-and-sequence.md](02-runtime-and-sequence.md): Runtime flow, startup flow, and typical call sequences.
- [03-tool-contracts.md](03-tool-contracts.md): MCP tool contracts, parameters, responses, and error codes.
- [04-artifact-job-design.md](04-artifact-job-design.md): Artifact and job data models and lifecycles.
- [05-provider-adapter-design.md](05-provider-adapter-design.md): High-level provider design for iKun image, TTS, Matrix, and printing.
- [06-security-deployment-design.md](06-security-deployment-design.md): Security, permissions, audit, configuration, and deployment.
- [07-next-stage-plan.md](07-next-stage-plan.md): Detailed-design follow-up and MVP implementation plan.

## Inputs

- Requirement analysis: `dev_documents/requirement/`
- iKun image API reference: `dev_documents/ikun/`
- ZeroClaw MCP configuration reference: `dev_documents/zeroclaw_mcp/`
