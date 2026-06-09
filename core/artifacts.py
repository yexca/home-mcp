from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, BinaryIO

from app.config import Settings
from core.errors import (
    ARTIFACT_FORBIDDEN,
    ARTIFACT_NOT_FOUND,
    GatewayError,
    INVALID_ARGUMENT,
)
from core.ids import new_artifact_id
from core.policy import CallerIdentity
from core.time import parse_iso, utc_now, utc_now_iso

KIND_DIRECTORIES = {
    "image": "images",
    "audio": "audio",
    "document": "documents",
    "print": "print",
    "temp": "tmp",
}


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    kind: str
    mime_type: str
    filename: str
    storage_path: str
    size_bytes: int
    sha256: str
    owner_caller_id: str
    source_tool: str
    source_job_id: str | None
    created_at: str
    expires_at: str | None
    metadata: dict[str, Any]

    def to_metadata(self, public_base_url: str | None = None) -> dict[str, Any]:
        data = {
            "id": self.id,
            "kind": self.kind,
            "mime_type": self.mime_type,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "owner_caller_id": self.owner_caller_id,
            "source_tool": self.source_tool,
            "source_job_id": self.source_job_id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "metadata": self.metadata,
        }
        if public_base_url:
            data["download_url"] = f"{public_base_url.rstrip('/')}/{self.id}"
        return data


