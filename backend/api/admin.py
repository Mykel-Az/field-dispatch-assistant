from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, Organization, Skill

# Register your models here.


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = [
        "email",
        "first_name",
        "last_name",
        "organization",
        "role",
        "is_staff",
        "is_active",
    ]
    list_filter = ["role", "is_staff", "is_active"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("role", "is_staff", "is_active")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "role",
                    "password1",
                    "password2",
                    "is_staff",
                    "is_active",
                ),
            },
        ),
    )
    search_fields = ["email"]
    ordering = ["date_joined"]


admin.site.register(CustomUser, CustomUserAdmin)


class OrganizationAdmin(admin.ModelAdmin):
    model = Organization
    list_display = ["name", "email", "phone_number", "is_active", "created_at"]
    search_fields = ["name", "email"]
    list_filter = ["is_active"]


admin.site.register(Organization, OrganizationAdmin)

admin.site.register(Skill)
