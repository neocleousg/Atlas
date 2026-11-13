"""
Επαναφορά των εικονικών δεδομένων στη σημερινή ημερομηνία, πριν από μια παρουσίαση.

Λειτουργεί ΜΟΝΟ όταν ATLAS_DEMO=1. Σβήνει δηλώσεις, προγράμματα, φορείς και χρήστες φορέων,
και ξαναδημιουργεί τα 5 προγράμματα του demo. Λογαριασμοί ΑΑΕΚ και διαχείρισης μένουν.
"""
import os
from io import StringIO

from django.conf import settings
from django.core.management import call_command
from django.db import transaction

from accounts.models import Role, User

from .models import Declaration, Organisation, Programme


class DemoResetError(Exception):
    pass


@transaction.atomic
def reset_demo_data():
    if not getattr(settings, "DEMO_MODE", False):
        raise DemoResetError("Η επαναφορά επιτρέπεται μόνο στη δοκιμαστική εκδοχή.")
    password = os.environ.get("ATLAS_DEMO_PASSWORD", "")
    if len(password) < 12:
        raise DemoResetError("Λείπει ο κωδικός demo (ATLAS_DEMO_PASSWORD) στις ρυθμίσεις του server.")
    Declaration.objects.all().delete()
    Programme.objects.all().delete()
    User.objects.filter(role=Role.ORGANISATION).delete()
    Organisation.objects.all().delete()
    call_command("seed_demo", force=True, password=password, stdout=StringIO())
