from django.urls import path

from .views import Loginview, Logoutview, Registerview, SkillViewSet, health_check

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("skills/", SkillViewSet.as_view(), name="skills"),
    path("register/", Registerview.as_view(), name="register"),
    path("login/", Loginview.as_view(), name="login"),
    path("logout/", Logoutview.as_view(), name="logout"),
]
