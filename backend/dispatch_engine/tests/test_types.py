from datetime import datetime, timedelta, timezone

import pytest

from dispatch_engine.types import JobView, Location


def create_job_view(**Kwargs) -> JobView:
    now = datetime.now(timezone.utc)
    defaults = {
        "id": "job1",
        "label": "Test Job",
        "location": Location(lat=30.2672, lng=-97.7431),
        "is_urgent": False,
        "created_at": now,
        "slot_start": now + timedelta(hours=1),
        "slot_end": now + timedelta(hours=2),
        "duration_minutes": 60,
        "acceptable_skill_ids": frozenset({1, 2}),
    }
    defaults.update(Kwargs)
    return JobView(**defaults)


def test_valid_job_view_instantiation():
    job = create_job_view()
    assert job.id == "job1"
    assert job.label == "Test Job"
    assert job.location.lat == 30.2672
    assert job.location.lng == -97.7431
    assert not job.is_urgent
    assert job.duration_minutes == 60
    assert job.acceptable_skill_ids == frozenset({1, 2})


def test_invalid_slot_times_raises_value_error():
    now = datetime.now(timezone.utc)
    with pytest.raises(
        ValueError, match="Slot start time .* cannot be after slot end time .*"
    ):
        create_job_view(
            slot_start=now + timedelta(hours=2), slot_end=now + timedelta(hours=1)
        )


def test_valid_none_slots():
    job = create_job_view(slot_start=None, slot_end=None)
    assert job.slot_start is None
    assert job.slot_end is None
