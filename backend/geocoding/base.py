"""The Geocoder interface (Adapter). Network I/O lives behind it, nothing else.

This package is framework-independent: it never imports Django, DRF or
dispatch_engine. The `api` layer decides what to do with a result.
"""

from dataclasses import dataclass
from typing import Protocol

# Plain strings, equal to the values of api.models.GeocodeStatus.
OK = "ok"
APPROXIMATE = "approximate"  # the postal code was found, the street was not


class GeocodingError(Exception):
    """The lookup could not be completed (timeout, rate limit, bad response)."""


@dataclass(frozen=True)
class GeocodeResult:
    lat: float
    lng: float
    status: str  # OK or APPROXIMATE
    label: str = ""  # the address as the geocoder understood it


class Geocoder(Protocol):
    def geocode(self, address: str, postal_code: str) -> GeocodeResult | None:
        """Return a result, None if nothing matched, or raise GeocodingError."""
        ...


class UnavailableGeocoder:
    """Safe default until a real provider is configured: every lookup fails.

    Jobs then get geocode_status="failed" and show "location needs attention"
    instead of silently getting invented coordinates.
    """

    def geocode(self, address: str, postal_code: str) -> GeocodeResult | None:
        raise GeocodingError("no geocoder configured")
