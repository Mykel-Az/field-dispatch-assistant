"""Geocoding through OpenStreetMap's Nominatim. Standard library only.

Public instance rules (https://operations.osmfoundation.org/policies/nominatim/):
at most 1 request per second, an identifying User-Agent, and cache results. The
`NominatimGeocoder` class only talks and parses; `CachedNominatimGeocoder` adds
the cache and the throttle and is what settings.GEOCODER_CLASS points at.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .base import APPROXIMATE, OK, GeocodeResult, GeocodingError
from .cache import CachingGeocoder, GeocodeCache
from .throttle import Throttle

DEFAULT_URL = "https://nominatim.openstreetmap.org/search"

# Result types that mean "a specific building or door", as opposed to a street or area.
_PRECISE_TYPES = {"house", "building", "apartments", "yes"}


def parse_response(payload, postal_code: str = "") -> GeocodeResult | None:
    """Turn Nominatim's JSON (a list of places, best first) into a result.

    Pure function, so it is tested against saved responses with no network.
    Returns None when nothing matched. Raises GeocodingError on a shape it
    does not understand (so a changed API is a visible failure, not a wrong pin).
    """
    if not isinstance(payload, list):
        raise GeocodingError("unexpected response shape")
    if not payload:
        return None
    best = payload[0]
    try:
        lat, lng = float(best["lat"]), float(best["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError("response has no usable coordinates") from exc
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise GeocodingError("coordinates out of range")

    address = best.get("address") or {}
    precise = (
        bool(address.get("house_number")) or best.get("addresstype") in _PRECISE_TYPES
    )
    label = str(best.get("display_name", ""))[:255]
    return GeocodeResult(
        round(lat, 6), round(lng, 6), OK if precise else APPROXIMATE, label
    )


class NominatimGeocoder:
    def __init__(
        self,
        base_url=None,
        user_agent=None,
        timeout=8.0,
        country_codes="us",
        fetch=None,
    ):
        self.base_url = base_url or os.environ.get("NOMINATIM_URL", DEFAULT_URL)
        self.user_agent = user_agent or os.environ.get(
            "NOMINATIM_USER_AGENT",
            "field-dispatch-assistant (set NOMINATIM_USER_AGENT)",
        )
        self.timeout = timeout
        self.country_codes = country_codes
        self._fetch = fetch or self._http_get

    def build_url(self, address: str, postal_code: str) -> str:
        query = ", ".join(p.strip() for p in (address, postal_code) if p.strip())
        params = {"q": query, "format": "jsonv2", "limit": 1, "addressdetails": 1}
        if self.country_codes:
            params["countrycodes"] = self.country_codes
        return f"{self.base_url}?{urllib.parse.urlencode(params)}"

    def geocode(self, address: str, postal_code: str) -> GeocodeResult | None:
        if not (address.strip() or postal_code.strip()):
            return None
        body = self._fetch(self.build_url(address, postal_code))
        try:
            payload = json.loads(body)
        except (TypeError, ValueError) as exc:
            raise GeocodingError("response is not JSON") from exc
        return parse_response(payload, postal_code)

    def _http_get(self, url: str) -> str:
        request = urllib.request.Request(
            url, headers={"User-Agent": self.user_agent, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            raise GeocodingError(f"provider answered {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise GeocodingError(f"provider unreachable: {exc}") from exc


class CachedNominatimGeocoder(CachingGeocoder):
    """What the app uses: Nominatim behind a cache and a 1 request/second throttle.

    SHARED = True tells api.services.locations to keep one instance per process,
    otherwise the cache and the throttle would reset on every lookup.
    """

    SHARED = True

    def __init__(self):
        super().__init__(NominatimGeocoder(), GeocodeCache(), Throttle(1.0))
