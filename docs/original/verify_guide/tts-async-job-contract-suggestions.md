# TTS Async Job Contract Suggestions

This note records the proposed TTS contract adjustment. It is intentionally
limited to a design and verification guide; no runtime code changes are implied
by this document.

## Goal

Align `tts_synthesize` with the first step of the image async workflow:

1. The caller starts speech synthesis.
2. The gateway returns a `job_id` immediately.
3. The caller polls the shared `job_status` tool until the job reaches a
   terminal state.
4. On success, the caller uses the shared `artifact_get` tool with the returned
   `artifact_id` to fetch artifact metadata and a signed download URL.

The TTS module should not introduce TTS-only status or artifact lookup tools.
Jobs and artifacts are already gateway-wide concepts and should remain shared.

## Current TTS Behavior

Current behavior is job-recorded but effectively synchronous:

- `tts_synthesize` is registered with `creates_job=True`.
- The dispatcher creates a job and marks it `running`.
- The TTS handler validates arguments, calls the configured provider, persists
  the audio artifact, and returns only after provider work is complete.
- The final response includes the artifact metadata and the dispatcher adds the
  `job_id`.

This means a slow or unavailable TTS provider can keep the MCP tool call open
for the provider duration.

## Target Product Semantics

`tts_synthesize` should become a real asynchronous start operation.

Recommended immediate response:

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

The immediate response should not include an audio artifact, because no audio
artifact is guaranteed to exist yet.

When the background TTS worker succeeds, the job record should contain:

- `status: succeeded`;
- `artifact_ids`, including the generated audio artifact id;
- a compact `result_summary` with non-secret synthesis metadata, such as
  provider name, MIME type, voice, language, format, speed, and size.

When the worker fails, the job record should contain:

- `status: failed`;
- a stable gateway error code;
- a safe error message;
- retryability where the existing error shape supports it.

## Shared Lookup Flow

Keep result lookup generic:

1. `job_status`
   - Input: `job_id`.
   - Output while running: status/progress only.
   - Output on success: status plus artifact ids and result summary.
   - Output on failure: status plus stable error details.

2. `artifact_get`
   - Input: `artifact_id`.
   - Output: artifact metadata and a short-lived signed `download_url` when the
     caller is allowed to read the artifact.

This preserves the existing ownership and signed-download boundary. The client
does not need to know where audio files are stored on disk.

## Polling Guidance

Document polling limits clearly for clients:

- Wait about `1-2` seconds after receiving `job_id` before the first
  `job_status` call.
- Poll every `2-5` seconds for normal TTS jobs.
- If the job remains `running`, back off to `5-10` seconds.
- Avoid sub-second polling and avoid multiple concurrent polls for the same
  job.
- Stop polling once the job reaches `succeeded` or `failed`.

`job_status` should continue enforcing job visibility:

- the job owner can read the job;
- admins with the configured shared-read behavior can read shared jobs;
- unrelated callers cannot use `job_id` as a disclosure channel.

If a future explicit `job_status` rate limit is added, it should be caller- or
IP-scoped and documented separately from TTS provider limits.

## Suggested Implementation Direction

Use the image background pattern as the reference, but keep the first TTS
implementation narrow.

Recommended steps:

1. Add a TTS background execution path.
2. Keep schema validation in the dispatcher.
3. Run cheap deterministic TTS validation before accepting the job when
   practical:
   - non-empty text;
   - text length;
   - allowed voice;
   - allowed language;
   - allowed format;
   - speed range.
4. Check `tts_jobs_per_caller_per_day` before scheduling work.
5. Return the accepted job response before calling the provider.
6. Run provider synthesis and artifact persistence in the background worker.
7. Mark the job `succeeded` with artifact ids when the artifact is persisted.
8. Mark the job `failed` with a stable error code when provider work fails.
9. Finish the audit event from the worker for both success and failure.

Do not add a TTS-specific artifact lookup tool. Reuse `artifact_get`.

## Provider And Artifact Rules

The existing TTS provider and artifact validation rules should remain:

- `local_http` sends JSON to the configured provider URL.
- `mock` remains available for deterministic local tests.
- Supported formats remain `ogg`, `mp3`, and `wav`.
- The provider MIME type must be supported and must match the requested format.
- Successful output is stored as an `audio` artifact.
- Artifact metadata should continue recording provider, voice, language,
  format, and speed.

The physical artifact storage layout does not need to change. Audio artifacts
continue to live under the shared artifact root in the `audio/YYYY/MM/`
directory, while callers access them only through `artifact_id`.

## Timeout And Stale Job Guidance

TTS should have a gateway-owned total deadline, separate from the provider
socket timeout.

Suggested config direction:

```yaml
modules:
  tts:
    total_timeout_seconds: 120
    stale_job_grace_seconds: 30
```

On timeout:

- mark the job `failed`;
- use `PROVIDER_TIMEOUT`;
- finish the audit event;
- do not create a partial artifact;
- keep the provider URL, API key, bearer token, raw text beyond configured
  summaries, and any signed URLs out of logs.

If the process restarts while TTS jobs are running, a startup reconciliation
step should mark stale non-terminal TTS jobs failed after the configured
deadline plus grace period.

## Verification Checklist

Add or update tests for:

- `tts_synthesize` returns quickly with `status: accepted` and `job_id`.
- The immediate response does not include an audio artifact.
- `job_status` shows `running` before provider completion.
- Successful background completion marks the job `succeeded`.
- Successful completion stores the audio artifact id in the job record.
- `artifact_get` returns metadata and a signed download URL for the generated
  audio artifact.
- Invalid text, voice, language, format, and speed are rejected before provider
  work starts when practical.
- Unsupported provider MIME types fail the job with `UNSUPPORTED_MEDIA_TYPE`.
- Provider timeout fails the job with `PROVIDER_TIMEOUT`.
- Provider 401/403, 429, and 5xx responses map to the existing stable gateway
  error codes.
- Non-owner callers cannot read another caller's TTS job or artifact.
- Audit events finish for success, validation failure, provider failure, and
  timeout.

Manual verification:

1. Enable `modules.tts` with `provider: mock`.
2. Call `tts_synthesize`.
3. Confirm the response returns a `job_id` immediately.
4. Poll `job_status` using the recommended interval.
5. Confirm the completed job contains an audio artifact id.
6. Call `artifact_get` with that artifact id.
7. Confirm the response includes audio metadata and a signed `download_url`.
8. Repeat with `provider: local_http`.
9. Simulate a slow or failed provider and confirm the job reaches `failed`
   without leaving stale `running` jobs.

## Acceptance Criteria

The change is complete when:

- `tts_synthesize` no longer holds the MCP tool call open for the provider
  duration.
- The first response is an accepted job response with `job_id`.
- `job_status` and `artifact_get` are the only required follow-up tools.
- Polling guidance is documented for clients.
- Generated audio remains a normal gateway artifact with signed download
  access.
- TTS provider failures, MIME mismatches, and timeouts are visible through the
  job record and audit trail.
