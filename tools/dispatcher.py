from __future__ import annotations

import logging
from typing import Any

from core.errors import GatewayError, internal_error
from core.ids import new_request_id
from tools.registry import ToolRegistry, call_handler
from tools.result import failure
from tools.validation import validate_arguments
from transport.request_context import CoreServices, RequestContext

logger = logging.getLogger(__name__)


class ToolDispatcher:
    def __init__(self, registry: ToolRegistry, services: CoreServices):
        self.registry = registry
        self.services = services

    async def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        *,
        authorization: str | None = None,
        metadata: dict[str, Any] | None = None,
        remote_addr: str | None = None,
    ) -> dict[str, Any]:
        request_id = new_request_id()
        job_id: str | None = None
        audit_id: str | None = None
        policy_decision = "not_evaluated"
        arguments = arguments or {}
        try:
            definition = self.registry.get(tool_name)
            validated = validate_arguments(definition.input_schema, arguments)
            caller = self.services.policy.resolve_caller(authorization, metadata, remote_addr)
            input_summary = self.services.audit.summarize_input(validated)
            if definition.creates_job:
                job = self.services.jobs.create(
                    request_id=request_id,
                    caller_id=caller.caller_id,
                    tool_name=tool_name,
                    input_summary=input_summary,
                )
                job_id = job.id
                self.services.jobs.mark_running(job_id)
            audit_id = self.services.audit.start(
                request_id=request_id,
                job_id=job_id,
                caller_id=caller.caller_id,
                tool_name=tool_name,
                risk_level=definition.risk_level,
                arguments=validated,
            )
            decision = self.services.policy.evaluate(
                caller=caller,
                tool_name=tool_name,
                risk_level=definition.risk_level,
                arguments=validated,
            )
            policy_decision = decision.action
            self.services.policy.require_allowed(decision)
            ctx = RequestContext(
                request_id=request_id,
                caller=caller,
                config=self.services.config,
                artifacts=self.services.artifacts,
                jobs=self.services.jobs,
                policy=self.services.policy,
                audit=self.services.audit,
                limits=self.services.limits,
                job_id=job_id,
                metadata=metadata or {},
            )
            result = await call_handler(definition.handler, validated, ctx)
            artifact_ids = _extract_artifact_ids(result)
            if job_id:
                self.services.jobs.mark_succeeded(job_id, result, artifact_ids)
                result.setdefault("job_id", job_id)
            self.services.audit.finish(
                audit_id=audit_id,
                policy_decision=policy_decision,
                status="succeeded",
                artifact_ids=artifact_ids,
            )
            return result
        except GatewayError as exc:
            if job_id:
                self.services.jobs.mark_failed(job_id, exc.code, exc.message)
            if audit_id:
                self.services.audit.finish(
                    audit_id=audit_id,
                    policy_decision=policy_decision,
                    status="failed",
                    error_code=exc.code,
                    error_message=exc.message,
                )
            return failure(request_id=request_id, error=exc, job_id=job_id)
        except Exception:
            # Keep tracebacks out of tool responses; application logs can capture this.
            logger.debug(
                "unhandled tool error",
                extra={"tool_name": tool_name, "request_id": request_id},
                exc_info=True,
            )
            exc = internal_error()
            if job_id:
                self.services.jobs.mark_failed(job_id, exc.code, exc.message)
            if audit_id:
                self.services.audit.finish(
                    audit_id=audit_id,
                    policy_decision=policy_decision,
                    status="failed",
                    error_code=exc.code,
                    error_message=exc.message,
                )
            return failure(request_id=request_id, error=exc, job_id=job_id)


def _extract_artifact_ids(result: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    artifact = result.get("artifact")
    if isinstance(artifact, dict) and isinstance(artifact.get("id"), str):
        ids.append(artifact["id"])
    artifacts = result.get("artifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                ids.append(item["id"])
    return ids
