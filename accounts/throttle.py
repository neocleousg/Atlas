"""
Περιορισμός αποπειρών σύνδεσης.

Οι αποτυχίες μετρώνται στη βάση (όχι στη μνήμη), ώστε το όριο να ισχύει για όλους
τους workers του server μαζί. Τρία όρια, μέσα σε ένα παράθυρο χρόνου:

1. ίδιο όνομα χρήστη από ίδια IP: αυστηρό (κάποιος μαντεύει έναν κωδικό),
2. ίδια IP, οποιοδήποτε όνομα: (κάποιος δοκιμάζει πολλούς λογαριασμούς),
3. ίδιο όνομα, οποιαδήποτε IP: χαλαρό (επίθεση από πολλές IP).

Το (3) είναι χαλαρό σκόπιμα: αλλιώς ο καθένας θα μπορούσε να κλειδώνει όποιον λογαριασμό
θέλει, π.χ. της ΑΑΕΚ, απλώς γράφοντας λάθος κωδικούς.

Μια επιτυχής σύνδεση μηδενίζει τον μετρητή για το (1) και το (3).
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Max
from django.utils import timezone

from .models import LoginAttempt

logger = logging.getLogger("atlas.security")


def _setting(name, default):
    return getattr(settings, name, default)


def window():
    return timedelta(minutes=_setting("LOGIN_LOCK_WINDOW_MINUTES", 15))


def normalise_username(username):
    return (username or "").strip().lower()[:150]


def client_ip(request):
    """
    IP του χρήστη. Το X-Forwarded-For λαμβάνεται υπόψη ΜΟΝΟ αν η εφαρμογή είναι πίσω από
    γνωστό reverse proxy (DJANGO_TRUSTED_PROXIES = πλήθος proxies). Αλλιώς ο επιτιθέμενος
    θα έγραφε ό,τι IP ήθελε και θα παρέκαμπτε το όριο.
    """
    if request is None:
        return None
    proxies = _setting("TRUSTED_PROXY_COUNT", 0)
    if proxies:
        chain = [p.strip() for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(chain) >= proxies:
            return chain[-proxies]
    return request.META.get("REMOTE_ADDR") or None


def _failures_since_last_success(qs, username, since):
    last_ok = (
        LoginAttempt.objects.filter(username=username, successful=True, created_at__gte=since)
        .aggregate(t=Max("created_at"))["t"]
    )
    qs = qs.filter(successful=False, created_at__gte=since)
    if last_ok:
        qs = qs.filter(created_at__gt=last_ok)
    return qs.count()


def is_locked(username, ip):
    """True αν πρέπει να απορριφθεί η προσπάθεια χωρίς καν έλεγχο κωδικού."""
    username = normalise_username(username)
    since = timezone.now() - window()

    if ip and username:
        n = _failures_since_last_success(LoginAttempt.objects.filter(username=username, ip_address=ip), username, since)
        if n >= _setting("LOGIN_LOCK_USER_IP_LIMIT", 5):
            return True
    if ip:
        n = LoginAttempt.objects.filter(ip_address=ip, successful=False, created_at__gte=since).count()
        if n >= _setting("LOGIN_LOCK_IP_LIMIT", 20):
            return True
    if username:
        n = _failures_since_last_success(LoginAttempt.objects.filter(username=username), username, since)
        if n >= _setting("LOGIN_LOCK_USER_LIMIT", 30):
            return True
    return False


def record(username, ip, successful):
    username = normalise_username(username)
    LoginAttempt.objects.create(username=username, ip_address=ip, successful=successful)
    if not successful and is_locked(username, ip):
        logger.warning("Κλείδωμα σύνδεσης: χρήστης=%r ip=%s", username, ip)
    # Ελαχιστοποίηση δεδομένων (GDPR): οι παλιές εγγραφές δεν χρειάζονται.
    cutoff = timezone.now() - timedelta(days=_setting("LOGIN_ATTEMPT_RETENTION_DAYS", 30))
    LoginAttempt.objects.filter(created_at__lt=cutoff).delete()


def unlock(username):
    """Ξεκλείδωμα από την ΑΑΕΚ: σβήνει τις πρόσφατες αποτυχίες του χρήστη."""
    username = normalise_username(username)
    return LoginAttempt.objects.filter(username=username, successful=False).delete()[0]
