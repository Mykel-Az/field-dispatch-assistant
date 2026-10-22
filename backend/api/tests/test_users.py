import pytest
from rest_framework.test import APIClient

from api.models import CustomUser, Skill, Technician

from .conftest import PASSWORD, Role, client_for, make_user

NEW_DISPATCHER = {
    "email": "New.Dispatcher@example.com",
    "password": PASSWORD,
    "full_name": "New Dispatcher",
    "role": "dispatcher",
}


def technician_body(skill_ids=None):
    if skill_ids is None:
        skill_ids = [Skill.objects.first().pk]
    return {
        "email": "newtech@example.com",
        "password": PASSWORD,
        "full_name": "New Tech",
        "role": "technician",
        "technician": {
            "skill_ids": list(skill_ids),
            "shift_start": "08:00",
            "shift_end": "17:00",
        },
    }


# ---- list ------------------------------------------------------------------
def test_list_shows_only_my_organizations_users(head_a, dispatcher_a, head_b):
    response = client_for(head_a).get("/api/users/")
    assert response.status_code == 200
    emails = {row["email"] for row in response.json()["results"]}
    assert emails == {head_a.email, dispatcher_a.email}


def test_list_filters_by_role_and_active(head_a, dispatcher_a, technician_a):
    CustomUser.objects.filter(pk=technician_a.pk).update(is_active=False)
    client = client_for(head_a)
    by_role = client.get("/api/users/?role=dispatcher").json()["results"]
    inactive = client.get("/api/users/?is_active=false").json()["results"]
    assert [row["email"] for row in by_role] == [dispatcher_a.email]
    assert [row["email"] for row in inactive] == [technician_a.email]


# ---- create ----------------------------------------------------------------
def test_create_dispatcher_lands_in_my_organization(head_a, org_a):
    response = client_for(head_a).post("/api/users/", NEW_DISPATCHER, format="json")
    assert response.status_code == 201
    created = CustomUser.objects.get(email="new.dispatcher@example.com")
    assert created.organization == org_a
    assert created.role == Role.DISPATCHER


def test_organization_in_the_body_is_ignored(head_a, org_a, org_b):
    body = {**NEW_DISPATCHER, "organization": org_b.pk}
    response = client_for(head_a).post("/api/users/", body, format="json")
    assert response.status_code == 201
    created = CustomUser.objects.get(email="new.dispatcher@example.com")
    assert created.organization == org_a


def test_head_can_create_another_head(head_a):
    body = {**NEW_DISPATCHER, "role": "head_dispatcher"}
    assert (
        client_for(head_a).post("/api/users/", body, format="json").status_code == 201
    )


def test_create_technician_makes_the_profile_with_skills(head_a, org_a):
    skills = list(Skill.objects.values_list("pk", flat=True)[:2])
    response = client_for(head_a).post(
        "/api/users/", technician_body(skills), format="json"
    )
    assert response.status_code == 201
    profile = Technician.objects.get(user__email="newtech@example.com")
    assert profile.organization == org_a
    assert set(profile.skills.values_list("pk", flat=True)) == set(skills)


def test_technician_block_is_required_for_technicians(head_a):
    body = technician_body()
    del body["technician"]
    assert (
        client_for(head_a).post("/api/users/", body, format="json").status_code == 400
    )


def test_technician_block_is_rejected_for_other_roles(head_a):
    body = {
        **NEW_DISPATCHER,
        "technician": {"shift_start": "08:00", "shift_end": "17:00"},
    }
    assert (
        client_for(head_a).post("/api/users/", body, format="json").status_code == 400
    )


def test_shift_end_must_be_after_shift_start(head_a):
    body = technician_body()
    body["technician"]["shift_end"] = "07:00"
    assert (
        client_for(head_a).post("/api/users/", body, format="json").status_code == 400
    )


def test_technician_needs_at_least_one_skill(head_a):
    body = technician_body()
    body["technician"]["skill_ids"] = []
    response = client_for(head_a).post("/api/users/", body, format="json")
    assert response.status_code == 400
    assert response.json()["technician"]["skill_ids"] == ["Select at least one skill."]
    assert not CustomUser.objects.filter(email=body["email"]).exists()


def test_technician_skill_ids_cannot_be_left_out(head_a):
    body = technician_body()
    del body["technician"]["skill_ids"]
    response = client_for(head_a).post("/api/users/", body, format="json")
    assert response.status_code == 400


def test_failed_technician_create_leaves_no_user_behind(head_a):
    body = technician_body()
    body["technician"]["skill_ids"] = [999999]  # unknown skill
    assert (
        client_for(head_a).post("/api/users/", body, format="json").status_code == 400
    )
    assert not CustomUser.objects.filter(email="newtech@example.com").exists()


def test_duplicate_email_in_another_organization_is_unavailable(head_a, head_b):
    body = {**NEW_DISPATCHER, "email": head_b.email.upper()}
    response = client_for(head_a).post("/api/users/", body, format="json")
    assert response.status_code == 400
    assert "unavailable" in str(response.json()["email"]).lower()


