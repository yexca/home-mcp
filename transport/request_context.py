from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.config import Settings
from core.artifacts import ArtifactStore
from core.audit import AuditLogger
from core.jobs import JobManager
from core.limits import InMemoryRateLimiter
from core.policy import CallerIdentity, PolicyEngine


@dataclass(slots=True)
class CoreServices:
    config: Settings
    artifacts: ArtifactStore
    jobs: JobManager
    policy: PolicyEngine
    audit: AuditLogger
    limits: InMemoryRateLimiter

    def close(self) -> None:
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
    metadata: dict[str, Any] | None = None
