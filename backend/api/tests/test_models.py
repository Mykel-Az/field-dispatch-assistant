import datetime

import pytest
from django.db import IntegrityError

from api.models import CustomUser, Organization, Technician

from .conftest import PASSWORD, Role, make_user


def test_non_superuser_without_organization_is_rejected_by_the_database(db):
    with pytest.raises(IntegrityError):
        CustomUser.objects.create_user(
            email="x@example.com", password=PASSWORD, role=Role.DISPATCHER
        )


def test_non_superuser_without_role_is_rejected_by_the_database(org_a):
    with pytest.raises(IntegrityError):
        CustomUser.objects.create_user(
            email="x@example.com", password=PASSWORD, organization=org_a
        )


def test_createsuperuser_works_with_no_organization(db):
    user = CustomUser.objects.create_superuser("root@example.com", PASSWORD)
    assert user.is_superuser and user.organization is None and user.role == ""


def test_email_is_stored_lowercase(org_a):
    user = make_user(org_a, Role.DISPATCHER, "Mixed.Case@Example.COM")
    assert user.email == "mixed.case@example.com"


def test_email_is_unique_ignoring_case_across_organizations(org_a, org_b):
    make_user(org_a, Role.DISPATCHER, "same@example.com")
    clash = CustomUser(
        email="SAME@example.com", role=Role.DISPATCHER, organization=org_b
    )
    with pytest.raises(IntegrityError):
        clash.save()  # bypasses create_user's lowercasing: the DB must catch it


def test_role_cannot_change_after_creation(dispatcher_a):
    dispatcher_a.role = Role.HEAD_DISPATCHER
    with pytest.raises(ValueError):
        dispatcher_a.save()


def test_organization_cannot_change_after_creation(dispatcher_a, org_b):
    dispatcher_a.organization = org_b
    with pytest.raises(ValueError):
        dispatcher_a.save()


def test_updating_other_fields_is_allowed(dispatcher_a):
    dispatcher_a.full_name = "New Name"
    dispatcher_a.save()
    dispatcher_a.refresh_from_db()
    assert dispatcher_a.full_name == "New Name"


def test_technician_organization_must_match_its_user(org_b, technician_a):
    technician_a.technician_profile.organization = org_b
    with pytest.raises(ValueError):
        technician_a.technician_profile.save()


def test_technician_in_another_organization_is_rejected_on_create(org_b, org_a):
    user = make_user(org_a, Role.DISPATCHER, "d@example.com")
    with pytest.raises(ValueError):
        Technician.objects.create(
            user=user,
            organization=org_b,
            shift_start=datetime.time(8),
            shift_end=datetime.time(17),
        )


def test_for_organization_filters_users(org_a, org_b, head_a, head_b):
    assert list(CustomUser.objects.for_organization(org_a)) == [head_a]
    assert list(CustomUser.objects.for_organization(org_b)) == [head_b]


def test_organization_is_configured_needs_workstation_and_hours(db):
    org = Organization.objects.create(name="X")
    assert org.is_configured is False
    org.lat, org.lng = 6.5, 3.4
    org.work_start, org.work_end = datetime.time(8), datetime.time(17)
    assert org.is_configured is True
