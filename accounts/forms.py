from django import forms
from django.contrib.auth.forms import AuthenticationForm


class AtlasAuthenticationForm(AuthenticationForm):
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
