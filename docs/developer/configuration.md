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

The WebUI saves configuration and agent fragments to `management_config`, and providers/models to `llm_providers` / `llm_models`. Management writes use a separate SQLite connection and serialized transactions. Module switches require a restart. Other controls and tool schemas apply immediately on save.

Health/readiness module flags reflect the tool set enabled at startup. The admin status API exposes saved switches as `configured_modules` and reports `restart_required` when they differ from runtime switches. Operational settings and agent policy are applied immediately without changing that startup tool set. Remote image model/credential updates preserve the runtime enabled flag until restart, avoiding an enabled health report with unregistered tools.

Providers expose an OpenAI-compatible `GET /v1/models` endpoint. Model tags are explicitly assigned (`text`, `image`); tags do not imply automatic provider capability detection. `modules.image.model_id` selects a persisted model tagged `image`. Provider keys are never returned by management APIs. Legacy provider URL/model/key settings are imported once and removed from the saved management document. Existing remote image tools pick up new selections immediately; deletion or untagging of the selected model is rejected.

## Modules

### Operational controls in the WebUI

The **Settings** page manages image/TTS/print quotas and counting windows, Matrix room throttling, job concurrency, artifact size/expiry/signing, audit summary length, caller tokens and MCP policy. Module pages expose supported sizes/formats, input limits, image CDN hosts, ComfyUI presets/node mappings, TTS voices/languages/speed and print defaults.

Quota keys retain their legacy `*_per_day` / `*_per_minute` names. Actual windows are `limits.image_rate_window_seconds`, `tts_rate_window_seconds`, `print_rate_window_seconds` (default 86400) and `matrix_rate_window_seconds` (default 60). A fixed window starts at the first request; counters are held in memory and reset on restart. Remote generation, image editing and local generation retain separate per-caller counters with the same image quota/window. Zero quota or concurrency values mean unlimited.

Concurrency admission checks pending/running jobs inside a SQLite write transaction on a dedicated job connection. Image global/per-caller limits include all three image tools; TTS and print have independent global limits. Excess requests return retryable `RATE_LIMITED` without contacting the provider.

Saving applies operational settings, caller/agent policy and updated tool schemas immediately. A prepared runtime snapshot replaces the settings, artifact store, policy, audit settings and registry together under a lock; each dispatched request captures one consistent snapshot. Background jobs keep their original snapshot. The shared rate limiter retains counters and recalculates the current window when its duration changes. Only module enable/disable switches require a restart; the header reports `restart_required` for these pending changes. Blank secret inputs preserve the existing value; APIs return masked secrets only. Invalid numbers, incompatible defaults and malformed workflow presets are rejected before saving.

Image download allowlists include the provider API host and configured CDN hosts. Enter `*` in the host list to allow every hostname, including redirect targets. Empty lists allow only the API host. The same scheme/host checks apply to redirects; HTTP remains controlled separately by `allow_http_image_urls`. Artifact expiry affects new artifacts and does not implement automatic disk cleanup.

Environment-only/bootstrap controls remain outside the WebUI: `HOME_MCP_LOGIN_KEY`, `HOME_MCP_DEV_MODE`, `CONFIG_PATH`, database location/WAL, server bind address/routes and artifact root. Provider driver choices remain fixed by each module. `audit.retention_days` / `log_provider_urls` currently have no implementation; they are intentionally not presented as working controls. The generic sync timeout is only a fallback when a module-specific timeout is missing.

Module provider settings live under `modules.*` in YAML. Provider secrets such as image API keys, TTS API keys, Matrix access tokens, and printer bridge API keys are configuration values, never tool arguments.
