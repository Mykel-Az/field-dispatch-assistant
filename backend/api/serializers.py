from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Job, JobStatusHistory, Organization, Skill, Technician
from .services.accounts import register_organization

User = get_user_model()

GENERIC_LOGIN_ERROR = "Invalid email or password."


class OrganizationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSummarySerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "organization",
        ]
        read_only_fields = fields


def _normalized_available_email(value: str) -> str:
    email = value.strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        # Deliberately vague: do not reveal which organization owns the email.
        raise serializers.ValidationError("Email unavailable.")
    return email


class RegisterSerializer(serializers.Serializer):
    organization_name = serializers.CharField(max_length=255, required=True)
    email = serializers.EmailField(required=True)
    full_name = serializers.CharField(max_length=150)
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        return _normalized_available_email(value)

    def create(self, validated_data):
        return register_organization(**validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            email=attrs["email"].strip().lower(),
            password=attrs["password"],
        )
        if user is None or user.organization_id is None:
            raise serializers.ValidationError(GENERIC_LOGIN_ERROR)
        attrs["user"] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        if not self.context["request"].user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate_new_password(self, value):
        validate_password(value, self.context["request"].user)
        return value


class TechnicianInputSerializer(serializers.Serializer):
    skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True,
        source="skills",
        allow_empty=False,
        error_messages={"empty": "Select at least one skill."},
    )
    shift_start = serializers.TimeField()
    shift_end = serializers.TimeField()

    def validate(self, attrs):
        if attrs["shift_end"] <= attrs["shift_start"]:
            raise serializers.ValidationError("shift_end must be after shift_start.")
        return attrs


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "description"]


class TechnicianDetailSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    skills = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = Technician
        fields = [
            "id",
            "user",
            "skills",
            "shift_start",
            "shift_end",
            "phone",
        ]
        read_only_fields = fields


class TechnicianUpdateSerializer(serializers.ModelSerializer):
    """PATCH /technicians/{id}/. No user, organization or coordinates here."""

    skill_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(),
        many=True,
        source="skills",
        required=False,
        allow_empty=False,
        error_messages={"empty": "Select at least one skill."},
    )

    class Meta:
        model = Technician
        fields = ["skill_ids", "shift_start", "shift_end", "phone"]

    def validate(self, attrs):
        # PATCH may send only one of the two, so fall back to the stored value.
        start = attrs.get("shift_start", self.instance.shift_start)
        end = attrs.get("shift_end", self.instance.shift_end)
        if end <= start:
            raise serializers.ValidationError("shift_end must be after shift_start.")
        return attrs


class StaffCreateSerializer(serializers.Serializer):
    """Input for POST /users/. There is deliberately no `organization` field."""

    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    full_name = serializers.CharField(max_length=150)
    role = serializers.ChoiceField(choices=User.Role.choices)
    technician = TechnicianInputSerializer(required=False)

    def validate_email(self, value):
        return _normalized_available_email(value)

    def validate(self, attrs):
        is_technician = attrs["role"] == User.Role.TECHNICIAN
        if is_technician and "technician" not in attrs:
            raise serializers.ValidationError(
                {"technician": "Required when role is technician."}
            )
        if not is_technician and "technician" in attrs:
            raise serializers.ValidationError(
                {"technician": "Only allowed when role is technician."}
            )
        return attrs


class UserUpdateSerializer(serializers.Serializer):
    """PATCH /users/{id}/ accepts full_name only; anything else is a 400."""

    full_name = serializers.CharField(max_length=150)

    def validate(self, attrs):
        extra = set(self.initial_data) - set(self.fields)
        if extra:
            raise serializers.ValidationError(
                {name: "This field cannot be changed." for name in sorted(extra)}
            )
        return attrs


class SetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        write_only=True, validators=[validate_password]
    )


class OrganizationSerializer(serializers.ModelSerializer):
    is_configured = serializers.BooleanField(read_only=True)
    # Required on PATCH: the version the client last saw (optimistic locking).
    version = serializers.IntegerField(min_value=1)

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "email",
            "phone",
            "address",
            "lat",
            "lng",
            "geocode_status",
            "work_start",
            "work_end",
            "scoring_strategy",
            "is_configured",
            "version",
        ]
        read_only_fields = ["id", "geocode_status"]
        extra_kwargs = {
            "lat": {"min_value": -90, "max_value": 90},
            "lng": {"min_value": -180, "max_value": 180},
        }

    def validate(self, attrs):
        if self.partial and "version" not in attrs:
            raise serializers.ValidationError({"version": "This field is required."})
        start = attrs.get("work_start", self.instance and self.instance.work_start)
        end = attrs.get("work_end", self.instance and self.instance.work_end)
        if start and end and end <= start:
            raise serializers.ValidationError("work_end must be after work_start.")
        return attrs


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()


class JobSerializer(serializers.ModelSerializer):
    technician = TechnicianDetailSerializer()

    class Meta:
        models = Job
        fields = [
            "id",
            "title",
            "customer_name",
            "address",
            "postal_code",
            "category",
            "is_urgent",
            "status",
            "technician{id, full_name}",
            "scheduled_date",
            "slot_start",
            "slot_end",
            "geocode_status",
            "location_label",
        ]


class JobHistorySerializer(serializers.ModelSerializer):
    class Meta:
        models = JobStatusHistory
        fields = ["__all__"]


class JobDetailSerializer(serializers.ModelSerializer):
    job = JobSerializer()
    history = JobHistorySerializer()
    acceptable_skills = SkillSerializer()

    class Meta:
        models = Job
        fields = [
            "job",
            "description",
            "customer_phone",
            "acceptable_skills[{id, name}]",
            "version",
            "created_at",
            "history",
        ]


class JobCreateSerializer(serializers.Serializer):
    pass
