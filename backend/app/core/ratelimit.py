"""Tiny in-memory sliding-window rate limiter (per user).

Good enough for a single Render instance. If you ever run multiple
instances, move this to Redis (Upstash free tier).
"""

import time
from collections import defaultdict, deque
from threading import Lock

from app.core.errors import AppError


class RateLimiter:
    def __init__(
        self,
        limit: int,
        window_seconds: float = 60.0,
        message: str = "Too many AI requests, wait a minute and try again",
    ):
        self.limit = limit
        self.window = window_seconds
        self.message = message
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.limit:
                raise AppError(429, "RATE_LIMITED", self.message)
            q.append(now)
