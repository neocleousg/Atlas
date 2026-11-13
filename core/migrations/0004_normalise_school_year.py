"""
Ενιαία μορφή περιόδου (2026–27) για όσα προγράμματα γράφτηκαν πριν από τον έλεγχο,
π.χ. 2026-27 ή 2026/27. Αν η αλλαγή θα δημιουργούσε διπλότυπο, η εγγραφή μένει ως έχει
για να τη δει ο διαχειριστής.
"""
import re

from django.db import migrations

PATTERN = re.compile(r"^\s*(\d{4})\s*[-–—/]\s*(\d{2})\s*$")


def normalise(apps, schema_editor):
    Programme = apps.get_model("core", "Programme")
    for p in Programme.objects.all():
        m = PATTERN.match(p.school_year or "")
        if not m:
            continue
        value = f"{m.group(1)}–{m.group(2)}"
        if value == p.school_year:
            continue
        clash = Programme.objects.filter(organisation_id=p.organisation_id, title=p.title, school_year=value)
        if not clash.exists():
            p.school_year = value
            p.save(update_fields=["school_year"])


class Migration(migrations.Migration):
    dependencies = [("core", "0003_programme_validators")]
    operations = [migrations.RunPython(normalise, migrations.RunPython.noop)]
