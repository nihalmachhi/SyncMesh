"""Small per-process fixed-window limiter for trusted lab controls."""

from collections import defaultdict
from time import monotonic

from fastapi import HTTPException, Request


class FixedWindowRateLimiter:
    """Bound request volume per client without an external service."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))

    def check(self, key: str, now: float | None = None) -> None:
        """Raise HTTP 429 after the configured count in the active time window."""
        moment = monotonic() if now is None else now
        current_window = int(moment // self.window_seconds)
        window, count = self._windows[key]
        if window != current_window:
            window, count = current_window, 0
        if count >= self.max_requests:
            retry_after = self.window_seconds - int(moment % self.window_seconds)
            raise HTTPException(
                status_code=429,
                detail="request rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
        self._windows[key] = (window, count + 1)
        if len(self._windows) > 10_000:
            self._windows = defaultdict(
                lambda: (0, 0),
                {
                    client: value
                    for client, value in self._windows.items()
                    if value[0] >= window - 2
                },
            )


def enforce_rate_limit(request: Request) -> None:
    """Apply the application-owned limiter to protected write routes."""
    limiter: FixedWindowRateLimiter = request.app.state.rate_limiter
    client_host = request.client.host if request.client else "unknown"
    limiter.check(f"{client_host}:{request.url.path}")
