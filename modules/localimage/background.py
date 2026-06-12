from __future__ import annotations

import logging
import queue
import threading
from datetime import timedelta
from typing import Any

from app.config import Settings
from core.artifacts import ArtifactStore
from core.audit import AuditLogger
from core.db import connect_database
from core.errors import GatewayError, PROVIDER_TIMEOUT, internal_error
from core.jobs import JobManager
from core.limits import InMemoryRateLimiter
from core.policy import CallerIdentity, PolicyEngine
from core.time import utc_now
from modules.localimage.providers import create_localimage_provider
from modules.localimage.service import (
    LocalImageDeadline,
    LocalImageGenerationService,
    PreparedLocalImageGenerate,
    prepare_local_image_generate,
)
from tools.result import success
from transport.request_context import CoreServices, RequestContext

logger = logging.getLogger(__name__)

LOCAL_IMAGE_DEADLINE_MESSAGE = "local image job exceeded gateway deadline or was abandoned during restart"


def schedule_local_image_generate_job(
    *,
    settings: Settings,
    request_id: str,
    caller: CallerIdentity,
    job_id: str,
    audit_id: str,
    policy_decision: str,
    prepared: PreparedLocalImageGenerate,
    metadata: dict[str, Any],
) -> None:
    logger.info("local image job created", extra={"request_id": request_id, "job_id": job_id})
    thread = threading.Thread(
        target=_run_local_image_generate_job,
        kwargs={
            "settings": settings,
            "request_id": request_id,
            "caller": caller,
            "job_id": job_id,
            "audit_id": audit_id,
            "policy_decision": policy_decision,
            "prepared": prepared,
            "metadata": metadata,
        },
        name=f"local-image-generate-{job_id}",
        daemon=True,
    )
    thread.start()


