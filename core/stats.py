"""
Σύνολα για τον πίνακα της ΑΑΕΚ και απόκρυψη μικρών τιμών.

Απόκρυψη (αρχή 3 της πρότασης):
- Πρωτογενής: κάθε τιμή 1–4 σε φύλο/ηλικία κρύβεται.
- Δευτερογενής: το σύνολο (νέοι) είναι πάντα ορατό. Αν κρυφτεί μόνο ένα κελί, βγαίνει με
  αφαίρεση από το σύνολο. Γι' αυτό κρύβεται και το μικρότερο από τα υπόλοιπα κελιά.
Ισχύει σε οθόνη ΚΑΙ σε εξαγωγές.
"""
from dataclasses import dataclass, field
from statistics import median

HIDDEN = "×"
SMALL = 5


def suppress(values):
    """
    values: λίστα ακεραίων (ένα σπάσιμο, π.χ. φύλο). Επιστρέφει λίστα με ακέραιους ή HIDDEN.
    None (δεν δηλώθηκε) → None.
    """
    if values is None:
        return None
    out = list(values)
    hidden = {i for i, v in enumerate(values) if 0 < v < SMALL}
    if len(hidden) == 1 and len(values) > 1:
        rest = sorted((v, i) for i, v in enumerate(values) if i not in hidden)
        hidden.add(rest[0][1])
    for i in hidden:
        out[i] = HIDDEN
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


def age_breakdown(age_groups, ages):
    """[(ηλικιακή ομάδα, τιμή μετά την απόκρυψη)]. Μόνο ομάδες με δηλωμένη τιμή."""
    if ages is None:
        return None
    groups = [a for a in age_groups if str(a.pk) in ages]
    shown = suppress([ages[str(a.pk)] for a in groups])
    return list(zip(groups, shown))
