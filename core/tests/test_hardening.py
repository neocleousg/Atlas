"""
Έλεγχοι για τις βελτιώσεις του Βήματος 1:
άκυρα φίλτρα, σύνδεση ανενεργού φορέα, μορφή περιόδου, όρια τιμών, αλλαγή κωδικού, σελίδες σφάλματος.
"""
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Role, User
from core.models import Organisation, PreventionLevel, Programme
from core.validators import normalise_school_year

from .test_access import make_programme, valid_post

PASSWORD = "x-Long-pass-123"


class BaseCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org_a = Organisation.objects.create(name="Α", code="a")
        cls.org_off = Organisation.objects.create(name="Κλειστός", code="off", is_active=False)
        cls.user_a = User.objects.create_user("ua", password=PASSWORD, role=Role.ORGANISATION, organisation=cls.org_a)
        cls.user_off = User.objects.create_user(
            "uoff", password=PASSWORD, role=Role.ORGANISATION, organisation=cls.org_off
        )
        cls.aaek = User.objects.create_user("aaek", password=PASSWORD, role=Role.AAEK)
        cls.prog_a = make_programme(cls.org_a, "Πρόγραμμα Α")


class FilterRobustnessTests(BaseCase):
    def test_invalid_filter_values_do_not_crash(self):
        self.client.force_login(self.aaek)
        for q in ({"organisation": "abc"}, {"district": "1.5"}, {"setting": "-1"}, {"level": "zzz"},
                  {"organisation": "' OR 1=1"}, {"school_year": "<script>"}):
            r = self.client.get(reverse("programme_list"), q)
            self.assertEqual(r.status_code, 200, q)

    def test_invalid_level_is_ignored_not_empty(self):
        self.client.force_login(self.aaek)
        self.assertContains(self.client.get(reverse("programme_list"), {"level": "zzz"}), "Πρόγραμμα Α")

    def test_filter_by_school_year(self):
        make_programme(self.org_a, "Παλιό").__class__.objects.filter(title="Παλιό").update(school_year="2025–26")
        self.client.force_login(self.aaek)
        r = self.client.get(reverse("programme_list"), {"school_year": "2025–26"})
        self.assertContains(r, "Παλιό")
        self.assertNotContains(r, "Πρόγραμμα Α")
        self.assertContains(r, "Καθαρισμός")


class LoginTests(BaseCase):
    def test_active_user_logs_in(self):
        r = self.client.post(reverse("login"), {"username": "ua", "password": PASSWORD})
        self.assertEqual(r.status_code, 302)

    def test_user_of_inactive_organisation_cannot_log_in(self):
        r = self.client.post(reverse("login"), {"username": "uoff", "password": PASSWORD})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ο φορέας σας είναι ανενεργός")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_password_message_is_generic(self):
        r = self.client.post(reverse("login"), {"username": "uoff", "password": "λάθος"})
        self.assertContains(r, "Λάθος όνομα χρήστη ή κωδικός")
        self.assertNotContains(r, "ανενεργός")  # δεν αποκαλύπτουμε τίποτα χωρίς σωστό κωδικό


class PasswordChangeTests(BaseCase):
    def test_requires_login(self):
        r = self.client.get(reverse("password_change"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("login"), r["Location"])

    def test_user_can_change_password(self):
        self.client.force_login(self.user_a)
        new = "νέος-κωδικός-ασφαλής-2026"
        r = self.client.post(reverse("password_change"),
                             {"old_password": PASSWORD, "new_password1": new, "new_password2": new})
        self.assertRedirects(r, reverse("password_change_done"))
        self.user_a.refresh_from_db()
        self.assertTrue(self.user_a.check_password(new))

    def test_short_password_rejected(self):
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("password_change"),
                             {"old_password": PASSWORD, "new_password1": "short1!", "new_password2": "short1!"})
        self.assertEqual(r.status_code, 200)
        self.user_a.refresh_from_db()
        self.assertTrue(self.user_a.check_password(PASSWORD))


class SchoolYearTests(BaseCase):
    def test_normalise_accepts_common_formats(self):
        for raw in ("2026–27", "2026-27", "2026/27", " 2026 - 27 ", "2026—27"):
            self.assertEqual(normalise_school_year(raw), "2026–27", raw)
        self.assertEqual(normalise_school_year("2099-00"), "2099–00")

    def test_normalise_rejects_bad_values(self):
        for raw in ("", "2026", "2026-28", "26-27", "1999-00", "φέτος"):
            with self.assertRaises(ValidationError, msg=raw):
                normalise_school_year(raw)

    def test_hyphen_counts_as_duplicate(self):
        """«2026-27» και «2026–27» είναι η ίδια περίοδος: δεν επιτρέπεται δεύτερο ίδιο πρόγραμμα."""
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("programme_create"), valid_post("Πρόγραμμα Α", school_year="2026-27"))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Υπάρχει ήδη πρόγραμμα")

    def test_stored_in_standard_form(self):
        self.client.force_login(self.user_a)
        self.client.post(reverse("programme_create"), valid_post("Νέο", school_year="2027/28"))
        self.assertEqual(Programme.objects.get(title="Νέο").school_year, "2027–28")

    def test_title_whitespace_collapsed(self):
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("programme_create"), valid_post("  Πρόγραμμα    Α "))
        self.assertContains(r, "Υπάρχει ήδη πρόγραμμα")


class FieldLimitTests(BaseCase):
    def test_zero_sessions_rejected(self):
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("programme_create"), valid_post("Μηδέν", planned_sessions=0))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Η φόρμα δεν αποθηκεύτηκε")
        self.assertFalse(Programme.objects.filter(title="Μηδέν").exists())

    def test_absurd_age_rejected(self):
        self.client.force_login(self.user_a)
        r = self.client.post(reverse("programme_create"), valid_post("Ηλικία", age_from=10, age_to=150))
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Programme.objects.filter(title="Ηλικία").exists())


@override_settings(DEBUG=False)
class ErrorPageTests(BaseCase):
    def test_404_in_greek(self):
        self.client.force_login(self.user_a)
        r = self.client.get("/den-yparxei/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "Η σελίδα δεν βρέθηκε", status_code=404)

    def test_403_in_greek(self):
        self.client.force_login(self.aaek)
        r = self.client.get(reverse("programme_create"))
        self.assertContains(r, "Δεν επιτρέπεται", status_code=403)

    def test_csrf_failure_in_greek(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        r = c.post(reverse("login"), {"username": "ua", "password": PASSWORD})
        self.assertContains(r, "Η φόρμα έληξε", status_code=403)


class LevelChoicesTests(TestCase):
    def test_level_values_stable(self):
        # Οι τιμές αποθηκεύονται στη βάση: αλλαγή τους σπάει τα ιστορικά δεδομένα.
        self.assertEqual(set(PreventionLevel.values), {"universal", "selective", "indicated", "environmental"})
