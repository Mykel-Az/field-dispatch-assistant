# ADR-005: No live GPS tracking

Date: <fill in> · Status: Accepted

## Context
A dispatcher map is useful, but live technician tracking needs mobile
background location, privacy handling and a push or streaming channel.

## Decision
No live GPS. The map (Leaflet / react-leaflet, OSM tiles) shows job pins
coloured by status and one coloured line per technician showing planned visit
order. Position is inferred from job status, not tracked.

## Alternatives considered
- **Live GPS from a technician app**: realistic, but expensive, privacy
  sensitive, and not what this project is demonstrating.
- **No map at all**: loses the clearest way to show the engine's output.

## Trade-offs
- The map shows the plan, not reality. Documented as an explicit non-goal.
- Keeps the deployment free-tier friendly (no streaming infrastructure).
