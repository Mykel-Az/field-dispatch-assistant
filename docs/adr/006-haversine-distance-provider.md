# ADR-006: Haversine distance behind a DistanceProvider interface

Date: <fill in> · Status: Accepted

## Context
Scoring and sequencing need distances and travel-time estimates. Road routing
APIs add cost, rate limits, network failure modes and test flakiness.

## Decision
Great-circle (haversine) distance times a configurable assumed speed, behind a
`DistanceProvider` interface (Strategy). The engine never knows how distance
is computed. Distances are computed live and never cached as a matrix.

## Alternatives considered
- **Routing API (OSRM, Google, Mapbox)**: more accurate, but adds an external
  dependency and cost to the hot path. Documented as a stretch only.
- **Precomputed road-distance matrix**: stretch; cut first if behind schedule.

## Trade-offs
- Straight-line distance underestimates real travel. Mitigation: assumed-speed
  config and a stated limitation in the design document.
- Swapping in a road-distance provider later touches one class.
