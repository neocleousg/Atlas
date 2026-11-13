"""
Βασικά μοντέλα του ΑΤΛΑΣ.

Οι ταξινομίες (επαρχίες, πλαίσια, ευάλωτες ομάδες, επίπεδα πρόληψης) ακολουθούν
την Εθνική Στρατηγική για την Αντιμετώπιση των Εξαρτήσεων 2021–2028 (σ. 39–41).
"""
import calendar
from datetime import date

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


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


class AgeGroup(TaxonomyItem):
    class Meta(TaxonomyItem.Meta):
        verbose_name = "Ηλικιακή ομάδα"
        verbose_name_plural = "Ηλικιακές ομάδες"


class PreventionLevel(models.TextChoices):
    UNIVERSAL = "universal", "Καθολική"
    SELECTIVE = "selective", "Επικεντρωμένη"
    INDICATED = "indicated", "Ενδεδειγμένη"
    ENVIRONMENTAL = "environmental", "Περιβαλλοντική"


# Στην περιβαλλοντική πρόληψη δεν υπάρχουν άτομα που «ολοκληρώνουν» ή «αποχωρούν»
# (ανοικτό ζήτημα 4 της πρότασης). Μέχρι να οριστεί, δεν δηλώνεται ανά τετραμηνία.
DECLARABLE_LEVELS = [PreventionLevel.UNIVERSAL, PreventionLevel.SELECTIVE, PreventionLevel.INDICATED]


