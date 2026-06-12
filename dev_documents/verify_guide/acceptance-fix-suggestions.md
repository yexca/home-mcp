# Acceptance Fix Suggestions

This document records fix suggestions from the current acceptance pass against
`dev_documents/coding_guide/` and the design documents under `dev_documents/`.

## Acceptance Result

The current build should not pass the full Phase 6 / release gate yet.

The basic regression, compilation, local health checks, and Docker Compose
startup checks passed. Two blocking issues remain:

1. `metadata.caller` from an HTTP request body can spoof caller identity.
2. `/mcp` is not an actual SSE MCP transport yet, so ZeroClaw
   `transport = "sse"` compatibility is not proven.

## Blocker 1: Caller Metadata Trust Boundary

### Symptom

The current request flow trusts caller metadata from a normal HTTP JSON body:

- `transport/mcp_server.py`: `_parse_mcp_payload(payload)` returns
  `payload.get("metadata", {})`.
- `tools/dispatcher.py`: calls
  `policy.resolve_caller(authorization, metadata, remote_addr)`.
- `core/policy.py`: returns the configured caller identity when
  `metadata["caller"]` matches a configured caller.

Observed reproduction:

An unauthenticated call without a Bearer token can pass
`metadata={"caller":"host_assistant"}` and be resolved as the admin caller.
In the acceptance check, this allowed `artifact_get` to read an artifact.

### Risk

This violates the requirement that Gateway policy is the final permission
source.

Impact:

- Admin identity spoofing.
- Artifact permission bypass.
- High-risk tool authorization bypass risk.
- Untrustworthy caller values in audit rows.

### Suggested Fix

Preferred approach:

1. Do not use HTTP request-body `metadata.caller` for authentication.
2. Resolve caller identity from `Authorization: Bearer <gateway caller token>`
   first.
3. If connection metadata caller support is required, accept only metadata
   created by the trusted transport layer, not arbitrary client body fields.
4. Split untrusted client metadata from trusted connection metadata, for
   example:
   - `client_metadata`: request body metadata, never used for auth.
   - `trusted_connection_metadata`: metadata produced by transport, mTLS, a
     trusted reverse proxy, or another trusted authentication layer.
5. Add a security regression test: with no Authorization header and
   `metadata.caller=host_assistant`, every non-`health_check` tool must return
   `POLICY_DENIED`.

Minimum acceptable fix:

- In `transport/mcp_server.py`, do not pass request-body metadata into caller
  resolution.
- Or remove the `metadata["caller"]` fallback in
  `PolicyEngine.resolve_caller()` until a trusted connection metadata source
  exists.

## Blocker 2: `/mcp` Is Not SSE MCP

### Symptom

The current `/mcp` behavior in `transport/mcp_server.py` is:

- `GET /mcp` returns a JSON tools list.
- `POST /mcp` accepts JSON and directly dispatches tool calls.

There is no visible SSE session, `text/event-stream` response, message
endpoint, or MCP SSE protocol handling.

### Risk

The coding guide and deployment notes require ZeroClaw configuration like:

```toml
[[mcp.servers]]
name = "home"
transport = "sse"
url = "http://127.0.0.1:8787/mcp"
deferred_loading = true
```

If ZeroClaw connects as a strict SSE MCP client, the current implementation may
not support tool discovery or tool calls.

### Suggested Fix

Choose one path:

1. Implement real SSE MCP transport:
   - `GET /mcp` opens a `text/event-stream` session.
   - Provide the MCP SSE message endpoint.
   - Support `tools/list`, `tools/call`, and deferred schema loading.
   - Add a contract test with ZeroClaw or a compatible MCP SSE client.
2. If this version intentionally supports only HTTP JSON, update the docs and
   ZeroClaw examples:
   - Do not document `transport = "sse"` for the current runtime.
   - Clearly mark `/mcp` as a JSON HTTP endpoint.
   - Move SSE integration out of the current Phase 0 / release gate or mark it
     as next-stage work.

The recommended path is to implement real SSE, because the requirements,
high-level design, coding guide, and deployment notes all target ZeroClaw SSE.

## Non-Blocking Fixes

### ResourceWarning Cleanup

The previous test runner passed 36 tests, but emitted several warnings:

- Unclosed SQLite connection.
- Unclosed socket.

Suggestions:

1. Add a `close()` method or context manager to `CoreServices`.
2. Close SQLite connections in test `tearDown()`.
3. Call `server_close()` on mock HTTP servers.
4. Later, consider CI with `-W error::ResourceWarning`.

### Manual Acceptance Gaps

These checks require local secrets, local services, or hardware and were not
included in the default automated run:

- ZeroClaw host SSE integration.
- Real iKun image smoke test.
- Matrix allowlisted-room audio workflow.
- Physical printer or printer bridge acceptance.

Keep these manual-only. Record only `request_id`, `job_id`, and `artifact_id`.
Do not record tokens, provider URL query strings, sensitive local paths, or
screenshots containing secrets.

## Checks That Passed

This acceptance pass verified:

- Previous test runner: 36 tests OK.
- `python -m compileall app core modules tools transport tests`.
- Local `/healthz` and `/readyz`.
- Tool registration under default, image, phase4, and phase5 configs.
- Secret scan: no real provider secrets found, only placeholders or test
  tokens.
- `docker compose build`.
- `docker compose up -d`, followed by `/healthz` and `/readyz`.

## Recommended Fix Order

1. Fix caller metadata spoofing.
2. Add a regression test for caller metadata spoofing.
3. Implement real SSE MCP transport, or explicitly document HTTP JSON instead.
4. Add ZeroClaw SSE contract or manual acceptance.
5. Clean up resource warnings.
6. Re-run the release checklist.
