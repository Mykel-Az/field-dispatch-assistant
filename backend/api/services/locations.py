"""Turn an address into coordinates. Failure is a normal outcome, never an error."""

import logging

from django.conf import settings
from django.utils.module_loading import import_string

from geocoding.base import GeocodingError

from ..models import GeocodeStatus

logger = logging.getLogger(__name__)


_shared = {}


def get_geocoder():
    """The provider named in settings.GEOCODER_CLASS (a dotted path).

    A class marked SHARED = True (the cached, throttled Nominatim one) is built
    once per process, so its cache and throttle survive between requests.
    """
    cls = import_string(settings.GEOCODER_CLASS)
    if getattr(cls, "SHARED", False):
        if cls not in _shared:
            _shared[cls] = cls()
        return _shared[cls]
    return cls()


def locate(obj, geocoder=None):
    """Fill lat, lng, geocode_status and location_label on `obj` (any AddressMixin).

    Does not save. Never raises: a lookup that fails or finds nothing leaves the
    object with geocode_status="failed" so the dispatcher can fix it by hand.
    Call this OUTSIDE a database transaction, because it can be slow.
    """
    if not obj.address.strip() and not obj.postal_code.strip():
        obj.lat = obj.lng = None
        obj.geocode_status = GeocodeStatus.PENDING
        obj.location_label = ""
        return obj

    geocoder = geocoder or get_geocoder()
    result = None
    try:
        result = geocoder.geocode(obj.address, obj.postal_code)
    except GeocodingError:
        logger.warning("geocoding failed for %r", obj.address)
    except Exception:  # a provider bug must never turn into a 500 on job creation
        logger.exception("unexpected geocoder error for %r", obj.address)

    if result is None:
        obj.lat = obj.lng = None
        obj.geocode_status = GeocodeStatus.FAILED
        obj.location_label = ""
    else:
        obj.lat, obj.lng = result.lat, result.lng
        obj.geocode_status = result.status
        obj.location_label = result.label
    return obj


def lookup(address, postal_code, geocoder=None):
    """Look an address up without touching any record (the form's "check address").

    Returns {"status", "lat", "lng", "label"}; status is "failed" when nothing
    was found or the provider is down. Never raises.
    """
    probe = locate(_Probe(address, postal_code), geocoder)
    return {
        "status": probe.geocode_status,
        "lat": probe.lat,
        "lng": probe.lng,
        "label": probe.location_label,
    }


class _Probe:
    """Just enough of an address-bearing object for locate()."""

    def __init__(self, address, postal_code):
        self.address, self.postal_code = address, postal_code
        self.lat = self.lng = None
        self.geocode_status = GeocodeStatus.PENDING
        self.location_label = ""
