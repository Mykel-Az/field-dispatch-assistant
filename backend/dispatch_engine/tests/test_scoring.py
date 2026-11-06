"""SCORE: slack, the OK / At risk / Breach label, risk, and the two strategies."""

from datetime import timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from dispatch_engine.scoring import (
    RISK_HORIZON_FACTOR,
    STRATEGIES,
    deadline_for,
    get_strategy,
    risk_score,
    score_candidates,
    sla_label,
)
from dispatch_engine.types import SlaLabel

from .builders import NOW, make_candidate, make_config, make_job, make_tech


# ---- deadline ---------------------------------------------------------------
def test_a_job_with_a_window_is_due_at_the_end_of_the_window():
    job = make_job(slot_end=NOW + timedelta(hours=5))
    assert deadline_for(job, 20, make_config()) == NOW + timedelta(hours=5)


def test_an_urgent_job_is_due_after_creation_plus_travel_plus_the_buffer():
    job = make_job(is_urgent=True, slot_start=None, slot_end=None)
    config = make_config(urgent_buffer_minutes=60)
    assert deadline_for(job, 20, config) == NOW + timedelta(minutes=80)


# ---- label ------------------------------------------------------------------
@pytest.mark.parametrize(
    "slack, expected",
    [
        (-1, SlaLabel.BREACH),
        (-0.1, SlaLabel.BREACH),
        (0, SlaLabel.AT_RISK),  # on the deadline is on time, but with no margin
        (29.9, SlaLabel.AT_RISK),
        (30, SlaLabel.OK),
        (500, SlaLabel.OK),
    ],
)
def test_label_thresholds(slack, expected):
    assert sla_label(slack, at_risk_minutes=30) == expected


# ---- risk -------------------------------------------------------------------
def test_risk_is_one_with_no_slack_and_zero_with_plenty():
    horizon = RISK_HORIZON_FACTOR * 30
    assert risk_score(0, 30) == 1.0
    assert risk_score(-50, 30) == 1.0
    assert risk_score(horizon, 30) == 0.0
    assert 0 < risk_score(horizon / 2, 30) < 1


@given(st.floats(-1e4, 1e4), st.floats(-1e4, 1e4), st.floats(0, 600))
def test_risk_stays_in_range_and_never_rises_as_slack_grows(a, b, at_risk):
    low, high = sorted((a, b))
    assert 0.0 <= risk_score(low, at_risk) <= 1.0
    assert risk_score(low, at_risk) >= risk_score(high, at_risk)


# ---- scoring one job --------------------------------------------------------
def test_slack_label_and_risk_come_from_arrival_and_deadline():
    job = make_job(slot_end=NOW + timedelta(hours=3))
    candidate = make_candidate(estimated_arrival=NOW + timedelta(hours=2, minutes=45))
    (scored,) = score_candidates(job, [candidate], [make_tech()], make_config())
    assert scored.slack_minutes == 15
    assert scored.sla_label == SlaLabel.AT_RISK
    assert 0 < scored.risk < 1


def test_arriving_after_the_window_is_a_breach_but_still_scored():
    job = make_job(slot_end=NOW + timedelta(hours=3))
    candidate = make_candidate(estimated_arrival=NOW + timedelta(hours=3, minutes=10))
    (scored,) = score_candidates(job, [candidate], [make_tech()], make_config())
    assert scored.slack_minutes == -10
    assert scored.sla_label == SlaLabel.BREACH
    assert scored.risk == 1.0


def test_no_candidates_means_no_scores():
    assert score_candidates(make_job(), [], [make_tech()], make_config()) == ()


# ---- strategies -------------------------------------------------------------
def _near_but_busy_vs_far_but_free():
    candidates = [
        make_candidate(technician_id=1, travel_minutes=5),
        make_candidate(technician_id=2, travel_minutes=25),
    ]
    techs = [make_tech(id=1, assigned_count=3), make_tech(id=2, assigned_count=0)]
    return candidates, techs


