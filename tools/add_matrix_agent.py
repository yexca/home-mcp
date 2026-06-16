from __future__ import annotations

import argparse
import secrets
import shutil
from pathlib import Path
from typing import Any

import yaml

MATRIX_TOOLS = ["matrix_send_text", "matrix_send_audio", "matrix_send_image"]


def main() -> None:
    args = _parse_args()
    agent_id = _validate_agent_id(args.agent_id)
    gateway_token_env = args.gateway_token_env or _env_name(agent_id, "GATEWAY_TOKEN_", "")
    matrix_token_env = args.matrix_token_env or _env_name(agent_id, "", "_MATRIX_ACCESS_TOKEN")
    gateway_token = args.gateway_token or secrets.token_urlsafe(32)
    matrix_access_token = args.matrix_access_token

    config_path = Path(args.config)
    env_path = Path(args.env)
    if not config_path.is_file():
        example_path = Path("config/config.example.yaml")
        if not example_path.is_file():
            raise SystemExit(f"config file not found: {config_path}")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(example_path, config_path)

    config = _read_yaml(config_path)
    _add_agent_to_config(
        config,
        agent_id=agent_id,
        gateway_token_env=gateway_token_env,
        matrix_token_env=matrix_token_env,
        homeserver=args.homeserver,
        allow_all_rooms=args.allow_all_rooms,
    )
    _write_yaml(config_path, config)

    env_updates = {gateway_token_env: gateway_token}
    if matrix_access_token is not None:
        env_updates[matrix_token_env] = matrix_access_token
    else:
        env_updates.setdefault(matrix_token_env, "")
    _upsert_env(env_path, env_updates)

    print(f"Added Matrix agent '{agent_id}'")
    print(f"  caller token env: {gateway_token_env}")
    print(f"  matrix token env: {matrix_token_env}")
    if matrix_access_token is None:
        print(f"  set {matrix_token_env}=... in {env_path} before sending Matrix messages")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add an MCP caller mapped to a Matrix sender account.")
    parser.add_argument("agent_id", help="Caller/account id, for example agent1 or alice_bot.")
    parser.add_argument("--config", default="config/config.yaml", help="YAML config to update.")
    parser.add_argument("--env", default=".env", help="dotenv file to update.")
    parser.add_argument("--gateway-token-env", help="Environment variable name for the MCP Bearer token.")
    parser.add_argument("--gateway-token", help="MCP Bearer token value. Defaults to a generated token.")
    parser.add_argument("--matrix-token-env", help="Environment variable name for the Matrix access token.")
    parser.add_argument("--matrix-access-token", help="Matrix access token value to write into .env.")
    parser.add_argument("--homeserver", help="Optional account-specific Matrix homeserver.")
    parser.add_argument(
        "--allow-all-rooms",
        action="store_true",
        help="Set policy.allowed_matrix_rooms to [] so all rooms are allowed.",
    )
    return parser.parse_args()


def _validate_agent_id(agent_id: str) -> str:
    if not agent_id:
        raise SystemExit("agent_id is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    if any(char not in allowed for char in agent_id):
        raise SystemExit("agent_id may contain only letters, numbers, underscores, and hyphens")
    return agent_id


def _env_name(agent_id: str, prefix: str, suffix: str) -> str:
    normalized = "".join(char if char.isalnum() else "_" for char in agent_id).upper()
    return f"{prefix}{normalized}{suffix}"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh) or {}
    if not isinstance(loaded, dict):
        raise SystemExit(f"configuration root must be an object: {path}")
    return loaded


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        yaml.safe_dump(data, fh, allow_unicode=False, sort_keys=False)


def _add_agent_to_config(
    config: dict[str, Any],
    *,
    agent_id: str,
    gateway_token_env: str,
    matrix_token_env: str,
    homeserver: str | None,
    allow_all_rooms: bool,
) -> None:
    callers = config.setdefault("callers", {})
    callers[agent_id] = {
        "role": "role_play",
        "token_env": gateway_token_env,
        "shared_artifact_read": False,
    }

    policy = config.setdefault("policy", {})
    high_risk = policy.setdefault("high_risk_allowed_callers", {})
    allowed_tools = high_risk.setdefault(agent_id, [])
    for tool_name in MATRIX_TOOLS:
        if tool_name not in allowed_tools:
            allowed_tools.append(tool_name)
    if allow_all_rooms:
        policy["allowed_matrix_rooms"] = []

    matrix = config.setdefault("modules", {}).setdefault("matrix", {})
    matrix["enabled"] = True
    caller_accounts = matrix.setdefault("caller_accounts", {})
    caller_accounts[agent_id] = agent_id
    accounts = matrix.setdefault("accounts", {})
    account_config = accounts.setdefault(agent_id, {})
    if homeserver:
        account_config["homeserver"] = homeserver
    account_config["access_token"] = "${" + matrix_token_env + "}"


def _upsert_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key, _ = line.split("=", 1)
        key = key.strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    missing = [key for key in updates if key not in seen]
    if missing and output and output[-1].strip():
        output.append("")
    for key in missing:
        output.append(f"{key}={updates[key]}")
    path.write_text("\n".join(output) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
