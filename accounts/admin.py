from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from . import throttle
from .models import LoginAttempt, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["username", "email", "role", "organisation", "is_active", "last_login"]
    list_filter = ["role", "organisation", "is_active"]
    fieldsets = BaseUserAdmin.fieldsets + (("ΑΤΛΑΣ", {"fields": ["role", "organisation"]}),)
    add_fieldsets = BaseUserAdmin.add_fieldsets + (("ΑΤΛΑΣ", {"fields": ["role", "organisation"]}),)
    actions = ["unlock_login"]

    @admin.action(description="Ξεκλείδωμα σύνδεσης (μηδενισμός αποτυχημένων προσπαθειών)")
    def unlock_login(self, request, queryset):
        total = sum(throttle.unlock(u.username) for u in queryset)
        messages.success(request, f"Ξεκλειδώθηκαν {queryset.count()} χρήστες ({total} αποτυχίες διαγράφηκαν).")


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Μόνο ανάγνωση: το αρχείο δεν διορθώνεται με το χέρι."""

    list_display = ["created_at", "username", "ip_address", "successful"]
    list_filter = ["successful", "created_at"]
    search_fields = ["username", "ip_address"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
