"""The Nominatim parser against responses saved from the real service.

`geocoding/fixtures/real_<kind>.json` are written by
`python -m geocoding.capture_real_fixtures` (by hand, never in CI) and committed.
The hand-written fixtures in test_geocoding.py pin the parser's rules; these pin
that the rules still match what Nominatim really sends.
"""

import json
import pathlib

import pytest

from geocoding.base import APPROXIMATE, OK
from geocoding.nominatim import parse_response

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "geocoding" / "fixtures"
REAL = sorted(FIXTURES.glob("real_*.json"))
KINDS = {"house", "street", "postcode", "empty"}

needs_real = pytest.mark.skipif(
    not REAL,
    reason="no real_*.json yet: run `python -m geocoding.capture_real_fixtures`",
)


def kind_of(path):
    return path.stem.removeprefix("real_")


@needs_real
@pytest.mark.parametrize("path", REAL, ids=lambda p: p.stem)
def test_real_response_parses_as_its_kind(path):
    assert kind_of(path) in KINDS, f"unknown kind in {path.name}"
    payload = json.loads(path.read_text())
    result = parse_response(payload)
    kind = kind_of(path)
    if kind == "empty":
        assert result is None
        return
    assert result is not None
    assert result.label
    # Inside the United States (the app is US only, ADR-007) and rounded to 6 places.
    assert 18 <= result.lat <= 72 and -180 <= result.lng <= -65
    assert result.lat == round(result.lat, 6) and result.lng == round(result.lng, 6)
    assert result.status == (OK if kind == "house" else APPROXIMATE)


@needs_real
@pytest.mark.parametrize("path", REAL, ids=lambda p: p.stem)
def test_real_response_still_has_the_fields_the_parser_reads(path):
    payload = json.loads(path.read_text())
    assert isinstance(payload, list)
    if not payload:
        return
    first = payload[0]
    for key in ("lat", "lon", "display_name"):
        assert key in first, f"Nominatim dropped `{key}`"
    assert "address" in first and "addresstype" in first
