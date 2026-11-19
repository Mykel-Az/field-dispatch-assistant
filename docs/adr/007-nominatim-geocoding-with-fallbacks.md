# ADR-007: Nominatim geocoding, cached, with manual fallback

Date: <fill in> · Status: Accepted

## Context
Jobs are created from addresses; the engine needs coordinates. Public
geocoders are rate limited and can time out or return ambiguous results.

## Decision
Public OpenStreetMap Nominatim, called once at job creation, behind a
`Geocoder` interface (Adapter). Results are cached (`GeocodeCache`) and
requests throttled to respect the usage policy. Failure is an expected
outcome: ambiguous or failed lookups fall back to a manual map pin or an
"approximate" flag. A `FakeGeocoder` is used in all tests and CI; only the
parsing logic of `NominatimGeocoder` is tested against saved fixtures.

## Invariant
A job is never Assigned while `geocode_status` is pending or failed (#16).

## Alternatives considered
- **Paid geocoder (Google, Mapbox)**: more reliable, but needs billing and
  keys, which conflicts with free-tier constraints.
- **Geocode at assignment time**: moves a slow, failure-prone call into the
  planning path.

## Trade-offs
- Nominatim has no SLA. Mitigation: caching, manual fallback, and a documented
  scaling path (self-hosted Nominatim or a paid provider) that is not built.

## Amendment (2026-11-19): real responses
The hand-written fixtures pin the parser's rules, but a hand-written fixture can
only match what we think Nominatim sends. `python -m geocoding.capture_real_fixtures`
saves raw answers for four public landmarks (house, street, postcode, no match)
as `real_*.json`, and `test_geocoding_real_responses.py` runs the parser over
every one. It is run by hand, never in CI: the public service has a 1 request
per second policy and no SLA, and a CI run must not depend on it. Re-run it when
Nominatim announces an API change or the parser is touched.
