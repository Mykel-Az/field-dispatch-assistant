"""Every endpoint that takes an object id must answer 404 for another organization.

When you add a tenant model (Job, Technician...) and its endpoint, this test fails
until you register how to create an org-A object for it below. That is the point.
"""

import pytest

from api.models import Technician

from .conftest import Role, api_endpoints, client_for, make_job, make_user

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
    "/api/jobs/{pk}/assign/": lambda owner: make_job(owner.organization).pk,
    "/api/jobs/{pk}/unassign/": lambda owner: make_job(owner.organization).pk,
    "/api/jobs/{pk}/force-assign/": lambda owner: make_job(owner.organization).pk,
    "/api/jobs/{pk}/location/": lambda owner: make_job(owner.organization).pk,
    "/api/jobs/{pk}/retry-geocode/": lambda owner: make_job(owner.organization).pk,
    "/api/technician/me/jobs/{pk}/arrive/": lambda owner: (
        make_job(owner.organization).pk
    ),
    "/api/technician/me/jobs/{pk}/complete/": lambda owner: (
        make_job(owner.organization).pk
    ),
    "/api/technician/me/jobs/{pk}/incomplete/": lambda owner: (
        make_job(owner.organization).pk
    ),
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
def test_other_organization_gets_404(
    method, path, dispatcher_a, technician_a, head_b, org_b
):
    object_id = OBJECT_ID_FOR[path](dispatcher_a)
    # The caller has the right ROLE for the endpoint (a technician for the technician
    # endpoints, a head for the rest), so only tenancy can be the reason for the 404.
    caller = head_b
    if path.startswith("/api/technician/"):
        caller = make_user(org_b, Role.TECHNICIAN, "tech-b@example.com")
    response = getattr(client_for(caller), method.lower())(
        path.format(pk=object_id), UNSAFE_BODY, format="json"
    )
    assert response.status_code == 404
