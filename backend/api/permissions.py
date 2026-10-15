from rest_framework.permissions import BasePermission

from .models import CustomUser


class DenyAll(BasePermission):
    """The project-wide default: a view must name its permissions explicitly."""

    def has_permission(self, request, view):
        return False


class HasRole(BasePermission):
    allowed_role: tuple = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.organization_id is not None
            and user.role in self.allowed_role
        )


class IsHeadDispatcher(HasRole):
    allowed_role = (CustomUser.Role.HEAD_DISPATCHER,)


class IsDispatcher(HasRole):
    """Dispatchers and head dispatchers (a head can do everything a dispatcher can)."""

    allowed_role = (CustomUser.Role.DISPATCHER, CustomUser.Role.HEAD_DISPATCHER)


class IsTechnician(HasRole):
    allowed_role = (CustomUser.Role.TECHNICIAN,)


class IsSignedInMember(BasePermission):
    """Any signed-in user who belongs to an organization (for /auth/* endpoints)."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.is_active
            and user.organization_id is not None
        )
