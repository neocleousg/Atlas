"""
Έλεγχοι πρόσβασης: το πιο κρίσιμο σημείο ασφαλείας του ΑΤΛΑΣ.
Ένας φορέας δεν πρέπει ποτέ να βλέπει ή να αλλάζει δεδομένα άλλου φορέα.
"""
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from core.models import District, Organisation, PreventionLevel, Programme, Setting


def make_programme(org, title):
    p = Programme.objects.create(
        organisation=org, title=title, school_year="2026–27", level=PreventionLevel.UNIVERSAL,
        age_from=13, age_to=15, need="x", objectives="x", expected_outcomes="x", planned_sessions=8,
    )
    p.settings.set([Setting.objects.first()])
    p.districts.set([District.objects.first()])
    return p


def valid_post(title="Νέο", **over):
    data = {
        "title": title, "school_year": "2026–27", "level": PreventionLevel.UNIVERSAL,
        "settings": [Setting.objects.first().pk], "districts": [District.objects.first().pk],
        "age_from": 13, "age_to": 15, "need": "α", "objectives": "β", "expected_outcomes": "γ", "planned_sessions": 8,
    }
    data.update(over)
    return data


class AccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organisation.objects.create(name="Α", code="a")
        cls.org_b = Organisation.objects.create(name="Β", code="b")
        cls.user_a = User.objects.create_user("ua", password="x-Long-pass-123", role=Role.ORGANISATION, organisation=cls.org_a)
        cls.user_b = User.objects.create_user("ub", password="x-Long-pass-123", role=Role.ORGANISATION, organisation=cls.org_b)
        cls.aaek = User.objects.create_user("aaek", password="x-Long-pass-123", role=Role.AAEK)
        cls.prog_a = make_programme(cls.org_a, "Πρόγραμμα Α")
        cls.prog_b = make_programme(cls.org_b, "Πρόγραμμα Β")

    # --- Ανώνυμοι ---
    def test_anonymous_redirected_to_login(self):
        for url in [reverse("programme_list"), reverse("programme_detail", args=[self.prog_a.pk]),
                    reverse("programme_create"), reverse("programme_update", args=[self.prog_a.pk])]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302, url)
            self.assertIn(reverse("login"), r["Location"])

    # --- Απομόνωση φορέων ---
    def test_organisation_sees_only_own_programmes_in_list(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("programme_list"))
        self.assertContains(r, "Πρόγραμμα Α")
        self.assertNotContains(r, "Πρόγραμμα Β")

    def test_organisation_list_ignores_filter_params(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("programme_list"), {"organisation": self.org_b.pk})
        self.assertNotContains(r, "Πρόγραμμα Β")

    def test_organisation_cannot_view_other_programme(self):
        self.client.force_login(self.user_a)
        r = self.client.get(reverse("programme_detail", args=[self.prog_b.pk]))
        self.assertEqual(r.status_code, 404)

    def test_organisation_cannot_edit_other_programme(self):
        self.client.force_login(self.user_a)
        url = reverse("programme_update", args=[self.prog_b.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        r = self.client.post(url, valid_post("Παραβίαση"))
        self.assertEqual(r.status_code, 404)
        self.prog_b.refresh_from_db()
        self.assertEqual(self.prog_b.title, "Πρόγραμμα Β")

    def test_create_always_uses_own_organisation(self):
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("programme_create"), valid_post("Δικό μου", organisation=self.org_b.pk))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Programme.objects.get(title="Δικό μου").organisation, self.org_a)

    def test_inactive_organisation_loses_access(self):
        self.org_a.is_active = False
        self.org_a.save()
        self.client.force_login(self.user_a)
        self.assertNotContains(self.client.get(reverse("programme_list")), "Πρόγραμμα Α")
        self.assertEqual(self.client.get(reverse("programme_create")).status_code, 403)
        self.org_a.is_active = True
        self.org_a.save()

    # --- ΑΑΕΚ ---
    def test_aaek_sees_all_programmes(self):
        self.client.force_login(self.aaek)
        r = self.client.get(reverse("programme_list"))
        self.assertContains(r, "Πρόγραμμα Α")
        self.assertContains(r, "Πρόγραμμα Β")
        self.assertEqual(self.client.get(reverse("programme_detail", args=[self.prog_b.pk])).status_code, 200)

    def test_aaek_filter_by_organisation(self):
        self.client.force_login(self.aaek)
        r = self.client.get(reverse("programme_list"), {"organisation": self.org_b.pk})
        self.assertContains(r, "Πρόγραμμα Β")
        self.assertNotContains(r, "Πρόγραμμα Α")

    def test_aaek_cannot_create_or_edit(self):
        self.client.force_login(self.aaek)
        self.assertEqual(self.client.get(reverse("programme_create")).status_code, 403)
        self.assertEqual(self.client.post(reverse("programme_create"), valid_post()).status_code, 403)
        self.assertEqual(self.client.get(reverse("programme_update", args=[self.prog_a.pk])).status_code, 403)

    # --- Ακεραιότητα δεδομένων ---
    def test_user_role_must_match_organisation(self):
        with transaction.atomic(), self.assertRaises(IntegrityError):
            User.objects.create_user("bad1", role=Role.ORGANISATION, organisation=None)
        with transaction.atomic(), self.assertRaises(IntegrityError):
            User.objects.create_user("bad2", role=Role.AAEK, organisation=self.org_a)

    def test_superuser_is_aaek_without_organisation(self):
        su = User.objects.create_superuser("admin", "a@example.org", "x-Long-pass-123")
        self.assertEqual(su.role, Role.AAEK)
        self.assertIsNone(su.organisation)

    def test_duplicate_title_same_year_rejected(self):
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("programme_create"), valid_post("Πρόγραμμα Α"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Υπάρχει ήδη πρόγραμμα")

    def test_age_range_validated(self):
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("programme_create"), valid_post("Ηλικίες", age_from=15, age_to=12))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Programme.objects.filter(title="Ηλικίες").exists())

    def test_environmental_programme_needs_no_ages(self):
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("programme_create"),
                             valid_post("Περιβαλλοντικό", level=PreventionLevel.ENVIRONMENTAL, age_from="", age_to=""))
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Programme.objects.get(title="Περιβαλλοντικό").has_individual_questionnaire)


class TaxonomyTests(TestCase):
    def test_strategy_taxonomies_seeded(self):
        from core.models import VulnerableGroup
        self.assertEqual(District.objects.count(), 5)
        self.assertEqual(Setting.objects.count(), 6)
        self.assertEqual(VulnerableGroup.objects.count(), 15)
        self.assertEqual(len(PreventionLevel.choices), 4)
