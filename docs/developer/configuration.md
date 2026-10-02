# Configuration

Management configuration is persisted in SQLite. YAML provides bootstrap defaults and legacy import input.

Load order:

1. Load `CONFIG_PATH` when it is set, then fill missing keys from `config/config.main.yaml`.
2. Otherwise load `config/config.main.yaml`.
3. If `config/config.yaml` exists, deep-merge it over the baseline.
4. If the selected database has `management_config`, load its saved settings, filling new defaults from the bootstrap config. Otherwise merge legacy agent YAML fragments.
5. Substitute `${NAME}` placeholders from the process environment for advanced test/development use.
6. Validate required sections and enabled modules.
7. On the first `build_services`, save imported management settings and agent fragments to SQLite. Import a legacy remote image provider/model with an `image` tag. Resolve a selected image model's provider credentials before registering tools.

YAML files remain useful for bootstrap configuration and isolated test databases:

| File | Purpose |
| --- | --- |
| `config/config.yaml` | Local runtime config, module switches, provider settings, and host caller tokens. |
| `config/agent/config.agent.<name>.yaml` | Per-agent caller token, Matrix token, and high-risk tool grants. |
| `config/config.main.yaml` | Committed baseline structure and defaults. |
| `tests/config/*.yaml` | Test-only configs. |

`CONFIG_PATH` is retained for tests and advanced development.

## Callers And Tokens

Caller tokens can be configured directly in YAML:

```yaml
callers:
  host_assistant:
    role: admin
    token: change-this
    shared_artifact_read: true
  role_default:
    role: role_play
    token: change-this-role
    shared_artifact_read: false
```

`token_env` is still accepted for older test fixtures and advanced setups, but new user config should use `token`.

## Artifacts

```yaml
artifacts:
  root: ./artifacts
  public_base_url: http://127.0.0.1:8787/artifacts
  signed_url_secret: change-this-secret
  signed_url_ttl_seconds: 300
```

If `signed_url_secret` is absent, the legacy `signed_url_secret_env` fallback is still supported.

## Agents

Enable agents in `config/config.yaml`:

```yaml
agents:
  enabled:
    - agent1
  config_dir: config/agent
```

An agent fragment looks like:

```yaml
caller:
  role: role_play
  token: change-this-agent-token
  shared_artifact_read: false

matrix:
  enabled: true
  account: agent1
  access_token: change-this-matrix-token

high_risk_tools:
  - matrix_send_text
  - matrix_send_image
  - matrix_send_audio
```

The loader turns this into `callers.<name>`, `policy.high_risk_allowed_callers.<name>`, `modules.matrix.caller_accounts.<name>`, and `modules.matrix.accounts.<name>`.

## WebUI

`HOME_MCP_LOGIN_KEY` supplies the management login key; `HOME_MCP_DEV_MODE=true` bypasses management authentication for development. Neither setting is persisted. MCP caller identity still uses caller tokens. The management key is checked with a constant-time comparison; management API responses use `Cache-Control: no-store` and reject cross-origin browser requests.

The WebUI saves configuration and agent fragments to `management_config`, and providers/models to `llm_providers` / `llm_models`. Management writes use a separate SQLite connection and serialized transactions. Restart after module switch or agent changes so the registered MCP tool set is rebuilt.

Health/readiness module flags reflect the tool set enabled at startup. The admin status API exposes saved switches as `configured_modules` and reports `restart_required` when they differ from runtime switches. Remote image model/credential updates preserve the runtime enabled flag until restart, avoiding an enabled health report with unregistered tools.

Providers expose an OpenAI-compatible `GET /v1/models` endpoint. Model tags are explicitly assigned (`text`, `image`); tags do not imply automatic provider capability detection. `modules.image.model_id` selects a persisted model tagged `image`. Provider keys are never returned by management APIs. Legacy provider URL/model/key settings are imported once and removed from the saved management document. Existing remote image tools pick up new selections immediately; deletion or untagging of the selected model is rejected.

## Modules

Module provider settings live under `modules.*` in YAML. Provider secrets such as image API keys, TTS API keys, Matrix access tokens, and printer bridge API keys are configuration values, never tool arguments.
