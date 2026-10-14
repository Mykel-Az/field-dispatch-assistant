from rest_framework.permissions import BasePermission

from .models import CustomUser


class HasRole(BasePermission):
    allowed_role = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_active
            and user.is_authenticated
            and user.role in self.allowed_role
        )


class IsHeadDispatcher(HasRole):
    allowed_role = (CustomUser.Role.HEAD_DISPATCHER,)


class IsDispatcher(HasRole):
    allowed_role = (CustomUser.Role.DISPATCHER, CustomUser.Role.HEAD_DISPATCHER)


class IsTechnician(HasRole):
    allowed_role = (CustomUser.Role.TECHNICIAN,)