async def local_image_generate_background(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    if not ctx.job_id or not ctx.audit_id or not ctx.policy_decision:
        raise internal_error()
    prepared = prepare_local_image_generate(arguments, ctx)
    schedule_local_image_generate_job(
        settings=ctx.config,
        request_id=ctx.request_id,
        caller=ctx.caller,
        job_id=ctx.job_id,
        audit_id=ctx.audit_id,
        policy_decision=ctx.policy_decision,
        prepared=prepared,
        metadata=ctx.metadata or {},
    )
    return success(
        request_id=ctx.request_id,
        status="accepted",
        job_id=ctx.job_id,
        job={"id": ctx.job_id, "status": "running", "progress": 0},
    )


def reconcile_stale_localimage_jobs(services: CoreServices) -> list[str]:
    localimage_config = services.config.modules.get("localimage", {})
    if not bool(localimage_config.get("enabled", False)):
        return []
    timeout_seconds = localimage_total_timeout_seconds(services.config)
    grace_seconds = float(localimage_config.get("stale_job_grace_seconds", 30))
    cutoff = utc_now() - timedelta(seconds=timeout_seconds + grace_seconds)
    cutoff_iso = cutoff.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    job_ids = services.jobs.mark_stale_failed(
        tool_name="local_image_generate",
        stale_before=cutoff_iso,
        error_code=PROVIDER_TIMEOUT,
        error_message=LOCAL_IMAGE_DEADLINE_MESSAGE,
    )
    services.audit.fail_started_for_jobs(
        job_ids=job_ids,
        error_code=PROVIDER_TIMEOUT,
        error_message=LOCAL_IMAGE_DEADLINE_MESSAGE,
    )
    if job_ids:
        logger.info("reconciled stale local image jobs", extra={"job_ids": job_ids})
    return job_ids


def localimage_total_timeout_seconds(settings: Settings) -> float:
    localimage_config = settings.modules.get("localimage", {})
    return float(localimage_config.get("total_timeout_seconds", settings.limits.get("sync_tool_timeout_seconds", 900)))


def _run_local_image_generate_job(
    *,
    settings: Settings,
    request_id: str,
    caller: CallerIdentity,
    job_id: str,
    audit_id: str,
    policy_decision: str,
    prepared: PreparedLocalImageGenerate,
    metadata: dict[str, Any],
) -> None:
    timeout_seconds = localimage_total_timeout_seconds(settings)
    deadline = LocalImageDeadline.after(timeout_seconds)
    local = _build_worker_services(settings)
    try:
        ctx = RequestContext(
            request_id=request_id,
            caller=caller,
            config=settings,
            artifacts=local.artifacts,
            jobs=local.jobs,
            policy=local.policy,
            audit=local.audit,
            limits=local.limits,
            job_id=job_id,
            metadata=metadata,
        )
        result = _run_with_deadline(prepared, ctx, deadline, timeout_seconds)
        artifact_ids = _extract_artifact_ids(result)
        local.jobs.mark_succeeded(job_id, result, artifact_ids)
        local.audit.finish(
            audit_id=audit_id,
            policy_decision=policy_decision,
            status="succeeded",
            artifact_ids=artifact_ids,
        )
        logger.info("local image job finished", extra={"request_id": request_id, "job_id": job_id})
    except GatewayError as exc:
        _fail_job(local, job_id, audit_id, policy_decision, exc)
        logger.info(
            "local image job failed",
            extra={"request_id": request_id, "job_id": job_id, "error_code": exc.code},
        )
    except Exception:
        logger.debug("unhandled local image job error", extra={"request_id": request_id, "job_id": job_id}, exc_info=True)
        _fail_job(local, job_id, audit_id, policy_decision, internal_error())
    finally:
        local.close()


def _run_with_deadline(
    prepared: PreparedLocalImageGenerate,
    ctx: RequestContext,
    deadline: LocalImageDeadline,
    timeout_seconds: float,
) -> dict[str, Any]:
    results: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def target() -> None:
        try:
            logger.info("local image provider request started", extra={"request_id": ctx.request_id, "job_id": ctx.job_id})
            provider = create_localimage_provider(ctx.config)
            result = LocalImageGenerationService(provider).generate_prepared(prepared, ctx, deadline)
            logger.info("local image artifact persisted", extra={"request_id": ctx.request_id, "job_id": ctx.job_id})
            results.put(("ok", result))
        except BaseException as exc:
            results.put(("error", exc))

    thread = threading.Thread(target=target, name=f"local-image-provider-{ctx.job_id}", daemon=True)
    thread.start()
    thread.join(timeout=max(0.001, timeout_seconds))
    if thread.is_alive():
        raise GatewayError(PROVIDER_TIMEOUT, LOCAL_IMAGE_DEADLINE_MESSAGE, retryable=True)
    try:
        status, payload = results.get_nowait()
    except queue.Empty as exc:
        raise internal_error() from exc
    if status == "error":
        raise payload
    return payload


def _build_worker_services(settings: Settings) -> CoreServices:
    conn = connect_database(
        settings.database["path"],
        wal=bool(settings.database.get("wal", True)),
        busy_timeout_ms=int(settings.database.get("busy_timeout_ms", 5000)),
    )
    return CoreServices(
        config=settings,
        artifacts=ArtifactStore(conn, settings),
        jobs=JobManager(conn),
        policy=PolicyEngine(settings),
        audit=AuditLogger(conn, settings),
        limits=InMemoryRateLimiter(),
    )


def _fail_job(
    services: CoreServices,
    job_id: str,
    audit_id: str,
    policy_decision: str,
    error: GatewayError,
) -> None:
    try:
        services.jobs.mark_failed(job_id, error.code, error.message)
    except GatewayError:
        pass
    services.audit.finish(
        audit_id=audit_id,
        policy_decision=policy_decision,
        status="failed",
        error_code=error.code,
        error_message=error.message,
    )


def _extract_artifact_ids(result: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    artifact = result.get("artifact")
    if isinstance(artifact, dict) and isinstance(artifact.get("id"), str):
        ids.append(artifact["id"])
        seen.add(artifact["id"])
    artifacts = result.get("artifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                artifact_id = item["id"]
                if artifact_id not in seen:
                    ids.append(artifact_id)
                    seen.add(artifact_id)
    return ids
