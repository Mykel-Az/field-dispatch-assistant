"""When could this job be booked? (ADR-032)"""

import datetime

import pytest

from api.models import Job, JobStatus, Skill
from api.services import scheduling
from dispatch_engine.clock import FixedClock

from .conftest import Role, client_for, make_job, make_user, technician_of

UTC = datetime.UTC
NOW = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=UTC)  # 9:00 in Chicago
DAY = datetime.date(2026, 11, 2)


def at(day_offset, hour, minute=0):
    base = datetime.datetime(2026, 11, 2, 15, 0, tzinfo=UTC)  # 9:00 local
    return base + datetime.timedelta(days=day_offset, hours=hour - 9, minutes=minute)


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch):
    monkeypatch.setattr(scheduling, "SystemClock", lambda: FixedClock(NOW))


@pytest.fixture
def org(org_a):
    org_a.lat, org_a.lng = 30.30, -97.70
    org_a.geocode_status = "manual"
    org_a.work_start, org_a.work_end = datetime.time(8), datetime.time(17)
    org_a.max_jobs_per_tech_per_day = 4
    org_a.save()
    return org_a


@pytest.fixture
def tech(org, technician_a):
    technician = technician_of(technician_a)
    technician.skills.add(Skill.objects.get(name="Heating & Air Conditioning"))
    return technician


def wanted(org, **fields):
    """The job someone is asking about, at the same address as everything else."""
    fields.setdefault("lat", 30.30)
    fields.setdefault("lng", -97.70)
    fields.setdefault("estimated_duration_minutes", 60)
    return make_job(org, **fields)


def held(org, tech, start_hour, end_hour, day=DAY, position=1, **fields):
    """An Assigned job the technician already has, fixed on the clock."""
    return make_job(
        org,
        status=JobStatus.ASSIGNED,
        technician=tech,
        scheduled_date=day,
        lat=30.30,
        lng=-97.70,
        estimated_arrival=at((day - DAY).days, start_hour),
        slot_start=at((day - DAY).days, start_hour),
        slot_end=at((day - DAY).days, end_hour),
        estimated_duration_minutes=(end_hour - start_hour) * 60,
        sequence_position=position,
        **fields,
    )


def slots(dispatcher, job, days=1):
    response = client_for(dispatcher).get(
        f"/api/jobs/{job.pk}/available-slots/?days={days}"
    )
    assert response.status_code == 200, response.content
    return response.json()


def test_a_free_technician_can_start_straight_away(org, tech, dispatcher_a):
    result = slots(dispatcher_a, wanted(org))
    assert len(result) == 1
    assert result[0]["technician_id"] == tech.pk
    assert result[0]["start"] == at(0, 9).isoformat().replace("+00:00", "Z")
    assert result[0]["end"] == at(0, 10).isoformat().replace("+00:00", "Z")


def test_a_booked_technician_is_offered_the_time_after_their_job(
    org, tech, dispatcher_a
):
    held(org, tech, 9, 10)
    result = slots(dispatcher_a, wanted(org))
    assert result[0]["start"] == at(0, 10).isoformat().replace("+00:00", "Z")


def test_a_gap_big_enough_is_offered_and_one_too_small_is_not(org, tech, dispatcher_a):
    held(org, tech, 9, 10)
    held(
        org, tech, 11, 12, position=2
    )  # one hour free between: a 60-minute job just fits
    first = slots(dispatcher_a, wanted(org))[0]
    assert first["start"] == at(0, 10).isoformat().replace("+00:00", "Z")
    Job.objects.filter(estimated_arrival=at(0, 11)).update(
        estimated_arrival=at(0, 10, 30), slot_start=at(0, 10, 30)
    )  # now busy 10:30 to 11:30: only 30 minutes are free before it
    later = slots(dispatcher_a, wanted(org))[0]
    assert later["start"] == at(0, 11, 30).isoformat().replace("+00:00", "Z")


