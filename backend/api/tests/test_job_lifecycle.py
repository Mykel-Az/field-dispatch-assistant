"""The transition table is pure Python: these tests need no database."""

import itertools

import pytest

from dispatch_engine import lifecycle as lc

STATES = sorted(lc.TRANSITIONS)

ALLOWED = {
    (lc.UNASSIGNED, lc.ASSIGNED),
    (lc.UNASSIGNED, lc.CANCELED),
    (lc.ASSIGNED, lc.UNASSIGNED),
    (lc.ASSIGNED, lc.ONGOING),
    (lc.ASSIGNED, lc.CANCELED),
    (lc.ONGOING, lc.COMPLETED),
    (lc.ONGOING, lc.INCOMPLETE),
    (lc.ONGOING, lc.FAILED),
    (lc.INCOMPLETE, lc.UNASSIGNED),
}


@pytest.mark.parametrize(("src", "dst"), list(itertools.product(STATES, STATES)))
def test_every_status_pair_matches_the_adr(src, dst):  # invariant 10
    expected = (src, dst) in ALLOWED
    assert lc.JobLifecycleEngine.can_transition(src, dst) is expected
    if expected:
        lc.JobLifecycleEngine.check_transition(src, dst)
    else:
        with pytest.raises(lc.IllegalTransition):
            lc.JobLifecycleEngine.check_transition(src, dst)


def test_all_seven_statuses_are_in_the_table():
    assert set(STATES) == {
        "unassigned", "assigned", "ongoing", "completed",
        "incomplete", "failed", "canceled",
    }  # fmt: skip


def test_terminal_statuses_have_no_way_out():  # invariant 8
    assert lc.TERMINAL == {lc.COMPLETED, lc.FAILED, lc.CANCELED}
    assert all(not lc.TRANSITIONS[s] for s in lc.TERMINAL)


def test_incomplete_only_returns_to_the_queue():  # invariant 9
    assert lc.TRANSITIONS[lc.INCOMPLETE] == {lc.UNASSIGNED}
