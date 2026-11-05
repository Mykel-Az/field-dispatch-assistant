"""Small builders shared by the engine tests. Override only the field a test is about."""

from datetime import datetime, timedelta, timezone

from dispatch_engine.types import Candidate, JobView, Location, OrgConfig, TechView

# A fixed moment, not datetime.now(): tests must give the same result on every run.
NOW = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
HERE = Location(30.2672, -97.7431)


class StubDistance:
    """A fixed travel time, so tests can hit boundaries exactly."""

    def __init__(self, minutes: float = 0.0):
        self.minutes = minutes

    def miles(self, a, b) -> float:
        return 0.0

    def travel_minutes(self, a, b) -> float:
        return self.minutes


def make_job(**overrides) -> JobView:
    fields = {
        "id": 100,
        "label": "AC not cooling",
        "location": HERE,
        "is_urgent": False,
        "created_at": NOW,
        "slot_start": NOW + timedelta(hours=1),
        "slot_end": NOW + timedelta(hours=3),
        "duration_minutes": 60,
        "acceptable_skill_ids": frozenset({1, 2}),
    }
    return JobView(**{**fields, **overrides})


def make_tech(**overrides) -> TechView:
    fields = {
        "id": 1,
        "label": "Sam",
        "skill_ids": frozenset({1}),
        "shift_start": NOW,
        "shift_end": NOW + timedelta(hours=8),
        "is_available": True,
        "free_at": NOW,
        "position": HERE,
        "assigned_count": 0,
    }
    return TechView(**{**fields, **overrides})


def make_config(**overrides) -> OrgConfig:
    fields = {
        "workstation": HERE,
        "scoring_strategy": "balanced",
        "speed_mph": 30.0,
        "urgent_buffer_minutes": 60.0,
        "at_risk_minutes": 30.0,
        "max_jobs_per_tech_per_day": 4,
    }
    return OrgConfig(**{**fields, **overrides})


def make_candidate(**overrides) -> Candidate:
    fields = {
        "technician_id": 1,
        "estimated_arrival": NOW + timedelta(hours=1),
        "travel_minutes": 10.0,
    }
    return Candidate(**{**fields, **overrides})