# ---- tenant isolation on every {pk} action ---------------------------------
@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("get", "/api/users/{pk}/", None),
        ("patch", "/api/users/{pk}/", {"full_name": "Hacked"}),
        ("post", "/api/users/{pk}/deactivate/", None),
        ("post", "/api/users/{pk}/reactivate/", None),
        (
            "post",
            "/api/users/{pk}/set-password/",
            {"new_password": "An0ther-long-phrase!"},
        ),
    ],
)
def test_other_organizations_user_is_404(head_a, dispatcher_b, method, path, body):
    client = client_for(head_a)
    response = getattr(client, method)(
        path.format(pk=dispatcher_b.pk), body, format="json"
    )
    assert response.status_code == 404
    dispatcher_b.refresh_from_db()
    assert dispatcher_b.is_active and dispatcher_b.full_name != "Hacked"


# ---- update ----------------------------------------------------------------
def test_patch_changes_full_name(head_a, dispatcher_a):
    response = client_for(head_a).patch(
        f"/api/users/{dispatcher_a.pk}/", {"full_name": "Renamed"}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["full_name"] == "Renamed"


@pytest.mark.parametrize("field", ["role", "organization", "email"])
def test_patch_rejects_immutable_fields(head_a, dispatcher_a, org_b, field):
    value = {"role": "head_dispatcher", "organization": org_b.pk, "email": "x@y.com"}[
        field
    ]
    response = client_for(head_a).patch(
        f"/api/users/{dispatcher_a.pk}/",
        {"full_name": "Ok", field: value},
        format="json",
    )
    assert response.status_code == 400
    dispatcher_a.refresh_from_db()
    assert dispatcher_a.role == Role.DISPATCHER and dispatcher_a.email != "x@y.com"


# ---- deactivate / reactivate -----------------------------------------------
def test_deactivate_and_reactivate_are_idempotent(head_a, dispatcher_a):
    client = client_for(head_a)
    for _ in range(2):
        response = client.post(f"/api/users/{dispatcher_a.pk}/deactivate/")
        assert response.status_code == 200 and response.json()["is_active"] is False
    for _ in range(2):
        response = client.post(f"/api/users/{dispatcher_a.pk}/reactivate/")
        assert response.status_code == 200 and response.json()["is_active"] is True


def test_last_active_head_cannot_be_deactivated(head_a):
    response = client_for(head_a).post(f"/api/users/{head_a.pk}/deactivate/")
    assert response.status_code == 409
    assert response.json()["detail"]
    head_a.refresh_from_db()
    assert head_a.is_active


def test_a_head_can_be_deactivated_when_another_active_head_exists(head_a, org_a):
    second = make_user(org_a, Role.HEAD_DISPATCHER, "head2-a@example.com")
    response = client_for(head_a).post(f"/api/users/{second.pk}/deactivate/")
    assert response.status_code == 200


def test_an_inactive_head_does_not_count_as_the_remaining_head(head_a, org_a):
    second = make_user(org_a, Role.HEAD_DISPATCHER, "head2-a@example.com")
    CustomUser.objects.filter(pk=second.pk).update(is_active=False)
    response = client_for(head_a).post(f"/api/users/{head_a.pk}/deactivate/")
    assert response.status_code == 409


def test_deactivated_user_cannot_log_in_but_can_after_reactivation(
    head_a, dispatcher_a
):
    client_for(head_a).post(f"/api/users/{dispatcher_a.pk}/deactivate/")
    login = {"email": dispatcher_a.email, "password": PASSWORD}
    assert APIClient().post("/api/auth/login/", login, format="json").status_code == 400
    client_for(head_a).post(f"/api/users/{dispatcher_a.pk}/reactivate/")
    assert APIClient().post("/api/auth/login/", login, format="json").status_code == 200


# ---- set-password ----------------------------------------------------------
def test_set_password_changes_it_and_kills_the_targets_sessions(head_a, dispatcher_a):
    target_session = client_for(dispatcher_a)
    response = client_for(head_a).post(
        f"/api/users/{dispatcher_a.pk}/set-password/",
        {"new_password": "An0ther-long-phrase!"},
        format="json",
    )
    assert response.status_code == 204
    assert target_session.get("/api/auth/me/").status_code == 401
    dispatcher_a.refresh_from_db()
    assert dispatcher_a.check_password("An0ther-long-phrase!")


def test_set_password_is_not_for_yourself(head_a):
    response = client_for(head_a).post(
        f"/api/users/{head_a.pk}/set-password/",
        {"new_password": "An0ther-long-phrase!"},
        format="json",
    )
    assert response.status_code == 400


def test_set_password_validates_the_password(head_a, dispatcher_a):
    response = client_for(head_a).post(
        f"/api/users/{dispatcher_a.pk}/set-password/",
        {"new_password": "12345678"},
        format="json",
    )
    assert response.status_code == 400
