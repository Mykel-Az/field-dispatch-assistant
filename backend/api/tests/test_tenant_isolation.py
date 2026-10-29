"""Every endpoint that takes an object id must answer 404 for another organization.

When you add a tenant model (Job, Technician...) and its endpoint, this test fails
until you register how to create an org-A object for it below. That is the point.
"""

import pytest

from api.models import Technician

from .conftest import api_endpoints, client_for, make_job

# path template -> function(org_a_user) returning an id owned by organization A
OBJECT_ID_FOR = {
    "/api/users/{pk}/": lambda owner: owner.pk,
    "/api/users/{pk}/deactivate/": lambda owner: owner.pk,
    "/api/users/{pk}/reactivate/": lambda owner: owner.pk,
    "/api/users/{pk}/set-password/": lambda owner: owner.pk,
    "/api/technicians/{pk}/": lambda owner: (
        Technician.objects.get(organization=owner.organization).pk
    ),
    "/api/jobs/{pk}/": lambda owner: make_job(owner.organization).pk,
    "/api/jobs/{pk}/cancel/": lambda owner: make_job(owner.organization).pk,
}
UNSAFE_BODY = {"full_name": "x", "new_password": "An0ther-long-phrase!"}


def endpoints_with_an_id():
    return [
        (method, path)
        for path, method, _ in api_endpoints()
        if "{pk}" in path and method in {"GET", "PATCH", "POST", "PUT", "DELETE"}
    ]


def test_every_id_endpoint_is_registered_for_the_isolation_test():
    assert endpoints_with_an_id(), "found no {pk} endpoints: the enumeration is broken"
    missing = {path for _, path in endpoints_with_an_id()} - set(OBJECT_ID_FOR)
    assert missing == set(), f"register these in OBJECT_ID_FOR: {sorted(missing)}"


@pytest.mark.parametrize(("method", "path"), endpoints_with_an_id())
def test_other_organization_gets_404(method, path, dispatcher_a, technician_a, head_b):
    object_id = OBJECT_ID_FOR[path](dispatcher_a)
    # Head B has the right ROLE, so only tenancy can be the reason for the 404.
    response = getattr(client_for(head_b), method.lower())(
        path.format(pk=object_id), UNSAFE_BODY, format="json"
    )
    assert response.status_code == 404
