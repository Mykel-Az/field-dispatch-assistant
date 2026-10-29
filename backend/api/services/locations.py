"""Turn an address into coordinates. Failure is a normal outcome, never an error."""

import logging

from django.conf import settings
from django.utils.module_loading import import_string

from geocoding.base import GeocodingError

from ..models import GeocodeStatus

logger = logging.getLogger(__name__)


def get_geocoder():
    """The provider named in settings.GEOCODER_CLASS (a dotted path)."""
    return import_string(settings.GEOCODER_CLASS)()


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
