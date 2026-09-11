"""Per-domain token-bucket rate limiter — the "appropriate rate-limiting"
ethical safeguard the problem statement calls for. One bucket per domain,
shared across every adapter hitting that domain, so we never hammer a
single site regardless of how many routes/windows we're collecting."""
from __future__ import annotations

import asyncio
import time

from app.config import DEFAULT_RATE_LIMIT_SECONDS


class DomainRateLimiter:
    def __init__(self, min_interval_seconds: float = DEFAULT_RATE_LIMIT_SECONDS) -> None:
        self._min_interval = min_interval_seconds
        self._last_request_at: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, domain: str) -> asyncio.Lock:
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()
        return self._locks[domain]

    async def wait(self, domain: str) -> None:
        async with self._lock_for(domain):
            now = time.monotonic()
            last = self._last_request_at.get(domain)
            if last is not None:
                elapsed = now - last
                remaining = self._min_interval - elapsed
                if remaining > 0:
                    await asyncio.sleep(remaining)
            self._last_request_at[domain] = time.monotonic()
