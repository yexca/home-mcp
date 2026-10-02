from __future__ import annotations

import json
import sqlite3
import threading
from copy import deepcopy
from typing import Any

from core.time import utc_now_iso


class ManagementStore:
    """Serialize management transactions on the gateway's shared SQLite connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.lock = threading.RLock()

    def load(self) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT config_json FROM management_config WHERE id = 1").fetchone()
            return json.loads(row[0]) if row else None

    def save(self, config: dict[str, Any]) -> None:
        config = deepcopy(config)
        # Authentication always comes from the process environment.
        config.pop("webui", None)
        image = config.get("modules", {}).get("image", {})
        if image.get("model_id"):
            provider = image.get("openai_compatible", {})
            for key in ("base_url", "model", "api_key"):
                provider.pop(key, None)
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO management_config(id, config_json, updated_at) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET config_json = excluded.config_json, updated_at = excluded.updated_at",
                (json.dumps(config, ensure_ascii=False), utc_now_iso()),
            )
