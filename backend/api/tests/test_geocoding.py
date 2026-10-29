"""Nominatim parsing (against saved responses), the cache, the throttle and the
HTTP adapter. No network anywhere: the fetch function is injected.

The fixtures follow Nominatim's documented `format=jsonv2` shape. To refresh one
from the real service:
  curl -A "your-app (you@example.com)" \
    "https://nominatim.openstreetmap.org/search?q=1204+Congress+Ave,+Austin&format=jsonv2&limit=1&addressdetails=1"
"""

import json
import pathlib
import urllib.error

import pytest

from geocoding.base import APPROXIMATE, OK, GeocodingError
from geocoding.cache import CachingGeocoder, GeocodeCache, cache_key
from geocoding.fake import FakeGeocoder
from geocoding.nominatim import NominatimGeocoder, parse_response
from geocoding.throttle import Throttle

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "geocoding" / "fixtures"


def fixture(name):
    return (FIXTURES / f"{name}.json").read_text()


# ---- parsing ----------------------------------------------------------------
def test_a_house_is_an_exact_result():
    result = parse_response(json.loads(fixture("house")))
    assert result.status == OK
    assert (result.lat, result.lng) == (30.270641, -97.74247)
    assert result.label.startswith("1204, Congress Avenue")


def test_a_street_without_a_house_number_is_approximate():
    assert parse_response(json.loads(fixture("street"))).status == APPROXIMATE


def test_a_postcode_area_is_approximate():
    assert parse_response(json.loads(fixture("postcode"))).status == APPROXIMATE


def test_no_match_is_none():
    assert parse_response(json.loads(fixture("empty"))) is None


@pytest.mark.parametrize(
    "payload",
    [
        {"error": "x"},  # not a list
        [{"lat": "abc", "lon": "1"}],  # not a number
        [{"lon": "1"}],  # missing latitude
        [{"lat": "95", "lon": "1"}],  # out of range
    ],
)
def test_unexpected_shapes_raise_instead_of_guessing(payload):
    with pytest.raises(GeocodingError):
        parse_response(payload)


# ---- the adapter ------------------------------------------------------------
def geocoder_returning(body):
    seen = []

    def fetch(url):
        seen.append(url)
        return body

    return NominatimGeocoder(base_url="http://test/search", fetch=fetch), seen


def test_the_request_carries_the_address_and_limits():
    geocoder, seen = geocoder_returning(fixture("house"))
    geocoder.geocode("1204 Congress Ave", "78701")
    url = seen[0]
    assert url.startswith("http://test/search?")
    assert "q=1204+Congress+Ave%2C+78701" in url
    assert "format=jsonv2" in url and "limit=1" in url and "countrycodes=us" in url


def test_a_blank_address_never_calls_the_provider():
    geocoder, seen = geocoder_returning(fixture("house"))
    assert geocoder.geocode("  ", "") is None
    assert seen == []


def test_non_json_is_a_geocoding_error():
    geocoder, _ = geocoder_returning("<html>Bad gateway</html>")
    with pytest.raises(GeocodingError):
        geocoder.geocode("1 Main St", "78701")


def test_http_failures_become_geocoding_errors(monkeypatch):
    def boom(*args, **kwargs):
        raise urllib.error.HTTPError("http://x", 429, "Too Many", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", boom)
    with pytest.raises(GeocodingError, match="429"):
        NominatimGeocoder().geocode("1 Main St", "78701")


def test_network_failures_become_geocoding_errors(monkeypatch):
    def down(*args, **kwargs):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr("urllib.request.urlopen", down)
    with pytest.raises(GeocodingError):
        NominatimGeocoder().geocode("1 Main St", "78701")


# ---- cache ------------------------------------------------------------------
def test_the_same_address_is_looked_up_once():
    fake = FakeGeocoder()
    cached = CachingGeocoder(fake)
    first = cached.geocode("1 Main St", "78701")
    second = cached.geocode("  1  MAIN st ", "78701")  # spacing and case do not matter
    assert first == second and len(fake.calls) == 1


def test_a_not_found_answer_is_cached_too():
    fake = FakeGeocoder()
    cached = CachingGeocoder(fake)
    assert cached.geocode("unfindable road", "78701") is None
    assert cached.geocode("unfindable road", "78701") is None
    assert len(fake.calls) == 1


def test_failures_are_not_cached():
    fake = FakeGeocoder()
    cached = CachingGeocoder(fake)
    for _ in range(2):
        with pytest.raises(GeocodingError):
            cached.geocode("boom street", "78701")
    assert len(fake.calls) == 2


def test_cache_entries_expire():
    now = [0.0]
    cache = GeocodeCache(ttl=10, clock=lambda: now[0])
    cache.put("k", None)
    assert cache.get("k") == (True, None)
    now[0] = 11
    assert cache.get("k") == (False, None)


def test_cache_has_a_size_cap():
    cache = GeocodeCache(max_entries=2)
    for key in ("a", "b", "c"):
        cache.put(key, None)
    assert cache.get("a")[0] is False and cache.get("c")[0] is True


def test_cache_key_ignores_case_and_spacing():
    assert cache_key(" 1  Main St", "78701") == cache_key("1 main st", "78701")


# ---- throttle ---------------------------------------------------------------
def test_throttle_spaces_calls_apart():
    now, slept = [0.0], []

    def sleep(seconds):
        slept.append(seconds)
        now[0] += seconds

    throttle = Throttle(1.0, clock=lambda: now[0], sleep=sleep)
    throttle.wait()  # first call: no wait
    now[0] += 0.25
    throttle.wait()  # 0.25 s later: waits the rest of the second
    assert slept == [pytest.approx(0.75)]


def test_cache_hits_skip_the_throttle():
    waits = []

    class Spy:
        def wait(self):
            waits.append(1)

    cached = CachingGeocoder(FakeGeocoder(), throttle=Spy())
    cached.geocode("1 Main St", "78701")
    cached.geocode("1 Main St", "78701")
    assert len(waits) == 1
