"""
Μεταφορά των υπαρχόντων προφίλ στη νέα, λιτή μορφή:
- πολλαπλές επαρχίες/πλαίσια → η πρώτη (κατά σειρά) γίνεται η επαρχία/το πλαίσιο,
- ηλικία από/έως → οι ηλικιακές ομάδες που επικαλύπτουν το εύρος,
- ίδιος τίτλος σε διαφορετικές περιόδους → προστίθεται η περίοδος στον τίτλο (νέα μοναδικότητα ανά φορέα).
Σπέρνει και τις ηλικιακές ομάδες του demo.
"""
from django.db import migrations

AGE_GROUPS = [("6–12", 6, 12), ("13–15", 13, 15), ("16–18", 16, 18), ("19–25", 19, 25), ("26+", 26, 200)]


def forward(apps, schema_editor):
    AgeGroup = apps.get_model("core", "AgeGroup")
    Programme = apps.get_model("core", "Programme")
    groups = []
    for i, (name, lo, hi) in enumerate(AGE_GROUPS, start=1):
        g, _ = AgeGroup.objects.update_or_create(name=name, defaults={"order": i})
        groups.append((g, lo, hi))

    seen = set()
    for p in Programme.objects.order_by("organisation_id", "title", "school_year"):
        d = p.districts.order_by("order").first()
        s = p.settings.order_by("order").first()
        p.district_id = d.pk if d else None
        p.setting_id = s.pk if s else None
        key = (p.organisation_id, p.title)
        if key in seen:
            p.title = f"{p.title} ({p.school_year})"[:200]
        seen.add((p.organisation_id, p.title))
        p.save(update_fields=["district", "setting", "title"])
        if p.age_from is not None and p.age_to is not None:
            p.age_groups.set([g for g, lo, hi in groups if lo <= p.age_to and hi >= p.age_from])

    # Προφίλ χωρίς επαρχία ή πλαίσιο δεν θα έπρεπε να υπάρχουν (ήταν υποχρεωτικά). Αν υπάρχουν, σταματάμε.
    broken = Programme.objects.filter(district__isnull=True) | Programme.objects.filter(setting__isnull=True)
    if broken.exists():
        raise RuntimeError(f"Προγράμματα χωρίς επαρχία ή πλαίσιο: {list(broken.values_list('pk', flat=True))}")


class Migration(migrations.Migration):
    dependencies = [("core", "0005_quarterly_declarations")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
