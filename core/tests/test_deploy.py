"""Ρυθμίσεις για server (Render) και πρώτη εκκίνηση."""
import os
from io import StringIO
from unittest import mock

from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from config.settings import database_from_url
from core.models import Declaration, Organisation


class DatabaseUrlTests(TestCase):
    def test_parse(self):
        db = database_from_url("postgres://atlas:p%40ss%3Aw@db.internal:6543/atlas_db")
        self.assertEqual((db["USER"], db["PASSWORD"], db["HOST"], db["PORT"], db["NAME"]),
                         ("atlas", "p@ss:w", "db.internal", "6543", "atlas_db"))
        self.assertEqual(database_from_url("postgresql://u:p@h/d")["PORT"], "5432")

    def test_rejects_other_schemes(self):
        with self.assertRaises(ImproperlyConfigured):
            database_from_url("mysql://u:p@h/d")


GOOD = "Μακρύς-Κωδικός-Δοκιμής-2026"


class BootstrapTests(TestCase):
    def run_bootstrap(self, **env):
        out = StringIO()
        with mock.patch.dict(os.environ, env, clear=False):
            for k in ("ATLAS_ADMIN_USERNAME", "ATLAS_ADMIN_PASSWORD", "ATLAS_DEMO", "ATLAS_DEMO_PASSWORD"):
                if k not in env:
                    os.environ.pop(k, None)
            call_command("bootstrap", stdout=out)
        return out.getvalue()

    def test_creates_admin_once_and_never_logs_password(self):
        out = self.run_bootstrap(ATLAS_ADMIN_USERNAME="greg", ATLAS_ADMIN_PASSWORD=GOOD)
        u = User.objects.get(username="greg")
        self.assertTrue(u.is_superuser and u.role == Role.AAEK and u.check_password(GOOD))
        self.assertNotIn(GOOD, out)
        out = self.run_bootstrap(ATLAS_ADMIN_USERNAME="greg", ATLAS_ADMIN_PASSWORD="άλλος-κωδικός-εντελώς-2026")
        self.assertIn("υπάρχει ήδη", out)
        self.assertTrue(User.objects.get(username="greg").check_password(GOOD))  # δεν αλλάζει σε επανεκκίνηση

    def test_weak_admin_password_rejected_without_crash(self):
        out = self.run_bootstrap(ATLAS_ADMIN_USERNAME="greg", ATLAS_ADMIN_PASSWORD="12345")
        self.assertFalse(User.objects.filter(username="greg").exists())
        self.assertIn("δεν έγινε δεκτός", out)

    def test_demo_data_only_once_and_only_in_demo(self):
        self.run_bootstrap(ATLAS_DEMO_PASSWORD=GOOD)  # χωρίς ATLAS_DEMO
        self.assertFalse(Organisation.objects.exists())
        out = self.run_bootstrap(ATLAS_DEMO="1", ATLAS_DEMO_PASSWORD=GOOD)
        self.assertNotIn(GOOD, out)
        self.assertTrue(User.objects.get(username="foreas_a").check_password(GOOD))
        n = Declaration.objects.count()
        self.assertGreater(n, 0)
        self.run_bootstrap(ATLAS_DEMO="1", ATLAS_DEMO_PASSWORD=GOOD)
        self.assertEqual(Declaration.objects.count(), n)  # δεν ξαναδημιουργούνται

    def test_demo_without_password_does_nothing(self):
        out = self.run_bootstrap(ATLAS_DEMO="1")
        self.assertFalse(Organisation.objects.exists())
        self.assertIn("ATLAS_DEMO_PASSWORD", out)


class DemoBannerTests(TestCase):
    @override_settings(DEMO_MODE=True)
    def test_banner_in_demo(self):
        self.assertContains(self.client.get(reverse("login")), "εικονικά δεδομένα")

    def test_no_banner_normally(self):
        self.assertNotContains(self.client.get(reverse("login")), "εικονικά δεδομένα")
