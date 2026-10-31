from django.contrib import admin

from .models import District, Organisation, Programme, Setting, VulnerableGroup


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]
    prepopulated_fields = {"code": ["name"]}


@admin.register(District, Setting, VulnerableGroup)
class TaxonomyAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    list_editable = ["order"]


@admin.register(Programme)
class ProgrammeAdmin(admin.ModelAdmin):
    list_display = ["title", "organisation", "school_year", "level", "updated_at"]
    list_filter = ["level", "school_year", "organisation", "districts"]
    search_fields = ["title", "organisation__name"]
    filter_horizontal = ["settings", "districts", "vulnerable_groups"]
