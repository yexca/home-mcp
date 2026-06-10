# Architecture

`home_mcp_gateway` is a single-process, modular Python gateway. It exposes MCP
tools over HTTP, applies authentication and policy checks in one place, and
keeps external provider details behind module adapters.

## Runtime Layers

| Layer | Package | Responsibility |
| --- | --- | --- |
| Application | `app/` | Load settings, open SQLite, build core services, register tools, start HTTP server. |
| Transport | `transport/` | Serve `/healthz`, `/readyz`, `/mcp`, `/mcp/messages`, and `/artifacts/{id}`. |
| Tool system | `tools/` | Register tool definitions, validate input schemas, dispatch handlers, normalize success/failure results. |
| Core services | `core/` | Artifacts, jobs, audit events, caller policy, rate limits, database migrations, stable errors. |
| Modules | `modules/` | Domain logic and tool registration for optional capabilities. |
| Providers | `modules/*/providers/` | HTTP adapters for external image, TTS, Matrix, and printer services. |

## Startup Flow

1. `app.main.build_services()` loads settings with `app.config.load_settings()`.
2. SQLite is opened through `core.db.connect_database()`, which applies schema migrations.
3. `CoreServices` is assembled with artifact, job, policy, audit, and rate-limit services.
4. Built-in tools are registered through `tools.builtin.register_builtin_tools()`.
5. Enabled module manifests are discovered by `modules.loader.register_configured_module_tools()`.
6. Enabled module startup hooks are run through `modules.loader.run_configured_module_startup_hooks()`.
7. `transport.mcp_server.create_http_server()` creates a `ThreadingHTTPServer`.

The module loader discovers packages under `modules/`, then imports
`modules.<name>.manifest` for each enabled module. A manifest may also expose an
optional startup hook for module-owned maintenance such as stale job
reconciliation. This keeps application startup independent from individual
module implementations.

## Request Flow

For tool calls, transport parsing ends in `ToolDispatcher.dispatch()`:

1. Generate a request ID.
2. Resolve the `ToolDefinition` from `ToolRegistry`.
3. Validate arguments against the tool input schema.
4. Resolve caller identity from bearer token, trusted metadata, or anonymous fallback.
5. Create a job when the tool has `creates_job=True`.
6. Start an audit event.
7. Evaluate policy and fail early on denied calls.
8. Build a `RequestContext` and call the tool handler.
9. Extract artifact IDs from the result.
10. Mark the job and audit event as succeeded or failed.
11. Return a stable success or failure dictionary.

Tools may declare a module-owned background handler. In that case the
dispatcher still owns validation, caller resolution, policy, job creation,
audit creation, and failure shaping. After policy passes it calls the
background handler, which should schedule worker-owned execution and return an
`accepted` response quickly. The worker later marks the job and audit event as
succeeded or failed, and callers use `job_status` to observe completion.

Unhandled exceptions are converted to `INTERNAL_ERROR`; stack traces are not
returned to MCP clients.

## Transport Protocols

The gateway supports three call shapes:

- HTTP health/readiness:
  - `GET /healthz`
  - `GET /readyz`
- MCP JSON-RPC:
  - `POST /mcp` with `initialize`, `ping`, `tools/list`, or `tools/call`.
- MCP SSE:
  - `GET /mcp` opens an SSE stream and returns an `endpoint` event.
  - `POST /mcp/messages?sessionId=...` sends JSON-RPC messages for that stream.
- Simple compatibility JSON:
  - `POST /mcp` with `{"method":"tools/list"}`.
  - `POST /mcp` with `{"tool":"health_check","arguments":{}}`.

Artifact files are served by `GET /artifacts/{artifact_id}` after the same
artifact ownership/grant checks used by `artifact_get`.

## Storage Model

SQLite schema version 1 creates:

- `artifacts`: artifact metadata, owner, storage path, hashes, expiry, and source tool/job.
- `jobs`: job status, progress, summaries, errors, and artifact IDs.
- `audit_events`: request audit records with caller, tool, policy decision, status, and errors.
- `caller_artifact_grants`: explicit read grants from artifact to caller.

The physical artifact root is `settings.artifacts.root`. Files are committed
under kind-specific directories such as `images/YYYY/MM/` and `audio/YYYY/MM/`.
Temporary writes go through `tmp/*.part` before metadata is inserted.

## Artifact Access

An artifact is readable when:

- The caller owns it.
- The caller is an admin and has `shared_artifact_read: true`.
- A non-expired `caller_artifact_grants` read grant exists.

`ArtifactStore.safe_path()` resolves paths under the configured artifact root
and rejects escaped paths before opening files.

## Risk And Policy

Each tool has a `risk_level` of `low`, `medium`, or `high`.

- Anonymous callers are denied unless the tool is in `policy.anonymous_allowed_tools`.
- `health_check` is always allowed.
- Admin callers are allowed after module-specific allowlist checks.
- `job_status` and `artifact_get` defer ownership checks to the backing stores.
- High-risk tools require explicit `policy.high_risk_allowed_callers`.
- Matrix room IDs and printer IDs are checked against allowlists before provider calls.
- Medium and low tools follow `policy.default_allow` for non-admin callers.
