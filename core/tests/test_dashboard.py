"""Πίνακας ΑΑΕΚ, εξαγωγή, απόκρυψη μικρών τιμών."""
from django.test import TestCase
from django.urls import reverse

from core.models import District, Period, PreventionLevel
import itertools

from core.stats import HIDDEN, cells, protect

from .helpers import age, declare, make_org, make_programme, make_user


class ProtectionTests(TestCase):
    def test_merge_instead_of_hiding(self):
        # «Άλλο» = 3 ενώνεται με τη μικρότερη κατηγορία· τα αγόρια μένουν ορατά
        self.assertEqual(protect([131, 126, 3]), [{"idx": [0], "v": 131}, {"idx": [1, 2], "v": 129}])
        self.assertEqual(protect([20, 30, 0]), [{"idx": [0], "v": 20}, {"idx": [1], "v": 30}, {"idx": [2], "v": 0}])
        # ηλικίες: μόνο με διπλανή ομάδα
        self.assertEqual(protect([156, 104, 3], ordinal=True), [{"idx": [0], "v": 156}, {"idx": [1, 2], "v": 107}])
        self.assertEqual(protect([3, 50, 10], ordinal=True), [{"idx": [0, 1], "v": 53}, {"idx": [2], "v": 10}])
        # μόνο μηδενικά γύρω: η τιμή θα φαινόταν από το σύνολο, άρα κρύβονται όλα
        self.assertEqual(protect([3, 0, 0]), [{"idx": [0, 1, 2], "v": HIDDEN}])
        self.assertIsNone(protect(None))

    def test_csv_matches_screen(self):
        self.assertEqual(cells(protect([131, 126, 3]), 3), [131, HIDDEN, HIDDEN])
        self.assertEqual(cells(protect([3, 30, 0]), 3), [HIDDEN, HIDDEN, 0])

    def test_no_small_value_ever_revealed(self):
        """
        Για κάθε συνδυασμό: (α) καμία ορατή ομάδα 1–4, (β) τα αθροίσματα διατηρούνται,
        (γ) κάθε μικρό κελί είναι μέσα σε ομάδα 2+ κελιών ή κρυφό, και στο CSV είναι «×».
        Οθόνη + CSV + σύνολο δεν δίνουν τίποτα παραπάνω: το CSV δείχνει μόνο ό,τι η οθόνη ήδη δείχνει μόνο του.
        """
        vals = [0, 1, 3, 4, 5, 9, 30]
        for ordinal, n in ((False, 3), (True, 3), (True, 5)):
            for combo in itertools.product(vals, repeat=n):
                groups = protect(list(combo), ordinal=ordinal)
                csv = cells(groups, n)
                shown = [g["v"] for g in groups if g["v"] != HIDDEN]
                self.assertFalse(any(0 < v < 5 for v in shown), (combo, groups))
                if all(g["v"] != HIDDEN for g in groups):
                    self.assertEqual(sum(shown), sum(combo))
                for i, v in enumerate(combo):
                    if 0 < v < 5:
                        g = next(g for g in groups if i in g["idx"])
                        self.assertTrue(len(g["idx"]) > 1 or g["v"] == HIDDEN, (combo, groups))
                        self.assertEqual(csv[i], HIDDEN, (combo, csv))
                    if ordinal:
                        g = next(g for g in groups if i in g["idx"])
                        self.assertEqual(g["idx"], list(range(g["idx"][0], g["idx"][-1] + 1)), "μη συνεχόμενες ηλικίες")


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

    def test_small_values_merged_in_aggregate(self):
        r = self.get()
        self.assertNotContains(r, "Άλλο / δεν δηλώθηκε 2")
        self.assertContains(r, "Αγόρια / άνδρες + άλλο 50")  # 48 + 2: ενώθηκε με τη μικρότερη κατηγορία
        self.assertContains(r, "Κορίτσια / γυναίκες 50")

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
        self.assertIn(f";{HIDDEN};50;{HIDDEN};", row)  # ό,τι ενώθηκε στην οθόνη, εδώ είναι «×»
        self.assertIn("Πυξίδα", text)
        self.assertNotIn("Τρία νέα σχολεία", text)  # τα σχόλια δεν εξάγονται

    def test_csv_injection_neutralised(self):
        self.p2.title = "=HYPERLINK(\"x\")"
        self.p2.save()
        text = self.client.get(reverse("aaek_export")).content.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", text)


    def test_completion_chart_grouped_by_level_not_ranked(self):
        rates = self.get().context["rates"]
        self.assertEqual([g["level"] for g in rates], ["Καθολική", "Επικεντρωμένη"])
        r = self.get()
        self.assertNotContains(r, "Κάτω από 60%")
        self.assertNotContains(r, "var(--c2)\"></i></span><b>")
