"""
Κανόνες πρόσβασης. ΟΛΗ η πρόσβαση σε προγράμματα και δηλώσεις περνά από εδώ.

- Λειτουργός φορέα: βλέπει και δηλώνει ΜΟΝΟ τα προγράμματα που του έχουν ανατεθεί.
  Ποτέ προγράμματα άλλου λειτουργού, πόσο μάλλον άλλου φορέα.
- ΑΑΕΚ: βλέπει όλα, δεν δηλώνει.
- Ανενεργός φορέας ή ανενεργό πρόγραμμα: καμία πρόσβαση για τον φορέα.

Οι κανόνες ελέγχονται αυτόματα στο core/tests/test_access.py.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from .models import Programme


def is_officer(user):
    return (
        user.is_authenticated
        and user.is_active
        and getattr(user, "is_organisation_user", False)
        and user.organisation.is_active
    )


def is_aaek(user):
    return user.is_authenticated and user.is_active and getattr(user, "is_aaek_user", False)


def officer_programmes(user):
    """Τα προγράμματα που ο λειτουργός δηλώνει."""
    if not is_officer(user):
        return Programme.objects.none()
    return Programme.objects.select_related("organisation", "district", "setting").filter(
        officer=user,
        organisation_id=user.organisation_id,
        organisation__is_active=True,
        is_active=True,
    )


class OfficerRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_officer(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class AaekRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not is_aaek(request.user):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)
