"""Δήλωση τετραμηνίας: ροή 4 βημάτων, έλεγχοι συνέπειας, μεταφορά ανοικτών, διόρθωση, προθεσμία."""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Declaration, Period, PreventionLevel

from .helpers import age, declare, make_org, make_programme, make_user


class DeclarationFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org("a")
        cls.officer = make_user("a1", cls.org)
        cls.p = make_programme(cls.org, "Πυξίδα", cls.officer, ages=("13–15",))
        cls.period = Period.to_declare()

    def setUp(self):
        self.client.force_login(self.officer)

    def step(self, n, data=None, follow=False):
        url = reverse("declaration", args=[self.p.pk, n])
        return self.client.post(url, data or {}, follow=follow) if data is not None else self.client.get(url)

    def fill(self, open_start=None, new=20, completed=15, withdrawn=5, profile=None):
        s1 = {"new": new}
        if open_start is not None:
            s1["open_start"] = open_start
        self.assertEqual(self.step(1, s1).status_code, 302)
        self.assertEqual(self.step(2, {"completed": completed, "withdrawn": withdrawn}).status_code, 302)
        self.assertEqual(self.step(3, profile or {"note": ""}).status_code, 302)
        return self.step(4, {})

    # --- Πλήρης ροή ---
    def test_first_declaration_asks_open_start(self):
        r = self.step(1)
        self.assertContains(r, "Πόσοι συνέχιζαν στο πρόγραμμα")
        r = self.fill(open_start=10)
        self.assertRedirects(r, reverse("programme_home", args=[self.p.pk]))
        d = Declaration.objects.get(programme=self.p, period=self.period)
        self.assertEqual((d.open_start, d.new, d.completed, d.withdrawn, d.open_end), (10, 20, 15, 5, 10))
        self.assertIsNone(d.sex)
        self.assertIsNone(d.ages)
        self.assertEqual(d.submitted_by, self.officer)
        self.assertIsNotNone(d.fill_seconds)

    def test_open_cases_carried_from_previous_declaration(self):
        prev = Period.get(Period.previous_key(self.period.key))
        declare(self.p, prev, open_start=5, new=30, completed=10, withdrawn=3)  # τέλους = 22
        r = self.step(1)
        self.assertNotContains(r, "Πόσοι συνέχιζαν στο πρόγραμμα")
        self.assertContains(r, "Συμπληρώνεται αυτόματα")
        self.assertContains(r, "22")
        self.fill(new=8, completed=20, withdrawn=4)
        self.assertEqual(Declaration.objects.get(period=self.period).open_start, 22)

    def test_carry_over_skips_missing_period(self):
        """Αν λείπει μια τετραμηνία, οι ανοικτές έρχονται από την πιο πρόσφατη δήλωση."""
        older = Period.get(Period.previous_key(Period.previous_key(self.period.key)))
        declare(self.p, older, open_start=0, new=12, completed=2, withdrawn=0)  # τέλους = 10
        self.fill(new=0, completed=5, withdrawn=0)
        self.assertEqual(Declaration.objects.get(period=self.period).open_start, 10)

    # --- Μηνύματα λάθους (ίδια με το demo) ---
    def test_empty_new_message(self):
        r = self.step(1, {"open_start": 0, "new": ""})
        self.assertContains(r, "Γράψτε πόσοι νέοι ξεκίνησαν. Αν δεν ξεκίνησε κανείς, γράψτε 0.")

    def test_non_integer_message(self):
        for bad in ("δέκα", "2.5", "-3"):
            r = self.step(1, {"open_start": 0, "new": bad})
            self.assertEqual(r.status_code, 200, bad)
            self.assertFalse(Declaration.objects.exists())

    def test_outflow_above_served_message(self):
        self.step(1, {"open_start": 10, "new": 20})
        r = self.step(2, {"completed": 25, "withdrawn": 10})
        self.assertContains(r, "Ολοκλήρωσαν και αποχώρησαν μαζί (35) είναι περισσότεροι από όσους εξυπηρετήθηκαν (30)")

    def test_sex_total_must_match_new(self):
        self.step(1, {"open_start": 0, "new": 20})
        self.step(2, {"completed": 0, "withdrawn": 0})
        r = self.step(3, {"sex_male": 10, "sex_female": 5})
        self.assertContains(r, "Το σύνολο κατά φύλο είναι 15, ενώ οι νέοι είναι 20")

    def test_age_total_must_match_new(self):
        self.step(1, {"open_start": 0, "new": 20})
        self.step(2, {"completed": 0, "withdrawn": 0})
        r = self.step(3, {f"age_{age('13–15').pk}": 12})
        self.assertContains(r, "Το σύνολο κατά ηλικία είναι 12, ενώ οι νέοι είναι 20")

    # --- Κενό ≠ μηδέν ---
    def test_partial_sex_saved_with_zeros_but_empty_is_none(self):
        self.fill(open_start=0, new=20, completed=0, withdrawn=0,
                  profile={"sex_male": 12, "sex_female": 8, f"age_{age('13–15').pk}": 18, f"age_{age('16–18').pk}": 2})
        d = Declaration.objects.get()
        # Μόλις συμπληρωθεί ένα πεδίο φύλου, τα κενά της ίδιας ομάδας είναι 0 (το άθροισμα ελέγχθηκε).
        self.assertEqual(d.sex, [12, 8, 0])
        self.assertEqual(d.ages, {str(age(n).pk): v for n, v in [("6–12", 0), ("13–15", 18), ("16–18", 2), ("19–25", 0), ("26+", 0)]})

    def test_changing_new_clears_stale_profile(self):
        self.period.deadline = timezone.localdate() + timedelta(days=10)
        self.period.save()
        self.fill(open_start=0, new=20, completed=0, withdrawn=0, profile={"sex_male": 12, "sex_female": 8})
        self.step(1, {"open_start": 0, "new": 25})
        self.step(2, {"completed": 0, "withdrawn": 0})
        r = self.step(3)
        self.assertNotContains(r, 'value="12"')  # παλιό φύλο (άθροισμα 20) δεν προσυμπληρώνεται για 25 νέους

    # --- Σχόλιο ---
    def test_note_warns_about_names_and_is_limited(self):
        self.step(1, {"open_start": 0, "new": 0})
        self.step(2, {"completed": 0, "withdrawn": 0})
        r = self.step(3)
        self.assertContains(r, "Μην γράφετε ονόματα")
        r = self.step(3, {"note": "α" * 301})
        self.assertContains(r, "έως 300 χαρακτήρες")

    # --- Παράκαμψη βημάτων ---
    def test_cannot_jump_to_submit(self):
        r = self.step(4, {})
        self.assertRedirects(r, reverse("declaration", args=[self.p.pk, 1]))
        self.assertFalse(Declaration.objects.exists())

    def test_invalid_step_404(self):
        self.assertEqual(self.client.get(reverse("declaration", args=[self.p.pk, 9])).status_code, 404)

    def test_back_button_does_not_validate(self):
        r = self.step(1, {"back": "1"})
        self.assertRedirects(r, reverse("programme_home", args=[self.p.pk]))

    # --- Διόρθωση και προθεσμία ---
    def test_correction_before_deadline(self):
        self.period.deadline = timezone.localdate() + timedelta(days=10)
        self.period.save()
        self.fill(open_start=10, new=20, completed=15, withdrawn=5)
        r = self.step(2)
        self.assertContains(r, 'value="15"')  # προσυμπλήρωση από την υπάρχουσα δήλωση
        self.step(2, {"completed": 12, "withdrawn": 5})
        self.step(3, {"note": ""})
        self.step(4, {})
        d = Declaration.objects.get()
        self.assertEqual((d.completed, d.revisions), (12, 1))

    def test_no_correction_after_deadline(self):
        self.period.deadline = timezone.localdate() - timedelta(days=1)
        self.period.save()
        declare(self.p, self.period)
        r = self.step(1)
        self.assertRedirects(r, reverse("programme_home", args=[self.p.pk]))

    def test_late_first_submission_allowed(self):
        """Χωρίς ένδειξη «καθυστέρησης»: μετά την προθεσμία η δήλωση γίνεται κανονικά."""
        self.period.deadline = timezone.localdate() - timedelta(days=1)
        self.period.save()
        self.fill(open_start=0, new=3, completed=1, withdrawn=0)
        d = Declaration.objects.get()
        self.assertFalse(d.on_time)
        r = self.client.get(reverse("programme_home", args=[self.p.pk]))
        self.assertNotContains(r, "καθυστέρ")

    # --- Περιορισμοί ---
    def test_environmental_programme_not_declarable(self):
        env = make_programme(self.org, "Αέρας", self.officer, level=PreventionLevel.ENVIRONMENTAL)
        self.assertEqual(self.client.get(reverse("declaration", args=[env.pk, 1])).status_code, 404)
        self.assertContains(self.client.get(reverse("programme_home", args=[env.pk])), "δεν δηλώνεται ανά τετραμηνία")

    def test_programme_starting_later_not_declarable_yet(self):
        later = make_programme(self.org, "Νέο", self.officer)
        later.first_period = Period.get((self.period.year + 1, 1))
        later.save()
        self.assertEqual(self.client.get(reverse("declaration", args=[later.pk, 1])).status_code, 404)

    def test_home_shows_history_and_status(self):
        r = self.client.get(reverse("programme_home", args=[self.p.pk]))
        self.assertContains(r, "Εκκρεμεί")
        self.assertContains(r, "Συμπλήρωση δήλωσης")
        self.fill(open_start=10)
        r = self.client.get(reverse("programme_home", args=[self.p.pk]))
        self.assertContains(r, "✓ Υποβλήθηκε")
        self.assertContains(r, "Ανοικτές περιπτώσεις σήμερα")
