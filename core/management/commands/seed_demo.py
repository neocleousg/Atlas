"""
Δημιουργεί ΕΙΚΟΝΙΚΑ δεδομένα για δοκιμή: δύο φορείς, χρήστες και προγράμματα.
Οι κωδικοί δημιουργούνται τυχαία και εμφανίζονται μία φορά στην οθόνη.
Δεν εκτελείται σε παραγωγή (DJANGO_DEBUG=0) χωρίς --force.
"""
import secrets

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import Role, User
from core.models import District, Organisation, PreventionLevel, Programme, Setting, VulnerableGroup


class Command(BaseCommand):
    help = "Εικονικά δεδομένα για δοκιμή (μόνο για ανάπτυξη)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Εκτέλεση ακόμα και με DEBUG=0.")
        parser.add_argument("--out", help="Αποθήκευση των κωδικών και σε αρχείο κειμένου (τοπικά).")

    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("Μόνο για ανάπτυξη. Χρησιμοποιήστε --force αν είστε βέβαιοι.")

        org_a, _ = Organisation.objects.get_or_create(code="foreas-a", defaults={"name": "Φορέας Α (εικονικός)"})
        org_b, _ = Organisation.objects.get_or_create(code="foreas-b", defaults={"name": "Φορέας Β (εικονικός)"})

        creds = []
        for username, role, org in (
            ("foreas_a", Role.ORGANISATION, org_a),
            ("foreas_b", Role.ORGANISATION, org_b),
            ("aaek", Role.AAEK, None),
        ):
            user, _ = User.objects.get_or_create(username=username, defaults={"role": role, "organisation": org})
            password = secrets.token_urlsafe(12)
            user.set_password(password)
            user.save()
            creds.append((username, password))

        s = {x.name: x for x in Setting.objects.all()}
        d = {x.name: x for x in District.objects.all()}
        v = {x.name: x for x in VulnerableGroup.objects.all()}
        demo = [
            (org_a, "Γέφυρες", PreventionLevel.UNIVERSAL, ["Σχολείο"], ["Λευκωσία", "Λάρνακα"], [], 13, 15, True, 10),
            (org_a, "Δέντρο", PreventionLevel.SELECTIVE, ["Οικογένεια", "Κοινότητα"], ["Λευκωσία"], ["Παιδιά γονέων με εξάρτηση"], 8, 12, False, 12),
            (org_b, "Πλώρη", PreventionLevel.INDICATED, ["Κοινότητα"], ["Λεμεσός"], ["Έφηβοι με παραβατική συμπεριφορά"], 14, 18, False, 16),
            (org_b, "Καθαρός Αέρας", PreventionLevel.ENVIRONMENTAL, ["Κοινότητα"], ["Πάφος"], [], None, None, False, 4),
        ]
        for org, title, level, sets, dists, vulns, a0, a1, trains, sessions in demo:
            p, _ = Programme.objects.update_or_create(
                organisation=org,
                title=title,
                school_year="2026–27",
                defaults=dict(
                    level=level, age_from=a0, age_to=a1, trains_professionals=trains, planned_sessions=sessions,
                    need="Εικονική περιγραφή ανάγκης.", objectives="Εικονικοί στόχοι.",
                    expected_outcomes="Εικονικά αναμενόμενα αποτελέσματα.",
                ),
            )
            p.settings.set([s[x] for x in sets])
            p.districts.set([d[x] for x in dists])
            p.vulnerable_groups.set([v[x] for x in vulns])

        self.stdout.write(self.style.SUCCESS("Εικονικά δεδομένα έτοιμα. Κωδικοί (εμφανίζονται μόνο τώρα):"))
        for u, pw in creds:
            self.stdout.write(f"  {u:10s} {pw}")
        if opts.get("out"):
            labels = {"foreas_a": "Χρήστης Φορέα Α", "foreas_b": "Χρήστης Φορέα Β", "aaek": "Χρήστης ΑΑΕΚ"}
            with open(opts["out"], "w", encoding="utf-8") as f:
                f.write("ΑΤΛΑΣ - κωδικοί δοκιμής (εικονικοί χρήστες, μόνο για τον υπολογιστή σας)\n\n")
                for u, pw in creds:
                    f.write(f"{labels[u]}\n  Όνομα χρήστη: {u}\n  Κωδικός:      {pw}\n\n")
                f.write("Διεύθυνση: http://127.0.0.1:8000\n")
