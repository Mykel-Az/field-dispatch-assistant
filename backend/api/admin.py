from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, Organization, Skill

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
