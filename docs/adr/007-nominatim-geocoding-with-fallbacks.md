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
