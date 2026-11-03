from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


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
    id: str
    label: str
    location: Location
    is_urgent: bool
    created_at: datetime
    slot_start: datetime | None
    slot_end: datetime | None
    duration_minutes: int
    acceptable_skill_ids: frozenset[int]

    def __post_init__(self):
        if self.slot_start and self.slot_end and self.slot_start > self.slot_end:
            raise ValueError(
                f"Slot start time {self.slot_start} cannot be after slot end time {self.slot_end}"
            )


@dataclass(frozen=True, slots=True)
class TechView:
    id: str
    label: str
    skill_ids: frozenset[int]
    shift_start: datetime | None
    shift_end: datetime | None
    is_available: bool
    free_at: datetime
    position: Location
    assigned_count: int

    def __post_init__(self):
        if self.shift_start and self.shift_end and self.shift_start > self.shift_end:
            raise ValueError(
                f"Shift start time {self.shift_start} cannot be after shift end time {self.shift_end}"
            )


@dataclass(frozen=True, slots=True)
class OrgConfig:
    workstation: Location
    scoring_strategy: str
    speed_mph: float
    urgent_buffer_mintes: float
    at_risk_minutes: float
    max_jobs_per_tech_per_day: int


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
    job_id: str
    technician_id: str
    estimated_arrival: datetime
    slack_minutes: float
    sla_label: SlaLabel
    risk: float
    explanation: Explanation


@dataclass(frozen=True, slots=True)
class unassigned:
    job_id: str
    explanation: Explanation


@dataclass(frozen=True, slots=True)
class Plan:
    assignments: tuple[Assignment, ...]
    unassigned: tuple[unassigned, ...]