def test_a_technician_without_the_skill_is_never_offered(org, tech, dispatcher_a):
    electrical = Skill.objects.exclude(name="Heating & Air Conditioning").first()
    job = wanted(org, skills=[electrical])
    assert slots(dispatcher_a, job) == []


def test_a_deactivated_technician_is_never_offered(org, tech, dispatcher_a):
    tech.user.is_active = False
    tech.user.save()
    assert slots(dispatcher_a, wanted(org)) == []


def test_a_full_day_moves_the_offer_to_the_next_day(org, tech, dispatcher_a):
    org.max_jobs_per_tech_per_day = 1
    org.save()
    held(org, tech, 12, 13)
    result = slots(dispatcher_a, wanted(org), days=2)
    assert [s["date"] for s in result] == ["2026-11-03"]


def test_days_sets_how_far_ahead_to_look(org, tech, dispatcher_a):
    assert len(slots(dispatcher_a, wanted(org), days=3)) == 3
    assert len(slots(dispatcher_a, wanted(org), days=1)) == 1


def test_days_is_limited(org, tech, dispatcher_a):
    assert len(slots(dispatcher_a, wanted(org), days=500)) == scheduling.MAX_SLOT_DAYS
    bad = client_for(dispatcher_a).get(
        f"/api/jobs/{wanted(org).pk}/available-slots/?days=x"
    )
    assert bad.status_code == 400


def test_the_job_itself_does_not_block_its_own_slot(org, tech, dispatcher_a):
    mine = held(org, tech, 9, 10)  # already booked at 9; asking again about this job
    result = slots(dispatcher_a, mine)
    assert result[0]["start"] == at(0, 9).isoformat().replace("+00:00", "Z")


def test_without_a_location_it_says_so(org, tech, dispatcher_a):
    job = wanted(org, lat=None, lng=None)
    response = client_for(dispatcher_a).get(f"/api/jobs/{job.pk}/available-slots/")
    assert response.status_code == 409
    assert "location" in response.json()["detail"].lower()


def test_it_reads_only(org, tech, dispatcher_a):
    job = wanted(org)
    before = list(Job.objects.values_list("pk", "status", "version", "technician_id"))
    slots(dispatcher_a, job)
    assert (
        list(Job.objects.values_list("pk", "status", "version", "technician_id"))
        == before
    )


def test_another_organizations_job_is_a_404(org, tech, dispatcher_a, org_b):
    theirs = make_job(org_b)
    assert (
        client_for(dispatcher_a)
        .get(f"/api/jobs/{theirs.pk}/available-slots/")
        .status_code
        == 404
    )


def test_technicians_cannot_ask(org, tech, technician_a):
    job = wanted(org)
    assert (
        client_for(technician_a).get(f"/api/jobs/{job.pk}/available-slots/").status_code
        == 403
    )


def test_other_organizations_technicians_are_not_offered(
    org, tech, dispatcher_a, org_b
):
    outsider = technician_of(make_user(org_b, Role.TECHNICIAN, "out@example.com"))
    outsider.skills.add(Skill.objects.get(name="Heating & Air Conditioning"))
    assert {s["technician_id"] for s in slots(dispatcher_a, wanted(org))} == {tech.pk}


def test_two_technicians_are_listed_soonest_first(org, tech, dispatcher_a):
    colleague = technician_of(make_user(org, Role.TECHNICIAN, "second@example.com"))
    colleague.skills.add(Skill.objects.get(name="Heating & Air Conditioning"))
    held(org, tech, 9, 10)  # the first technician is busy until 10
    result = slots(dispatcher_a, wanted(org))
    assert [s["technician_id"] for s in result] == [colleague.pk, tech.pk]
    assert result[0]["start"] == at(0, 9).isoformat().replace("+00:00", "Z")
    assert result[1]["start"] == at(0, 10).isoformat().replace("+00:00", "Z")
