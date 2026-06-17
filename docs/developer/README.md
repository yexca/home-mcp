# Developer Documents

This directory is the current developer-facing documentation for `home_mcp_gateway`. It describes the implementation as it exists in the source tree, not the historical phase plans.

## Index

- [Architecture](architecture.md): runtime layers, request flow, storage, and protocols.
- [Configuration](configuration.md): config load rules, environment variables, agent fragments, and policies.
- [Deployment](deployment.md): Docker Compose, health checks, and artifact URL behavior.
- [Tool Contracts](tool-contracts.md): built-in and module tool schemas, responses, and errors.
- [Module Development](module-development.md): how to add or modify a module without changing transport code.
- [Testing And Release](testing-and-release.md): regression tests, manual checks, and release gates.

## Source Map

- `app/`: application composition and settings loading.
- `transport/`: HTTP, SSE, JSON-RPC, artifact download, and request context.
- `tools/`: tool registry, schema validation, result shape, dispatch, and helper scripts.
- `core/`: SQLite migrations, jobs, artifacts, policy, audit, IDs, limits, and errors.
- `modules/`: optional capability modules and provider adapters.
- `config/config.main.yaml`: application baseline config.
- `config/comfyui/`: workflow JSON examples.
- `config/agent/`: generated per-agent config fragments.
- `.env.example`: user-facing environment template.
- `tests/`: test suite, test configs, and test runner.

## Current Capability Modules

| Module | Tools | Default state | Provider |
| --- | --- | --- | --- |
| `image` | `image_generate`, `image_edit` | disabled | OpenAI-compatible image API |
| `localimage` | `localimage_generate` | disabled | ComfyUI |
| `tts` | `tts_synthesize` | disabled | local HTTP TTS or mock provider |
| `matrix` | `matrix_send_text`, `matrix_send_audio`, `matrix_send_image` | disabled | Matrix Client/Media HTTP APIs |
| `printer` | `printer_print_file` | disabled | local HTTP printer bridge |

The gateway also always registers `health_check`, `artifact_get`, `artifact_get_image`, and `job_status`.

## Developer Quick Start

```powershell
Copy-Item .env.example .env
python -m pip install -e .
python -m app.main
```

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
