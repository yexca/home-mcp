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
from modules.tts.service import PreparedTTSSynthesis, TTSSynthesisService, create_tts_provider, prepare_tts_synthesize
from tools.result import success
from transport.request_context import CoreServices, RequestContext

logger = logging.getLogger(__name__)

TTS_DEADLINE_MESSAGE = "tts job exceeded gateway deadline or was abandoned during restart"


def schedule_tts_synthesize_job(
    *,
    settings: Settings,
    request_id: str,
    caller: CallerIdentity,
    job_id: str,
    audit_id: str,
    policy_decision: str,
    prepared: PreparedTTSSynthesis,
    metadata: dict[str, Any],
) -> None:
    logger.info("tts job created", extra={"request_id": request_id, "job_id": job_id})
    thread = threading.Thread(
        target=_run_tts_synthesize_job,
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
        name=f"tts-synthesize-{job_id}",
        daemon=True,
    )
    thread.start()


async def tts_synthesize_background(arguments: dict[str, Any], ctx: RequestContext) -> dict[str, Any]:
    if not ctx.job_id or not ctx.audit_id or not ctx.policy_decision:
        raise internal_error()
    prepared = prepare_tts_synthesize(arguments, ctx)
    schedule_tts_synthesize_job(
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


def reconcile_stale_tts_jobs(services: CoreServices) -> list[str]:
    tts_config = services.config.modules.get("tts", {})
    if not bool(tts_config.get("enabled", False)):
        return []
    timeout_seconds = tts_total_timeout_seconds(services.config)
    grace_seconds = float(tts_config.get("stale_job_grace_seconds", 30))
    cutoff = utc_now() - timedelta(seconds=timeout_seconds + grace_seconds)
    cutoff_iso = cutoff.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    job_ids = services.jobs.mark_stale_failed(
        tool_name="tts_synthesize",
        stale_before=cutoff_iso,
        error_code=PROVIDER_TIMEOUT,
        error_message=TTS_DEADLINE_MESSAGE,
    )
    services.audit.fail_started_for_jobs(
        job_ids=job_ids,
        error_code=PROVIDER_TIMEOUT,
        error_message=TTS_DEADLINE_MESSAGE,
    )
    if job_ids:
        logger.info("reconciled stale tts jobs", extra={"job_ids": job_ids})
    return job_ids


def tts_total_timeout_seconds(settings: Settings) -> float:
    tts_config = settings.modules.get("tts", {})
    return float(tts_config.get("total_timeout_seconds", settings.limits.get("sync_tool_timeout_seconds", 120)))


def _run_tts_synthesize_job(
    *,
    settings: Settings,
    request_id: str,
    caller: CallerIdentity,
    job_id: str,
    audit_id: str,
    policy_decision: str,
    prepared: PreparedTTSSynthesis,
    metadata: dict[str, Any],
) -> None:
    timeout_seconds = tts_total_timeout_seconds(settings)
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
        result = _run_with_deadline(prepared, ctx, timeout_seconds)
        artifact_ids = _extract_artifact_ids(result)
        result_summary = _tts_result_summary(result, prepared)
        local.jobs.mark_succeeded(job_id, result_summary, artifact_ids)
        local.audit.finish(
            audit_id=audit_id,
            policy_decision=policy_decision,
            status="succeeded",
            artifact_ids=artifact_ids,
        )
        logger.info("tts job finished", extra={"request_id": request_id, "job_id": job_id})
    except GatewayError as exc:
        _fail_job(local, job_id, audit_id, policy_decision, exc)
        logger.info(
            "tts job failed",
            extra={"request_id": request_id, "job_id": job_id, "error_code": exc.code},
        )
    except Exception:
        logger.debug("unhandled tts job error", extra={"request_id": request_id, "job_id": job_id}, exc_info=True)
        _fail_job(local, job_id, audit_id, policy_decision, internal_error())
    finally:
        local.close()


def _run_with_deadline(
    prepared: PreparedTTSSynthesis,
    ctx: RequestContext,
    timeout_seconds: float,
) -> dict[str, Any]:
    results: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)

    def target() -> None:
        try:
            logger.info("tts provider request started", extra={"request_id": ctx.request_id, "job_id": ctx.job_id})
            provider = create_tts_provider(ctx.config)
            result = TTSSynthesisService(provider).synthesize_prepared(prepared, ctx)
            logger.info("tts artifact persisted", extra={"request_id": ctx.request_id, "job_id": ctx.job_id})
            results.put(("ok", result))
        except BaseException as exc:
            results.put(("error", exc))

    thread = threading.Thread(target=target, name=f"tts-provider-{ctx.job_id}", daemon=True)
    thread.start()
    thread.join(timeout=max(0.001, timeout_seconds))
    if thread.is_alive():
        raise GatewayError(PROVIDER_TIMEOUT, TTS_DEADLINE_MESSAGE, retryable=True)
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
    artifact = result.get("artifact")
    if isinstance(artifact, dict) and isinstance(artifact.get("id"), str):
        return [artifact["id"]]
    return []


def _tts_result_summary(result: dict[str, Any], prepared: PreparedTTSSynthesis) -> dict[str, Any]:
    artifact = result.get("artifact") if isinstance(result.get("artifact"), dict) else {}
    metadata = artifact.get("metadata") if isinstance(artifact.get("metadata"), dict) else {}
    summary: dict[str, Any] = {
        "status": "succeeded",
        "provider": metadata.get("provider"),
        "mime_type": artifact.get("mime_type"),
        "voice": metadata.get("voice", prepared.voice),
        "language": metadata.get("language", prepared.language),
        "format": metadata.get("format", prepared.output_format),
        "speed": metadata.get("speed", prepared.speed),
        "size_bytes": artifact.get("size_bytes"),
    }
    return {key: value for key, value in summary.items() if value is not None}
