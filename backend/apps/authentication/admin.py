from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CampusShareUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("CampusShare", {"fields": ("role",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("CampusShare", {"fields": ("role",)}),
    )
    list_display = (*UserAdmin.list_display, "role")
