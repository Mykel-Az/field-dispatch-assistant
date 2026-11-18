"""Deterministic geocoder for tests, CI and local development. No network."""

import hashlib

from .base import APPROXIMATE, OK, GeocodeResult, GeocodingError


class FakeGeocoder:
    """Same input, same coordinates. Magic words in the address force outcomes:

    - "unfindable": nothing matches (returns None)
    - "boom":       the provider fails (raises GeocodingError)
    - a blank address with a postal code gives an "approximate" result
    """

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    def geocode(self, address: str, postal_code: str) -> GeocodeResult | None:
        self.calls.append((address, postal_code))
        text = address.lower()
        if "boom" in text:
            raise GeocodingError("fake provider failure")
        if "unfindable" in text or not (address.strip() or postal_code.strip()):
            return None
        digest = hashlib.sha256(f"{address}|{postal_code}".encode()).digest()
        # A box about 14 miles across around central Austin, like one city's service
        # area: a wider box made demo jobs hours apart and every plan look late.
        lat = 30.20 + 0.20 * int.from_bytes(digest[:4], "big") / 2**32  # 30.20 .. 30.40
        lng = (
            -97.85 + 0.20 * int.from_bytes(digest[4:8], "big") / 2**32
        )  # -97.85 .. -97.65
        status = OK if address.strip() else APPROXIMATE
        label = ", ".join(
            part for part in (address.strip(), postal_code.strip()) if part
        )
        return GeocodeResult(round(lat, 6), round(lng, 6), status, label)
