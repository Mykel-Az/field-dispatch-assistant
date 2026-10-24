from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower

from .manager import TenantQuerySet, TenantScopedModel

# Create your models here.
phone_validator = RegexValidator(
    r"^\+?[0-9\s().-]{7,20}$",
    "Enter a valid phone number (digits, spaces, + ( ) - . only).",
)


class CustomUserManager(BaseUserManager.from_queryset(TenantQuerySet)):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")

        email = self.normalize_email(email).lower()

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self.db)
        return user

    def create_superuser(
        self, email, password=None, organization=None, role="", **extra_fields
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(
            email=email,
            password=password,
            organization=organization,
            role=role,
            **extra_fields,
        )


class GeocodeStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    OK = "ok", "OK"
    APPROXIMATE = "approximate", "Approximate"  # ZIP centre, street not found
    MANUAL = "manual", "Manual"  # reserved for the map pin-drop fix
    FAILED = "failed", "Failed"


class AddressMixin(models.Model):
    address = models.CharField(max_length=255, blank=True, default="")
    postal_code = models.CharField(max_length=10, blank=True, default="")
    lat = models.FloatField(blank=True, null=True)  # internal: never user-edited
    lng = models.FloatField(blank=True, null=True)
    geocode_status = models.CharField(
        max_length=12, choices=GeocodeStatus.choices, default=GeocodeStatus.PENDING
    )
    location_label = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        abstract = True


class Organization(AddressMixin, models.Model):
    class ScoringStrategy(models.TextChoices):
        BALANCED = "balanced", "Balanced"

    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, default="")
    phone = models.CharField(
        max_length=20, blank=True, default="", validators=[phone_validator]
    )

    work_start = models.TimeField(blank=True, null=True)
    work_end = models.TimeField(blank=True, null=True)
    scoring_strategy = models.CharField(
        max_length=20, choices=ScoringStrategy.choices, default=ScoringStrategy.BALANCED
    )

    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_configured(self) -> bool:
        """Ready to schedule: located (geocoded or pinned) and working hours set."""
        return (
            self.geocode_status in ("ok", "manual")
            and self.lat is not None
            and self.lng is not None
            and self.work_start is not None
            and self.work_end is not None
        )

    def __str__(self) -> str:
        return self.name


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        HEAD_DISPATCHER = "head_dispatcher", "Head Dispatcher"
        DISPATCHER = "dispatcher", "Dispatcher"
        TECHNICIAN = "technician", "Technician"

    username = None
    first_name = None
    last_name = None
    full_name = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True, verbose_name="email address")
    role = models.CharField(max_length=20, choices=Role.choices, blank=True, default="")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="users",
        blank=True,
        null=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()  # type: ignore

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(is_superuser=True)
                | (models.Q(organization__isnull=False) & ~models.Q(role="")),
                name="non_superuser_has_org_and_role",
            ),
            models.UniqueConstraint(Lower("email"), name="unique_lower_case_email"),
        ]

    def get_full_name(self) -> str:
        return self.full_name

    def get_short_name(self) -> str:
        return self.full_name.split(" ")[0] if self.full_name else self.email

    def save(self, *args, **kwargs):
        # Invariant 21: role and organization never change after creation.
        update_fields = kwargs.get("update_fields")
        touches = {"role", "organization", "organization_id"}
        if self.pk and (update_fields is None or touches & set(update_fields)):
            old = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("role", "organization_id")
                .first()
            )
            if old and (
                old["role"] != self.role
                or old["organization_id"] != self.organization_id
            ):
                raise ValueError("role and organization cannot be changed")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.full_name or self.email} ({self.role or 'superuser'})"


