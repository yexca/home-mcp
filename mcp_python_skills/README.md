# MCP Python Skills For ZeroClaw

This directory contains Python-backed ZeroClaw skills for docker_new_6.

Each immediate child directory is a self-contained skill package. Keep this
layout because ZeroClaw can load the package after copying the whole directory
to an agent workspace:

```text
mcp_python_skills/
  <skill-name>/
    SKILL.md
    helper_script.py
    test_*.py
```

The skill directory may include lightweight tests beside the runtime files.
`__pycache__/` and other generated files should not be copied or committed.

These skills are versioned with the local MCP gateway contract. When tool
names, payloads, artifact/job behavior, or Matrix policy change in the gateway,
update the affected skill in the same repository.

## mcp-image-send

Path: `mcp_python_skills/mcp-image-send/`

Purpose:

- submit image generation/edit jobs to the local MCP gateway,
- poll `job_status` with a finite `max_wait_seconds`,
- send generated image artifacts through MCP `matrix_send_image`,
- optionally save debug copies into `/zeroclaw-data/workspace/imgs` when `download_copy=true`.

The helper sends Matrix images itself through MCP. It no longer returns Matrix image markers such as `[IMAGE:/zeroclaw-data/workspace/imgs/...png]`, and the LLM should not output a marker after success.

`room_id` is required in the payload unless `MATRIX_DEFAULT_ROOM_ID` is set in the agent environment. The room still must be allowlisted by MCP policy.

## Install Into docker_new_6 Agents

ZeroClaw loads skills from each agent workspace under `skills/<skill-name>/`.
Copy the self-contained package into any agent that should use it:

```powershell
Copy-Item -Recurse -Force `
  .\mcp_python_skills\mcp-image-send `
  .\docker_new_6\instances\agent1\workspace\skills\mcp-image-send
```

Repeat for `agent2` or `agent3` if needed.

If you want to avoid copying tests into the runtime workspace, copy only
`SKILL.md` and `mcp_image_send.py`. Keeping the tests in the source package is
still useful because they document the expected MCP call sequence.

The helper expects these docker_new_6 defaults:

- `MCP_URL=http://host.docker.internal:8787/mcp`
- `MCP_GATEWAY_TOKEN` set in the agent environment
- `MATRIX_DEFAULT_ROOM_ID` optional fallback room
- `ZEROCLAW_AGENT_WORKSPACE=/zeroclaw-data/workspace`

Each agent should use its own `MCP_GATEWAY_TOKEN`. MCP resolves the caller from that token and selects the configured Matrix account/access token on the server side. Skills and LLMs should not read, store, or pass Matrix `access_token`, and should not pass `matrix_account`.

Note: the current docker_new_6 agent image should be checked for `python3`. If it is missing, install Python in the agent runtime image before using this skill.
