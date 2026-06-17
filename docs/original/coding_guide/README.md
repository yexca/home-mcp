# MCP Gateway Coding Guide

This directory contains the implementation guide for `home_mcp_gateway`. It follows the requirement, high-level design, and detailed design documents under:

- `dev_documents/requirement/`
- `dev_documents/high_design/`
- `dev_documents/detail_design/`

The goal is to keep the development plan executable while avoiding encoding issues in the actual implementation workflow. All documents in this directory are written in English and use the same phase structure that was already established.

## Document Index

- [01-development-phases.md](01-development-phases.md): Development phases, tasks, exit criteria, and deliverables.
- [02-coding-rules.md](02-coding-rules.md): Code structure, module boundaries, tool contracts, security rules, and configuration rules.
- [03-test-and-acceptance.md](03-test-and-acceptance.md): Test layers, phase acceptance checks, regression gates, and manual test requirements.
- [04-integration-playbook.md](04-integration-playbook.md): ZeroClaw, iKun, Docker, artifact download, and integration notes.

## Implementation Order

The first version should be built in this order:

1. Phase 0: Project skeleton and technical validation.
2. Phase 1: Gateway core infrastructure.
3. Phase 2: iKun `image_generate`.
4. Phase 3: iKun `image_edit`.
5. Phase 4: TTS and Matrix audio workflow.
6. Phase 5: Printer module.
7. Phase 6: Module extension rules and release hardening.

Phase 0 to Phase 3 form the minimum useful MVP path: ZeroClaw can connect to the Gateway, the Gateway can create jobs, write artifacts, audit calls, and generate/edit images through iKun.

## Development Principles

- Keep the external contract stable. MCP tool schemas must not expose provider `base_url`, API keys, Matrix tokens, printer system paths, or local absolute paths.
- Keep responsibilities separated. `transport` handles protocol details, `tools` handles schemas and dispatch, application code orchestrates use cases, modules handle domain logic, and provider adapters handle external APIs.
- Persist file outputs. Images, audio files, documents, and print files must be stored as artifacts. MCP responses should return metadata and download URLs, not large binary payloads.
- Recheck high-risk actions in the Gateway. Gateway policy is required even if ZeroClaw uses auto approve.
- Never copy secrets into source code, config examples, logs, responses, audit summaries, or documentation. `dev_documents/ikun/key.txt` is only a local reference and must not be copied into development artifacts.
