"""
Φόρμες της δήλωσης τετραμηνίας, μία ανά βήμα (όπως στο demo).
Τα μηνύματα λάθους λένε τι φταίει και με ποιους αριθμούς, σε απλά ελληνικά.
"""
from django import forms

NOTE_MAX = 300

INT_ERRORS = {
    "invalid": "Γράψτε έναν ακέραιο αριθμό, χωρίς γράμματα ή δεκαδικά.",
    "min_value": "Ο αριθμός δεν μπορεί να είναι αρνητικός.",
    "max_value": "Ο αριθμός είναι υπερβολικά μεγάλος. Ελέγξτε τον.",
}


def count_field(label="", required=True, required_msg=None, **kwargs):
    errors = dict(INT_ERRORS)
    if required_msg:
        errors["required"] = required_msg
    return forms.IntegerField(
        label=label,
        required=required,
        min_value=0,
        max_value=100000,
        error_messages=errors,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "pattern": "[0-9]*", "autocomplete": "off", "placeholder": "0"}),
        **kwargs,
    )


class StepNewForm(forms.Form):
    """Βήμα 1: πόσοι ήρθαν. Στην πρώτη δήλωση ζητάμε και τις ανοικτές περιπτώσεις αρχής."""

    open_start = count_field(
        "Πόσοι συνέχιζαν στο πρόγραμμα στην αρχή της τετραμηνίας;",
        required_msg="Γράψτε πόσοι συνέχιζαν από πριν. Αν κανείς, γράψτε 0.",
        help_text="Μόνο αυτή τη φορά. Από την επόμενη δήλωση συμπληρώνεται αυτόματα.",
    )
    new = count_field(
        "Νέοι εξυπηρετούμενοι αυτή την τετραμηνία",
        required_msg="Γράψτε πόσοι νέοι ξεκίνησαν. Αν δεν ξεκίνησε κανείς, γράψτε 0.",
    )

    def __init__(self, *args, first_declaration=False, months="", **kwargs):
        super().__init__(*args, **kwargs)
        if not first_declaration:
            del self.fields["open_start"]
        self.fields["new"].help_text = f"Όσοι ξεκίνησαν το πρόγραμμα από {months}." if months else ""


class StepOutcomeForm(forms.Form):
    """Βήμα 2: τι έγινε μέσα στην τετραμηνία."""

    completed = count_field("Ολοκλήρωσαν το πρόγραμμα", help_text="Παρακολούθησαν μέχρι το τέλος, όπως σχεδιάστηκε.")
    withdrawn = count_field("Αποχώρησαν πριν το τέλος", help_text="Σταμάτησαν για οποιονδήποτε λόγο.")

    def __init__(self, *args, served=0, **kwargs):
        super().__init__(*args, **kwargs)
        self.served = served
        for f in self.fields.values():
            f.error_messages["required"] = "Συμπληρώστε και τα δύο πεδία. Αν δεν ισχύει, γράψτε 0."

    def clean(self):
        cleaned = super().clean()
        c, w = cleaned.get("completed"), cleaned.get("withdrawn")
        if c is not None and w is not None and c + w > self.served:
            raise forms.ValidationError(
                f"Ολοκλήρωσαν και αποχώρησαν μαζί ({c + w}) είναι περισσότεροι από όσους "
                f"εξυπηρετήθηκαν ({self.served}). Ελέγξτε τους αριθμούς."
            )
        return cleaned


SEX_FIELDS = [("sex_male", "Αγόρια / άνδρες"), ("sex_female", "Κορίτσια / γυναίκες"), ("sex_other", "Άλλο / δεν δηλώθηκε")]


class StepProfileForm(forms.Form):
    """
    Βήμα 3 (προαιρετικό): φύλο και ηλικία των νέων, σχόλιο.
    Κενό ≠ μηδέν: αν μείνουν όλα κενά, αποθηκεύεται «δεν δηλώθηκε».
    """

    note = forms.CharField(
        label="Δυσκολίες ή σχόλια",
        required=False,
        max_length=NOTE_MAX,
        error_messages={"max_length": f"Το σχόλιο μπορεί να έχει έως {NOTE_MAX} χαρακτήρες."},
        help_text="Μην γράφετε ονόματα ή οτιδήποτε μπορεί να δείξει ποιο πρόσωπο εννοείτε.",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "π.χ. δύο σχολεία ζήτησαν αναβολή λόγω εξετάσεων"}),
    )

    def __init__(self, *args, new=0, target_ages=(), other_ages=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.new = new
        self.target_ages, self.other_ages = list(target_ages), list(other_ages)
        for name, label in SEX_FIELDS:
            self.fields[name] = count_field(label, required=False)
        for ag in self.target_ages + self.other_ages:
            self.fields[f"age_{ag.pk}"] = count_field(f"{ag.name} ετών", required=False)
        self.order_fields([n for n, _ in SEX_FIELDS] + [f"age_{a.pk}" for a in self.target_ages + self.other_ages] + ["note"])

    def sex_fields(self):
        return [self[n] for n, _ in SEX_FIELDS]

    def target_age_fields(self):
        return [self[f"age_{a.pk}"] for a in self.target_ages]

    def other_age_fields(self):
        return [self[f"age_{a.pk}"] for a in self.other_ages]

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        sex = [cleaned.get(n) for n, _ in SEX_FIELDS]
        if any(v is not None for v in sex):
            total = sum(v or 0 for v in sex)
            if total != self.new:
                raise forms.ValidationError(
                    f"Το σύνολο κατά φύλο είναι {total}, ενώ οι νέοι είναι {self.new}. "
                    "Διορθώστε ή αφήστε τα πεδία κενά."
                )
        ages = [cleaned.get(f"age_{a.pk}") for a in self.target_ages + self.other_ages]
        if any(v is not None for v in ages):
            total = sum(v or 0 for v in ages)
            if total != self.new:
                raise forms.ValidationError(
                    f"Το σύνολο κατά ηλικία είναι {total}, ενώ οι νέοι είναι {self.new}. "
                    "Διορθώστε ή αφήστε τα πεδία κενά."
                )
        return cleaned

    def to_draft(self):
        c = self.cleaned_data
        sex = [c.get(n) for n, _ in SEX_FIELDS]
        ages = {str(a.pk): c.get(f"age_{a.pk}") for a in self.target_ages + self.other_ages}
        return {
            "sex": None if all(v is None for v in sex) else [v or 0 for v in sex],
            "ages": None if all(v is None for v in ages.values()) else {k: v or 0 for k, v in ages.items()},
            "note": " ".join((c.get("note") or "").split()),
        }
