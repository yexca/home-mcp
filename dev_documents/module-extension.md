# Module Extension Notes

## Required Layout

Each runtime module lives under `modules/<name>/` and should include:

```text
modules/<name>/
  __init__.py
  manifest.py
  schemas.py
  service.py
  providers/
    __init__.py
tests/
  test_<name>.py
```

`manifest.py` is the only module entry point used by application startup. It must expose:

```python
def register_tools(registry, settings) -> None:
    ...
```

The function should return without registering tools when `settings.modules["<name>"].enabled` is false.

## Extension Rules

- Adding a module must not require changes in `transport/`.
- Adding a module should not require changes in `app/main.py`; application startup discovers enabled module manifests.
- Tool schemas are the external MCP contract. Provider details such as `api_key`, `token`, `base_url`, local paths, and system paths must stay out of schemas.
- Provider response formats must be normalized inside `modules/<name>/providers/` or `service.py`.
- Cross-module workflows should be composed by ZeroClaw or a higher orchestration layer, not by direct imports between modules.
- Slow or side-effecting tools should set `creates_job=True` and must produce audit records through the dispatcher.

## Provider Rules

Providers are selected from configuration and created inside module service code. Adding a provider may add internal adapter code and config validation, but it must not change existing MCP tool names or schemas unless the contract is intentionally versioned.

For image providers, `image_generate` and `image_edit` continue to return artifact metadata only. New providers must normalize their outputs into the same internal response shape and must support persisted artifacts rather than returning provider URLs, base64 strings, or binary payloads to MCP callers.