class Period(models.Model):
    """Τετραμηνία: Ιαν–Απρ (1), Μάι–Αύγ (2), Σεπ–Δεκ (3)."""

    PARTS = {1: (1, 4, "Ιαν–Απρ"), 2: (5, 8, "Μαΐ–Αυγ"), 3: (9, 12, "Σεπ–Δεκ")}

    year = models.PositiveSmallIntegerField("Έτος")
    part = models.PositiveSmallIntegerField("Τετραμηνία", choices=[(k, v[2]) for k, v in PARTS.items()])
    deadline = models.DateField("Προθεσμία υποβολής", help_text="Ορίζεται από την ΑΑΕΚ.")

    class Meta:
        verbose_name = "Τετραμηνία"
        verbose_name_plural = "Τετραμηνίες"
        ordering = ["-year", "-part"]
        constraints = [models.UniqueConstraint(fields=["year", "part"], name="unique_period")]

    def __str__(self):
        return self.label

    @property
    def label(self):
        return f"{self.PARTS[self.part][2]} {self.year}"

    @property
    def key(self):
        return (self.year, self.part)

    @property
    def start(self):
        return date(self.year, self.PARTS[self.part][0], 1)

    @property
    def end(self):
        m = self.PARTS[self.part][1]
        return date(self.year, m, calendar.monthrange(self.year, m)[1])

    @staticmethod
    def default_deadline(year, part):
        """Τελευταία μέρα του επόμενου μήνα: 31/05, 30/09, 31/01."""
        if part == 3:
            return date(year + 1, 1, 31)
        m = Period.PARTS[part][1] + 1
        return date(year, m, calendar.monthrange(year, m)[1])

    @staticmethod
    def key_for(day):
        return (day.year, (day.month - 1) // 4 + 1)

    @staticmethod
    def previous_key(key):
        year, part = key
        return (year - 1, 3) if part == 1 else (year, part - 1)

    @classmethod
    def get(cls, key):
        year, part = key
        obj, _ = cls.objects.get_or_create(year=year, part=part, defaults={"deadline": cls.default_deadline(year, part)})
        return obj

    @classmethod
    def to_declare(cls, today=None):
        """Η τετραμηνία που δηλώνεται τώρα: η τελευταία που έκλεισε."""
        today = today or timezone.localdate()
        return cls.get(cls.previous_key(cls.key_for(today)))

    @classmethod
    def recent(cls, n=3, today=None):
        """Οι n τελευταίες τετραμηνίες που έκλεισαν, από την παλαιότερη στη νεότερη."""
        key = cls.to_declare(today).key
        keys = [key]
        for _ in range(n - 1):
            keys.append(cls.previous_key(keys[-1]))
        return [cls.get(k) for k in reversed(keys)]

    def is_open_for_edits(self, today=None):
        return (today or timezone.localdate()) <= self.deadline


class Programme(models.Model):
    """
    Προφίλ προγράμματος, όπως στο demo: λίγα στοιχεία, ορίζονται μία φορά από τη Διαχείριση.
    Κάθε πρόγραμμα έχει έναν υπεύθυνο λειτουργό του φορέα, που κάνει τις δηλώσεις.
    """

    organisation = models.ForeignKey(
        Organisation, on_delete=models.PROTECT, related_name="programmes", verbose_name="Φορέας"
    )
    title = models.CharField("Όνομα προγράμματος", max_length=200)
    level = models.CharField("Επίπεδο πρόληψης", max_length=20, choices=PreventionLevel.choices)
    district = models.ForeignKey(District, on_delete=models.PROTECT, verbose_name="Επαρχία", related_name="programmes")
    setting = models.ForeignKey(Setting, on_delete=models.PROTECT, verbose_name="Πλαίσιο", related_name="programmes")
    age_groups = models.ManyToManyField(
        AgeGroup, verbose_name="Ηλικιακές ομάδες-στόχος", related_name="programmes", blank=True
    )
    officer = models.ForeignKey(
        django_settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="programmes",
        verbose_name="Υπεύθυνος λειτουργός",
        limit_choices_to={"role": "organisation"},
        help_text="Βλέπει και δηλώνει μόνο τα προγράμματα που του έχουν ανατεθεί.",
    )
    first_period = models.ForeignKey(
        Period,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Πρώτη τετραμηνία δήλωσης",
        help_text="Αφήστε κενό αν το πρόγραμμα δηλώνει από την αρχή του ΑΤΛΑΣ.",
    )
    is_active = models.BooleanField("Ενεργό", default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Πρόγραμμα"
        verbose_name_plural = "Προγράμματα"
        ordering = ["organisation__name", "title"]
        constraints = [
            models.UniqueConstraint(fields=["organisation", "title"], name="unique_programme_per_organisation"),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        if self.officer_id and self.organisation_id and self.officer.organisation_id != self.organisation_id:
            raise ValidationError({"officer": "Ο λειτουργός πρέπει να ανήκει στον ίδιο φορέα με το πρόγραμμα."})

    @property
    def is_declarable(self):
        return self.level in DECLARABLE_LEVELS

    def expected_in(self, period):
        """Αναμένεται δήλωση για αυτή την τετραμηνία;"""
        if not self.is_declarable:
            return False
        return self.first_period is None or self.first_period.key <= period.key

    def declaration_for(self, period):
        return self.declarations.filter(period=period).first()

    def previous_declaration(self, period):
        """Η πιο πρόσφατη δήλωση πριν από την τετραμηνία: από εκεί έρχονται οι ανοικτές περιπτώσεις."""
        return (
            self.declarations.filter(Q(period__year__lt=period.year) | Q(period__year=period.year, period__part__lt=period.part))
            .order_by("-period__year", "-period__part")
            .first()
        )


class Declaration(models.Model):
    """
    Δήλωση τετραμηνίας για ένα πρόγραμμα. Μόνο σύνολα, κανένα στοιχείο συμμετεχόντων.

    Φύλο και ηλικίες είναι προαιρετικά: None σημαίνει «δεν δηλώθηκε», ΟΧΙ μηδέν.
    """

    programme = models.ForeignKey(Programme, on_delete=models.PROTECT, related_name="declarations", verbose_name="Πρόγραμμα")
    period = models.ForeignKey(Period, on_delete=models.PROTECT, related_name="declarations", verbose_name="Τετραμηνία")

    open_start = models.PositiveIntegerField("Ανοικτές περιπτώσεις από προηγούμενη τετραμηνία")
    new = models.PositiveIntegerField("Νέοι εξυπηρετούμενοι")
    completed = models.PositiveIntegerField("Ολοκλήρωσαν")
    withdrawn = models.PositiveIntegerField("Αποχώρησαν")

    sex_male = models.PositiveIntegerField("Αγόρια / άνδρες", null=True, blank=True)
    sex_female = models.PositiveIntegerField("Κορίτσια / γυναίκες", null=True, blank=True)
    sex_other = models.PositiveIntegerField("Άλλο / δεν δηλώθηκε", null=True, blank=True)
    ages = models.JSONField(
        "Νέοι κατά ηλικία", null=True, blank=True, help_text="{id ηλικιακής ομάδας: πλήθος}. Κενό = δεν δηλώθηκε."
    )
    note = models.TextField("Δυσκολίες ή σχόλια", max_length=300, blank=True)

    submitted_at = models.DateTimeField("Πρώτη υποβολή", default=timezone.now)
    updated_at = models.DateTimeField("Τελευταία αλλαγή", auto_now=True)
    submitted_by = models.ForeignKey(
        django_settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
        verbose_name="Υποβλήθηκε από",
    )
    revisions = models.PositiveSmallIntegerField("Διορθώσεις", default=0)
    fill_seconds = models.PositiveIntegerField("Χρόνος συμπλήρωσης (δευτ.)", null=True, blank=True)

    class Meta:
        verbose_name = "Δήλωση τετραμηνίας"
        verbose_name_plural = "Δηλώσεις τετραμηνίας"
        ordering = ["-period__year", "-period__part", "programme__title"]
        constraints = [
            models.UniqueConstraint(fields=["programme", "period"], name="one_declaration_per_period"),
            models.CheckConstraint(
                condition=Q(completed__lte=F("open_start") + F("new") - F("withdrawn")),
                name="outflow_not_above_served",
            ),
        ]

    def __str__(self):
        return f"{self.programme} · {self.period}"

    @property
    def served(self):
        return self.open_start + self.new

    @property
    def open_end(self):
        return self.served - self.completed - self.withdrawn

    @property
    def completion_rate(self):
        done = self.completed + self.withdrawn
        return round(self.completed * 100 / done) if done else None

    @property
    def sex(self):
        values = [self.sex_male, self.sex_female, self.sex_other]
        return None if all(v is None for v in values) else [v or 0 for v in values]

    @property
    def on_time(self):
        return timezone.localdate(self.submitted_at) <= self.period.deadline
