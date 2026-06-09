from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import monotonic

from core.errors import GatewayError, RATE_LIMITED


@dataclass(slots=True)
class _Bucket:
    count: int
    reset_at: float


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, _Bucket] = defaultdict(lambda: _Bucket(0, 0.0))

    def check(self, key: str, *, limit: int, window_seconds: int) -> None:
        now = monotonic()
        bucket = self._buckets[key]
        if now >= bucket.reset_at:
            bucket.count = 0
            bucket.reset_at = now + window_seconds
        if bucket.count >= limit:
            raise GatewayError(RATE_LIMITED, "rate limit exceeded", retryable=True)
        bucket.count += 1
