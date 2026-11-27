"""Offering times for a job that has no window yet (ADR-032)."""

from datetime import timedelta

from dispatch_engine.slots import earliest_slots
from dispatch_engine.types import Commitment

from .builders import HERE, NOW, StubDistance, make_job, make_tech


def job(**over):
    return make_job(
        id=1,
        slot_start=NOW,
        slot_end=NOW + timedelta(hours=8),
        duration_minutes=60,
        **over,
    )


def test_each_technician_gets_their_earliest_start_soonest_first():
    busy = make_tech(
        id=1,
        free_at=NOW + timedelta(hours=2),
        commitments=(Commitment(NOW, NOW + timedelta(hours=2), HERE),),
    )
    free = make_tech(id=2)
    slots = earliest_slots(job(), [busy, free], StubDistance(0), NOW)
    assert [s.technician_id for s in slots] == [2, 1]  # the free one first, though id 2
    assert slots[0].start == NOW and slots[0].end == NOW + timedelta(hours=1)
    assert slots[1].start == NOW + timedelta(hours=2)


def test_equal_starts_go_to_the_lower_id():
    slots = earliest_slots(
        job(), [make_tech(id=3), make_tech(id=2)], StubDistance(0), NOW
    )
    assert [s.technician_id for s in slots] == [2, 3]


def test_the_slot_includes_the_drive():
    slot = earliest_slots(job(), [make_tech()], StubDistance(15), NOW)[0]
    assert slot.start == NOW + timedelta(minutes=15) and slot.travel_minutes == 15


def test_a_technician_who_cannot_take_the_job_is_not_offered():
    wrong = make_tech(id=1, skill_ids=frozenset({9}))
    gone = make_tech(id=2, is_available=False)
    full = make_tech(id=3, assigned_count=4)
    assert earliest_slots(job(), [wrong, gone, full], StubDistance(0), NOW, 4) == []


def test_nobody_means_an_empty_list():
    assert earliest_slots(job(), [], StubDistance(0), NOW) == []
