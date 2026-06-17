# Local Image Artifact Upload Suggestions

This note records a usability gap found while reviewing the `image_edit`
contract. The existing resolved verification notes are intentionally left
untouched.

## Finding

`image_edit` accepts `image_artifact_id` or `image_artifact_ids`, but those
values must already exist in the gateway artifact store. They are not local file
paths, public URLs, or raw image bytes.

Current behavior:

- Generated images can be reused because `image_generate` returns an image
  artifact id.
- Existing local images cannot be used directly through the public MCP tool
  surface.
- `artifact_get` can read artifact metadata, and `/artifacts/{id}` can download
  an existing artifact, but there is no public upload/import tool that creates a
  new image artifact from a caller-provided local image.

## User Impact

Users naturally expect this workflow:

```text
local image -> gateway artifact id -> image_edit
```

Today, the first step is missing from the MCP contract. A caller cannot pass
`C:/path/to/image.png` to `image_edit`, because the service looks up the value
as an artifact id through `ctx.artifacts.get(...)`.

## Suggested Fix

Add a dedicated low- or medium-risk tool for importing image artifacts, for
example `artifact_upload_image` or `image_upload`.

Recommended input schema:

```json
{
  "filename": "input.png",
  "mime_type": "image/png",
  "b64_data": "<base64 image bytes>"
}
```

Recommended output:

```json
{
  "ok": true,
  "status": "succeeded",
  "request_id": "req_...",
  "artifact": {
    "id": "art_...",
    "kind": "image",
    "mime_type": "image/png",
    "filename": "art_....png",
    "size_bytes": 12345,
    "sha256": "...",
    "download_url": "http://127.0.0.1:8787/artifacts/art_...",
    "metadata": {}
  }
}
```

The handler should persist the decoded bytes with `ctx.artifacts.create_from_bytes(...)`.

## Validation Rules

The upload tool should enforce the same image constraints used by `image_edit`:

- Accept only configured image MIME types, currently `image/png`, `image/jpeg`,
  and `image/webp`.
- Enforce `artifacts.max_artifact_bytes`.
- Reject empty or invalid base64 payloads.
- Derive the storage filename from the generated artifact id, not from the
  caller-provided filename.
- Store the original filename only in artifact metadata if needed.
- Keep artifact ownership scoped to the authenticated caller.

## Security Notes

Avoid accepting arbitrary server-side file paths in the public tool contract.
Path-based imports are convenient for local development, but they blur the trust
boundary and can expose files that the gateway process can read. If a local-only
path import is added, keep it admin-only and document that it is not suitable for
remote callers.

Base64 upload is the safer default MCP-facing contract because the caller sends
the exact bytes it wants imported.

## Suggested Verification Steps

1. Upload a small PNG through the new tool and confirm the response contains
   `artifact.id`, `mime_type`, `size_bytes`, `sha256`, and `download_url`.
2. Call `artifact_get` with the returned id and confirm the metadata is readable
   by the same caller.
3. Call `image_edit` with `image_artifact_ids: ["art_..."]` and confirm the
   provider receives the uploaded image bytes.
4. Try invalid MIME type, invalid base64, oversized image, and cross-caller
   access cases.
5. Confirm no raw image bytes, local paths, provider URLs, or secrets appear in
   audit logs.

## Documentation Updates

Update `documents/tool-contracts.md` and `documents/configuration.md` after the
tool is implemented. The docs should explain that `image_artifact_ids` are
gateway artifact ids and that local images must first be imported/uploaded to
the gateway artifact store.
