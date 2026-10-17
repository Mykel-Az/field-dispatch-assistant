from django.urls import include, path
from rest_framework.routers import SimpleRouter

from .views import (
    ChangePasswordView,
    LoginView,
    LogoutView,
    MeView,
    OrganizationView,
    RegisterView,
    SkillViewSet,
    TechnicianViewSet,
    UserViewSet,
    get_csrf_token,
    health_check,
)

router = SimpleRouter()  # SimpleRouter: no auto-generated API root view
router.register("users", UserViewSet, basename="user")
router.register("technicians", TechnicianViewSet, basename="technician")

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("skills/", SkillViewSet.as_view(), name="skills"),
    path("auth/csrf/", get_csrf_token, name="csrf"),
    path("auth/register/", RegisterView.as_view(), name="register"),
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    path("auth/change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("organization/", OrganizationView.as_view(), name="organization"),
    path("", include(router.urls)),
]
