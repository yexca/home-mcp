# Configuration

Configuration is YAML-first.

Load order:

1. Load `CONFIG_PATH` when it is set, then fill missing keys from `config/config.main.yaml`.
2. Otherwise load `config/config.main.yaml`.
3. If `config/config.yaml` exists, deep-merge it over the baseline.
4. If `agents.enabled` is present, merge enabled `config/agent/config.agent.<name>.yaml` fragments.
5. Substitute `${NAME}` placeholders from the process environment for advanced test/development use.
6. Validate required sections and enabled modules.

Normal local use should edit only ignored YAML files:

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

The WebUI saves directly to `config/config.yaml` and `config/agent/*.yaml`. Restart the service after module switch or agent changes so the registered MCP tool set is rebuilt.

## Modules

Module provider settings live under `modules.*` in YAML. Provider secrets such as image API keys, TTS API keys, Matrix access tokens, and printer bridge API keys are configuration values, never tool arguments.
