"""Who may call what: one table drives the role x endpoint matrix."""

import pytest
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from api.permissions import DenyAll

from .conftest import api_endpoints, client_for

ANON, TECH, DISP, HEAD, SUPER = "anon", "technician", "dispatcher", "head", "superuser"

MATRIX = [
    ("get", "/api/auth/me/", None,
     {ANON: 401, TECH: 200, DISP: 200, HEAD: 200, SUPER: 403}),
    ("get", "/api/skills/", None,
     {ANON: 401, TECH: 403, DISP: 200, HEAD: 200, SUPER: 403}),
    ("get", "/api/organization/", None,
     {ANON: 401, TECH: 403, DISP: 200, HEAD: 200, SUPER: 403}),
    ("patch", "/api/organization/", {"version": 1, "name": "N"},
     {ANON: 401, TECH: 403, DISP: 403, HEAD: 200, SUPER: 403}),
    ("get", "/api/users/", None,
     {ANON: 401, TECH: 403, DISP: 403, HEAD: 200, SUPER: 403}),
    ("post", "/api/users/", {},
     {ANON: 401, TECH: 403, DISP: 403, HEAD: 400, SUPER: 403}),
]  # fmt: skip


@pytest.fixture
def clients(head_a, dispatcher_a, technician_a, superuser):
    return {
        ANON: APIClient(),
        TECH: client_for(technician_a),
        DISP: client_for(dispatcher_a),
        HEAD: client_for(head_a),
        SUPER: client_for(superuser),
    }


@pytest.mark.parametrize(
    ("method", "path", "body", "expected"),
    MATRIX,
    ids=[f"{m.upper()} {p}" for m, p, _, _ in MATRIX],
)
def test_role_matrix(clients, method, path, body, expected):
    order = [ANON, TECH, DISP, SUPER, HEAD]
    for who in order:
        response = getattr(clients[who], method)(path, body, format="json")
        assert response.status_code == expected[who], f"{who}: {response.content!r}"


def test_every_api_route_names_its_permissions():
    """A new view that forgets permission_classes would be DenyAll: catch it here."""
    default = api_settings.DEFAULT_PERMISSION_CLASSES
    assert list(default) == [DenyAll]
    unnamed = [
        f"{method} {path}"
        for path, method, callback in api_endpoints()
        if list(callback.cls.permission_classes) == [DenyAll]
    ]
    assert unnamed == []
