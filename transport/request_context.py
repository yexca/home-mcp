from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from app.config import Settings
from core.artifacts import ArtifactStore
from core.audit import AuditLogger
from core.jobs import JobManager
from core.limits import InMemoryRateLimiter
from core.policy import CallerIdentity, PolicyEngine
from core.management import ManagementStore
from core.llm import LLMStore
from tools.registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class RuntimeSnapshot:
    config: Settings
    artifacts: ArtifactStore
    policy: PolicyEngine
    audit: AuditLogger
    registry: ToolRegistry


@dataclass(slots=True)
class CoreServices:
    config: Settings
    artifacts: ArtifactStore
    jobs: JobManager
    policy: PolicyEngine
    audit: AuditLogger
    limits: InMemoryRateLimiter
    management: ManagementStore | None = None
    llm: LLMStore | None = None
    registry: ToolRegistry | None = None
    runtime_lock: Any = field(default_factory=RLock)
    on_tools_changed: Any = None

    def snapshot(self, registry: ToolRegistry | None = None) -> RuntimeSnapshot:
        with self.runtime_lock:
            return RuntimeSnapshot(self.config, self.artifacts, self.policy, self.audit, (registry or self.registry).copy())

    def prepare_runtime(self, settings: Settings) -> RuntimeSnapshot:
        from modules.loader import register_configured_module_tools
        from tools.builtin import register_builtin_tools
        registry = ToolRegistry()
        register_builtin_tools(registry)
        register_configured_module_tools(registry, settings)
        audit = AuditLogger(self.audit.conn, settings)
        audit._started_perf = self.audit._started_perf
        return RuntimeSnapshot(settings, ArtifactStore(self.artifacts.conn, settings), PolicyEngine(settings), audit, registry)

    def apply_runtime(self, snapshot: RuntimeSnapshot) -> None:
        with self.runtime_lock:
            changed = self.registry is not None and self.registry.list_tools() != snapshot.registry.list_tools()
            self.config, self.artifacts, self.policy, self.audit = snapshot.config, snapshot.artifacts, snapshot.policy, snapshot.audit
            if self.registry is not None:
                self.registry.replace(snapshot.registry)
            else:
                self.registry = snapshot.registry
        if changed and self.on_tools_changed is not None:
            self.on_tools_changed()

    def list_tools(self, registry: ToolRegistry) -> list[dict[str, Any]]:
        with self.runtime_lock:
            return registry.list_tools()

    def close(self) -> None:
        if self.management is not None:
            self.management.conn.close()
        if self.jobs.conn is not self.artifacts.conn:
            self.jobs.conn.close()
        self.artifacts.conn.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass


@dataclass(slots=True)
class RequestContext:
    request_id: str
    caller: CallerIdentity
    config: Settings
    artifacts: ArtifactStore
    jobs: JobManager
    policy: PolicyEngine
    audit: AuditLogger
    limits: InMemoryRateLimiter
    job_id: str | None = None
    audit_id: str | None = None
    policy_decision: str | None = None
    metadata: dict[str, Any] | None = None
