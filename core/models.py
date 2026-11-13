"""
Βασικά μοντέλα του ΑΤΛΑΣ.

Οι ταξινομίες (επαρχίες, πλαίσια, ευάλωτες ομάδες, επίπεδα πρόληψης) ακολουθούν
την Εθνική Στρατηγική για την Αντιμετώπιση των Εξαρτήσεων 2021–2028 (σ. 39–41).
"""
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .validators import validate_school_year


class Organisation(models.Model):
    """Φορέας που υλοποιεί αδειοδοτημένο προληπτικό πρόγραμμα."""

    name = models.CharField("Επωνυμία", max_length=200, unique=True)
    code = models.SlugField("Κωδικός", max_length=30, unique=True, help_text="Σύντομος κωδικός, π.χ. foreas-a.")
    is_active = models.BooleanField("Ενεργός", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Φορέας"
        verbose_name_plural = "Φορείς"
        ordering = ["name"]

    def __str__(self):
        return self.name


class TaxonomyItem(models.Model):
    name = models.CharField("Ονομασία", max_length=150, unique=True)
    order = models.PositiveSmallIntegerField("Σειρά", default=0)

    class Meta:
        abstract = True
        ordering = ["order", "name"]

    def __str__(self):
        return self.name


class District(TaxonomyItem):
    class Meta(TaxonomyItem.Meta):
        verbose_name = "Επαρχία"
        verbose_name_plural = "Επαρχίες"


class Setting(TaxonomyItem):
    class Meta(TaxonomyItem.Meta):
        verbose_name = "Πλαίσιο"
        verbose_name_plural = "Πλαίσια"


class VulnerableGroup(TaxonomyItem):
    class Meta(TaxonomyItem.Meta):
        verbose_name = "Ευάλωτη ομάδα"
        verbose_name_plural = "Ευάλωτες ομάδες"


class PreventionLevel(models.TextChoices):
    UNIVERSAL = "universal", "Καθολική"
    SELECTIVE = "selective", "Επικεντρωμένη"
    INDICATED = "indicated", "Ενδεδειγμένη"
    ENVIRONMENTAL = "environmental", "Περιβαλλοντική"


class Programme(models.Model):
    """Προφίλ προληπτικού προγράμματος. Συμπληρώνεται μία φορά τον χρόνο από τον φορέα."""

    organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, related_name="programmes", verbose_name="Φορέας"
    )
    title = models.CharField("Τίτλος προγράμματος", max_length=200)
    school_year = models.CharField(
        "Περίοδος υλοποίησης", max_length=20, validators=[validate_school_year], help_text="π.χ. 2026–27"
    )
    level = models.CharField("Επίπεδο πρόληψης", max_length=20, choices=PreventionLevel.choices)
    settings = models.ManyToManyField(Setting, verbose_name="Πλαίσια", related_name="programmes")
    districts = models.ManyToManyField(District, verbose_name="Επαρχίες", related_name="programmes")
    vulnerable_groups = models.ManyToManyField(
        VulnerableGroup, verbose_name="Ευάλωτες ομάδες", related_name="programmes", blank=True
    )
    age_from = models.PositiveSmallIntegerField(
        "Ηλικία από", null=True, blank=True, validators=[MaxValueValidator(99)]
    )
    age_to = models.PositiveSmallIntegerField(
        "Ηλικία έως", null=True, blank=True, validators=[MaxValueValidator(99)]
    )
    trains_professionals = models.BooleanField(
        "Εκπαιδεύει επαγγελματίες για να εφαρμόσουν το πρόγραμμα",
        default=False,
        help_text="π.χ. εκπαιδευτικούς που υλοποιούν το πρόγραμμα στην τάξη.",
    )
    # Λογικό μοντέλο (Οδηγός Πρόληψης / EDPQS)
    need = models.TextField("Ανάγκη που καλύπτει")
    objectives = models.TextField("Στόχοι")
    theory = models.TextField("Θεωρητική βάση", blank=True)
    planned_sessions = models.PositiveSmallIntegerField(
        "Προγραμματισμένες συναντήσεις ανά ομάδα", validators=[MinValueValidator(1), MaxValueValidator(200)]
    )
    expected_outcomes = models.TextField("Αναμενόμενα αποτελέσματα")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+", editable=False
    )

    class Meta:
        verbose_name = "Πρόγραμμα"
        verbose_name_plural = "Προγράμματα"
        ordering = ["organisation__name", "title"]
        constraints = [
            models.UniqueConstraint(fields=["organisation", "title", "school_year"], name="unique_programme_per_year"),
        ]

    def __str__(self):
        return f"{self.title} ({self.school_year})"

    def clean(self):
        if self.age_from is not None and self.age_to is not None and self.age_from > self.age_to:
            raise ValidationError({"age_to": "Η ηλικία «έως» δεν μπορεί να είναι μικρότερη από την ηλικία «από»."})
        if self.level != PreventionLevel.ENVIRONMENTAL and (self.age_from is None or self.age_to is None):
            raise ValidationError({"age_from": "Συμπληρώστε το ηλικιακό εύρος (δεν απαιτείται μόνο στην περιβαλλοντική πρόληψη)."})

    @property
    def has_individual_questionnaire(self):
        """Στην περιβαλλοντική πρόληψη δεν εφαρμόζεται ατομικό ερωτηματολόγιο."""
        return self.level != PreventionLevel.ENVIRONMENTAL
