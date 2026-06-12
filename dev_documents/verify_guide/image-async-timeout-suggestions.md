# Image Async Timeout Suggestions

This note records the follow-up guidance from the image provider timeout
diagnosis. Other resolved acceptance reports are intentionally left untouched.

## Finding

The image provider path is reachable, and MCP discovery is working, but
`image_generate` is still effectively synchronous from the MCP caller's point of
view.

Current behavior:

- `image_generate` is registered with `creates_job=True`.
- The dispatcher creates a job and marks it `running`.
- The dispatcher then waits for the image handler to finish.
- Only after the handler returns does the response include `job_id`.
- If the provider call or provider image download hangs, the job and audit event
  remain open as `running` / `started`.

This means `creates_job=True` currently means "record this long-running call",
not "return a job id immediately and continue in the background".

## Timeout Finding

`modules.image.ikun.timeout_seconds` is passed to `urllib.request.urlopen`.
That timeout does not act as a strict wall-clock deadline for the whole image
workflow. It applies to blocking socket operations. A request can still take a
long time overall if the provider keeps the connection alive, responds slowly,
or if the subsequent image URL download keeps making progress.

ZeroClaw's `MCP_TOOL_TIMEOUT_SECS=600` is also not a complete fix. It caps how
long ZeroClaw waits for the MCP tool call, but it does not force the MCP gateway
handler to stop its provider call or to mark the gateway job failed.

There is also a configured `limits.sync_tool_timeout_seconds` value in the
gateway config example, but the current dispatcher does not enforce it.

## Suggested Product Semantics

For slow image operations, prefer a real asynchronous contract:

1. `image_generate` validates input, creates a job, schedules background work,
   and returns immediately.
2. The immediate response includes `job_id`, initial status, and no artifact.
3. The caller polls `job_status`.
4. When the background worker succeeds, `job_status` returns artifact ids and a
   result summary.
5. The caller fetches artifact metadata with `artifact_get`.

Recommended immediate response shape:

```json
{
  "ok": true,
  "status": "accepted",
  "request_id": "req_...",
  "job_id": "job_...",
  "job": {
    "id": "job_...",
    "status": "running",
    "progress": 0
  }
}
```

This makes the Matrix/ZeroClaw workflow reliable: the bot can tell the user the
image is queued, then poll until the artifact is ready.

## Suggested Implementation Direction

Keep the first implementation narrow and image-focused unless the dispatcher is
ready for a more general background job framework.

Recommended steps:

1. Add an image-specific background execution path.
2. Return `job_id` before calling the provider.
3. Run the provider call and artifact persistence in a background worker.
4. Mark the job `succeeded` or `failed` from that worker.
5. Finish the audit event from that worker.
6. Store artifact ids in the job record on success.

Important SQLite note:

- The current service uses one SQLite connection in `CoreServices`.
- Before moving work to a background thread, confirm whether the connection can
  be safely used there.
- If needed, open a fresh connection per worker using the same database path and
  construct worker-local `ArtifactStore`, `JobManager`, and `AuditLogger`
  instances.

Avoid keeping the HTTP request thread alive while waiting for the provider.

## Deadline Requirement

Add a gateway-owned total deadline around the whole image operation. The
deadline should include:

- provider generation POST;
- provider response decoding;
- provider image URL download, if the provider returns a URL;
- artifact persistence.

Suggested config:

```yaml
modules:
  image:
    total_timeout_seconds: 600
```

or reuse `limits.sync_tool_timeout_seconds` only for still-synchronous tools.
The important point is that image jobs need a wall-clock deadline owned by the
gateway, not only socket timeouts owned by `urlopen`.

On deadline expiry:

- mark job `failed`;
- set `error_code` to `PROVIDER_TIMEOUT`;
- finish the audit event;
- do not create a partial artifact;
- return/persist a retryable timeout error.

## Orphan Running Jobs

Restarting the gateway clears in-process provider calls, but it does not repair
old `running` rows in SQLite.

Add a startup reconciliation step or a maintenance tool that marks stale
non-terminal jobs as failed when their `updated_at` is older than the configured
deadline.

Suggested error code/message:

```text
PROVIDER_TIMEOUT
image job exceeded gateway deadline or was abandoned during restart
```

Keep this conservative: only close jobs whose age clearly exceeds the configured
deadline plus a small grace period.

## Logging And Audit Guidance

Add low-volume lifecycle logs for image jobs:

- job created;
- provider request started;
- provider response received;
- provider URL download started;
- artifact persisted;
- job finished;
- job failed or timed out.

Do not log:

- provider API keys;
- bearer tokens;
- full signed provider image URLs;
- raw base64 image data.

The audit table can keep durations, status, error code, artifact ids, and a
prompt summary.

## Verification Checklist

Add tests for:

- `image_generate` returns quickly with `job_id` before provider completion.
- `job_status` shows `running` while provider work is in progress.
- successful background completion updates job to `succeeded`.
- successful background completion stores artifact ids in `jobs.artifact_ids_json`.
- provider timeout marks job `failed` with `PROVIDER_TIMEOUT`.
- gateway deadline closes the job even when the provider keeps blocking.
- restart/stale reconciliation marks old running image jobs failed.
- audit events are finished for success, provider failure, and deadline failure.

Manual verification:

1. Configure the real image provider.
2. Trigger `image_generate` from ZeroClaw.
3. Confirm the bot receives a `job_id` quickly.
4. Poll `job_status` until completion.
5. Confirm the final artifact is readable with `artifact_get`.
6. Trigger or simulate a slow provider response.
7. Confirm the job reaches `failed` after the gateway deadline.
8. Confirm no stale `running` image jobs remain beyond the deadline window.

## Acceptance Criteria

The fix is complete when:

- MCP tools/list and health remain unchanged.
- `image_generate` no longer holds the MCP tool call open for the full provider
  duration.
- ZeroClaw can start an image job, wait independently, and later fetch the
  artifact.
- Gateway jobs never remain `running` forever after provider hangs or gateway
  restarts.
- Timeout behavior is deterministic and visible in `jobs` and `audit_events`.
