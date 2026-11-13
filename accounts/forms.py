from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm

from . import throttle

LOCKED_MESSAGE = (
    "Πάρα πολλές αποτυχημένες προσπάθειες σύνδεσης. Περιμένετε {minutes} λεπτά και δοκιμάστε ξανά. "
    "Αν ξεχάσατε τον κωδικό, επικοινωνήστε με την ΑΑΕΚ."
)


class ThrottledLoginMixin:
    """
    Ελέγχει το όριο ΠΡΙΝ από τον κωδικό: όσο ισχύει το κλείδωμα, ακόμα και ο σωστός κωδικός
    απορρίπτεται, αλλιώς το κλείδωμα δεν θα σταματούσε κάποιον που μαντεύει.
    Το μήνυμα είναι το ίδιο είτε υπάρχει ο χρήστης είτε όχι.
    """

    def clean(self):
        username = self.data.get("username", "")
        ip = throttle.client_ip(self.request)
        if throttle.is_locked(username, ip):
            minutes = int(throttle.window().total_seconds() // 60)
            raise forms.ValidationError(LOCKED_MESSAGE.format(minutes=minutes), code="locked")
        try:
            cleaned = super().clean()
        except forms.ValidationError as e:
            # Μόνο ο λάθος κωδικός μετρά ως αποτυχία. Σωστός κωδικός σε ανενεργό λογαριασμό δεν μετρά.
            if any(getattr(err, "code", None) == "invalid_login" for err in e.error_list):
                throttle.record(username, ip, successful=False)
            raise
        if username:
            throttle.record(username, ip, successful=True)
        return cleaned


class AtlasAuthenticationForm(ThrottledLoginMixin, AuthenticationForm):
    """Σύνδεση. Χρήστης απενεργοποιημένου φορέα δεν μπαίνει καθόλου."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Λάθος όνομα χρήστη ή κωδικός.",
        "inactive": "Ο λογαριασμός είναι ανενεργός. Επικοινωνήστε με την ΑΑΕΚ.",
        "organisation_inactive": "Ο φορέας σας είναι ανενεργός. Επικοινωνήστε με την ΑΑΕΚ.",
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_organisation_user and not user.organisation.is_active:
            raise forms.ValidationError(self.error_messages["organisation_inactive"], code="organisation_inactive")


class AtlasAdminAuthenticationForm(ThrottledLoginMixin, AdminAuthenticationForm):
    """Η σελίδα σύνδεσης της διαχείρισης έχει το ίδιο όριο. Αλλιώς θα ήταν πίσω πόρτα."""
