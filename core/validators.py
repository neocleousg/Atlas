"""Έλεγχοι τιμών που χρησιμοποιούνται σε μοντέλα και φόρμες."""
import re

from django.core.exceptions import ValidationError

# Δεκτές μορφές: 2026–27, 2026-27, 2026/27, 2026 - 27. Αποθηκεύεται πάντα ως 2026–27.
_SCHOOL_YEAR_RE = re.compile(r"^\s*(\d{4})\s*[-–—/]\s*(\d{2})\s*$")


def normalise_school_year(value):
    """Επιστρέφει την περίοδο στη μορφή ΕΕΕΕ–ΕΕ ή σηκώνει ValidationError."""
    m = _SCHOOL_YEAR_RE.match(value or "")
    if not m:
        raise ValidationError("Γράψτε την περίοδο στη μορφή 2026–27.", code="school_year_format")
    start, end = int(m.group(1)), int(m.group(2))
    if not 2000 <= start <= 2099:
        raise ValidationError("Το έτος έναρξης πρέπει να είναι μεταξύ 2000 και 2099.", code="school_year_range")
    if end != (start + 1) % 100:
        raise ValidationError(
            f"Η περίοδος πρέπει να καλύπτει δύο συνεχόμενα έτη, π.χ. {start}–{(start + 1) % 100:02d}.",
            code="school_year_span",
        )
    return f"{start}–{end:02d}"


def validate_school_year(value):
    """Δέχεται μόνο την αποθηκευμένη μορφή ΕΕΕΕ–ΕΕ."""
    if normalise_school_year(value) != value:
        raise ValidationError("Γράψτε την περίοδο στη μορφή 2026–27.", code="school_year_format")
