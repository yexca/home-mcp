# 03. Modules And Skill Extension Model

## Module Definition

In this project, a module is a high-cohesion capability/skill package. It includes:

- Module configuration schema.
- Input and output schemas.
- External service interface.
- One or more provider adapters.
- MCP tool registration function.
- Module-level tests.

Modules do not depend on each other's implementation details. Shared files go through the artifact store. Approval decisions go through the policy engine. External services are accessed through provider adapters.

## Module Interface Convention

Each module should expose:

```text
ModuleManifest
  name
  version
  description
  tools
  required_config
  required_secrets
  risk_level

register_tools(registry)
health_check()
```

Each tool handler should follow:

```text
handle(input, context) -> ToolResult
```

The `context` contains:

- Caller identity: which ZeroClaw instance made the call.
- Request id.
- Artifact store.
- Job manager.
- Policy engine.
- Audit logger.
- Config/secrets reader.

## Adding A New Skill

1. Create `modules/<skill_name>/`.
2. Define input and output schemas.
3. Implement the service interface.
4. Implement provider adapters.
5. Register MCP tools inside the module.
6. Add module configuration.
7. Add unit tests and minimal integration tests.
8. Document tool names, risk level, and auto-approval recommendation.

## Module Boundaries

### image module

Responsibilities:

- Image generation.
- Image editing.
- Call third-party OpenAI image2-compatible/proxy APIs.
- Keep the provider adapter flexible enough to switch to official OpenAI, other image services, or local services later.
- Write images to the artifact store.
- Return artifact metadata.

Not responsible for:

- Sending images through Matrix.
- Long-term archive policy.
- UI display.
- Exposing vendor-specific implementation details in MCP tool schemas.

### tts module

Responsibilities:

- Text-to-speech synthesis.
- Support parameters such as voice, format, and speed.
- Call local or remote TTS providers.
- Write audio files to the artifact store.

Not responsible for:

- Matrix sending.
- Chat logic beyond audio message format preparation.

### matrix module

Responsibilities:

- Send text messages.
- Send audio artifacts.
- Optionally send image artifacts.
- Manage Matrix room allowlists.

Not responsible for:

- Generating audio.
- Generating images.
- Deciding message content.

### printer module

Responsibilities:

- List printers.
- Query print job status.
- Print artifacts or files inside allowlisted directories.
- Perform basic format conversion.

Not responsible for:

- Downloading arbitrary files from the internet.
- Parsing untrusted complex documents.
- Bypassing system printer permissions.

## Module Communication

Recommended communication objects:

- Artifact id.
- Job id.
- Typed config.
- Typed result.
- Domain event.

Discouraged communication objects:

- Direct imports of another module's service implementation.
- Arbitrary raw file system paths.
- Shared mutable global state.
- Large base64 payloads in tool responses.

