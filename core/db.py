from __future__ import annotations

import sqlite3
from pathlib import Path

from core.time import utc_now_iso

SCHEMA_VERSION = 1

MIGRATIONS: list[tuple[int, str, str]] = [
    (
        1,
        "phase_1_core",
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS artifacts (
          id TEXT PRIMARY KEY,
          kind TEXT NOT NULL,
          mime_type TEXT NOT NULL,
          filename TEXT NOT NULL,
          storage_path TEXT NOT NULL,
          size_bytes INTEGER NOT NULL,
          sha256 TEXT NOT NULL,
          owner_caller_id TEXT NOT NULL,
          source_tool TEXT NOT NULL,
          source_job_id TEXT,
          created_at TEXT NOT NULL,
          expires_at TEXT,
          deleted_at TEXT,
          metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_artifacts_owner_created
          ON artifacts(owner_caller_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_artifacts_source_job
          ON artifacts(source_job_id);

        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY,
          request_id TEXT NOT NULL,
          caller_id TEXT NOT NULL,
          tool_name TEXT NOT NULL,
          status TEXT NOT NULL,
          progress REAL NOT NULL DEFAULT 0,
          input_summary_json TEXT NOT NULL DEFAULT '{}',
          result_summary_json TEXT,
          error_code TEXT,
          error_message TEXT,
          artifact_ids_json TEXT NOT NULL DEFAULT '[]',
          created_at TEXT NOT NULL,
          started_at TEXT,
          updated_at TEXT NOT NULL,
          finished_at TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_caller_created
          ON jobs(caller_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_jobs_status_updated
          ON jobs(status, updated_at);

        CREATE TABLE IF NOT EXISTS audit_events (
          id TEXT PRIMARY KEY,
          request_id TEXT NOT NULL,
          job_id TEXT,
          caller_id TEXT NOT NULL,
          tool_name TEXT NOT NULL,
          risk_level TEXT NOT NULL,
          input_summary_json TEXT NOT NULL DEFAULT '{}',
          policy_decision TEXT,
          status TEXT NOT NULL,
          artifact_ids_json TEXT NOT NULL DEFAULT '[]',
          error_code TEXT,
          error_message TEXT,
          started_at TEXT NOT NULL,
          finished_at TEXT,
          duration_ms INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_audit_request
          ON audit_events(request_id);
        CREATE INDEX IF NOT EXISTS idx_audit_caller_started
          ON audit_events(caller_id, started_at);

        CREATE TABLE IF NOT EXISTS caller_artifact_grants (
          artifact_id TEXT NOT NULL,
          caller_id TEXT NOT NULL,
          permission TEXT NOT NULL,
          created_at TEXT NOT NULL,
          expires_at TEXT,
          PRIMARY KEY (artifact_id, caller_id, permission),
          FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
        );
        """,
    ),
]


def connect_database(path: str, *, wal: bool = True, busy_timeout_ms: int = 5000) -> sqlite3.Connection:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
    conn.execute("PRAGMA foreign_keys = ON")
    if wal:
        conn.execute("PRAGMA journal_mode = WAL")
    run_migrations(conn)
    return conn


def run_migrations(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
    )
    applied = {
        row["version"]
        for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
    }
    for version, name, ddl in MIGRATIONS:
        if version in applied:
            continue
        with conn:
            conn.executescript(ddl)
            conn.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, utc_now_iso()),
            )
