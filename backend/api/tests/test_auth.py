import pytest
from rest_framework.test import APIClient

from api.models import CustomUser, Organization

from .conftest import PASSWORD, client_for

REGISTER = {
    "organization_name": "Cool Air Ltd",
    "email": "Boss@Example.com",
    "full_name": "Ada Boss",
    "password": PASSWORD,
}


# ---- csrf -------------------------------------------------------------------
def test_csrf_endpoint_sets_the_cookie():
    client = APIClient()
    response = client.get("/api/auth/csrf/")
    assert response.status_code == 204
    assert "csrftoken" in response.cookies


# ---- register ---------------------------------------------------------------
@pytest.mark.django_db
def test_register_creates_organization_and_head_and_signs_in(csrf_client):
    response = csrf_client.post(
        "/api/auth/register/", REGISTER, format="json", **csrf_client.csrf_headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "boss@example.com"
    assert body["role"] == "head_dispatcher"
    assert body["organization"]["name"] == "Cool Air Ltd"
    assert csrf_client.get("/api/auth/me/").status_code == 200  # session was created


@pytest.mark.django_db
def test_register_requires_csrf(csrf_client):
    response = csrf_client.post("/api/auth/register/", REGISTER, format="json")
    assert response.status_code == 403
    assert Organization.objects.count() == 0


@pytest.mark.django_db
def test_register_duplicate_email_in_any_case_is_a_generic_400(head_a):
    client = APIClient()
    body = {**REGISTER, "email": head_a.email.upper()}
    response = client.post("/api/auth/register/", body, format="json")
    assert response.status_code == 400
    assert "unavailable" in str(response.json()["email"]).lower()
    assert Organization.objects.count() == 1  # nothing half-created


@pytest.mark.django_db
def test_register_rejects_a_weak_password():
    response = APIClient().post(
        "/api/auth/register/", {**REGISTER, "password": "12345678"}, format="json"
    )
    assert response.status_code == 400
    assert "password" in response.json()


# ---- login ------------------------------------------------------------------
def test_login_returns_user_and_creates_a_session(head_a, csrf_client):
    response = csrf_client.post(
        "/api/auth/login/",
        {"email": "HEAD-A@example.com", "password": PASSWORD},
        format="json",
        **csrf_client.csrf_headers,
    )
    assert response.status_code == 200
    assert response.json()["organization"] == {
        "id": head_a.organization_id,
        "name": "Org A",
    }
    assert csrf_client.get("/api/auth/me/").status_code == 200


def test_login_requires_csrf(head_a, csrf_client):
    response = csrf_client.post(
        "/api/auth/login/",
        {"email": head_a.email, "password": PASSWORD},
        format="json",
    )
    assert response.status_code == 403


def test_login_failures_are_one_generic_400(head_a, dispatcher_a, superuser):
    dispatcher_a.is_active = False
    dispatcher_a.save(update_fields=["is_active"])
    attempts = [
        {"email": head_a.email, "password": "wrong"},
        {"email": "nobody@example.com", "password": PASSWORD},
        {"email": dispatcher_a.email, "password": PASSWORD},  # inactive
        {"email": superuser.email, "password": PASSWORD},  # admin site only
        {},
    ]
    bodies = []
    for attempt in attempts:
        response = APIClient().post("/api/auth/login/", attempt, format="json")
        assert response.status_code == 400
        bodies.append(response.json())
    assert all(body == bodies[0] for body in bodies)  # nothing to tell cases apart


def test_login_is_throttled(head_a):
    codes = [
        APIClient()
        .post(
            "/api/auth/login/",
            {"email": head_a.email, "password": "x"},
            format="json",
        )
        .status_code
        for _ in range(12)
    ]
    assert codes[:10] == [400] * 10
    assert 429 in codes[10:]


# ---- me / logout -----------------------------------------------------------
def test_me_returns_the_user_with_organization(head_a):
    response = client_for(head_a).get("/api/auth/me/")
    assert response.status_code == 200
    assert response.json() == {
        "id": head_a.pk,
        "email": head_a.email,
        "full_name": "head-a",
        "role": "head_dispatcher",
        "is_active": True,
        "organization": {"id": head_a.organization_id, "name": "Org A"},
    }


@pytest.mark.django_db
def test_anonymous_gets_401_not_403():
    assert APIClient().get("/api/auth/me/").status_code == 401


def test_logout_ends_the_session(head_a):
    client = client_for(head_a)
    assert client.post("/api/auth/logout/").status_code == 204
    assert client.get("/api/auth/me/").status_code == 401


def test_signed_in_unsafe_requests_need_the_csrf_header(head_a):
    client = APIClient(enforce_csrf_checks=True)
    client.force_login(head_a)
    assert client.post("/api/auth/logout/").status_code == 403


# ---- sessions die with the account -----------------------------------------
def test_deactivated_users_existing_session_dies(dispatcher_a):
    client = client_for(dispatcher_a)
    assert client.get("/api/auth/me/").status_code == 200
    CustomUser.objects.filter(pk=dispatcher_a.pk).update(is_active=False)
    assert client.get("/api/auth/me/").status_code == 401


# ---- change password -------------------------------------------------------
def test_change_password_keeps_this_session_and_kills_others(dispatcher_a):
    this_session, other_session = client_for(dispatcher_a), client_for(dispatcher_a)
    response = this_session.post(
        "/api/auth/change-password/",
        {"current_password": PASSWORD, "new_password": "An0ther-long-phrase!"},
        format="json",
    )
    assert response.status_code == 204
    assert this_session.get("/api/auth/me/").status_code == 200
    assert other_session.get("/api/auth/me/").status_code == 401
    dispatcher_a.refresh_from_db()
    assert dispatcher_a.check_password("An0ther-long-phrase!")


def test_change_password_rejects_wrong_current_and_weak_new(dispatcher_a):
    client = client_for(dispatcher_a)
    wrong = client.post(
        "/api/auth/change-password/",
        {"current_password": "nope", "new_password": "An0ther-long-phrase!"},
        format="json",
    )
    weak = client.post(
        "/api/auth/change-password/",
        {"current_password": PASSWORD, "new_password": "12345678"},
        format="json",
    )
    assert wrong.status_code == 400
    assert weak.status_code == 400
