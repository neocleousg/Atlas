"""
Σύνολα για τον πίνακα της ΑΑΕΚ και προστασία μικρών τιμών.

Προστασία (αρχή 3 της πρότασης): καμία τιμή 1–4 σε φύλο/ηλικία δεν εμφανίζεται.
Αντί να κρύβουμε κελιά (που θα έκρυβε και μεγάλες τιμές, π.χ. «Κορίτσια 126» επειδή «Άλλο» = 3),
ΕΝΩΝΟΥΜΕ το μικρό κελί με ένα γειτονικό:
- φύλο: με τη μικρότερη άλλη κατηγορία (π.χ. «Κορίτσια / γυναίκες + άλλο: 129»),
- ηλικία: με διπλανή ηλικιακή ομάδα (π.χ. «13–18: 107»).
Επαναλαμβάνεται μέχρι να μη μείνει κανένα μικρό σύνολο. Αν δεν γίνεται, όλα κρύβονται.

Οθόνη ΚΑΙ CSV χρησιμοποιούν την ΙΔΙΑ ομαδοποίηση: το CSV δείχνει μόνο όσα κελιά έμειναν
μόνα τους, και «×» για κάθε κελί που ενώθηκε. Έτσι ο συνδυασμός οθόνης και CSV δεν
αποκαλύπτει τίποτα παραπάνω.
"""
from dataclasses import dataclass, field
from statistics import median

HIDDEN = "×"
SMALL = 5


def protect(values, ordinal=False):
    """
    values: λίστα ακεραίων ενός σπασίματος (π.χ. φύλο ή ηλικίες με τη σειρά τους).
    Επιστρέφει ομάδες: [{"idx": [δείκτες], "v": άθροισμα ή HIDDEN}], με τη σειρά των δεικτών.
    """
    if values is None:
        return None
    groups = [[i] for i in range(len(values))]

    def total(g):
        return sum(values[i] for i in g)

    def small(g):
        return 0 < total(g) < SMALL

    while True:
        smalls = [g for g in groups if small(g)]
        if not smalls:
            return [{"idx": g, "v": total(g)} for g in groups]
        g = min(smalls, key=total)
        pos = groups.index(g)
        if len(groups) == 1:
            return [{"idx": g, "v": HIDDEN}]
        if ordinal:
            cands = [groups[j] for j in (pos - 1, pos + 1) if 0 <= j < len(groups)]
        else:
            cands = [x for x in groups if x is not g]
        nonzero = [c for c in cands if total(c) > 0]
        if nonzero:
            target = min(nonzero, key=total)
        elif ordinal and any(total(x) > 0 for x in groups if x is not g):
            # Προς την πλευρά όπου υπάρχει μη μηδενική ομάδα.
            left = any(total(x) > 0 for x in groups[:pos])
            target = groups[pos - 1] if left and pos > 0 else groups[pos + 1]
        else:
            # Μόνο μηδενικά γύρω: η μικρή τιμή θα φαινόταν από το σύνολο. Κρύβονται όλα.
            return [{"idx": [i for x in groups for i in x], "v": HIDDEN}]
        merged = sorted(g + target)
        groups = [x for x in groups if x is not g and x is not target]
        groups.append(merged)
        groups.sort(key=lambda x: x[0])


def cells(groups, n):
    """Για το CSV: τιμή ανά αρχική στήλη, ή HIDDEN αν η στήλη ενώθηκε/κρύφτηκε."""
    out = [HIDDEN] * n
    for g in groups or []:
        if len(g["idx"]) == 1 and g["v"] != HIDDEN:
            out[g["idx"][0]] = g["v"]
    return out


def rate(completed, withdrawn):
    done = completed + withdrawn
    return round(completed * 100 / done) if done else None


@dataclass
class Totals:
    expected: int = 0
    submitted: int = 0
    open_start: int = 0
    new: int = 0
    completed: int = 0
    withdrawn: int = 0
    sex: list = field(default_factory=lambda: [0, 0, 0])
    sex_reported: int = 0
    ages: dict = field(default_factory=dict)
    ages_reported: int = 0
    on_time: int = 0
    fill_seconds: list = field(default_factory=list)

    @property
    def served(self):
        return self.open_start + self.new

    @property
    def open_end(self):
        return self.served - self.completed - self.withdrawn

    @property
    def rate(self):
        return rate(self.completed, self.withdrawn)

    @property
    def median_minutes(self):
        return round(median(self.fill_seconds) / 60, 1) if self.fill_seconds else None

    def add(self, d):
        self.submitted += 1
        self.open_start += d.open_start
        self.new += d.new
        self.completed += d.completed
        self.withdrawn += d.withdrawn
        if d.sex is not None:
            self.sex_reported += 1
            self.sex = [a + b for a, b in zip(self.sex, d.sex)]
        if d.ages is not None:
            self.ages_reported += 1
            for k, v in d.ages.items():
                self.ages[k] = self.ages.get(k, 0) + v
        if d.on_time:
            self.on_time += 1
        if d.fill_seconds:
            self.fill_seconds.append(d.fill_seconds)


def totals(programmes, period, declarations):
    """declarations: {programme_id: Declaration} για την τετραμηνία."""
    t = Totals()
    for p in programmes:
        if p.expected_in(period) or p.pk in declarations:
            t.expected += 1
        if p.pk in declarations:
            t.add(declarations[p.pk])
    return t


def age_groups_of(age_groups, ages):
    """Οι ηλικιακές ομάδες με τιμή, με τη σειρά τους, και οι τιμές τους."""
    groups = [a for a in age_groups if str(a.pk) in ages]
    return groups, [ages[str(a.pk)] for a in groups]


def _bounds(name):
    lo, _, hi = name.replace("+", "").partition("–")
    return lo, (hi or None) if not name.endswith("+") else None


def age_label(groups):
    lo = _bounds(groups[0].name)[0]
    hi = _bounds(groups[-1].name)[1]
    return f"{lo}–{hi}" if hi else f"{lo}+"


def age_breakdown(age_groups, ages):
    """[(ετικέτα, τιμή μετά την προστασία, ομάδες)]. None αν δεν δηλώθηκε ηλικία."""
    if ages is None:
        return None
    groups, values = age_groups_of(age_groups, ages)
    out = []
    for g in protect(values, ordinal=True):
        members = [groups[i] for i in g["idx"]]
        out.append((age_label(members), g["v"], members))
    return out


def age_cells(age_groups, ages):
    """Για το CSV: {id ηλικιακής ομάδας: τιμή ή HIDDEN}."""
    if ages is None:
        return {}
    groups, values = age_groups_of(age_groups, ages)
    return dict(zip((str(a.pk) for a in groups), cells(protect(values, ordinal=True), len(values))))
