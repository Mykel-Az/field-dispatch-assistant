"""generate_schedule: the engine's plan, saved safely."""

import datetime

import pytest

from api.adapters import OrganizationNotConfigured
from api.models import Job, JobStatus, JobStatusHistory, Skill
from api.services import jobs as job_service
from api.services import scheduling
from dispatch_engine.clock import FixedClock

from .conftest import Role, make_job, make_user, technician_of

UTC = datetime.UTC
NOW = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=UTC)  # 9:00 in Chicago (CST)
DAY = datetime.date(2026, 11, 2)
CLOCK = FixedClock(NOW)


def at(hour, minute=0):
    return datetime.datetime(2026, 11, 2, hour, minute, tzinfo=UTC)


@pytest.fixture
def org(org_a):
    org_a.lat, org_a.lng = 30.27, -97.74
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.save()
    return org_a


@pytest.fixture
def hvac(db):
    return Skill.objects.get(name="HVAC")


@pytest.fixture
def tech(org, technician_a, hvac):
    technician = technician_of(technician_a)
    technician.skills.add(hvac)
    return technician


def job(org, **fields):
    """A job in the afternoon of DAY: slot 12:00-14:00 local (18:00-20:00 UTC)."""
    fields.setdefault("slot_start", at(18))
    fields.setdefault("slot_end", at(20))
    fields.setdefault("scheduled_date", DAY)
    fields.setdefault("lat", 30.30)
    fields.setdefault("lng", -97.70)
    made = make_job(org, **fields)
    Job.objects.filter(pk=made.pk).update(created_at=NOW)
    return Job.objects.get(pk=made.pk)


def run(org, actor, **kwargs):
    return scheduling.generate_schedule(
        organization=org, actor=actor, plan_date=DAY, clock=CLOCK, **kwargs
    )


def fresh(j):
    return Job.objects.get(pk=j.pk)


# ---- the happy path ---------------------------------------------------------
def test_an_unassigned_job_is_assigned_and_saved(org, dispatcher_a, tech):
    j = job(org)
    result = run(org, dispatcher_a)
    saved = fresh(j)
    assert saved.status == JobStatus.ASSIGNED and saved.technician_id == tech.pk
    assert saved.sequence_position == 1
    assert saved.estimated_arrival == at(
        18
    )  # a slot job is never planned before it opens
    assert [p.job_id for p in result.assigned] == [j.pk]


def test_the_history_row_names_the_dispatcher_and_the_technician(
    org, dispatcher_a, tech
):
    j = job(org)
    run(org, dispatcher_a)
    row = JobStatusHistory.objects.get(job=j, to_status="assigned")
    assert row.changed_by == dispatcher_a and row.technician_id == tech.pk


def test_the_explanation_is_stored_with_reasons_and_a_sentence(org, dispatcher_a, tech):
    j = job(org)
    run(org, dispatcher_a)
    stored = fresh(j).plan_explanation
    assert stored["reasons"][0]["code"] == "assigned"
    assert stored["reasons"][0]["facts"]["technician_id"] == tech.pk
    assert "was chosen for" in stored["sentence"]


def test_jobs_get_consecutive_stop_numbers_in_planned_order(org, dispatcher_a, tech):
    early = job(org, slot_start=at(15), slot_end=at(17))
    late = job(org, slot_start=at(19), slot_end=at(21))
    run(org, dispatcher_a)
    assert (fresh(early).sequence_position, fresh(late).sequence_position) == (1, 2)


def test_new_stops_continue_after_the_technicians_existing_ones(
    org, dispatcher_a, tech
):
    existing = job(
        org,
        slot_start=at(15),
        slot_end=at(16),
        status=JobStatus.ASSIGNED,
        technician=tech,
        sequence_position=1,
        estimated_arrival=at(15),
    )
    new = job(org, slot_start=at(19), slot_end=at(21))
    run(org, dispatcher_a)
    assert fresh(existing).sequence_position == 1  # untouched (invariant 12)
    assert fresh(new).sequence_position == 2
    assert fresh(new).technician_id == tech.pk


def test_running_twice_changes_nothing_the_second_time(org, dispatcher_a, tech):
    j = job(org)
    run(org, dispatcher_a)
    version = fresh(j).version
    second = run(org, dispatcher_a)
    assert second.assigned == [] and second.unassigned == []
    assert fresh(j).version == version
    assert (
        JobStatusHistory.objects.filter(job=j).count() == 1
    )  # one assignment, not two


# ---- scope ------------------------------------------------------------------
def test_only_jobs_for_the_plan_date_are_planned(org, dispatcher_a, tech):
    other_day = job(org, scheduled_date=DAY + datetime.timedelta(days=1))
    run(org, dispatcher_a)
    assert fresh(other_day).status == JobStatus.UNASSIGNED


