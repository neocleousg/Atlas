"""Πίνακας ΑΑΕΚ, εξαγωγή, απόκρυψη μικρών τιμών."""
from django.test import TestCase
from django.urls import reverse

from core.models import District, Period, PreventionLevel
from core.stats import HIDDEN, suppress

from .helpers import age, declare, make_org, make_programme, make_user


class SuppressionTests(TestCase):
    def test_primary_and_secondary(self):
        self.assertEqual(suppress([20, 30, 0]), [20, 30, 0])
        # ένα μικρό κελί → κρύβεται και το μικρότερο από τα υπόλοιπα, αλλιώς βγαίνει με αφαίρεση
        self.assertEqual(suppress([3, 30, 12]), [HIDDEN, 30, HIDDEN])
        self.assertEqual(suppress([3, 30, 0]), [HIDDEN, 30, HIDDEN])
        # δύο μικρά κελιά → αρκεί
        self.assertEqual(suppress([3, 2, 30]), [HIDDEN, HIDDEN, 30])
        self.assertIsNone(suppress(None))

    def test_no_single_hidden_cell_ever(self):
        import itertools
        for vals in itertools.product([0, 1, 4, 5, 9], repeat=3):
            out = suppress(list(vals))
            self.assertNotEqual(out.count(HIDDEN), 1, vals)


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = make_org("a")
        cls.off = make_user("a1", cls.org)
        cls.aaek = make_user("aaek", aaek=True)
        cls.period = Period.to_declare()
        cls.p1 = make_programme(cls.org, "Ανεμόμυλος", cls.off)
        cls.p2 = make_programme(cls.org, "Φάρος", cls.off, level=PreventionLevel.SELECTIVE,
                                district=District.objects.get(name="Λεμεσός"))
        cls.p3 = make_programme(cls.org, "Πυξίδα", cls.off)  # χωρίς δήλωση
        cls.env = make_programme(cls.org, "Αέρας", cls.off, level=PreventionLevel.ENVIRONMENTAL)
        cls.d1 = declare(cls.p1, cls.period, open_start=40, new=100, completed=90, withdrawn=10,
                         sex_male=48, sex_female=50, sex_other=2, ages={str(age("13–15").pk): 100}, note="Τρία νέα σχολεία.")
        cls.d2 = declare(cls.p2, cls.period, open_start=10, new=20, completed=5, withdrawn=5)

    def setUp(self):
        self.client.force_login(self.aaek)

    def get(self, **q):
        return self.client.get(reverse("aaek_dashboard"), q)

    def test_totals_only_from_submitted(self):
        r = self.get()
        T = r.context["T"]
        self.assertEqual((T.submitted, T.expected), (2, 3))  # η περιβαλλοντική δεν αναμένεται
        self.assertEqual((T.served, T.new, T.completed, T.withdrawn, T.open_end), (170, 120, 95, 15, 60))
        self.assertEqual(T.rate, 86)
        self.assertContains(r, "Δηλώσεις: 2 από 3")
        self.assertContains(r, "Δεν έχει υποβληθεί ακόμα")
        self.assertContains(r, "Τα σύνολα περιλαμβάνουν μόνο τις δηλώσεις που έχουν υποβληθεί")
        self.assertNotContains(r, "Αέρας")

    def test_optional_fields_counted_honestly(self):
        T = self.get().context["T"]
        self.assertEqual((T.sex_reported, T.ages_reported), (1, 1))
        self.assertEqual(T.sex, [48, 50, 2])  # το Φάρος δεν δήλωσε φύλο: ΔΕΝ μετρά ως 0 αγόρια
        self.assertContains(self.get(), "Φύλο από 1 από 2 δηλώσεις")

    def test_small_values_hidden_in_aggregate(self):
        r = self.get()
        self.assertNotContains(r, "Άλλο / δεν δηλώθηκε 2")
        self.assertContains(r, f"Άλλο / δεν δηλώθηκε {HIDDEN}")
        self.assertContains(r, f"Αγόρια / άνδρες {HIDDEN}")  # δευτερογενής απόκρυψη (μικρότερο από τα υπόλοιπα)

    def test_filters(self):
        r = self.get(dist=District.objects.get(name="Λεμεσός").pk)
        self.assertEqual(r.context["T"].served, 30)
        self.assertNotContains(r, "Ανεμόμυλος")
        r = self.get(lvl="selective")
        self.assertEqual([x["p"].title for x in r.context["rows"]], ["Φάρος"])

    def test_bad_filters_ignored(self):
        for q in ({"per": "x"}, {"dist": "1.5"}, {"lvl": "zzz"}, {"sel": "-1"}, {"per": "999999"}):
            self.assertEqual(self.get(**q).status_code, 200, q)

    def test_detail_and_comments(self):
        r = self.get(sel=self.p1.pk)
        self.assertContains(r, "«Ανεμόμυλος»: όλες οι τετραμηνίες")
        self.assertContains(r, "Τρία νέα σχολεία.")
        r = self.get()
        self.assertContains(r, "Τι σημειώνουν οι φορείς")

    def test_other_period(self):
        prev = Period.get(Period.previous_key(self.period.key))
        declare(self.p1, prev, open_start=0, new=40, completed=0, withdrawn=0)
        r = self.get(per=prev.pk)
        self.assertEqual(r.context["T"].new, 40)

    def test_targets_line(self):
        self.d1.fill_seconds = 300
        self.d1.save()
        self.assertContains(self.get(), "διάμεσος χρόνος συμπλήρωσης: 5,0 λεπτά")

    def test_csv_export(self):
        r = self.client.get(reverse("aaek_export"), {"per": self.period.pk})
        self.assertEqual(r.status_code, 200)
        text = r.content.decode("utf-8-sig")
        lines = text.strip().splitlines()
        self.assertTrue(lines[0].startswith("Τετραμηνία;Πρόγραμμα"))
        row = next(line for line in lines if "Ανεμόμυλος" in line)
        self.assertIn(f";{HIDDEN};50;{HIDDEN};", row)  # ίδια απόκρυψη με την οθόνη
        self.assertIn("Πυξίδα", text)
        self.assertNotIn("Τρία νέα σχολεία", text)  # τα σχόλια δεν εξάγονται

    def test_csv_injection_neutralised(self):
        self.p2.title = "=HYPERLINK(\"x\")"
        self.p2.save()
        text = self.client.get(reverse("aaek_export")).content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", text)
