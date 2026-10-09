from django.urls import path

from .views import SkillViewSet, health_check

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("skills/", SkillViewSet.as_view(), name="skills"),
]
