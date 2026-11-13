"""
Έλεγχοι πρόσβασης: το πιο κρίσιμο σημείο ασφαλείας του ΑΤΛΑΣ.
Ο λειτουργός βλέπει και δηλώνει ΜΟΝΟ ό,τι του έχει ανατεθεί. Η ΑΑΕΚ βλέπει όλα, δεν δηλώνει.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from core.models import AgeGroup, District, Period, PreventionLevel, Setting, VulnerableGroup

from .helpers import declare, make_org, make_programme, make_user


class AccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a, cls.org_b = make_org("a"), make_org("b")
        cls.a1, cls.a2 = make_user("a1", cls.org_a), make_user("a2", cls.org_a)
        cls.b1 = make_user("b1", cls.org_b)
        cls.aaek = make_user("aaek", aaek=True)
        cls.pa1 = make_programme(cls.org_a, "Πρόγραμμα Α1", cls.a1)
        cls.pa2 = make_programme(cls.org_a, "Πρόγραμμα Α2", cls.a2)
        cls.pb1 = make_programme(cls.org_b, "Πρόγραμμα Β1", cls.b1)

    def urls(self, p):
        return [reverse("programme_home", args=[p.pk]), reverse("declaration", args=[p.pk, 1]),
                reverse("declaration", args=[p.pk, 4])]

    def test_anonymous_redirected_to_login(self):
        for url in self.urls(self.pa1) + [reverse("programme_list"), reverse("aaek_dashboard"), reverse("aaek_export")]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse("login"), r["Location"])

    def test_officer_sees_only_assigned_programmes(self):
        self.client.force_login(self.a1)
        r = self.client.get(reverse("programme_list"))
        self.assertContains(r, "Πρόγραμμα Α1")
        self.assertNotContains(r, "Πρόγραμμα Α2")  # ίδιος φορέας, άλλος λειτουργός
        self.assertNotContains(r, "Πρόγραμμα Β1")

    def test_officer_cannot_open_colleague_or_other_org_programme(self):
        self.client.force_login(self.a1)
        for p in (self.pa2, self.pb1):
            for url in self.urls(p):
                self.assertEqual(self.client.get(url).status_code, 404, url)

    def test_officer_cannot_post_declaration_for_others(self):
        self.client.force_login(self.a1)
        for p in (self.pa2, self.pb1):
            r = self.client.post(reverse("declaration", args=[p.pk, 1]), {"open_start": 1, "new": 1})
            self.assertEqual(r.status_code, 404)
        self.assertFalse(self.pb1.declarations.exists())

    def test_unassigned_programme_invisible(self):
        orphan = make_programme(self.org_a, "Χωρίς λειτουργό")
        self.client.force_login(self.a1)
        self.assertEqual(self.client.get(reverse("programme_home", args=[orphan.pk])).status_code, 404)

    def test_inactive_programme_invisible(self):
        self.pa1.is_active = False
        self.pa1.save()
        self.client.force_login(self.a1)
        self.assertEqual(self.client.get(reverse("programme_home", args=[self.pa1.pk])).status_code, 404)

    def test_inactive_organisation_loses_access(self):
        self.org_a.is_active = False
        self.org_a.save()
        self.client.force_login(self.a1)
        self.assertEqual(self.client.get(reverse("programme_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("programme_home", args=[self.pa1.pk])).status_code, 403)

    def test_officer_reassigned_loses_access(self):
        self.client.force_login(self.a1)
        self.assertEqual(self.client.get(reverse("programme_home", args=[self.pa1.pk])).status_code, 200)
        self.pa1.officer = self.a2
        self.pa1.save()
        self.assertEqual(self.client.get(reverse("programme_home", args=[self.pa1.pk])).status_code, 404)

    def test_officer_cannot_see_aaek_dashboard(self):
        self.client.force_login(self.a1)
        self.assertEqual(self.client.get(reverse("aaek_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("aaek_export")).status_code, 403)

    def test_aaek_sees_all_but_cannot_declare(self):
        declare(self.pb1)
        self.client.force_login(self.aaek)
        r = self.client.get(reverse("aaek_dashboard"))
        for t in ("Πρόγραμμα Α1", "Πρόγραμμα Α2", "Πρόγραμμα Β1"):
            self.assertContains(r, t)
        self.assertEqual(self.client.get(reverse("programme_list")).status_code, 403)
        self.assertEqual(self.client.get(reverse("declaration", args=[self.pa1.pk, 1])).status_code, 403)

    def test_home_routes_by_role(self):
        self.client.force_login(self.aaek)
        self.assertRedirects(self.client.get("/"), reverse("aaek_dashboard"))
        self.client.force_login(self.a1)
        self.assertRedirects(self.client.get("/"), reverse("programme_list"))

    def test_officer_must_belong_to_programme_organisation(self):
        from django.core.exceptions import ValidationError
        self.pa1.officer = self.b1
        with self.assertRaises(ValidationError):
            self.pa1.full_clean()


class IntegrityTests(TestCase):
    def test_user_role_must_match_organisation(self):
        org = make_org("x")
        with transaction.atomic(), self.assertRaises(IntegrityError):
            User.objects.create_user("bad1", role=Role.ORGANISATION, organisation=None)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            User.objects.create_user("bad2", role=Role.AAEK, organisation=org)

    def test_superuser_is_aaek_without_organisation(self):
        su = User.objects.create_superuser("admin", "a@example.org", "x-Long-pass-123")
        self.assertEqual(su.role, Role.AAEK)
        self.assertIsNone(su.organisation)

    def test_one_declaration_per_period(self):
        p = make_programme(make_org("x"), "Π")
        declare(p)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            declare(p)

    def test_database_rejects_impossible_numbers(self):
        p = make_programme(make_org("x"), "Π")
        with transaction.atomic(), self.assertRaises(IntegrityError):
            declare(p, open_start=1, new=1, completed=2, withdrawn=1)


class TaxonomyTests(TestCase):
    def test_taxonomies_seeded(self):
        self.assertEqual(District.objects.count(), 5)
        self.assertEqual(Setting.objects.count(), 6)
        self.assertEqual(VulnerableGroup.objects.count(), 15)
        self.assertEqual(list(AgeGroup.objects.values_list("name", flat=True)), ["6–12", "13–15", "16–18", "19–25", "26+"])
        self.assertEqual(set(PreventionLevel.values), {"universal", "selective", "indicated", "environmental"})


class PeriodTests(TestCase):
    def test_period_arithmetic(self):
        from datetime import date
        self.assertEqual(Period.key_for(date(2026, 11, 13)), (2026, 3))
        self.assertEqual(Period.key_for(date(2027, 1, 12)), (2027, 1))
        self.assertEqual(Period.previous_key((2027, 1)), (2026, 3))
        p = Period.to_declare(date(2027, 1, 12))
        self.assertEqual(p.label, "Σεπ–Δεκ 2026")
        self.assertEqual(p.deadline, date(2027, 1, 31))
        self.assertEqual(Period.get((2026, 1)).deadline, date(2026, 5, 31))
        self.assertEqual(Period.get((2026, 2)).deadline, date(2026, 9, 30))
        self.assertEqual([x.label for x in Period.recent(3, date(2027, 1, 12))],
                         ["Ιαν–Απρ 2026", "Μαΐ–Αυγ 2026", "Σεπ–Δεκ 2026"])
