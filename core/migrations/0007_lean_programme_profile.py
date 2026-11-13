"""
Λιτό προφίλ προγράμματος, όπως στο demo: αφαιρούνται περίοδος, λογικό μοντέλο, συναντήσεις,
ηλικίες από/έως, πολλαπλά πλαίσια/επαρχίες. Τα δεδομένα τους μεταφέρθηκαν στο 0006.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("core", "0006_migrate_programme_profiles")]

    operations = [
        migrations.RemoveConstraint(
            model_name="programme",
            name="unique_programme_per_year",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="age_from",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="age_to",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="created_by",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="districts",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="expected_outcomes",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="need",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="objectives",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="planned_sessions",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="school_year",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="settings",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="theory",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="trains_professionals",
        ),
        migrations.RemoveField(
            model_name="programme",
            name="vulnerable_groups",
        ),
        migrations.AlterField(
            model_name="programme",
            name="district",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="programmes",
                to="core.district",
                verbose_name="Επαρχία",
            ),
        ),
        migrations.AlterField(
            model_name="programme",
            name="setting",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="programmes",
                to="core.setting",
                verbose_name="Πλαίσιο",
            ),
        ),
        migrations.AddConstraint(
            model_name="programme",
            constraint=models.UniqueConstraint(
                fields=("organisation", "title"),
                name="unique_programme_per_organisation",
            ),
        ),
    ]
