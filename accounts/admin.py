from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "role", "organisation", "is_active", "last_login"]
    list_filter = ["role", "organisation", "is_active"]
    fieldsets = BaseUserAdmin.fieldsets + (("ΑΤΛΑΣ", {"fields": ["role", "organisation"]}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("ΑΤΛΑΣ", {"fields": ["role", "organisation"]}),)
