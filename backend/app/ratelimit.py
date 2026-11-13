"""A small in-memory limiter for public endpoints that have no account to count
against (invitation links). It resets when the server restarts, which is fine:
it only exists to slow down guessing and noise. Sign-in throttling is different:
it is counted in the audit log so it survives restarts."""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window_seconds: float, clock=time.monotonic):
        self.limit = limit
        self.window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Records one request for `key`; False when it is over the limit."""
        now = self._clock()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return False
            hits.append(now)
            if len(self._hits) > 10_000:  # bound memory under a flood of distinct addresses
                for stale in [k for k, v in self._hits.items() if not v or now - v[-1] >= self.window]:
                    del self._hits[stale]
            return True

    def retry_after(self, key: str) -> int:
        """Seconds until `key` may try again (0 if it may now)."""
        now = self._clock()
        with self._lock:
            hits = self._hits.get(key)
            if not hits or len(hits) < self.limit:
                return 0
            return max(1, int(self.window - (now - hits[0])) + 1)
