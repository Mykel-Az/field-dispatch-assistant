from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    CandidateSkillRule,
    CustomUser,
    Job,
    JobStatusHistory,
    Organization,
    Skill,
)

# Register your models here.


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = [
        "email",
        "full_name",
        "organization",
        "role",
        "is_staff",
        "is_active",
    ]
    list_filter = ["role", "is_staff", "is_active"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("full_name",)}),
        (
            "Access",
            {
                "fields": (
                    "role",
                    "organization",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "full_name",
                    "role",
                    "organization",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
    search_fields = ["email", "full_name"]
    ordering = ["date_joined"]

    def get_readonly_fields(self, request, obj=None):
        # Invariant 21: role and organization are fixed once the user exists.
        return ("role", "organization") if obj else ()


admin.site.register(CustomUser, CustomUserAdmin)


class OrganizationAdmin(admin.ModelAdmin):
    model = Organization
    list_display = ["name", "email", "phone", "is_active", "created_at"]
    search_fields = ["name", "email"]
    list_filter = ["is_active"]


admin.site.register(Organization, OrganizationAdmin)

admin.site.register(Skill)


class ReadOnlyAdmin(admin.ModelAdmin):
    """Jobs change through services (status rules, history), never by hand."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Job)
class JobAdmin(ReadOnlyAdmin):
    list_display = ["title", "organization", "status", "technician", "scheduled_date"]
    list_filter = ["status", "category"]
    search_fields = ["title", "customer_name"]


@admin.register(JobStatusHistory)
class JobStatusHistoryAdmin(ReadOnlyAdmin):
    list_display = ["job", "from_status", "to_status", "changed_by", "created_at"]
    list_filter = ["to_status"]


admin.site.register(CandidateSkillRule)