def test_another_organizations_jobs_and_technicians_are_never_touched(
    org, org_b, dispatcher_a, tech, head_b, hvac
):
    theirs = job(org_b)
    their_tech = make_user(org_b, Role.TECHNICIAN, "tech-b@example.com")
    technician_of(their_tech).skills.add(hvac)
    mine = job(org)
    run(org, dispatcher_a)
    assert fresh(theirs).status == JobStatus.UNASSIGNED
    assert fresh(mine).technician_id == tech.pk


def test_a_job_without_a_location_is_skipped_not_assigned(org, dispatcher_a, tech):
    j = job(org, geocode_status="failed", lat=None, lng=None)
    result = run(org, dispatcher_a)
    assert fresh(j).status == JobStatus.UNASSIGNED
    assert [(s.job_id, s.code) for s in result.skipped] == [(j.pk, "needs_location")]
    assert result.assigned == [] and result.unassigned == []


def test_an_unconfigured_organization_cannot_be_planned(org_a, dispatcher_a):
    with pytest.raises(OrganizationNotConfigured):
        run(org_a, dispatcher_a)


# ---- expected "nobody" outcomes ---------------------------------------------
def test_a_job_nobody_can_take_stays_unassigned_with_a_stored_reason(
    org, dispatcher_a, tech
):
    other_skill = Skill.objects.exclude(name="HVAC").first()
    j = job(org, skills=[other_skill])
    result = run(org, dispatcher_a)
    assert fresh(j).status == JobStatus.UNASSIGNED
    assert [u.job_id for u in result.unassigned] == [j.pk]
    stored = fresh(j).plan_explanation
    assert stored["reasons"][0]["code"] == "no_feasible_technician"
    assert "does not have a matching skill" in stored["sentence"]


def test_no_technicians_gives_unassigned_jobs_not_an_error(org, dispatcher_a):
    j = job(org)
    result = run(org, dispatcher_a)
    assert [u.job_id for u in result.unassigned] == [j.pk]
    assert "no technicians" in result.unassigned[0].sentence


def test_the_organizations_daily_limit_is_applied(org, dispatcher_a, tech):
    org.max_jobs_per_tech_per_day = 1
    org.save()
    first = job(org, slot_start=at(15), slot_end=at(17))
    second = job(org, slot_start=at(19), slot_end=at(21))
    result = run(org, dispatcher_a)
    assert fresh(first).status == JobStatus.ASSIGNED
    assert fresh(second).status == JobStatus.UNASSIGNED
    assert "daily limit of 1" in result.unassigned[0].sentence


def test_an_ongoing_job_counts_toward_the_limit(org, dispatcher_a, tech):
    org.max_jobs_per_tech_per_day = 1
    org.save()
    job(
        org,
        status=JobStatus.ONGOING,
        technician=tech,
        arrived_at=at(15),
        slot_start=at(15),
        slot_end=at(16),
        sequence_position=1,
    )
    waiting = job(org)
    run(org, dispatcher_a)
    assert fresh(waiting).status == JobStatus.UNASSIGNED


# ---- stored explanations stay honest ----------------------------------------
def test_assigning_by_hand_clears_an_old_unassigned_reason(org, dispatcher_a, tech):
    j = job(org)
    Job.objects.filter(pk=j.pk).update(plan_explanation={"sentence": "old"})
    saved = job_service.transition(fresh(j), "assigned", dispatcher_a, technician=tech)
    assert saved.plan_explanation is None


def test_the_explanation_survives_the_technician_starting_the_job(
    org, dispatcher_a, tech
):
    j = job(org)
    run(org, dispatcher_a)
    job_service.transition(fresh(j), "ongoing", dispatcher_a)
    assert fresh(j).plan_explanation is not None


