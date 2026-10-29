from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from ..models import Job, JobStatus, Organization, Technician
from .jobs import release_assigned_jobs

User = get_user_model()


class AccountError(Exception):
    """Base class. `code` is what the API puts in the response."""

    code = "error"


class EmailUnavailableError(AccountError):
    code = "email_unavailable"


class LastHeadError(AccountError):
    code = "last_head"


class HasOngoingJobError(AccountError):
    code = "has_ongoing_job"


class CannotChangeOwnPasswordHereError(AccountError):
    code = "use_change_password"


def _create_user(**fields):
    """Create a user; a duplicate email (any letter case) is a normal outcome."""
    email = fields["email"].lower()
    if User.objects.filter(email__iexact=email).exists():
        raise EmailUnavailableError
    try:
        # Nested atomic: an IntegrityError must not poison the outer transaction.
        with transaction.atomic():
            return User.objects.create_user(**{**fields, "email": email})
    except IntegrityError as exc:  # two requests raced past the exists() check
        raise EmailUnavailableError from exc


@transaction.atomic
def register_organization(*, organization_name, email, full_name, password):
    """Create a new organization and its first head dispatcher, atomically."""
    organization = Organization.objects.create(name=organization_name)
    return _create_user(
        email=email,
        full_name=full_name,
        password=password,
        role=User.Role.HEAD_DISPATCHER,
        organization=organization,
    )


@transaction.atomic
def create_staff_user(*, creator, email, password, full_name, role, technician=None):
    """Create a user inside the creator's organization (never taken from the request).

    `technician` is a dict {"skills": [...], "shift_start": t, "shift_end": t}
    and is required when role is technician.
    """
    organization = creator.organization
    user = _create_user(
        email=email,
        full_name=full_name,
        password=password,
        role=role,
        organization=organization,
    )
    if role == User.Role.TECHNICIAN:
        profile = Technician.objects.create(
            user=user,
            organization=organization,
            shift_start=technician["shift_start"],
            shift_end=technician["shift_end"],
        )
        profile.skills.set(technician.get("skills", []))
    return user


@transaction.atomic
def deactivate_user(*, actor, target):
    """Deactivate a user in the actor's organization. Idempotent."""
    # Lock the organization row: two heads deactivating each other are serialised.
    organization = Organization.objects.select_for_update().get(
        pk=actor.organization_id
    )
    target = (
        User.objects.for_organization(organization)
        .select_for_update()
        .get(pk=target.pk)
    )
    if not target.is_active:
        return target
    if target.role == User.Role.HEAD_DISPATCHER:
        other_heads = (
            User.objects.for_organization(organization)
            .filter(role=User.Role.HEAD_DISPATCHER, is_active=True)
            .exclude(pk=target.pk)
        )
        if not other_heads.exists():
            raise LastHeadError
    if target.role == User.Role.TECHNICIAN:
        technician = Technician.objects.get(user=target)
        # Refuse before touching anything; the whole function is one transaction.
        if Job.objects.filter(technician=technician, status=JobStatus.ONGOING).exists():
            raise HasOngoingJobError
        release_assigned_jobs(technician, actor)
    target.is_active = False
    target.save(update_fields=["is_active"])
    return target


@transaction.atomic
def reactivate_user(*, actor, target):
    """Reactivate a user in the actor's organization. Idempotent."""
    target = (
        User.objects.for_organization(actor.organization)
        .select_for_update()
        .get(pk=target.pk)
    )
    if not target.is_active:
        target.is_active = True
        target.save(update_fields=["is_active"])
    return target


def set_password(*, actor, target, new_password):
    """Head sets another user's password. Their sessions die (auth hash changes)."""
    if actor.pk == target.pk:
        raise CannotChangeOwnPasswordHereError
    target.set_password(new_password)  # why does it call it own function(Recurtion)
    target.save(update_fields=["password"])
