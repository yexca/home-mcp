# Release Checklist

## Regression Gate

- Run `.\env\run_tests.ps1`.
- Verify contract tests cover `tools/list`, success results, failure results, and stable error codes.
- Verify artifact integration tests cover owner, grant, expired, and forbidden reads.
- Verify provider mock tests cover URL and base64 image outputs.
- Verify policy tests cover Matrix rooms, printer allowlists, and high-risk actions.

## Security Gate

- Search the repository for real `IMAGE_API_KEY`, `MATRIX_ACCESS_TOKEN`, `PRINTER_BRIDGE_API_KEY`, and caller tokens.
- Confirm `dev_documents/ikun/key.txt` was not copied into source, config, fixtures, logs, or documentation.
- Confirm schemas do not expose `api_key`, `token`, `base_url`, `authorization`, `access_token`, or local path fields.
- Confirm MCP responses and audit rows do not contain provider tokens, Authorization headers, provider URLs with query strings, stack traces, or sensitive absolute paths.
- Confirm artifact reads are scoped to owner, grants, or configured admin access.

## Deployment Gate

- Build the image with `docker compose build`.
- Start with `docker compose up` and check `http://127.0.0.1:8787/healthz`.
- Check `http://127.0.0.1:8787/readyz` for enabled module state and no secrets.
- Connect ZeroClaw from the host with `http://127.0.0.1:8787/mcp`.
- For same-compose-network clients, use `http://home-mcp:8787/mcp`.
- Keep only low-risk tools in any default auto approve list.

## Manual Smoke Tests

- Run one iKun image generation with a local token and record only `request_id`, `job_id`, and `artifact_id`.
- Run one TTS to Matrix workflow against an allowlisted room when Matrix credentials are locally configured.
- Run one printer bridge test against an allowlisted test printer when the bridge is available.
