from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


def _require_aware(name: str, value: datetime) -> None:
    """Engine times are absolute. A naive datetime would silently mean 'some local clock'."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class Location:
    lat: float
    lng: float

    def __post_init__(self):
        if not (-90 <= self.lat <= 90):
            raise ValueError(f"Latitude must be between -90 and 90, got {self.lat}")
        if not (-180 <= self.lng <= 180):
            raise ValueError(f"Longitude must be between -180 and 180, got {self.lng}")


@dataclass(frozen=True, slots=True)
class JobView:
    id: int
    label: str
    location: Location
    is_urgent: bool
    created_at: datetime
    slot_start: datetime | None
    slot_end: datetime | None
    duration_minutes: int
    acceptable_skill_ids: frozenset[int]

    def __post_init__(self):
        _require_aware("created_at", self.created_at)
        if (self.slot_start is None) != (self.slot_end is None):
            raise ValueError("slot_start and slot_end must be set together")
        if self.slot_start is None:
            if not self.is_urgent:  # invariant 7
                raise ValueError("a non-urgent job needs a slot")
        else:
            assert self.slot_end is not None
            _require_aware("slot_start", self.slot_start)
            _require_aware("slot_end", self.slot_end)
            if self.slot_start >= self.slot_end:
                raise ValueError(
                    f"Slot start time {self.slot_start} must be before slot end time {self.slot_end}"
                )
        if self.duration_minutes < 1:
            raise ValueError("duration_minutes must be at least 1")


@dataclass(frozen=True, slots=True)
class TechView:
    id: int
    label: str
    skill_ids: frozenset[int]
    shift_start: datetime
    shift_end: datetime
    is_available: bool
    free_at: datetime
    position: Location
    assigned_count: int

    def __post_init__(self):
        for name in ("shift_start", "shift_end", "free_at"):
            _require_aware(name, getattr(self, name))
        if self.shift_start >= self.shift_end:
            raise ValueError(
                f"Shift start time {self.shift_start} must be before shift end time {self.shift_end}"
            )
        if self.assigned_count < 0:
            raise ValueError("assigned_count cannot be negative")


@dataclass(frozen=True, slots=True)
class OrgConfig:
    workstation: Location
    scoring_strategy: str
    speed_mph: float
    urgent_buffer_minutes: float
    at_risk_minutes: float
    max_jobs_per_tech_per_day: int

    def __post_init__(self):
        if self.speed_mph <= 0:  # distance divides by this
            raise ValueError("speed_mph must be positive")
        if self.urgent_buffer_minutes < 0 or self.at_risk_minutes < 0:
            raise ValueError("buffer and threshold minutes cannot be negative")
        if self.max_jobs_per_tech_per_day < 1:
            raise ValueError("max_jobs_per_tech_per_day must be at least 1")


class ReasonCode(StrEnum):
    SKILL_MISMATCH = "skill_mismatch"
    AFTER_CLOSING = "after_closing"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class Reason:
    code: ReasonCode
    facts: Mapping[str, int | float | str]


@dataclass(frozen=True, slots=True)
class Explanation:
    reasons: tuple[Reason, ...]


class SlaLabel(StrEnum):
    OK = "ok"
    AT_RISK = "at_risk"
    BREACH = "breach"


@dataclass(frozen=True, slots=True)
class Assignment:
    job_id: int
    technician_id: int
    estimated_arrival: datetime
    slack_minutes: float
    sla_label: SlaLabel
    risk: float
    explanation: Explanation

    def __post_init__(self):
        _require_aware("estimated_arrival", self.estimated_arrival)
        if not 0.0 <= self.risk <= 1.0:  # internal ranking value, never shown
            raise ValueError("risk must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class Unassigned:
    job_id: int
    explanation: Explanation


@dataclass(frozen=True, slots=True)
class Plan:
    assignments: tuple[Assignment, ...]
    unassigned: tuple[Unassigned, ...]


@dataclass(frozen=True, slots=True)
class Candidate:
    """A technician who can take the job, with the arrival time SCORE needs."""

    technician_id: int
    estimated_arrival: datetime
    travel_minutes: float

    def __post_init__(self):
        _require_aware("estimated_arrival", self.estimated_arrival)


@dataclass(frozen=True, slots=True)
class Rejection:
    """A technician who cannot take the job, and the one reason why."""

    technician_id: int
    reason: Reason


@dataclass(frozen=True, slots=True)
class FilterResult:
    feasible: tuple[Candidate, ...]
    rejected: tuple[Rejection, ...]
