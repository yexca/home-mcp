# Developer Documents

This directory is the current developer-facing documentation for
`home_mcp_gateway`. It describes the implementation as it exists in the source
tree, not the historical phase plans.

## Index

- [Architecture](architecture.md): runtime layers, request flow, storage, and protocols.
- [Configuration](configuration.md): config merge rules, module settings, secrets, and policies.
- [Tool Contracts](tool-contracts.md): built-in and module tool schemas, responses, and errors.
- [Module Development](module-development.md): how to add or modify a module without changing transport code.
- [Testing And Release](testing-and-release.md): regression tests, manual checks, and release gates.

## Source Map

- `app/`: application composition and settings loading.
- `transport/`: HTTP, SSE, JSON-RPC, artifact download, and request context.
- `tools/`: tool registry, schema validation, result shape, and dispatch.
- `core/`: SQLite migrations, jobs, artifacts, policy, audit, IDs, limits, and errors.
- `modules/`: optional capability modules and provider adapters.
- `config/`, `.env.example`: runtime config template/user config and
  environment template.
- `tests/`: test suite, test configs, and test runner.
- `deploy/`: Docker image and deployment notes.
- `tests/`: contract, policy, artifact, provider, module, and transport tests.

## Current Capability Modules

| Module | Tools | Default state | Provider |
| --- | --- | --- | --- |
| `image` | `image_generate`, `image_edit` | disabled | iKun/OpenAI-compatible image API |
| `tts` | `tts_synthesize` | disabled | local HTTP TTS or mock provider |
| `matrix` | `matrix_send_text`, `matrix_send_audio`, `matrix_send_image` | disabled | Matrix Client/Media HTTP APIs |
| `printer` | `printer_list`, `printer_print_file` | disabled | local HTTP printer bridge |

The gateway also always registers `health_check`, `artifact_get`, and
`job_status`.

## Developer Quick Start

```powershell
python -m pip install -e .
Copy-Item config/config.example.yaml config/config.yaml
Copy-Item .env.example .env
python -m app.main
```

`tests/config/test.config.yaml` is reserved for the test runner. The recommended
local runtime config is `config/config.yaml`, created from the example
template. When `CONFIG_PATH` is not set, the application auto-loads that file
if it exists.

For Docker Compose, use the same `config/config.yaml`, edit local tokens in
`.env`, and run `docker compose up --build`.

Run tests:

```powershell
.\tests\run_tests.ps1
```

List tools using the simple HTTP compatibility shape:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8787/mcp `
  -ContentType "application/json" `
  -Body '{"method":"tools/list"}'
```
