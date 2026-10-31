from django import forms

from .models import PreventionLevel, Programme


class ProgrammeForm(forms.ModelForm):
    """Ο φορέας ΔΕΝ επιλέγεται στη φόρμα: ορίζεται πάντα από τον λογαριασμό του χρήστη."""

    class Meta:
        model = Programme
        fields = [
            "title",
            "school_year",
            "level",
            "settings",
            "districts",
            "vulnerable_groups",
            "age_from",
            "age_to",
            "trains_professionals",
            "need",
            "objectives",
            "theory",
            "planned_sessions",
            "expected_outcomes",
        ]
        widgets = {
            "settings": forms.CheckboxSelectMultiple,
            "districts": forms.CheckboxSelectMultiple,
            "vulnerable_groups": forms.CheckboxSelectMultiple,
            "level": forms.RadioSelect,
            "need": forms.Textarea(attrs={"rows": 3}),
            "objectives": forms.Textarea(attrs={"rows": 3}),
            "theory": forms.Textarea(attrs={"rows": 2}),
            "expected_outcomes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._organisation = organisation
        self.fields["level"].choices = PreventionLevel.choices  # χωρίς κενή επιλογή «---------»

    def clean(self):
        cleaned = super().clean()
        # Ο φορέας ορίζεται πριν από τον έλεγχο μοναδικότητας τίτλου/περιόδου.
        if self._organisation is not None:
            self.instance.organisation = self._organisation
            # Ο έλεγχος μοναδικότητας του Django παραλείπει πεδία εκτός φόρμας (organisation),
            # γι' αυτό γίνεται ρητά εδώ.
            title, year = cleaned.get("title"), cleaned.get("school_year")
            if title and year:
                dup = Programme.objects.filter(organisation=self._organisation, title=title, school_year=year)
                if self.instance.pk:
                    dup = dup.exclude(pk=self.instance.pk)
                if dup.exists():
                    self.add_error("title", "Υπάρχει ήδη πρόγραμμα με αυτόν τον τίτλο για την ίδια περίοδο.")
        return cleaned
