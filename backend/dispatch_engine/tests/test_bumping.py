"""Force-assign: the bump rule and the urgent-fit check (ADR-029)."""

import random
from datetime import timedelta

from hypothesis import given
from hypothesis import strategies as st

from dispatch_engine.bumping import BumpCandidate, pick_bump, urgent_fit
from dispatch_engine.distance import HaversineProvider
from dispatch_engine.types import Commitment, Location, Priority, SlaLabel

from .builders import NOW, make_config, make_job, make_tech

DISTANCE = HaversineProvider(speed_mph=30.0)
BASE = Location(30.0, -97.0)


def cand(job_id, priority=Priority.NORMAL, slack=60.0):
    return BumpCandidate(job_id, priority, slack)


def urgent(**overrides):
    return make_job(
        id=900,
        is_urgent=True,
        slot_start=None,
        slot_end=None,
        location=BASE,
        duration_minutes=30,
        **overrides,
    )


# ---- who is bumped first ---------------------------------------------------------
def test_nothing_to_bump_gives_none():
    assert pick_bump([]) is None


def test_the_lowest_priority_goes_first():
    picked = pick_bump(
        [cand(1, Priority.HIGH), cand(2, Priority.LOW), cand(3, Priority.NORMAL)]
    )
    assert picked == 2


def test_among_equal_priority_the_job_with_most_slack_goes_first():
    assert pick_bump([cand(1, slack=20), cand(2, slack=300), cand(3, slack=90)]) == 2


def test_a_full_tie_goes_to_the_lowest_id():
    assert pick_bump([cand(7), cand(4), cand(9)]) == 4


@given(st.permutations([cand(1), cand(2, Priority.LOW), cand(3, slack=5), cand(4)]))
def test_the_choice_does_not_depend_on_input_order(perm):
    assert pick_bump(perm) == 2


def test_priority_beats_slack():
    """A high-priority job with lots of slack is still kept over a low one with none."""
    assert pick_bump([cand(1, Priority.HIGH, 500), cand(2, Priority.LOW, 0)]) == 2


# ---- does the urgent job fit -----------------------------------------------------
def test_a_free_technician_meets_the_deadline():
    tech = make_tech(position=BASE, home=BASE)
    fit = urgent_fit(urgent(), tech, make_config(), DISTANCE, NOW)
    assert fit.meets_deadline and fit.arrival == NOW
    assert fit.slack_minutes >= 60  # the whole urgent buffer is spare


def test_a_technician_booked_solid_misses_it_and_the_slack_goes_negative():
    block = Commitment(NOW, NOW + timedelta(hours=4), BASE)
    tech = make_tech(
        position=BASE,
        home=BASE,
        commitments=(block,),
        free_at=block.end,
        assigned_count=1,
    )
    fit = urgent_fit(urgent(), tech, make_config(), DISTANCE, NOW)
    assert not fit.meets_deadline
    assert fit.label == SlaLabel.BREACH
    assert fit.arrival == block.end


def test_removing_the_blocking_job_makes_it_fit():
    """What a bump does: the same technician without that commitment reaches it on time."""
    block = Commitment(NOW, NOW + timedelta(hours=4), BASE)
    busy = make_tech(position=BASE, home=BASE, commitments=(block,), free_at=block.end)
    freed = make_tech(position=BASE, home=BASE)
    config = make_config()
    assert not urgent_fit(urgent(), busy, config, DISTANCE, NOW).meets_deadline
    assert urgent_fit(urgent(), freed, config, DISTANCE, NOW).meets_deadline


def test_a_gap_before_a_later_commitment_is_enough():
    later = Commitment(NOW + timedelta(hours=3), NOW + timedelta(hours=4), BASE)
    tech = make_tech(position=BASE, home=BASE, commitments=(later,), free_at=later.end)
    fit = urgent_fit(urgent(), tech, make_config(), DISTANCE, NOW)
    assert fit.meets_deadline and fit.arrival == NOW


def test_shuffling_candidates_is_irrelevant_for_many_sizes():
    rng = random.Random(7)
    items = [
        cand(i, Priority(rng.choice([1, 2, 3])), rng.uniform(0, 400)) for i in range(12)
    ]
    expected = pick_bump(items)
    for _ in range(20):
        rng.shuffle(items)
        assert pick_bump(items) == expected
