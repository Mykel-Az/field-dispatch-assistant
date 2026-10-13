from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Skill
from .services.accounts import register_organization

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "organization",
            "is_staff",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "role", "is_staff", "is_active", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(max_length=255, required=True)
    password = serializers.CharField(write_only=True, required=True)

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

    def validate(self, value):
        validate_password(value, self.instance)
        return value

    def create(self, validated_data):
        user = register_organization(**validated_data)
        return user


class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        user = authenticate(attrs["email"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        attrs["user"] = user
        return attrs


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "description"]
