"""Explanations: the sentence is a template over the structured reasons."""

import re
from datetime import timedelta

from dispatch_engine.assignment import assign_jobs
from dispatch_engine.clock import FixedClock
from dispatch_engine.explanations import assignment_sentence, unassigned_sentence

from .builders import NOW, StubDistance, make_config, make_job, make_tech


def at(minutes):
    return NOW + timedelta(minutes=minutes)


def plan_for(jobs, techs, travel=12, config=None):
    return assign_jobs(
        jobs, techs, config or make_config(), StubDistance(travel), FixedClock(NOW)
    )


def sentences(plan, jobs, techs):
    by_job = {j.id: j for j in jobs}
    by_tech = {t.id: t for t in techs}
    return (
        [assignment_sentence(a, by_job[a.job_id], by_tech) for a in plan.assignments],
        [unassigned_sentence(u, by_job[u.job_id], by_tech) for u in plan.unassigned],
    )


JOB = make_job(id=1, label="AC not cooling", slot_start=at(0), slot_end=at(60))


def test_a_normal_assignment_reads_in_plain_english():
    techs = [make_tech(id=1, label="Sam"), make_tech(id=2, label="Alex")]
    done, _ = sentences(plan_for([JOB], techs), [JOB], techs)
    assert done == [
        (
            "Sam was chosen for “AC not cooling”: 12 min away, would arrive with 48 min to spare."
            " Best of 2 available technicians (balanced strategy)."
        )
    ]


def test_a_single_candidate_has_no_best_of_line():
    techs = [make_tech(id=1, label="Sam")]
    (sentence,), _ = sentences(plan_for([JOB], techs), [JOB], techs)
    assert "Best of" not in sentence


def test_a_tight_arrival_says_so():
    tight = make_job(id=1, label="AC not cooling", slot_start=at(0), slot_end=at(20))
    techs = [make_tech(id=1, label="Sam")]
    (sentence,), _ = sentences(plan_for([tight], techs), [tight], techs)
    assert "only 8 min to spare" in sentence


def test_a_late_arrival_says_how_late():
    late = make_job(id=1, label="AC not cooling", slot_start=at(0), slot_end=at(5))
    techs = [make_tech(id=1, label="Sam")]
    (sentence,), _ = sentences(plan_for([late], techs), [late], techs)
    assert "7 min after the deadline" in sentence


def test_an_urgent_job_over_the_limit_says_why():
    rush = make_job(
        id=1, label="Gas leak", is_urgent=True, slot_start=None, slot_end=None
    )
    techs = [make_tech(id=1, label="Sam", assigned_count=4)]
    (sentence,), _ = sentences(plan_for([rush], techs), [rush], techs)
    assert (
        "Sam already has 4 jobs today (limit 4), but this job is urgent"
        " and no technician under the limit could take it." in sentence
    )


def test_a_technician_at_the_limit_is_named_in_the_unassigned_sentence():
    techs = [make_tech(id=1, label="Sam", assigned_count=4)]
    _, (sentence,) = sentences(plan_for([JOB], techs), [JOB], techs)
    assert sentence == (
        "No technician can take \u201cAC not cooling\u201d: Sam has reached the daily limit of 4 jobs."
    )


def test_an_unassigned_job_names_every_technician_and_why():
    techs = [
        make_tech(id=1, label="Sam", skill_ids=frozenset({9})),
        make_tech(id=2, label="Alex", is_available=False),
        make_tech(id=3, label="Jo", shift_end=at(5)),
    ]
    _, (sentence,) = sentences(plan_for([JOB], techs), [JOB], techs)
    assert sentence == (
        "No technician can take “AC not cooling”: Sam does not have a matching skill; "
        "Alex is unavailable; Jo would arrive 7 min after closing."
    )


def test_no_technicians_has_its_own_sentence():
    _, (sentence,) = sentences(plan_for([JOB], []), [JOB], [])
    assert sentence == "There are no technicians to assign “AC not cooling” to."


def test_every_number_in_a_sentence_is_in_the_facts():
    """The explanation of record is the facts; the text may not invent a number."""
    techs = [
        make_tech(id=1, label="Sam"),
        make_tech(id=2, label="Alex", is_available=False),
    ]
    tight = make_job(id=1, label="AC not cooling", slot_start=at(0), slot_end=at(20))
    plan = plan_for([tight], techs)
    done, _ = sentences(plan, [tight], techs)
    facts = {
        f"{value:g}" if isinstance(value, float) else str(value)
        for reason in plan.assignments[0].explanation.reasons
        for value in reason.facts.values()
    }
    for number in re.findall(r"\d+(?:\.\d+)?", done[0]):
        assert number in facts, f"{number} is not in the facts {facts}"


def test_the_assignment_keeps_the_reasons_the_others_were_rejected():
    techs = [
        make_tech(id=1, label="Sam"),
        make_tech(id=2, label="Alex", is_available=False),
    ]
    plan = plan_for([JOB], techs)
    codes = [r.code for r in plan.assignments[0].explanation.reasons]
    assert "unavailable" in codes
