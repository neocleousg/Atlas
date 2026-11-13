from django.contrib import admin, messages

from .models import AgeGroup, Declaration, District, Organisation, Period, Programme, Setting, VulnerableGroup


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]
    prepopulated_fields = {"code": ["name"]}


@admin.register(District, Setting, VulnerableGroup, AgeGroup)
class TaxonomyAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ["title", "organisation", "level", "district", "setting", "officer", "is_active"]
    list_filter = ["is_active", "level", "district", "organisation"]
    search_fields = ["title", "organisation__name"]
    filter_horizontal = ["age_groups"]
    autocomplete_fields = []

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "officer":
            from accounts.models import User
            kwargs["queryset"] = User.objects.filter(role="organisation", is_active=True).select_related("organisation")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Period)
class PeriodAdmin(admin.ModelAdmin):
    list_display = ["label", "deadline"]
    fields = ["year", "part", "deadline"]


@admin.register(Declaration)
class DeclarationAdmin(admin.ModelAdmin):
    """
    Οι δηλώσεις διορθώνονται μόνο από τον φορέα. Η Διαχείριση μπορεί μόνο να τις δει
    και να σβήσει ένα σχόλιο που περιέχει κατά λάθος προσωπικά στοιχεία.
    """

    list_display = ["programme", "period", "new", "completed", "withdrawn", "submitted_at", "revisions"]
    list_filter = ["period", "programme__organisation"]
    search_fields = ["programme__title", "note"]
    actions = ["clear_note"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.action(description="Διαγραφή σχολίου (π.χ. περιέχει προσωπικά στοιχεία)")
    def clear_note(self, request, queryset):
        n = queryset.exclude(note="").update(note="")
        messages.success(request, f"Διαγράφηκαν {n} σχόλια.")
