"""After a job runs over, the technician's later stops are restated (ADR-031)."""

import datetime

import pytest

from api.models import Job, JobStatus, Skill
from api.services import scheduling
from dispatch_engine.clock import FixedClock

from .conftest import client_for, make_job, technician_of

UTC = datetime.UTC
DAY = datetime.date(2026, 11, 2)
START = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=UTC)  # 9:00 in Chicago


def at(minutes):
    return START + datetime.timedelta(minutes=minutes)


@pytest.fixture
def org(org_a):
    org_a.lat, org_a.lng = 30.30, -97.70
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    return org_a


@pytest.fixture
def tech(org, technician_a):
    technician = technician_of(technician_a)
    technician.skills.add(Skill.objects.get(name="HVAC"))
    return technician


def job(org, tech, status, position, window_end, minutes=60, **fields):
    """Everything at one address, so travel is zero and the numbers are easy to check."""
    return make_job(
        org,
        status=status,
        technician=tech,
        sequence_position=position,
        scheduled_date=DAY,
        lat=30.30,
        lng=-97.70,
        slot_start=at(0),
        slot_end=at(window_end),
        estimated_duration_minutes=minutes,
        estimated_arrival=at(0),
        plan_explanation={
            "reasons": [],
            "sentence": "x",
            "sla_label": "ok",
            "slack_minutes": 99,
        },
        **fields,
    )


def run(tech, finished, minutes_after_start):
    return scheduling.reestimate_after_finish(
        technician=tech,
        finished_job=finished,
        clock=FixedClock(at(minutes_after_start)),
    )


def test_a_job_that_ran_over_pushes_later_stops_and_flags_the_late_ones(org, tech):
    done = job(org, tech, JobStatus.COMPLETED, 1, 60)
    b = job(org, tech, JobStatus.ASSIGNED, 2, 100)  # window to +100, takes 60
    c = job(org, tech, JobStatus.ASSIGNED, 3, 400)
    late = run(tech, done, 90)  # finished at +90, an hour of overrun
    b, c = Job.objects.get(pk=b.pk), Job.objects.get(pk=c.pk)
    assert b.estimated_arrival == at(90)  # same address: no drive
    assert b.plan_explanation["slack_minutes"] == 10  # +100 - +90
    assert b.plan_explanation["sla_label"] == "at_risk"
    assert c.estimated_arrival == at(150)  # after B's 60 minutes
    assert c.plan_explanation["slack_minutes"] == 250
    assert late == 0


def test_a_stop_pushed_past_its_window_is_reported_late(org, tech):
    done = job(org, tech, JobStatus.COMPLETED, 1, 60)
    b = job(org, tech, JobStatus.ASSIGNED, 2, 100)
    assert run(tech, done, 130) == 1
    saved = Job.objects.get(pk=b.pk)
    assert saved.plan_explanation["slack_minutes"] == -30
    assert saved.plan_explanation["sla_label"] == "breach"


def test_only_times_change_never_the_technician_the_order_or_the_version(org, tech):
    done = job(org, tech, JobStatus.COMPLETED, 1, 60)
    b = job(org, tech, JobStatus.ASSIGNED, 2, 100)
    c = job(org, tech, JobStatus.ASSIGNED, 3, 100)  # tighter than B would suggest
    before = {j.pk: (j.technician_id, j.sequence_position, j.version) for j in (b, c)}
    run(tech, done, 130)
    after = {
        j.pk: (j.technician_id, j.sequence_position, j.version)
        for j in Job.objects.filter(pk__in=before)
    }
    assert after == before
    assert Job.objects.get(pk=b.pk).sequence_position == 2


def test_the_explanation_keeps_its_reasons_and_sentence(org, tech):
    done = job(org, tech, JobStatus.COMPLETED, 1, 60)
    b = job(org, tech, JobStatus.ASSIGNED, 2, 100)
    run(tech, done, 30)
    saved = Job.objects.get(pk=b.pk).plan_explanation
    assert saved["sentence"] == "x" and saved["reasons"] == []


def test_an_early_finish_pulls_later_stops_sooner(org, tech):
    done = job(org, tech, JobStatus.COMPLETED, 1, 60)
    b = job(org, tech, JobStatus.ASSIGNED, 2, 100)
    Job.objects.filter(pk=b.pk).update(estimated_arrival=at(90), slot_start=at(0))
    run(tech, done, 20)
    assert Job.objects.get(pk=b.pk).estimated_arrival == at(20)


def test_nothing_left_to_restate_is_fine(org, tech):
    done = job(org, tech, JobStatus.COMPLETED, 1, 60)
    assert run(tech, done, 90) == 0


def test_another_technicians_stops_are_not_touched(org, tech):
    from .conftest import Role, make_user

    colleague = technician_of(make_user(org, Role.TECHNICIAN, "second@example.com"))
    done = job(org, tech, JobStatus.COMPLETED, 1, 60)
    theirs = job(org, colleague, JobStatus.ASSIGNED, 1, 100)
    run(tech, done, 130)
    assert Job.objects.get(pk=theirs.pk).estimated_arrival == at(0)


def test_a_stop_the_technician_already_started_is_left_alone(org, tech):
    done = job(org, tech, JobStatus.COMPLETED, 1, 60)
    started = job(org, tech, JobStatus.ONGOING, 2, 100)
    run(tech, done, 130)
    assert Job.objects.get(pk=started.pk).estimated_arrival == at(0)


def test_completing_through_the_api_restates_the_next_stop(
    org, tech, technician_a, monkeypatch
):
    monkeypatch.setattr(scheduling, "SystemClock", lambda: FixedClock(at(130)))
    ongoing = job(org, tech, JobStatus.ONGOING, 1, 60)
    b = job(org, tech, JobStatus.ASSIGNED, 2, 100)
    response = client_for(technician_a).post(
        f"/api/technician/me/jobs/{ongoing.pk}/complete/"
    )
    assert response.status_code == 200
    saved = Job.objects.get(pk=b.pk)
    assert saved.estimated_arrival == at(130)
    assert saved.plan_explanation["sla_label"] == "breach"


def test_a_failure_while_restating_never_undoes_the_completion(
    org, tech, technician_a, monkeypatch
):
    def boom(**_):
        raise RuntimeError("no")

    monkeypatch.setattr(scheduling, "reestimate_after_finish", boom)
    ongoing = job(org, tech, JobStatus.ONGOING, 1, 60)
    response = client_for(technician_a).post(
        f"/api/technician/me/jobs/{ongoing.pk}/complete/"
    )
    assert response.status_code == 200
    assert Job.objects.get(pk=ongoing.pk).status == JobStatus.COMPLETED
