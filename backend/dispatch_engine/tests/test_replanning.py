"""Re-estimating the rest of a technician's day after a job ran over (ADR-031)."""

from datetime import timedelta

import pytest

from dispatch_engine.replanning import reestimate
from dispatch_engine.types import SlaLabel

from .builders import HERE, NOW, StubDistance, make_config, make_job, make_tech


def stops():
    """A: window to +60, 30 min. B: window to +100, 30 min. 10 minutes' drive between."""
    a = make_job(
        id=1,
        slot_start=NOW,
        slot_end=NOW + timedelta(minutes=60),
        duration_minutes=30,
    )
    b = make_job(
        id=2,
        slot_start=NOW,
        slot_end=NOW + timedelta(minutes=100),
        duration_minutes=30,
    )
    return [a, b]


def run(now):
    return reestimate(
        stops(),
        make_tech(),
        make_config(at_risk_minutes=30.0),
        StubDistance(10),
        now=now,
        position=HERE,
    )


def test_on_schedule_the_stops_keep_their_slack():
    first, second = run(NOW)
    # A: arrive +10, done +40. B: arrive +50 (10 drive after A).
    assert first.estimated_arrival == NOW + timedelta(minutes=10)
    assert first.slack_minutes == 50
    assert second.estimated_arrival == NOW + timedelta(minutes=50)
    assert second.slack_minutes == 50
    assert {first.sla_label, second.sla_label} == {SlaLabel.OK}


def test_a_late_start_pushes_every_later_stop_and_flags_the_ones_now_late():
    first, second = run(NOW + timedelta(minutes=60))
    # Free at +60: A arrive +70 (10 late), done +100; B arrive +110 (10 late).
    assert first.estimated_arrival == NOW + timedelta(minutes=70)
    assert first.slack_minutes == -10
    assert first.sla_label == SlaLabel.BREACH
    assert second.estimated_arrival == NOW + timedelta(minutes=110)
    assert second.slack_minutes == -10
    assert second.sla_label == SlaLabel.BREACH


def test_the_order_and_the_jobs_never_change():
    result = run(NOW + timedelta(minutes=60))
    assert [e.job_id for e in result] == [1, 2]  # as given, even when B has more room


def test_an_empty_rest_of_day_is_an_empty_answer():
    assert (
        reestimate(
            [], make_tech(), make_config(), StubDistance(10), now=NOW, position=HERE
        )
        == []
    )


def test_the_drive_starts_from_where_the_technician_finished():
    from dispatch_engine.distance import HaversineProvider
    from dispatch_engine.types import Location

    job = make_job(id=1, slot_start=NOW, slot_end=NOW + timedelta(hours=5))
    far = Location(HERE.lat + 0.5, HERE.lng)  # a long drive
    kwargs = {"now": NOW}
    near_result = reestimate(
        [job],
        make_tech(),
        make_config(),
        HaversineProvider(30.0),
        position=HERE,
        **kwargs,
    )
    far_result = reestimate(
        [job],
        make_tech(),
        make_config(),
        HaversineProvider(30.0),
        position=far,
        **kwargs,
    )
    assert near_result[0].estimated_arrival == NOW
    drive = (far_result[0].estimated_arrival - NOW).total_seconds() / 60
    assert drive == pytest.approx(HaversineProvider(30.0).travel_minutes(far, HERE))
    assert drive > 60
