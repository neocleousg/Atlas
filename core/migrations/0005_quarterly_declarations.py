"""Δήλωση τετραμηνίας: νέα μοντέλα και νέα πεδία προγράμματος (τα παλιά αφαιρούνται στο 0007)."""

import django.db.models.deletion
import django.db.models.expressions
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_normalise_school_year"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AgeGroup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        max_length=150, unique=True, verbose_name="Ονομασία"
                    ),
                ),
                (
                    "order",
                    models.PositiveSmallIntegerField(default=0, verbose_name="Σειρά"),
                ),
            ],
            options={
                "verbose_name": "Ηλικιακή ομάδα",
                "verbose_name_plural": "Ηλικιακές ομάδες",
                "ordering": ["order", "name"],
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="Declaration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "open_start",
                    models.PositiveIntegerField(
                        verbose_name="Ανοικτές περιπτώσεις από προηγούμενη τετραμηνία"
                    ),
                ),
                (
                    "new",
                    models.PositiveIntegerField(verbose_name="Νέοι εξυπηρετούμενοι"),
                ),
                ("completed", models.PositiveIntegerField(verbose_name="Ολοκλήρωσαν")),
                ("withdrawn", models.PositiveIntegerField(verbose_name="Αποχώρησαν")),
                (
                    "sex_male",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Αγόρια / άνδρες"
                    ),
                ),
                (
                    "sex_female",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Κορίτσια / γυναίκες"
                    ),
                ),
                (
                    "sex_other",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Άλλο / δεν δηλώθηκε"
                    ),
                ),
                (
                    "ages",
                    models.JSONField(
                        blank=True,
                        help_text="{id ηλικιακής ομάδας: πλήθος}. Κενό = δεν δηλώθηκε.",
                        null=True,
                        verbose_name="Νέοι κατά ηλικία",
                    ),
                ),
                (
                    "note",
                    models.TextField(
                        blank=True, max_length=300, verbose_name="Δυσκολίες ή σχόλια"
                    ),
                ),
                (
                    "submitted_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="Πρώτη υποβολή"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Τελευταία αλλαγή"
                    ),
                ),
                (
                    "revisions",
                    models.PositiveSmallIntegerField(
                        default=0, verbose_name="Διορθώσεις"
                    ),
                ),
                (
                    "fill_seconds",
                    models.PositiveIntegerField(
                        blank=True, null=True, verbose_name="Χρόνος συμπλήρωσης (δευτ.)"
                    ),
                ),
            ],
            options={
                "verbose_name": "Δήλωση τετραμηνίας",
                "verbose_name_plural": "Δηλώσεις τετραμηνίας",
                "ordering": ["-period__year", "-period__part", "programme__title"],
            },
        ),
        migrations.CreateModel(
            name="Period",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("year", models.PositiveSmallIntegerField(verbose_name="Έτος")),
                (
                    "part",
                    models.PositiveSmallIntegerField(
                        choices=[(1, "Ιαν–Απρ"), (2, "Μαΐ–Αυγ"), (3, "Σεπ–Δεκ")],
                        verbose_name="Τετραμηνία",
                    ),
                ),
                (
                    "deadline",
                    models.DateField(
                        help_text="Ορίζεται από την ΑΑΕΚ.",
                        verbose_name="Προθεσμία υποβολής",
                    ),
                ),
            ],
            options={
                "verbose_name": "Τετραμηνία",
                "verbose_name_plural": "Τετραμηνίες",
                "ordering": ["-year", "-part"],
            },
        ),
        migrations.AddField(
            model_name="programme",
            name="district",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="programmes",
                to="core.district",
                verbose_name="Επαρχία",
            ),
        ),
        migrations.AddField(
            model_name="programme",
            name="is_active",
            field=models.BooleanField(default=True, verbose_name="Ενεργό"),
        ),
        migrations.AddField(
            model_name="programme",
            name="officer",
            field=models.ForeignKey(
                blank=True,
                help_text="Βλέπει και δηλώνει μόνο τα προγράμματα που του έχουν ανατεθεί.",
                limit_choices_to={"role": "organisation"},
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="programmes",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Υπεύθυνος λειτουργός",
            ),
        ),
        migrations.AddField(
            model_name="programme",
            name="setting",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="programmes",
                to="core.setting",
                verbose_name="Πλαίσιο",
            ),
        ),
        migrations.AlterField(
            model_name="programme",
            name="title",
            field=models.CharField(max_length=200, verbose_name="Όνομα προγράμματος"),
        ),
        migrations.AddField(
            model_name="programme",
            name="age_groups",
            field=models.ManyToManyField(
                blank=True,
                related_name="programmes",
                to="core.agegroup",
                verbose_name="Ηλικιακές ομάδες-στόχος",
            ),
        ),
        migrations.AddField(
            model_name="declaration",
            name="programme",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="declarations",
                to="core.programme",
                verbose_name="Πρόγραμμα",
            ),
        ),
        migrations.AddField(
            model_name="declaration",
            name="submitted_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Υποβλήθηκε από",
            ),
        ),
        migrations.AddConstraint(
            model_name="period",
            constraint=models.UniqueConstraint(
                fields=("year", "part"), name="unique_period"
            ),
        ),
        migrations.AddField(
            model_name="declaration",
            name="period",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="declarations",
                to="core.period",
                verbose_name="Τετραμηνία",
            ),
        ),
        migrations.AddField(
            model_name="programme",
            name="first_period",
            field=models.ForeignKey(
                blank=True,
                help_text="Αφήστε κενό αν το πρόγραμμα δηλώνει από την αρχή του ΑΤΛΑΣ.",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="core.period",
                verbose_name="Πρώτη τετραμηνία δήλωσης",
            ),
        ),
        migrations.AddConstraint(
            model_name="declaration",
            constraint=models.UniqueConstraint(
                fields=("programme", "period"), name="one_declaration_per_period"
            ),
        ),
        migrations.AddConstraint(
            model_name="declaration",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "completed__lte",
                        django.db.models.expressions.CombinedExpression(
                            django.db.models.expressions.CombinedExpression(
                                models.F("open_start"), "+", models.F("new")
                            ),
                            "-",
                            models.F("withdrawn"),
                        ),
                    )
                ),
                name="outflow_not_above_served",
            ),
        ),
    ]
