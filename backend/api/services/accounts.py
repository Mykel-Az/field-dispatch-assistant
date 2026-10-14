from django.contrib.auth import get_user_model
from django.db import transaction

from ..models import Organization, Technician

User = get_user_model()


@transaction.atomic
def register_organization(
    *,
    organization_name,
    email,
    first_name,
    last_name,
    password,
):
    organization = Organization.objects.create(name=organization_name)
    return User.objects.create_user(
        email=email.lower(),
        first_name=first_name,
        last_name=last_name,
        password=password,
        role=User.Role.HEAD_DISPATCHER,
        organization=organization,
    )


@transaction.atomic
def create_staff_user(
    *, creator, role, first_name="", last_name="", email, password, **tech_fields
):
    user = User.objects.create_user(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        role=role,
        organization=creator.organization,  # never taken from the request
    )
    if role == User.Role.TECHNICIAN:
        Technician.objects.create(
            user=user, organization=creator.organization, **tech_fields
        )
    return user


class LastHeadError(Exception): ...


@transaction.atomic
def deactivate_user(*, actor, target):
    org = Organization.objects.select_for_update().get(pk=actor.organization_id)
    if target.role == User.Role.HEAD_DISPATCHER and target.is_active:
        others = (
            User.objects.for_organization(org)
            .filter(role=User.Role.HEAD_DISPATCHER, is_active=True)
            .exclude(pk=target.pk)
        )
        if not others.exists():
            raise LastHeadError
    target.is_active = False
    target.save(update_fields=["is_active"])
