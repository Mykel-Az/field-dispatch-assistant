"""Keep calls to a rate-limited provider apart. Thread-safe, no Django."""

import threading
import time


class Throttle:
    """Blocks so that successive `wait()` calls are at least `min_interval` apart.

    Nominatim's public service allows one request per second. This is per process:
    two gunicorn workers can still hit it together (TIME: a shared limiter, or a
    paid provider, if the app ever needs more than a handful of lookups a minute).
    """

    def __init__(self, min_interval=1.0, clock=time.monotonic, sleep=time.sleep):
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_at = 0.0

    def wait(self):
        with self._lock:
            now = self._clock()
            delay = self._next_at - now
            if delay > 0:
                self._sleep(delay)
                now = self._clock()
            self._next_at = now + self.min_interval
