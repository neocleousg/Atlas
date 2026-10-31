"""
Κανόνες πρόσβασης. ΟΛΗ η πρόσβαση σε δεδομένα προγραμμάτων περνά από εδώ.

Αρχή: ένας χρήστης φορέα δεν μπορεί ποτέ να δει ή να αλλάξει δεδομένα άλλου φορέα.
Οι κανόνες ελέγχονται αυτόματα στο core/tests/test_access.py.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import Programme


def visible_programmes(user):
    """Τα προγράμματα που επιτρέπεται να δει ο χρήστης."""
    qs = Programme.objects.select_related("organisation")
    if not user.is_authenticated or not user.is_active:
        return qs.none()
    if getattr(user, "is_aaek_user", False):
        return qs
    if getattr(user, "is_organisation_user", False):
        return qs.filter(organisation_id=user.organisation_id, organisation__is_active=True)
    return qs.none()


def can_create_programme(user):
    return (
        user.is_authenticated
        and user.is_active
        and getattr(user, "is_organisation_user", False)
        and user.organisation.is_active
    )


def can_edit_programme(user, programme):
    return can_create_programme(user) and programme.organisation_id == user.organisation_id


class OrganisationUserRequiredMixin(LoginRequiredMixin):
    """Μόνο ενεργοί χρήστες ενεργού φορέα. Η ΑΑΕΚ δεν καταχωρίζει δεδομένα φορέων."""

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not can_create_programme(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
