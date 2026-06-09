from __future__ import annotations

from app.config import Settings, load_settings
from core.artifacts import ArtifactStore
from core.audit import AuditLogger
from core.db import connect_database
from core.jobs import JobManager
from core.limits import InMemoryRateLimiter
from core.policy import PolicyEngine
from modules.loader import register_configured_module_tools
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
    services = CoreServices(
        config=settings,
        artifacts=ArtifactStore(conn, settings),
        jobs=JobManager(conn),
        policy=PolicyEngine(settings),
        audit=AuditLogger(conn, settings),
        limits=InMemoryRateLimiter(),
    )
    registry = ToolRegistry()
    register_builtin_tools(registry)
    register_configured_module_tools(registry, settings)
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
