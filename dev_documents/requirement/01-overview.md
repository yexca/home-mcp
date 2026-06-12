# 01. Overview

## Background

The plan is to run one host ZeroClaw instance as the primary assistant and run multiple role play ZeroClaw instances in Docker. All ZeroClaw instances need access to shared capabilities such as image generation, speech synthesis, Matrix message sending, and local printers.

If each ZeroClaw container stores its own secrets and starts its own tool processes, deployment becomes repetitive, permissions spread across containers, logs are scattered, and state becomes inconsistent. The first version therefore uses a centralized MCP Gateway.

## Product Goals

- Provide a unified MCP tool entrypoint for multiple ZeroClaw instances.
- Support SSE transport for long-running tasks, progress events, and tool result delivery.
- Support both Docker deployment and direct host execution.
- Encapsulate external service adapters and local system capabilities inside the Gateway.
- Keep the implementation modular so future capabilities/skills can be added easily.
- Manage images, audio files, print files, and other outputs through a unified artifact store.

## Users And Runtime Actors

- Host ZeroClaw: The local assistant directly used by the user. It may have relatively higher trust.
- Role play ZeroClaw: Role instances running in Docker. Their permissions should be more constrained.
- MCP Gateway: The tool execution boundary. It owns secrets and system resource permissions.
- External/local services: Third-party OpenAI image2-compatible/proxy image API, local TTS, Matrix homeserver, and printer system.

## Key Scenarios

### Scenario 1: Image Generation

ZeroClaw calls `image_generate`. The Gateway calls a third-party OpenAI image2-compatible/proxy API through the image provider, saves the image to artifacts, and returns image artifact metadata.

### Scenario 2: TTS And Matrix Voice Sending

ZeroClaw first calls `tts_synthesize` to generate an audio artifact, then calls `matrix_send_audio` to send it to a target room. The two tools remain decoupled, and ZeroClaw composes the workflow.

### Scenario 3: Local Printing

ZeroClaw calls `printer_list` to list printers and calls `printer_print_file` to print an artifact or an allowlisted file. Printing requires approval, allowlists, and audit records.

## Non-Functional Goals

- High cohesion: Each module owns one domain capability.
- Low coupling: Modules communicate through artifacts, configuration, events, and interfaces instead of implementation details.
- Observability: Every tool call records logs, duration, result, and error code.
- Cost control: Paid tools such as third-party image APIs can limit concurrency, request frequency, and maximum output size.
- Recoverability: Long-running tasks use a job/artifact model so interrupted requests do not lose outputs.

