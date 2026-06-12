# Local SSE MCP Gateway Detailed Design

## Objective

This directory continues the requirement analysis in `dev_documents/requirement/` and the high-level design in `dev_documents/high_design/`. It turns `home_mcp_gateway` into an implementation-ready MVP design.

The first version runs locally or in Docker, exposes a unified SSE MCP entry point for the host ZeroClaw assistant and multiple Docker role-play ZeroClaw instances, and centralizes image generation, TTS, Matrix messaging, printing, artifacts, jobs, auditing, and policy enforcement.

## Design Decisions

- Use Python 3.11+, FastAPI/Starlette, SQLite with WAL, and a local filesystem artifact store for the MVP.
- Expose `/mcp` as the SSE MCP endpoint and `/artifacts/{artifact_id}` as the artifact download endpoint.
- Keep MCP tool schemas provider-neutral. iKun/OpenAI-compatible details belong only in the image provider adapter.
- Create a job for every long-running or side-effecting tool. Return the final result when the tool finishes within the synchronous timeout; otherwise return `job_id`.
- Support both iKun image response shapes: `data[].url` and `data[].b64_json`. Persist either form immediately into the local artifact store.
- Do not allow tool arguments to provide arbitrary provider URLs, local file paths, Matrix rooms, or printers.
- Run every high-risk action through the Gateway policy engine, even when ZeroClaw has `auto_approve` configured.
- Treat `dev_documents/ikun/key.txt` as local-only reference material. Do not copy its contents into design docs, config examples, logs, or code.

## Document Index

- [01-mcp-transport-detail.md](01-mcp-transport-detail.md): MCP/SSE entry point, HTTP routes, tool dispatch, connection handling, and error handling.
- [02-core-schema-detail.md](02-core-schema-detail.md): Core directory structure, context object, SQLite DDL, artifact/job/audit services.
- [03-image-provider-detail.md](03-image-provider-detail.md): iKun/OpenAI-compatible provider configuration, request mapping, response normalization, and persistence.
- [04-security-policy-detail.md](04-security-policy-detail.md): caller identity, policy engine, rate limits, secrets, path safety, and download security.
- [05-test-plan.md](05-test-plan.md): unit, integration, contract, E2E, security, and regression test plan.
- [06-zeroclaw-config-detail.md](06-zeroclaw-config-detail.md): ZeroClaw MCP configuration, auto-approval guidance, and Docker networking.
- [config.example.yaml](config.example.yaml): first-version Gateway configuration example.

## MVP Scope

The first implementation should prioritize:

1. `health_check`, `job_status`, and `artifact_get`.
2. artifact store, job manager, audit logger, and policy engine.
3. `image_generate` and `image_edit`, backed by iKun `/v1/images/generations` and `/v1/images/edits`.
4. TTS, Matrix, and printer interfaces/configuration skeletons, with concrete providers implemented in later phases as needed.

Out of scope for the first version:

- public multi-tenant service.
- web admin console.
- standalone human approval UI.
- distributed queue cluster.
- arbitrary file download or arbitrary local-path printing.
- full pass-through of provider-private parameters in MCP tool schemas.

