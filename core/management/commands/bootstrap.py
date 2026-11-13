"""
Πρώτη εκκίνηση σε server (π.χ. Render). Τρέχει σε κάθε εκκίνηση, αλλά κάνει κάτι μόνο την πρώτη φορά:

- Λογαριασμός διαχείρισης από ATLAS_ADMIN_USERNAME / ATLAS_ADMIN_PASSWORD, αν δεν υπάρχει ήδη.
- Με ATLAS_DEMO=1 και άδεια βάση: εικονικά δεδομένα, με κωδικό ATLAS_DEMO_PASSWORD για τους
  χρήστες foreas_a, foreas_b, aaek.

Οι κωδικοί δίνονται από τον διαχειριστή στις ρυθμίσεις του server και δεν γράφονται ποτέ σε logs.
Αν κάτι λείπει ή είναι λάθος, γράφει μήνυμα και συνεχίζει: η εφαρμογή ξεκινά κανονικά.
"""
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.models import User
from core.models import Organisation


class Command(BaseCommand):
    help = "Λογαριασμός διαχείρισης και (σε demo) εικονικά δεδομένα, μόνο την πρώτη φορά."

    def warn(self, msg):
        self.stdout.write(self.style.WARNING(f"[bootstrap] {msg}"))

    def ok(self, msg):
        self.stdout.write(self.style.SUCCESS(f"[bootstrap] {msg}"))

    def password_ok(self, name, value, user=None):
        try:
            validate_password(value, user)
            return True
        except ValidationError as e:
            self.warn(f"Ο κωδικός στο {name} δεν έγινε δεκτός: {' '.join(e.messages)}")
            return False

    def handle(self, *args, **opts):
        username = os.environ.get("ATLAS_ADMIN_USERNAME", "").strip()
        password = os.environ.get("ATLAS_ADMIN_PASSWORD", "")
        if username and password:
            if User.objects.filter(username=username).exists():
                self.ok(f"Ο λογαριασμός διαχείρισης «{username}» υπάρχει ήδη.")
            elif self.password_ok("ATLAS_ADMIN_PASSWORD", password, User(username=username)):
                User.objects.create_superuser(username, None, password, first_name="Διαχείριση")
                self.ok(f"Δημιουργήθηκε ο λογαριασμός διαχείρισης «{username}».")
        else:
            self.warn("Δεν ορίστηκαν ATLAS_ADMIN_USERNAME / ATLAS_ADMIN_PASSWORD: χωρίς λογαριασμό διαχείρισης.")

        if os.environ.get("ATLAS_DEMO", "0").strip().lower() not in ("1", "true", "yes", "on"):
            return
        if Organisation.objects.exists():
            self.ok("Η βάση έχει ήδη δεδομένα: τα εικονικά δεδομένα δεν ξαναδημιουργούνται.")
            return
        demo_pw = os.environ.get("ATLAS_DEMO_PASSWORD", "")
        if not demo_pw:
            self.warn("Δεν ορίστηκε ATLAS_DEMO_PASSWORD: χωρίς εικονικά δεδομένα.")
            return
        if not self.password_ok("ATLAS_DEMO_PASSWORD", demo_pw, User(username="foreas_a")):
            return
        call_command("seed_demo", force=True, password=demo_pw, stdout=self.stdout)
