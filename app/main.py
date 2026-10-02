from __future__ import annotations

from app.config import Settings, load_settings
from core.artifacts import ArtifactStore
from core.audit import AuditLogger
from core.db import connect_database
from core.management import ManagementStore
from core.llm import LLMStore
from core.jobs import JobManager
from core.limits import InMemoryRateLimiter
from core.policy import PolicyEngine
from modules.loader import register_configured_module_tools, run_configured_module_startup_hooks
from tools.builtin import register_builtin_tools
from tools.dispatcher import ToolDispatcher
from tools.registry import ToolRegistry
from transport.mcp_server import create_http_server
from transport.request_context import CoreServices


def build_services(settings: Settings | None = None) -> tuple[CoreServices, ToolRegistry, ToolDispatcher]:
    settings = settings or load_settings()
    conn = connect_database(
        settings.database["path"],
        wal=bool(settings.database.get("wal", True)),
        busy_timeout_ms=int(settings.database.get("busy_timeout_ms", 5000)),
    )
    management = ManagementStore(connect_database(
        settings.database["path"],
        wal=bool(settings.database.get("wal", True)),
        busy_timeout_ms=int(settings.database.get("busy_timeout_ms", 5000)),
    ))
    llm = LLMStore(management)
    if management.load() is None:
        image = settings.modules.get("image", {})
        legacy = image.get("openai_compatible", {})
        if all(legacy.get(key) for key in ("base_url", "model", "api_key")) and not image.get("model_id"):
            provider_id = llm.save_provider({"name": "Imported Remote Image", "base_url": legacy["base_url"], "api_key": legacy["api_key"]})
            llm.save_models(provider_id, [{"model_id": legacy["model"], "tags": ["image"]}])
            image["model_id"] = llm.models(provider_id)[0]["id"]
        settings.raw["_sqlite_managed"] = True
        management.save(settings.raw)
    if settings.modules.get("image", {}).get("model_id"):
        settings.modules["image"].setdefault("openai_compatible", {}).update(llm.resolve_image(settings.modules["image"]["model_id"]))
    services = CoreServices(
        config=settings,
        artifacts=ArtifactStore(conn, settings),
        jobs=JobManager(conn),
        policy=PolicyEngine(settings),
        audit=AuditLogger(conn, settings),
        limits=InMemoryRateLimiter(),
        management=management,
        llm=llm,
    )
    registry = ToolRegistry()
    register_builtin_tools(registry)
    register_configured_module_tools(registry, settings)
    run_configured_module_startup_hooks(services, settings)
    dispatcher = ToolDispatcher(registry, services)
    return services, registry, dispatcher


def main() -> None:
    services, registry, dispatcher = build_services()
    httpd = create_http_server(services, registry, dispatcher)
    host, port = httpd.server_address
    print(f"home_mcp_gateway listening on http://{host}:{port}")
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
        services.close()


if __name__ == "__main__":
    main()
