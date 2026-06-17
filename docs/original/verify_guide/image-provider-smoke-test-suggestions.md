# Image Provider Smoke Test Suggestions

This note records the real image provider smoke test findings and suggested
follow-up fixes. It is separate from the general acceptance report.

## Smoke Test Result

The image provider was tested with:

- `image_generate`: text-to-image.
- `image_edit`: image-to-image using the generated image artifact as input.

Both operations succeeded during the diagnostic smoke test, and the resulting
files were written under `tmp_result/`:

- `tmp_result/text_to_image.png`
- `tmp_result/image_to_image.png`
- `tmp_result/image_service_test_report.md`
- `tmp_result/image_service_test_summary.json`

No provider API keys or gateway bearer tokens were written to the result files.

## Configuration Finding

`IMAGE_API_BASE_URL` must be the OpenAI-compatible API root, not the image
endpoint path.

Correct shape:

```env
IMAGE_API_BASE_URL=https://api.example.com
```

Incorrect shape:

```env
IMAGE_API_BASE_URL=https://api.example.com/v1/images
```

Reason: the provider adapter already appends these paths:

- `/v1/images/generations`
- `/v1/images/edits`

If `/v1/images` is included in `IMAGE_API_BASE_URL`, requests become malformed,
for example:

```text
https://api.example.com/v1/images/v1/images/generations
```

## Provider Image URL Host Finding

The provider API host used for requests was:

```text
api.image-provider.example
```

The generated image URL host observed during the smoke test was:

```text
images.image-provider.example
```

When the provider returns URL outputs instead of `b64_json`, the gateway
downloads and persists the image immediately. The current downloader requires
the image URL host to appear in:

```yaml
modules:
  image:
    ikun:
      allowed_image_url_hosts:
        - images.image-provider.example
```

Suggested fix:

1. Add the observed image host to the production/local image config.
2. Document that `allowed_image_url_hosts` should contain provider response
   image hosts, not only the provider API host.
3. Keep the allowlist explicit; do not allow arbitrary image download hosts.

## Downloader Finding

After dynamically allowing `images.image-provider.example`, the original downloader still
failed to download the provider image URL during the smoke test. A diagnostic
fallback downloader with browser-like headers succeeded.

Observed implication:

- Provider calls are working.
- Artifact creation is working.
- The image URL download path may need more compatible request headers for this
  CDN/provider.

Suggested fix:

Add a conservative `User-Agent` header to image URL downloads in
`modules/image/service.py`.

Current request shape:

```python
request.Request(url, method="GET", headers={"Accept": "image/png,image/jpeg,image/webp"})
```

Suggested shape:

```python
request.Request(
    url,
    method="GET",
    headers={
        "Accept": "image/png,image/jpeg,image/webp,*/*",
        "User-Agent": "home-mcp-gateway/0.1",
    },
)
```

Also consider preserving the HTTP status code in the mapped error message for
download failures. Do not include the full provider image URL in logs or tool
responses, because signed URLs can contain sensitive query parameters.

## Suggested Verification Steps

1. Set image environment variables in local `.env`:

   ```env
   IMAGE_API_BASE_URL=https://api.example.com
   IMAGE_API_MODEL=<configured image model>
   IMAGE_API_KEY=<configured provider key>
   ```

2. Enable the image module in a local or temporary config.
3. Add `images.image-provider.example` to `modules.image.ikun.allowed_image_url_hosts`.
4. Run `image_generate`.
5. Confirm an image artifact is created and persisted locally.
6. Run `image_edit` using the generated artifact id.
7. Confirm the edited image artifact is created and persisted locally.
8. Record only artifact ids, hashes, file sizes, and local result paths.

## Follow-Up Test Coverage

Add or extend tests for:

- URL provider outputs where the image host differs from the API host.
- Image downloads that require a normal `User-Agent`.
- Error mapping that reports HTTP status class without leaking signed URLs.
- Config guidance that prevents users from putting `/v1/images` into
  `IMAGE_API_BASE_URL`.
