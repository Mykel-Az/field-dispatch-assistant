import datetime

import pytest
from rest_framework.test import APIClient

from api.models import Skill, Technician

from .conftest import client_for, make_user


def profile_of(user):
    return Technician.objects.get(user=user)


def patch(user, tech, body):
    return client_for(user).patch(f"/api/technicians/{tech.pk}/", body, format="json")


def test_dispatcher_lists_only_own_organization(
    dispatcher_a, technician_a, technician_b
):
    response = client_for(dispatcher_a).get("/api/technicians/")
    assert response.status_code == 200
    assert [t["user"]["email"] for t in response.json()] == [technician_a.email]


def test_list_shape_has_user_skills_and_shift(dispatcher_a, technician_a):
    row = client_for(dispatcher_a).get("/api/technicians/").json()[0]
    assert set(row) == {
        "id",
        "user",
        "skills",
        "shift_start",
        "shift_end",
        "phone",
    }
    assert row["user"]["role"] == "technician"


def test_list_does_not_run_a_query_per_technician(
    dispatcher_a, technician_a, org_a, django_assert_max_num_queries
):
    for i in range(5):
        make_user(org_a, "technician", f"extra{i}@example.com")
    client = client_for(dispatcher_a)  # login outside the counted block
    with django_assert_max_num_queries(6):  # session, user, org, techs, skills
        client.get("/api/technicians/")


def test_technician_cannot_list(technician_a):
    assert client_for(technician_a).get("/api/technicians/").status_code == 403


def test_anonymous_gets_401():
    assert APIClient().get("/api/technicians/").status_code == 401


def test_head_edits_shift_phone_and_skills(head_a, technician_a):
    skill = Skill.objects.first()
    tech = profile_of(technician_a)
    response = patch(
        head_a,
        tech,
        {
            "shift_start": "07:00",
            "shift_end": "15:30",
            "phone": "555-123-4567",
            "skill_ids": [skill.pk],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] == "555-123-4567"
    assert [s["id"] for s in body["skills"]] == [skill.pk]
    tech.refresh_from_db()
    assert tech.shift_end == datetime.time(15, 30)


def test_dispatcher_cannot_edit(dispatcher_a, technician_a):
    assert (
        patch(dispatcher_a, profile_of(technician_a), {"phone": "1"}).status_code == 403
    )


def test_technician_cannot_edit_even_self(technician_a):
    assert (
        patch(technician_a, profile_of(technician_a), {"phone": "1"}).status_code == 403
    )


def test_head_of_other_org_gets_404_and_nothing_changes(head_b, technician_a):
    tech = profile_of(technician_a)
    assert patch(head_b, tech, {"phone": "hacked"}).status_code == 404
    tech.refresh_from_db()
    assert tech.phone != "hacked"


def test_shift_end_must_be_after_start_using_stored_values(head_a, technician_a):
    # stored shift is 08:00-17:00; moving only the end before the start is invalid
    response = patch(head_a, profile_of(technician_a), {"shift_end": "07:00"})
    assert response.status_code == 400


def test_unknown_skill_is_rejected(head_a, technician_a):
    assert (
        patch(head_a, profile_of(technician_a), {"skill_ids": [999999]}).status_code
        == 400
    )


@pytest.mark.parametrize("field", ["user", "organization", "latitude", "role"])
def test_protected_fields_are_ignored(head_a, technician_a, org_b, field):
    tech = profile_of(technician_a)
    before = (tech.organization_id, tech.user_id)
    patch(head_a, tech, {field: 1})
    tech.refresh_from_db()
    assert (tech.organization_id, tech.user_id) == before


def test_post_and_delete_are_not_allowed(head_a, technician_a):
    c = client_for(head_a)
    assert c.post("/api/technicians/", {}, format="json").status_code == 405
    assert (
        c.delete(f"/api/technicians/{profile_of(technician_a).pk}/").status_code == 405
    )


@pytest.mark.parametrize("phone", ["call me", "08O1234567", "12", "555-123-4567 ext 9"])
def test_phone_with_letters_or_wrong_length_is_rejected(head_a, technician_a, phone):
    tech = profile_of(technician_a)
    assert patch(head_a, tech, {"phone": phone}).status_code == 400
    tech.refresh_from_db()
    assert tech.phone != phone


@pytest.mark.parametrize("phone", ["+1 (555) 123-4567", "555-123-4567", "5551234567"])
def test_normal_us_phone_formats_are_accepted(head_a, technician_a, phone):
    assert patch(head_a, profile_of(technician_a), {"phone": phone}).status_code == 200


def test_phone_can_be_cleared(head_a, technician_a):
    tech = profile_of(technician_a)
    assert patch(head_a, tech, {"phone": None}).status_code == 200


def test_skills_cannot_be_cleared_but_may_be_left_alone(head_a, technician_a):
    tech = profile_of(technician_a)
    tech.skills.set([Skill.objects.first()])
    response = patch(head_a, tech, {"skill_ids": []})
    assert response.status_code == 400
    assert response.json()["skill_ids"] == ["Select at least one skill."]
    assert tech.skills.count() == 1
    assert patch(head_a, tech, {"phone": "555-123-4567"}).status_code == 200
