# Changelog

## v0.2.0 - Matrix agent configuration

- Added Matrix caller/account mapping for multi-agent sender tokens.
- Added a helper script to register Matrix-capable agents without committing secrets.
- Allowed empty Matrix room allowlists to mean all rooms are permitted.
- Updated Docker Compose image tagging to `yexca/home-mcp-gateway:0.2.0`.
- Updated runtime version metadata and image download User-Agent to `0.2.0`.

## v0.1.0 - MVP

- Added dynamic module manifest discovery for enabled modules.
- Added a provider factory entry point for image providers while keeping `image_generate` and `image_edit` schemas stable.
- Added Phase 6 regression coverage for dummy module extension.
- Added Dockerfile, Docker Compose, health checks, volume mounts, and compose runtime config.
- Added module extension notes and release hardening checklist.
