from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

from .manager import TenantQuerySet, TenantScopedModel

# Create your models here.


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


class Organization(models.Model):
    class ScoringStrategy(models.TextChoices):
        OPTION1 = "option_1", "Option 1"

    name = models.CharField(max_length=255)
    workstation_address = models.CharField(max_length=255, blank=True, null=True)
    workstation_latitude = models.FloatField(blank=True, null=True)
    workstation_longitude = models.FloatField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    work_hours_start = models.TimeField(blank=True, null=True)
    work_hours_end = models.TimeField(blank=True, null=True)

    scoring_strategy = models.CharField(
        max_length=20, choices=ScoringStrategy.choices, default=ScoringStrategy.OPTION1
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        HEAD_DISPATCHER = "head_dispatcher", "Head Dispatcher"
        DISPATCHER = "dispatcher", "Dispatcher"
        TECHNICIAN = "technician", "Technician"

    username = None
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

    def __str__(self) -> str:
        return f"{self.get_full_name()} - ({self.email}) - {self.role}"


class Technician(TenantScopedModel):
    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="technician_profile"
    )
    skills = models.ManyToManyField("Skill", related_name="technicians", blank=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)

    def __str__(self) -> str:
        return f"{self.user.get_full_name()} - ({self.user.email})"


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
