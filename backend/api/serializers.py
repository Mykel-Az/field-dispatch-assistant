from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Organization, Skill
from .services.accounts import register_organization

User = get_user_model()


class OrganizationSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name"]


class UserSerializer(serializers.ModelSerializer):
    organization = OrganizationSummarySerializer()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "organization",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "organization", "role", "is_active", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(max_length=255, required=True)
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "organization_name",
            "password",
        ]

    def create(self, validated_data):
        user = register_organization(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        request = self.context.get("request")

        user = authenticate(request=request, email=email.lower(), password=password)
        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.")
        self.context["user"] = user
        return data


class StaffCreateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, validators=[validate_password]
    )

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "role",
            "password",
        ]


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "description"]