def test_nearest_picks_the_closest_even_if_busy():
    candidates, techs = _near_but_busy_vs_far_but_free()
    ranked = score_candidates(
        make_job(), candidates, techs, make_config(scoring_strategy="nearest")
    )
    assert [s.technician_id for s in ranked] == [1, 2]


def test_balanced_prefers_the_free_technician_over_a_slightly_closer_busy_one():
    candidates, techs = _near_but_busy_vs_far_but_free()
    ranked = score_candidates(
        make_job(), candidates, techs, make_config(scoring_strategy="balanced")
    )
    assert [s.technician_id for s in ranked] == [2, 1]


def test_equal_costs_are_ranked_by_technician_id():
    candidates = [make_candidate(technician_id=i) for i in (3, 1, 2)]
    techs = [make_tech(id=i) for i in (3, 1, 2)]
    ranked = score_candidates(make_job(), candidates, techs, make_config())
    assert [s.technician_id for s in ranked] == [1, 2, 3]


@pytest.mark.parametrize(
    "idle_travel, expected_first",
    [
        (
            18,
            2,
        ),  # the idle technician is 8 minutes farther: within the band, so load wins
        (21, 1),  # 11 minutes farther: beyond the band, so the closest wins
    ],
)
def test_nearest_lets_load_outweigh_about_ten_minutes_of_driving(
    idle_travel, expected_first
):
    candidates = [
        make_candidate(technician_id=1, travel_minutes=10),  # three jobs already
        make_candidate(technician_id=2, travel_minutes=idle_travel),  # idle
    ]
    techs = [make_tech(id=1, assigned_count=3), make_tech(id=2, assigned_count=0)]
    config = make_config(scoring_strategy="nearest")
    ranked = score_candidates(make_job(), candidates, techs, config)
    assert ranked[0].technician_id == expected_first


@pytest.mark.parametrize("name", ["nearest", "balanced"])
def test_every_strategy_counts_every_factor(name):
    """More travel, more load or more risk never makes a technician cheaper."""
    strategy = get_strategy(name)
    config = make_config()
    base = {"travel_minutes": 10.0, "assigned_count": 0, "risk": 0.0, "config": config}
    cost = strategy.cost(**base)
    assert strategy.cost(**{**base, "travel_minutes": 20.0}) > cost
    assert strategy.cost(**{**base, "assigned_count": 1}) > cost
    assert strategy.cost(**{**base, "risk": 1.0}) > cost


# ---- registry ---------------------------------------------------------------
def test_both_strategies_are_registered():
    assert set(STRATEGIES) == {"nearest", "balanced"}


def test_an_unknown_strategy_name_is_refused_with_the_valid_names():
    with pytest.raises(ValueError, match="unknown scoring strategy.*balanced.*nearest"):
        get_strategy("cheapest")


# ---- determinism (invariant 14) ---------------------------------------------
@st.composite
def pools(draw):
    rows = draw(
        st.lists(
            st.tuples(
                st.integers(0, 120),  # travel minutes
                st.integers(0, 6),  # jobs already assigned
                st.integers(0, 600),  # arrival offset in minutes
            ),
            min_size=1,
            max_size=8,
        )
    )
    candidates = [
        make_candidate(
            technician_id=i,
            travel_minutes=travel,
            estimated_arrival=NOW + timedelta(minutes=arrival),
        )
        for i, (travel, _, arrival) in enumerate(rows, start=1)
    ]
    techs = [
        make_tech(id=i, assigned_count=n) for i, (_, n, _) in enumerate(rows, start=1)
    ]
    return candidates, techs


@given(pools(), st.sampled_from(["nearest", "balanced"]), st.randoms())
def test_same_inputs_give_the_same_ranking_in_any_input_order(pool, strategy, rnd):
    candidates, techs = pool
    config = make_config(scoring_strategy=strategy)
    job = make_job()
    first = score_candidates(job, candidates, techs, config)
    shuffled = list(candidates)
    rnd.shuffle(shuffled)
    assert score_candidates(job, shuffled, techs, config) == first
    assert score_candidates(job, candidates, techs, config) == first
    assert list(first) == sorted(first, key=lambda s: (s.cost, s.technician_id))
