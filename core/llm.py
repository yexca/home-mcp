from __future__ import annotations

import json
import uuid
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from core.management import ManagementStore


def api_root(base_url: str) -> str:
    parsed = urlparse(base_url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("API address must be an http(s) URL without credentials, query or fragment")
    root = base_url.strip().rstrip("/")
    if parsed.path.rstrip("/").endswith(("/models", "/images", "/images/generations", "/chat/completions")):
        raise ValueError("Use the API base address, not a models, image or chat endpoint")
    return root if root.endswith("/v1") else root + "/v1"


class LLMStore:
    def __init__(self, management: ManagementStore) -> None:
        self.management = management
        self.conn = management.conn
        self.lock = management.lock

    def catalog(self) -> dict[str, Any]:
        with self.lock:
            providers = [dict(row) for row in self.conn.execute("SELECT * FROM llm_providers ORDER BY name, id")]
            for provider in providers:
                provider["key_configured"] = bool(provider.pop("api_key"))
                provider["models"] = self.models(provider["id"])
            return {"providers": providers}

    def provider(self, provider_id: str) -> dict[str, Any]:
        with self.lock:
            row = self.conn.execute("SELECT * FROM llm_providers WHERE id = ?", (provider_id,)).fetchone()
            if row is None:
                raise ValueError("Provider not found")
            return dict(row)

    def models(self, provider_id: str) -> list[dict[str, Any]]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM llm_models WHERE provider_id = ? ORDER BY model_id", (provider_id,)).fetchall()
            return [{"id": row["id"], "provider_id": row["provider_id"], "model_id": row["model_id"], "tags": json.loads(row["tags_json"])} for row in rows]

    def save_provider(self, payload: dict[str, Any]) -> str:
        if payload.get("id") is not None and not isinstance(payload["id"], str):
            raise ValueError("Provider id must be a string")
        provider_id = payload.get("id") or uuid.uuid4().hex
        existing = self.provider(provider_id) if payload.get("id") else {}
        name = str(payload.get("name", "")).strip()
        base_url = str(payload.get("base_url", "")).strip().rstrip("/")
        api_root(base_url)
        key = str(payload.get("api_key") or existing.get("api_key") or "").strip()
        if not name or not key:
            raise ValueError("Provider name and API key are required")
        if "\n" in key or "\r" in key:
            raise ValueError("API key contains invalid characters")
        with self.lock, self.conn:
            self.conn.execute(
                "INSERT INTO llm_providers(id, name, base_url, api_key) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET name = excluded.name, base_url = excluded.base_url, api_key = excluded.api_key",
                (provider_id, name, base_url, key),
            )
        return provider_id

    def selected_id(self) -> str:
        config = self.management.load() or {}
        return str(config.get("modules", {}).get("image", {}).get("model_id") or "")

    def delete_provider(self, provider_id: str) -> None:
        with self.lock:
            self.provider(provider_id)
            if self.selected_id() in {model["id"] for model in self.models(provider_id)}:
                raise ValueError("Change the Remote Image selection before removing this provider")
            with self.conn:
                self.conn.execute("DELETE FROM llm_providers WHERE id = ?", (provider_id,))

    def save_models(self, provider_id: str, models: Any) -> None:
        if not isinstance(models, list):
            raise ValueError("models must be a list")
        with self.lock:
            self.provider(provider_id)
            existing = {model["model_id"]: model for model in self.models(provider_id)}
            selected = self.selected_id()
            normalized = []
            seen = set()
            for model in models:
                if not isinstance(model, dict):
                    raise ValueError("Model entries must be objects")
                model_id = str(model.get("model_id", "")).strip()
                tags = model.get("tags", [])
                if not model_id or model_id in seen:
                    raise ValueError("Model ids must be nonempty and unique")
                if not isinstance(tags, list) or not tags or any(tag not in {"text", "image"} for tag in tags):
                    raise ValueError("Select at least one model tag: text or image")
                seen.add(model_id)
                item_id = existing.get(model_id, {}).get("id") or uuid.uuid4().hex
                normalized.append((item_id, provider_id, model_id, json.dumps(sorted(set(tags)))))
            selected_row = next((row for row in normalized if row[0] == selected), None)
            if selected in {item["id"] for item in existing.values()} and (not selected_row or "image" not in json.loads(selected_row[3])):
                raise ValueError("Change the Remote Image selection before removing its model or image tag")
            with self.conn:
                self.conn.execute("DELETE FROM llm_models WHERE provider_id = ?", (provider_id,))
                self.conn.executemany("INSERT INTO llm_models(id, provider_id, model_id, tags_json) VALUES (?, ?, ?, ?)", normalized)

    def resolve_image(self, model_id: str) -> dict[str, Any]:
        with self.lock:
            row = self.conn.execute(
                "SELECT m.model_id AS model, m.tags_json, p.base_url, p.api_key FROM llm_models m "
                "JOIN llm_providers p ON p.id = m.provider_id WHERE m.id = ?", (model_id,),
            ).fetchone()
            if row is None or "image" not in json.loads(row["tags_json"]):
                raise ValueError("Remote Image requires an added model tagged image")
            return {key: row[key] for key in ("model", "base_url", "api_key")}

    def discover(self, provider_id: str) -> list[str]:
        provider = self.provider(provider_id)
        endpoint = api_root(provider["base_url"]) + "/models"
        req = request.Request(endpoint, headers={
            "Authorization": f"Bearer {provider['api_key']}",
            "Accept": "application/json",
            "User-Agent": "home-mcp-gateway/0.2.2",
        })
        try:
            with request.urlopen(req, timeout=30) as response:
                body = response.read(4 * 1024 * 1024 + 1)
            if len(body) > 4 * 1024 * 1024:
                raise ValueError("Model list response is too large")
            payload = json.loads(body)
            rows = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip() for row in rows):
                raise ValueError("Provider did not return an OpenAI-compatible model list")
            return sorted({row["id"] for row in rows})
        except error.HTTPError as exc:
            raise ValueError(f"Model discovery failed (HTTP {exc.code})") from exc
        except (error.URLError, TimeoutError, OSError) as exc:
            raise ValueError("Could not reach the model provider") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Provider returned invalid JSON") from exc