class ArtifactStore:
    def __init__(self, conn: sqlite3.Connection, settings: Settings):
        self.conn = conn
        self.settings = settings
        self.root = Path(settings.artifacts["root"]).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "tmp").mkdir(parents=True, exist_ok=True)
        self.max_bytes = int(settings.artifacts.get("max_artifact_bytes", 50 * 1024 * 1024))

    def create_from_bytes(
        self,
        *,
        kind: str,
        mime_type: str,
        extension: str,
        data: bytes,
        owner: CallerIdentity | str,
        source_tool: str,
        source_job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        if kind not in KIND_DIRECTORIES:
            raise GatewayError(INVALID_ARGUMENT, "unsupported artifact kind")
        if len(data) > self.max_bytes:
            raise GatewayError(INVALID_ARGUMENT, "artifact exceeds max size")
        artifact_id = new_artifact_id()
        extension = extension.lstrip(".") or "bin"
        filename = f"{artifact_id}.{extension}"
        tmp_path = self.root / "tmp" / f"{artifact_id}.part"
        digest = hashlib.sha256()
        try:
            with tmp_path.open("wb") as fh:
                fh.write(data)
                digest.update(data)
            artifact = self._commit_file(
                artifact_id=artifact_id,
                tmp_path=tmp_path,
                kind=kind,
                mime_type=mime_type,
                filename=filename,
                size_bytes=len(data),
                sha256=digest.hexdigest(),
                owner_caller_id=owner.caller_id if isinstance(owner, CallerIdentity) else owner,
                source_tool=source_tool,
                source_job_id=source_job_id,
                metadata=metadata or {},
            )
            return artifact
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def create_from_file(
        self,
        *,
        kind: str,
        mime_type: str,
        source_path: str | Path,
        owner: CallerIdentity | str,
        source_tool: str,
        source_job_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Artifact:
        path = Path(source_path).resolve()
        if not path.is_file():
            raise GatewayError(INVALID_ARGUMENT, "source file does not exist")
        artifact_id = new_artifact_id()
        tmp_path = self.root / "tmp" / f"{artifact_id}.part"
        digest = hashlib.sha256()
        size = 0
        try:
            with path.open("rb") as src, tmp_path.open("wb") as dst:
                for chunk in iter(lambda: src.read(1024 * 1024), b""):
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise GatewayError(INVALID_ARGUMENT, "artifact exceeds max size")
                    digest.update(chunk)
                    dst.write(chunk)
            return self._commit_file(
                artifact_id=artifact_id,
                tmp_path=tmp_path,
                kind=kind,
                mime_type=mime_type,
                filename=f"{artifact_id}{path.suffix or '.bin'}",
                size_bytes=size,
                sha256=digest.hexdigest(),
                owner_caller_id=owner.caller_id if isinstance(owner, CallerIdentity) else owner,
                source_tool=source_tool,
                source_job_id=source_job_id,
                metadata=metadata or {},
            )
        finally:
            if tmp_path.exists():
                tmp_path.unlink()

    def get(self, artifact_id: str, caller: CallerIdentity) -> Artifact:
        row = self.conn.execute("SELECT * FROM artifacts WHERE id = ? AND deleted_at IS NULL", (artifact_id,)).fetchone()
        if not row:
            raise GatewayError(ARTIFACT_NOT_FOUND, "artifact not found")
        artifact = self._from_row(row)
        if self._is_expired(artifact):
            raise GatewayError(ARTIFACT_FORBIDDEN, "artifact expired")
        if not self.can_read(artifact, caller):
            raise GatewayError(ARTIFACT_FORBIDDEN, "artifact access denied")
        return artifact

    def open_stream(self, artifact_id: str, caller: CallerIdentity) -> BinaryIO:
        artifact = self.get(artifact_id, caller)
        path = self.safe_path(artifact)
        return path.open("rb")

    def safe_path(self, artifact: Artifact) -> Path:
        path = (self.root / artifact.storage_path).resolve()
        root = self.root.resolve()
        if os.path.commonpath([str(root), str(path)]) != str(root):
            raise GatewayError(ARTIFACT_FORBIDDEN, "artifact path escaped root")
        if not path.is_file():
            raise GatewayError(ARTIFACT_NOT_FOUND, "artifact file not found")
        return path

    def grant(
        self,
        artifact_id: str,
        caller_id: str,
        permission: str = "read",
        expires_at: str | None = None,
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO caller_artifact_grants
                (artifact_id, caller_id, permission, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (artifact_id, caller_id, permission, utc_now_iso(), expires_at),
            )

    def can_read(self, artifact: Artifact, caller: CallerIdentity) -> bool:
        if caller.caller_id == artifact.owner_caller_id:
            return True
        if caller.is_admin and caller.shared_artifact_read:
            return True
        row = self.conn.execute(
            """
            SELECT expires_at FROM caller_artifact_grants
            WHERE artifact_id = ? AND caller_id = ? AND permission = 'read'
            """,
            (artifact.id, caller.caller_id),
        ).fetchone()
        if not row:
            return False
        expires_at = parse_iso(row["expires_at"])
        return expires_at is None or expires_at > utc_now()

    def _commit_file(
        self,
        *,
        artifact_id: str,
        tmp_path: Path,
        kind: str,
        mime_type: str,
        filename: str,
        size_bytes: int,
        sha256: str,
        owner_caller_id: str,
        source_tool: str,
        source_job_id: str | None,
        metadata: dict[str, Any],
    ) -> Artifact:
        now = utc_now()
        retention_days = int(self.settings.artifacts.get("retention_days", {}).get(kind, 1))
        expires_at = (now + timedelta(days=retention_days)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        subdir = KIND_DIRECTORIES[kind]
        target_dir = self.root / subdir / f"{now:%Y}" / f"{now:%m}"
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        shutil.move(str(tmp_path), str(target_path))
        storage_path = str(target_path.resolve().relative_to(self.root)).replace("\\", "/")
        artifact = Artifact(
            id=artifact_id,
            kind=kind,
            mime_type=mime_type,
            filename=filename,
            storage_path=storage_path,
            size_bytes=size_bytes,
            sha256=sha256,
            owner_caller_id=owner_caller_id,
            source_tool=source_tool,
            source_job_id=source_job_id,
            created_at=now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            expires_at=expires_at,
            metadata=metadata,
        )
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO artifacts
                (id, kind, mime_type, filename, storage_path, size_bytes, sha256,
                 owner_caller_id, source_tool, source_job_id, created_at, expires_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.id,
                    artifact.kind,
                    artifact.mime_type,
                    artifact.filename,
                    artifact.storage_path,
                    artifact.size_bytes,
                    artifact.sha256,
                    artifact.owner_caller_id,
                    artifact.source_tool,
                    artifact.source_job_id,
                    artifact.created_at,
                    artifact.expires_at,
                    json.dumps(artifact.metadata, ensure_ascii=True, sort_keys=True),
                ),
            )
        return artifact

    def _from_row(self, row: sqlite3.Row) -> Artifact:
        return Artifact(
            id=row["id"],
            kind=row["kind"],
            mime_type=row["mime_type"],
            filename=row["filename"],
            storage_path=row["storage_path"],
            size_bytes=row["size_bytes"],
            sha256=row["sha256"],
            owner_caller_id=row["owner_caller_id"],
            source_tool=row["source_tool"],
            source_job_id=row["source_job_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            metadata=json.loads(row["metadata_json"] or "{}"),
        )

    def _is_expired(self, artifact: Artifact) -> bool:
        expires_at = parse_iso(artifact.expires_at)
        return expires_at is not None and expires_at <= utc_now()
