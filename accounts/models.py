from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models


class Role(models.TextChoices):
    ORGANISATION = "organisation", "Φορέας"
    AAEK = "aaek", "ΑΑΕΚ"


class AtlasUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # Ο διαχειριστής του συστήματος δεν ανήκει σε φορέα.
        extra_fields.setdefault("role", Role.AAEK)
        extra_fields.setdefault("organisation", None)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Χρήστης του ΑΤΛΑΣ.

    - Ρόλος «Φορέας»: ανήκει υποχρεωτικά σε έναν φορέα και βλέπει μόνο τα δικά του.
    - Ρόλος «ΑΑΕΚ»: βλέπει όλα, χωρίς να καταχωρίζει δεδομένα φορέων.
    """

    role = models.CharField("Ρόλος", max_length=20, choices=Role.choices, default=Role.ORGANISATION)
    organisation = models.ForeignKey(
        "core.Organisation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
        verbose_name="Φορέας",
    )

    objects = AtlasUserManager()

    class Meta:
        verbose_name = "Χρήστης"
        verbose_name_plural = "Χρήστες"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(role="organisation", organisation__isnull=False)
                    | models.Q(role="aaek", organisation__isnull=True)
                ),
                name="role_matches_organisation",
            ),
        ]

    def clean(self):
        super().clean()
        if self.role == Role.ORGANISATION and not self.organisation_id:
            raise ValidationError({"organisation": "Ο χρήστης φορέα πρέπει να ανήκει σε φορέα."})
        if self.role == Role.AAEK and self.organisation_id:
            raise ValidationError({"organisation": "Ο χρήστης ΑΑΕΚ δεν ανήκει σε φορέα."})

    @property
    def is_organisation_user(self):
        return self.role == Role.ORGANISATION and self.organisation_id is not None

    @property
    def is_aaek_user(self):
        return self.role == Role.AAEK


class LoginAttempt(models.Model):
    """
    Μία προσπάθεια σύνδεσης. Χρησιμοποιείται για τον περιορισμό αποπειρών (accounts/throttle.py).
    Η διεύθυνση IP είναι προσωπικό δεδομένο: οι εγγραφές διαγράφονται αυτόματα μετά από
    LOGIN_ATTEMPT_RETENTION_DAYS ημέρες.
    """

    username = models.CharField("Όνομα χρήστη", max_length=150, db_index=True)
    ip_address = models.GenericIPAddressField("Διεύθυνση IP", null=True, blank=True, db_index=True)
    successful = models.BooleanField("Επιτυχής", default=False)
    created_at = models.DateTimeField("Χρόνος", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Προσπάθεια σύνδεσης"
        verbose_name_plural = "Προσπάθειες σύνδεσης"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} · {self.ip_address or '—'} · {'επιτυχής' if self.successful else 'αποτυχία'}"
