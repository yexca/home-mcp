from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import monotonic
from threading import Lock

from core.errors import GatewayError, RATE_LIMITED


@dataclass(slots=True)
class _Bucket:
    count: int
    reset_at: float
    started_at: float = 0.0


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(0, 0.0))
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        if limit == 0:
            return
        with self._lock:
            now = monotonic()
            bucket = self._buckets[key]
            if bucket.reset_at:
                bucket.reset_at = bucket.started_at + window_seconds
            if now >= bucket.reset_at:
                bucket.count = 0
                bucket.started_at = now
                bucket.reset_at = now + window_seconds
            if bucket.count >= limit:
                raise GatewayError(RATE_LIMITED, "rate limit exceeded", retryable=True)
            bucket.count += 1
