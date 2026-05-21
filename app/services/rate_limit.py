"""IP-bazlı sliding window rate limiter (in-memory).

Production'da multi-worker veya horizontal scale durumunda Redis tabanlı bir
sayaç gerekir. Tek-worker dev/Render starter için yeterli. /api/v1/auth/login
gibi spesifik endpoint'lere uygulamak için get_login_limiter dependency'sini
kullan.

Algoritma: sabit-pencere değil, sliding (deque ile per-IP timestamp listesi).
Pencere = 60sn, eşik settings.api_login_rate_per_min.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque

from fastapi import HTTPException, Request, status


class SlidingWindowLimiter:
    """Per-key sliding window. Thread-safe (Lock). RAM-only."""

    def __init__(self, *, window_seconds: int, max_hits: int) -> None:
        self.window = window_seconds
        self.max_hits = max_hits
        self._buckets: dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        """True/False izin, kalan retry-after saniye (limit aşıldıysa)."""
        if now is None:
            now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            q = self._buckets.setdefault(key, deque())
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_hits:
                retry_after = max(1, int(self.window - (now - q[0])))
                return False, retry_after
            q.append(now)
            return True, 0

    def reset(self, key: str | None = None) -> None:
        """Test temizliği. key=None ise tüm cache temizlenir."""
        with self._lock:
            if key is None:
                self._buckets.clear()
            else:
                self._buckets.pop(key, None)


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    return (request.client.host if request.client else "unknown")[:64]


# Singleton login limiter — settings'ten yapılandırılır
_login_limiter: SlidingWindowLimiter | None = None


def get_login_limiter() -> SlidingWindowLimiter:
    global _login_limiter
    if _login_limiter is None:
        from app.config import settings
        _login_limiter = SlidingWindowLimiter(
            window_seconds=60, max_hits=max(1, settings.api_login_rate_per_min)
        )
    return _login_limiter


def enforce_login_rate_limit(request: Request) -> None:
    """FastAPI dependency — /api/v1/auth/login için.

    Limit aşılırsa 429 + retry-after header.
    """
    limiter = get_login_limiter()
    key = _client_ip(request)
    ok, retry_after = limiter.hit(key)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Çok fazla deneme. Daha sonra tekrar deneyin.",
                "code": "rate_limited",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )
