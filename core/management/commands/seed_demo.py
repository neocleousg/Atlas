"""
Δημιουργεί ΕΙΚΟΝΙΚΑ δεδομένα για δοκιμή, όπως στο demo: 5 προγράμματα σε 5 επαρχίες,
δηλώσεις για τις 3 τελευταίες τετραμηνίες. Στην πιο πρόσφατη λείπουν 2 δηλώσεις,
ώστε να φαίνεται η εκκρεμότητα.

Οι κωδικοί δημιουργούνται τυχαία και εμφανίζονται μία φορά στην οθόνη.
Δεν εκτελείται σε παραγωγή (DJANGO_DEBUG=0) χωρίς --force.
"""
import random
import secrets
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import Role, User
from core.models import AgeGroup, Declaration, District, Organisation, Period, PreventionLevel, Programme, Setting

L = PreventionLevel
# όνομα, φορέας, επίπεδο, επαρχία, πλαίσιο, ηλικιακές ομάδες, ανοικτές αρχικά, νέοι ανά τετραμηνία, % ολοκλ., % αποχ.
PROGRAMMES = [
    ("Πυξίδα", "a", L.UNIVERSAL, "Λάρνακα", "Σχολείο", ["13–15"], 20, [60, 4, 75], .70, .03),
    ("Ανεμόμυλος", "a", L.UNIVERSAL, "Λευκωσία", "Σχολείο", ["6–12", "13–15"], 40, [180, 10, 260], .72, .04),
    ("Φάρος", "b", L.SELECTIVE, "Λεμεσός", "Κοινότητα", ["13–15", "16–18"], 14, [22, 8, 30], .45, .12),
    ("Ελιά", "b", L.SELECTIVE, "Πάφος", "Οικογένεια", ["6–12"], 9, [12, 6, 15], .55, .10),
    ("Αλυκή", "a", L.INDICATED, "Αμμόχωστος", "Κοινότητα", ["16–18", "19–25"], 6, [8, 5, 10], .40, .18),
]
NOT_SUBMITTED = {"Πυξίδα", "Αλυκή"}  # στην πιο πρόσφατη τετραμηνία
COMMENTS = {
    "Φάρος": "Δύο ομάδες ξεκίνησαν με καθυστέρηση λόγω αλλαγής χώρου.",
    "Ελιά": "Αυξημένες αποχωρήσεις λόγω αργιών.",
    "Ανεμόμυλος": "Τρία νέα σχολεία εντάχθηκαν στο πρόγραμμα.",
}


def split(n, weights):
    s = sum(weights)
    out = [n * w // s for w in weights]
    for i in range(n - sum(out)):
        out[i % len(out)] += 1
    return out


class Command(BaseCommand):
    help = "Εικονικά δεδομένα για δοκιμή (μόνο για ανάπτυξη)."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Εκτέλεση ακόμα και με DEBUG=0.")
        parser.add_argument("--out", help="Αποθήκευση των κωδικών και σε αρχείο κειμένου (τοπικά).")
        parser.add_argument("--password", help="Ίδιος κωδικός για όλους τους εικονικούς χρήστες (δεν εμφανίζεται).")

    @transaction.atomic
    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts["force"]:
            raise CommandError("Μόνο για ανάπτυξη. Χρησιμοποιήστε --force αν είστε βέβαιοι.")
        rnd = random.Random(7)

        orgs = {
            "a": Organisation.objects.get_or_create(code="foreas-a", defaults={"name": "Φορέας Α (εικονικός)"})[0],
            "b": Organisation.objects.get_or_create(code="foreas-b", defaults={"name": "Φορέας Β (εικονικός)"})[0],
        }
        creds, users = [], {}
        for username, role, org, first in (
            ("foreas_a", Role.ORGANISATION, orgs["a"], "Λειτουργός Α"),
            ("foreas_b", Role.ORGANISATION, orgs["b"], "Λειτουργός Β"),
            ("aaek", Role.AAEK, None, "Λειτουργός ΑΑΕΚ"),
        ):
            user, _ = User.objects.get_or_create(username=username, defaults={"role": role, "organisation": org})
            user.first_name = first
            password = opts.get("password") or secrets.token_urlsafe(12)
            user.set_password(password)
            user.save()
            users[username] = user
            creds.append((username, password))

        districts = {x.name: x for x in District.objects.all()}
        settings_ = {x.name: x for x in Setting.objects.all()}
        ages = {x.name: x for x in AgeGroup.objects.all()}
        periods = Period.recent(3)

        for name, org, level, dist, sett, age_names, open0, news, cr, wr in PROGRAMMES:
            p, _ = Programme.objects.update_or_create(
                organisation=orgs[org], title=name,
                defaults=dict(level=level, district=districts[dist], setting=settings_[sett],
                              officer=users[f"foreas_{org}"], is_active=True, first_period=None),
            )
            targets = [ages[a] for a in age_names]
            p.age_groups.set(targets)
            p.declarations.all().delete()
            open_ = open0
            for i, (period, new) in enumerate(zip(periods, news)):
                last = i == len(periods) - 1
                if last and name in NOT_SUBMITTED:
                    continue
                served = open_ + new
                comp = min(served, round(served * cr * (.9 + rnd.random() * .2)))
                left = min(served - comp, round(served * wr * (.8 + rnd.random() * .4)))
                other = round(new * .01) if new >= 20 else 0
                boys = round((new - other) * (.44 + rnd.random() * .12))
                age_counts = split(new, [3] + [2] * (len(targets) - 1))
                Declaration.objects.create(
                    programme=p, period=period, open_start=open_, new=new, completed=comp, withdrawn=left,
                    sex_male=boys, sex_female=new - other - boys, sex_other=other,
                    ages={str(a.pk): n for a, n in zip(targets, age_counts)},
                    note=COMMENTS.get(name, "") if last else "",
                    fill_seconds=rnd.randint(180, 540), submitted_by=p.officer,
                    # Εικονική ημερομηνία υποβολής: λίγες μέρες μετά το τέλος της τετραμηνίας.
                    submitted_at=timezone.make_aware(datetime.combine(period.end + timedelta(days=rnd.randint(3, 25)), time(10))),
                )
                open_ = served - comp - left

        if opts.get("password"):
            self.stdout.write(self.style.SUCCESS("Εικονικά δεδομένα έτοιμα. Χρήστες: foreas_a, foreas_b, aaek."))
            return
        self.stdout.write(self.style.SUCCESS("Εικονικά δεδομένα έτοιμα. Κωδικοί (εμφανίζονται μόνο τώρα):"))
        for u, pw in creds:
            self.stdout.write(f"  {u:10s} {pw}")
        if opts.get("out"):
            labels = {"foreas_a": "Λειτουργός Φορέα Α (Πυξίδα, Ανεμόμυλος, Αλυκή)",
                      "foreas_b": "Λειτουργός Φορέα Β (Φάρος, Ελιά)", "aaek": "Λειτουργός ΑΑΕΚ"}
            with open(opts["out"], "w", encoding="utf-8") as f:
                f.write("ΑΤΛΑΣ - κωδικοί δοκιμής (εικονικοί χρήστες, μόνο για τον υπολογιστή σας)\n\n")
                for u, pw in creds:
                    f.write(f"{labels[u]}\n  Όνομα χρήστη: {u}\n  Κωδικός:      {pw}\n\n")
                f.write("Διεύθυνση: http://127.0.0.1:8000\n")
