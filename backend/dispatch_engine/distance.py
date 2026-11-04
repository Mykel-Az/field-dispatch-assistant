"""Distance and travel time between two points. Standard library only (ADR-006).

The engine asks a DistanceProvider and never knows how the answer is made, so a
road-distance provider can replace HaversineProvider later by touching one class.
Units are miles and mph: the product is US only.
"""

import math
from typing import Protocol

from .types import Location

EARTH_RADIUS_MILES = 3958.8

# Estimated average speed for city and suburban driving.
DEFAULT_SPEED_MPH = 30.0

# Roads are longer than the straight line between two points. This multiplier
# makes travel *time* less optimistic. TIME shortcut: 1.3 is an estimate; the
# full-fidelity path is a road-distance provider (ADR-006). 1.0 turns it off.
ROAD_FACTOR = 1.3


class DistanceProvider(Protocol):
    """How far apart two places are, and how long the trip takes."""

    def miles(self, a: Location, b: Location) -> float: ...

    def travel_minutes(self, a: Location, b: Location) -> float: ...


class HaversineProvider:
    """Straight-line (great-circle) distance, with travel time from an assumed speed."""

    def __init__(self, speed_mph: float = DEFAULT_SPEED_MPH) -> None:
        if speed_mph <= 0:
            raise ValueError("speed_mph must be positive")
        self.speed_mph = speed_mph

    def miles(self, a: Location, b: Location) -> float:
        if a == b:
            return 0.0
        lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
        d_lat = lat2 - lat1
        d_lng = math.radians(b.lng - a.lng)
        h = (
            math.sin(d_lat / 2) ** 2
            + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
        )
        return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))

    def travel_minutes(self, a: Location, b: Location) -> float:
        return self.miles(a, b) * ROAD_FACTOR / self.speed_mph * 60
