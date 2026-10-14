from django.urls import path

from .views import (
    Loginview,
    Logoutview,
    MeView,
    Registerview,
    SkillViewSet,
    get_csrf_token,
    health_check,
)

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("skills/", SkillViewSet.as_view(), name="skills"),
    path("auth/csrf", get_csrf_token, name="csrf"),
    path("auth/register/", Registerview.as_view(), name="register"),
    path("auth/login/", Loginview.as_view(), name="login"),
    path("auth/logout/", Logoutview.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
]
