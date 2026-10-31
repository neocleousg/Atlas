"""
Ταξινομίες της Εθνικής Στρατηγικής για την Αντιμετώπιση των Εξαρτήσεων 2021–2028.
Πλαίσια: σ. 40. Ευάλωτες ομάδες: σ. 41.
"""
from django.db import migrations

DISTRICTS = ["Λευκωσία", "Λεμεσός", "Λάρνακα", "Πάφος", "Αμμόχωστος"]
SETTINGS = ["Οικογένεια", "Σχολείο", "Πανεπιστήμιο", "Εθνική Φρουρά", "Κοινότητα", "Εργασία"]
VULNERABLE_GROUPS = [
    "Παιδιά που εγκαταλείπουν το σχολείο",
    "Μαθητές σε πειραματική χρήση",
    "Στρατιώτες σε πειραματική χρήση",
    "Φοιτητές σε πειραματική χρήση",
    "Παιδιά φυλακισμένων",
    "Παιδιά ψυχικά ασθενών γονέων",
    "Παιδιά γονέων με εξάρτηση",
    "Παιδιά που έχουν δεχθεί κακοποίηση",
    "Παιδιά υπό την επιμέλεια του κράτους",
    "Παιδιά με ΔΕΠΥ και μαθησιακές δυσκολίες",
    "Παιδιά μετανάστες",
    "Παιδιά κάτω από το όριο της φτώχειας",
    "Έφηβοι με παραβατική συμπεριφορά",
    "Έγκυες που κάνουν χρήση",
    "Άνεργοι και άτομα τρίτης ηλικίας",
]


def seed(apps, schema_editor):
    for model_name, names in (("District", DISTRICTS), ("Setting", SETTINGS), ("VulnerableGroup", VULNERABLE_GROUPS)):
        Model = apps.get_model("core", model_name)
        for i, name in enumerate(names, start=1):
            Model.objects.update_or_create(name=name, defaults={"order": i})


def unseed(apps, schema_editor):
    for model_name, names in (("District", DISTRICTS), ("Setting", SETTINGS), ("VulnerableGroup", VULNERABLE_GROUPS)):
        apps.get_model("core", model_name).objects.filter(name__in=names).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