# ---- all or nothing ---------------------------------------------------------
def test_a_failure_part_way_leaves_nothing_half_planned(
    org, dispatcher_a, tech, monkeypatch
):
    first = job(org, slot_start=at(15), slot_end=at(17))
    second = job(org, slot_start=at(19), slot_end=at(21))
    real = scheduling.transition
    calls = []

    def flaky(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("boom")
        return real(*args, **kwargs)

    monkeypatch.setattr(scheduling, "transition", flaky)
    with pytest.raises(RuntimeError):
        run(org, dispatcher_a)
    assert fresh(first).status == JobStatus.UNASSIGNED
    assert fresh(second).status == JobStatus.UNASSIGNED
    assert not JobStatusHistory.objects.filter(to_status="assigned").exists()


# ---- the default day --------------------------------------------------------
def test_the_default_day_is_today_on_the_organizations_clock(org, dispatcher_a, tech):
    j = job(org)
    late_utc = FixedClock(
        datetime.datetime(2026, 11, 3, 3, 0, tzinfo=UTC)
    )  # still Nov 2 in Chicago
    result = scheduling.generate_schedule(
        organization=org, actor=dispatcher_a, clock=late_utc
    )
    assert result.plan_date == DAY
    assert fresh(j).status in (JobStatus.UNASSIGNED, JobStatus.ASSIGNED)


def test_an_urgent_job_planned_for_a_later_day_is_not_flagged_hopelessly_late(
    org, dispatcher_a, tech
):
    """Logged "now" for tomorrow: the urgent buffer counts from when tomorrow opens."""
    tomorrow = DAY + datetime.timedelta(days=1)
    j = job(
        org, is_urgent=True, slot_start=None, slot_end=None, scheduled_date=tomorrow
    )
    Job.objects.filter(pk=j.pk).update(created_at=NOW)  # created a day earlier
    result = scheduling.generate_schedule(
        organization=org, actor=dispatcher_a, plan_date=tomorrow, clock=CLOCK
    )
    (planned,) = result.assigned
    assert planned.sla_label == "ok"


# ---- reading the plan back (current_schedule) -------------------------------
def read(org, **kwargs):
    return scheduling.current_schedule(organization=org, plan_date=DAY, **kwargs)


def test_the_stored_plan_reads_back_exactly_as_the_run_returned_it(
    org, dispatcher_a, tech
):
    placed = job(org)
    nobody = job(org, skills=[Skill.objects.exclude(name="HVAC").first()])
    nowhere = job(org, geocode_status="failed", lat=None, lng=None)
    ran = run(org, dispatcher_a)
    again = read(org)
    assert again == ran
    assert [p.job_id for p in again.assigned] == [placed.pk]
    assert [u.job_id for u in again.unassigned] == [nobody.pk]
    assert [s.job_id for s in again.skipped] == [nowhere.pk]


def test_reading_changes_nothing(org, dispatcher_a, tech):
    j = job(org)
    run(org, dispatcher_a)
    before = (fresh(j).version, fresh(j).updated_at, JobStatusHistory.objects.count())
    read(org)
    assert (
        fresh(j).version,
        fresh(j).updated_at,
        JobStatusHistory.objects.count(),
    ) == before


def test_jobs_the_planner_has_not_seen_yet_are_not_listed(org, tech):
    job(org)  # located and unassigned, but no run yet
    waiting_without_location = job(org, geocode_status="failed", lat=None, lng=None)
    result = read(org)
    assert result.assigned == [] and result.unassigned == []
    assert [s.job_id for s in result.skipped] == [waiting_without_location.pk]


def test_a_job_assigned_by_hand_is_not_part_of_the_plan(org, dispatcher_a, tech):
    j = job(org)
    job_service.transition(fresh(j), "assigned", dispatcher_a, technician=tech)
    assert read(org).assigned == []


def test_an_ongoing_job_stays_in_the_plan(org, dispatcher_a, tech):
    j = job(org)
    run(org, dispatcher_a)
    job_service.transition(fresh(j), "ongoing", dispatcher_a)
    assert [p.job_id for p in read(org).assigned] == [j.pk]


def test_stops_come_back_in_each_technicians_order(org, dispatcher_a, tech):
    late = job(org, slot_start=at(19), slot_end=at(21))
    early = job(org, slot_start=at(15), slot_end=at(17))
    run(org, dispatcher_a)
    assert [p.job_id for p in read(org).assigned] == [early.pk, late.pk]


def test_only_this_organization_and_this_day_are_read(org, org_b, dispatcher_a, tech):
    other_day = job(org, scheduled_date=DAY + datetime.timedelta(days=1))
    theirs = job(org_b)
    run(org, dispatcher_a)
    Job.objects.filter(pk__in=[other_day.pk, theirs.pk]).update(
        plan_explanation={"reasons": [], "sentence": "x"}
    )
    ids = [u.job_id for u in read(org).unassigned] + [
        p.job_id for p in read(org).assigned
    ]
    assert other_day.pk not in ids and theirs.pk not in ids


def test_an_explanation_saved_before_the_sla_was_stored_still_reads(
    org, dispatcher_a, tech
):
    j = job(org)
    run(org, dispatcher_a)
    stored = fresh(j).plan_explanation
    stored.pop("sla_label")
    stored.pop("slack_minutes")
    Job.objects.filter(pk=j.pk).update(plan_explanation=stored)
    (planned,) = read(org).assigned
    assert planned.sla_label == "unknown"


def test_the_default_day_for_reading_is_today_on_the_organizations_clock(
    org, dispatcher_a, tech
):
    job(org)
    run(org, dispatcher_a)
    late_utc = FixedClock(
        datetime.datetime(2026, 11, 3, 3, 0, tzinfo=UTC)
    )  # still Nov 2 in Chicago
    assert (
        len(scheduling.current_schedule(organization=org, clock=late_utc).assigned) == 1
    )
