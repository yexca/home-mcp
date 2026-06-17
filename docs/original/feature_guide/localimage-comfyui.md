# Local Image Feature Guide

## Purpose

This guide defines the local image generation feature for the MCP gateway when the actual image engine runs on a separate machine with ComfyUI.

Example network target:

- Hostname: `comfyui-workstation.example`
- IP: `192.0.2.10`
- ComfyUI API: `http://192.0.2.10:8188`

Connectivity should be verified from the gateway workspace:

- `GET /system_stats` returned `200`
- `GET /object_info` returned `200`

## Naming

Use two separate capability modules:

- `remoteimage` for remote/provider-backed image generation
- `localimage` for ComfyUI-backed local image generation

Do not use `image_local` as the primary module name. `localimage` reads more naturally in tool names and keeps the capability grouped by deployment model.

Recommended MCP tool names:

- `local_image_generate`
- `local_image_edit`

## Architectural Choice

Keep `localimage` as a separate module instead of adding ComfyUI as another provider inside the existing remote image module.

Why:

- The two paths have different operational shapes.
- Remote image generation is provider API driven.
- Local image generation is workflow driven and depends on ComfyUI node mapping.
- A separate module keeps the contract clean and makes future maintenance easier.

Suggested call chain:

```text
LLM -> MCP tool -> localimage module -> ComfyUI HTTP API -> artifact store
```

## Module Responsibilities

`localimage` should own:

- MCP tool registration
- prompt and size validation
- ComfyUI workflow loading
- node parameter injection
- job tracking and timeout handling
- artifact persistence
- response normalization

`localimage` should not expose:

- raw ComfyUI workflow internals in the MCP schema
- arbitrary local file paths
- provider-specific node IDs to the caller
- direct image bytes in tool responses

## ComfyUI Integration Model

Use ComfyUI as an HTTP backend and treat the workflow JSON as configuration.

Typical sequence:

1. Load a workflow template.
2. Inject prompt, negative prompt, width, height, seed, steps, sampler, and similar values.
3. `POST /prompt` to start generation.
4. Poll `GET /history/{prompt_id}` until output is ready.
5. Fetch the resulting image through `GET /view`.
6. Save the bytes as a local artifact.
7. Return artifact metadata to the MCP caller.

## Recommended Tool Contract

Keep the first version semantic and small:

```json
{
  "prompt": "string",
  "negative_prompt": "string optional",
  "size": "1024x1024 | 1024x1536 | 1536x1024 | 1280x720 | 720x1280",
  "quality": "draft | standard | high",
  "style": "default | anime | realistic | illustration optional",
  "seed": "integer optional",
  "output_format": "png | jpeg | webp"
}
```

Suggested mapping:

- `size` -> `width` + `height`
- `quality` -> workflow preset for steps / cfg / sampler
- `style` -> workflow preset or LoRA selection
- `seed` omitted -> random seed

Do not expose raw ComfyUI-specific fields in the external MCP schema unless there is a strong reason.

## Configuration Guidance

Example config shape:

```yaml
modules:
  localimage:
    enabled: true
    provider: comfyui
    default_size: 1024x1024
    default_quality: standard
    total_timeout_seconds: 900
    comfyui:
      base_url: http://192.0.2.10:8188
      workflow_path: ./config/comfyui/sdxl_text_to_image.example.json
      timeout_seconds: 30
      poll_interval_seconds: 1
      max_wait_seconds: 900
```

Prefer IP-based access first. Hostname access can be kept as a convenience later, but the IP is the clearer operational default.

## Security And Policy Notes

- Keep the ComfyUI base URL in configuration, not in tool arguments.
- Allowlist the ComfyUI host explicitly.
- Do not permit arbitrary provider URLs from MCP calls.
- Persist outputs locally before returning results.
- Use the same artifact and audit rules as the rest of the gateway.

## MVP Scope

Phase 1 should focus on text-to-image only.

Later additions can include:

- image-to-image
- inpaint / edit
- upscaling
- model or LoRA preset selection
- multiple workflow templates

## Acceptance Criteria

The `localimage` feature is ready when:

- the gateway can reach `http://192.0.2.10:8188`
- generation completes through ComfyUI
- output is saved as an image artifact
- tool responses contain artifact metadata only
- the caller never sees workflow internals or provider secrets
