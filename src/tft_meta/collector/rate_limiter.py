"""Client-side rate limiting: wait before sending instead of getting a 429."""

import time
from collections import deque


class SlidingWindow:
    """Tracks one limit: at most max_requests in any window_seconds period."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps: deque[float] = deque()

    def wait_time(self, now: float) -> float:
        # Forget requests that have left the window
        while self.timestamps and now - self.timestamps[0] >= self.window_seconds:
            self.timestamps.popleft()

        if len(self.timestamps) < self.max_requests:
            return 0.0

        # The window is full: wait until the oldest request leaves it
        return self.window_seconds - (now - self.timestamps[0])

    def record(self, now: float) -> None:
        self.timestamps.append(now)


class RateLimiter:
    """Combines several limits; a request must satisfy all of them."""

    def __init__(self, limits: list[tuple[int, float]]) -> None:
        self.windows = [SlidingWindow(count, seconds) for count, seconds in limits]

    def acquire(self) -> None:
        """Block until a request is allowed, then record it."""
        while True:
            now = time.monotonic()
            wait = max(window.wait_time(now) for window in self.windows)
            if wait == 0:
                break
            time.sleep(wait)

        for window in self.windows:
            window.record(now)
