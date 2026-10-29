import datetime

import pytest
from django.core.cache import cache
from drf_spectacular.generators import EndpointEnumerator
from rest_framework.test import APIClient

from api.models import CustomUser, Job, Organization, Skill, Technician

PASSWORD = "Str0ng-pass-phrase!"
Role = CustomUser.Role


def api_endpoints():
    """Every (path, METHOD, view callback) the API exposes, e.g. /api/users/{pk}/."""
    return [
        (path, method, callback)
        for path, _regex, method, callback in EndpointEnumerator().get_api_endpoints()
    ]


@pytest.fixture(autouse=True)
def _clear_cache():
    """Throttle counters live in the cache; start every test from zero."""
    cache.clear()


def make_user(organization, role, email, **extra):
    user = CustomUser.objects.create_user(
        email=email,
        password=PASSWORD,
        full_name=extra.pop("full_name", email.split("@")[0]),
        role=role,
        organization=organization,
        **extra,
    )
    if role == Role.TECHNICIAN:
        Technician.objects.create(
            user=user,
            organization=organization,
            shift_start=datetime.time(8),
            shift_end=datetime.time(17),
        )
    return user


def client_for(user):
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def org_a(db):
    return Organization.objects.create(name="Org A")


@pytest.fixture
def org_b(db):
    return Organization.objects.create(name="Org B")


@pytest.fixture
def head_a(org_a):
    return make_user(org_a, Role.HEAD_DISPATCHER, "head-a@example.com")


@pytest.fixture
def dispatcher_a(org_a):
    return make_user(org_a, Role.DISPATCHER, "disp-a@example.com")


@pytest.fixture
def technician_a(org_a):
    return make_user(org_a, Role.TECHNICIAN, "tech-a@example.com")


@pytest.fixture
def head_b(org_b):
    return make_user(org_b, Role.HEAD_DISPATCHER, "head-b@example.com")


@pytest.fixture
def dispatcher_b(org_b):
    return make_user(org_b, Role.DISPATCHER, "disp-b@example.com")


@pytest.fixture
def technician_b(org_b):
    return make_user(org_b, Role.TECHNICIAN, "tech-b@example.com")


@pytest.fixture
def superuser(db):
    return CustomUser.objects.create_superuser("root@example.com", PASSWORD)


@pytest.fixture
def csrf_client():
    """A client that enforces CSRF like a browser, plus its token header."""
    client = APIClient(enforce_csrf_checks=True)
    client.get("/api/auth/csrf/")
    token = client.cookies["csrftoken"].value
    client.csrf_headers = {"HTTP_X_CSRFTOKEN": token}
    return client


def make_job(organization, **overrides):
    """A valid, unassigned, non-urgent job with a located address."""
    start = datetime.datetime(2026, 11, 2, 9, tzinfo=datetime.UTC)
    fields = {
        "title": "Fix AC",
        "customer_name": "Ada Customer",
        "category": "hvac",
        "address": "1 Main St",
        "postal_code": "78701",
        "geocode_status": "ok",
        "lat": 30.2,
        "lng": -97.7,
        "slot_start": start,
        "slot_end": start + datetime.timedelta(hours=2),
        "scheduled_date": start.date(),
    }
    skills = overrides.pop("skills", None)
    fields.update(overrides)
    job = Job.objects.create(organization=organization, **fields)
    job.acceptable_skills.set(skills or Skill.objects.filter(name="HVAC"))
    return job


def technician_of(user):
    return Technician.objects.get(user=user)
