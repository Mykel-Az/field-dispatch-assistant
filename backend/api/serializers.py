from rest_framework import serializers

from .models import Skill


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name", "description"]
