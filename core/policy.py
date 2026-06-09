from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from core.errors import GatewayError, POLICY_DENIED


@dataclass(frozen=True, slots=True)
class CallerIdentity:
    caller_id: str
    role: str = "anonymous"
    shared_artifact_read: bool = False

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    action: str
    reason: str
    matched_rules: tuple[str, ...] = ()

    @property
    def allowed(self) -> bool:
        return self.action == "allow"


class PolicyEngine:
    def __init__(self, settings: Any):
        self.settings = settings

    def resolve_caller(
        self,
        authorization: str | None = None,
        metadata: dict[str, Any] | None = None,
        remote_addr: str | None = None,
    ) -> CallerIdentity:
        token = None
        if authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        if token:
            for caller_id, spec in self.settings.callers.items():
                expected = os.getenv(spec.get("token_env", ""))
                if expected and token == expected:
                    return CallerIdentity(
                        caller_id=caller_id,
                        role=spec.get("role", "role_play"),
                        shared_artifact_read=bool(spec.get("shared_artifact_read", False)),
                    )
        if metadata and metadata.get("caller") in self.settings.callers:
            spec = self.settings.callers[metadata["caller"]]
            return CallerIdentity(
                caller_id=metadata["caller"],
                role=spec.get("role", "role_play"),
                shared_artifact_read=bool(spec.get("shared_artifact_read", False)),
            )
        return CallerIdentity("anonymous", role="anonymous", shared_artifact_read=False)

    def evaluate(
        self,
        *,
        caller: CallerIdentity,
        tool_name: str,
        risk_level: str,
        arguments: dict[str, Any],
    ) -> PolicyDecision:
        anonymous_allowed = set(self.settings.policy.get("anonymous_allowed_tools", []))
        if caller.caller_id == "anonymous" and tool_name not in anonymous_allowed:
            return PolicyDecision("deny", "anonymous caller is not allowed for this tool", ("anonymous",))
        if tool_name == "health_check":
            return PolicyDecision("allow", "health checks are always allowed", ("health_check",))
        if caller.is_admin:
            return PolicyDecision("allow", "admin caller", ("admin",))
        if tool_name in {"job_status", "artifact_get"}:
            return PolicyDecision("allow", "ownership is checked by the backing store", ("own_or_grant",))
        if risk_level == "high":
            return PolicyDecision("deny", "high risk tools require explicit allowlist", ("high_risk_default_deny",))
        default_allow = bool(self.settings.policy.get("default_allow", False))
        action = "allow" if default_allow else "deny"
        reason = "default allow" if default_allow else "default deny"
        return PolicyDecision(action, reason, ("default",))

    def require_allowed(self, decision: PolicyDecision) -> None:
        if not decision.allowed:
            raise GatewayError(POLICY_DENIED, decision.reason, retryable=False)
