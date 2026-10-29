"""Remember geocoding answers, so the same address is looked up once.

Nominatim's usage policy asks clients to cache. Both hits and misses are kept
(a "not found" is an answer too); failures (timeouts, 5xx) are never cached.
"""

import re
import threading
import time

from .base import GeocodeResult, GeocodingError

_MISS = object()  # a cached "nothing matched"


def cache_key(address: str, postal_code: str) -> str:
    """Same address typed with different spacing or case shares one entry."""
    clean = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    return f"{clean(address)}|{clean(postal_code)}"


class GeocodeCache:
    """In-memory, per process, with a time limit and a size cap.

    TIME: lost on restart and not shared between workers. Full-fidelity path:
    a database table (address key -> result) shared by every worker.
    """

    def __init__(self, ttl=60 * 60 * 24 * 30, max_entries=5000, clock=time.monotonic):
        self._ttl = ttl
        self._max = max_entries
        self._clock = clock
        self._data: dict[str, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, key):
        """Returns (found, value). `value` is a GeocodeResult or None (a cached miss)."""
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return False, None
            stored_at, value = entry
            if self._clock() - stored_at > self._ttl:
                del self._data[key]
                return False, None
            return True, None if value is _MISS else value

    def put(self, key, value):
        with self._lock:
            if len(self._data) >= self._max:
                self._data.pop(next(iter(self._data)))  # oldest first
            self._data[key] = (self._clock(), _MISS if value is None else value)


class CachingGeocoder:
    """Wraps any Geocoder: cache first, then (throttled) the real one."""

    def __init__(self, inner, cache=None, throttle=None):
        self.inner = inner
        self.cache = cache if cache is not None else GeocodeCache()
        self.throttle = throttle

    def geocode(self, address: str, postal_code: str) -> GeocodeResult | None:
        key = cache_key(address, postal_code)
        found, value = self.cache.get(key)
        if found:
            return value
        if self.throttle is not None:
            self.throttle.wait()
        result = self.inner.geocode(address, postal_code)  # may raise GeocodingError
        self.cache.put(key, result)
        return result


__all__ = ["CachingGeocoder", "GeocodeCache", "GeocodingError", "cache_key"]
