from django.contrib.auth import get_user_model
from django.db import transaction

from ..models import Organization, Technician

User = get_user_model()


@transaction.atomic
def register_organization(
    *,
    organization_name,
    username="",
    email,
    fisrt_name,
    last_name,
    password,
):
    organization = Organization.objects.create(name=organization_name)
    return User.objects.create_user(
        username=username,
        email=email,
        fisrt_name=fisrt_name,
        last_name=last_name,
        password=password,
        role=User.Role.HEAD_DISPATCHER,
        organization=organization,
    )


@transaction.atomic
def create_staff_user(*, creator, role, username="", email, password, **tech_fields):
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        role=role,
        organization=creator.organization,  # never taken from the request
    )
    if role == User.Role.TECHNICIAN:
        Technician.objects.create(
            user=user, organization=creator.organization, **tech_fields
        )
    return user


def login(request, user):
    pass


def logout(request):
    pass