class Technician(TenantScopedModel):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="technician_profile"
    )
    skills = models.ManyToManyField("Skill", related_name="technicians", blank=True)
    shift_start = models.TimeField()
    shift_end = models.TimeField()

    phone = models.CharField(
        max_length=20, blank=True, null=True, validators=[phone_validator]
    )

    def save(self, *args, **kwargs):
        # Invariant 25: a technician belongs to the same organization as its user.
        if self.organization_id != self.user.organization_id:
            raise ValueError("technician organization must equal its user's")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.full_name} ({self.user.email})"


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Job(AddressMixin, TenantScopedModel):
    class Status(models.TextChoices):
        UNASSINGED = "unassigned", "Unassigned"
        ASSIGNED = "assigned", "Assigned"
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "completed"
        INCOMPLETE = "incomplete", "Incompleted"
        FAILED = "failed", " Failed"
        CANCELLED = "canceled", "Cancelled"

    class Categories(models.TextChoices):
        HVAC = "hvac", "Hvac"
        ELECTRICAL = "electrical", "Electrical"
        APPLIANCE = "appliance", "Appliance"

    title = models.CharField(max_length=100)
    description = models.TextField()
    customer_name = models.CharField(max_length=50)
    customer_phone = models.CharField(
        max_length=20, blank=True, null=True, validators=[phone_validator]
    )

    category = models.TextChoices(max_length=30, choice=Categories.choices)
    is_urgent = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UNASSINGED
    )
    technician = models.ForeignKey(
        Technician, on_delete=models.PROTECT, related_name="Jobs", blank=True, null=True
    )

    acceptable_skils = models.ManyToManyField(Skill)
    scheduled_date = models.DateTimeField(null=True, blank=True)
    slot_start = models.DateTimeField(null=True, blank=True)
    slot_end = models.DateTimeField(null=True, blank=True)
    sequence_position = models.PositiveIntegerField(null=True, blank=True)
    estimated_arrival = models.DateTimeField(null=True, blank=True)
    version = models.PositiveIntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["technician"],
                condition=Q(status="ongoing"),
                name="one_ongoing_job_per_technician",
            ),  # inv 3
            models.UniqueConstraint(
                fields=["technician", "scheduled_date", "sequence_position"],
                name="unique_stop_per_technician_day",
            ),  # NULLs are distinct in Postgres/SQLite
            models.CheckConstraint(
                condition=~Q(status__in=["assigned", "ongoing"])
                | Q(technician__isnull=False),
                name="assigned_needs_technician",
            ),
            models.CheckConstraint(
                condition=~Q(status="unassigned") | Q(technician__isnull=True),
                name="unassigned_has_no_technician",
            ),  # inv 1
            models.CheckConstraint(
                condition=Q(is_urgent=True)
                | Q(slot_start__isnull=False, slot_end__isnull=False),
                name="non_urgent_has_slot",
            ),  # inv 7
            models.CheckConstraint(
                condition=Q(slot_start__isnull=True) | Q(slot_end__gt=F("slot_start")),
                name="slot_end_after_start",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=["assigned", "ongoing"])
                | Q(geocode_status__in=["ok", "approximate", "manual"]),
                name="no_assignment_without_location",
            ),  # inv 16
        ]
        indexes = [
            models.Index(fields=["organization", "status"], name="wo_org_status_idx"),
            models.Index(
                fields=["organization", "scheduled_date"], name="wo_org_sched_idx"
            ),
            models.Index(fields=["technician"], name="wo_technician_idx"),
        ]

    def save(self, *args, **kwargs):
        # Invariant 25: a technician belongs to the same organization as its user.
        if self.technician.organization_id != self.organization_id:
            raise ValueError("technician organization must equal its user's")
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.title} ({self.status} - {self.technician})"


class JobStatusHistory(TenantScopedModel):
    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="job_history")
    from_status = models.CharField(blank=True)
    to_status = models.CharField()
    changed_by = models.ForeignKey(
        CustomUser, on_delete=models.PROTECT, related_name="job_history"
    )
    reason = models.TextField(max_length=500)
    created_At = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValueError("history rows are append-only")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("history rows are append-only")


class CandidateSkillRule(models.Model):
    category = models.CharField(max_length=30)
    skill = models.ForeignKey(
        Skill, on_delete=models.CASCADE, related_name="candidate_skill_rule"
    )

    class Meta:
        constrainst = [models.UniqueConstraint(fields=["category", "skill"])]
