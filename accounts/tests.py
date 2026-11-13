"""Έλεγχοι για τον περιορισμό αποπειρών σύνδεσης."""
from datetime import timedelta

from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts import throttle
from accounts.models import LoginAttempt, Role, User
from core.models import Organisation

PASSWORD = "x-Long-pass-123"


@override_settings(
    LOGIN_LOCK_WINDOW_MINUTES=15, LOGIN_LOCK_USER_IP_LIMIT=5, LOGIN_LOCK_IP_LIMIT=20, LOGIN_LOCK_USER_LIMIT=30,
    TRUSTED_PROXY_COUNT=0,
)
class LoginThrottleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organisation.objects.create(name="Α", code="a")
        cls.user = User.objects.create_user("foreas_a", password=PASSWORD, role=Role.ORGANISATION, organisation=cls.org)
        cls.admin = User.objects.create_superuser("admin", "a@example.org", PASSWORD)

    def login(self, username="foreas_a", password=PASSWORD, ip="10.0.0.1", url=None, **extra):
        return self.client.post(url or reverse("login"), {"username": username, "password": password},
                                REMOTE_ADDR=ip, **extra)

    def fail(self, n, **kw):
        for _ in range(n):
            self.login(password="λάθος-κωδικός", **kw)

    def assertLocked(self, r):
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Πάρα πολλές αποτυχημένες προσπάθειες")
        self.assertNotIn("_auth_user_id", self.client.session)

    # --- Βασική λειτουργία ---
    def test_four_failures_still_allow_login(self):
        self.fail(4)
        self.assertEqual(self.login().status_code, 302)

    def test_five_failures_lock_even_correct_password(self):
        self.fail(5)
        self.assertLocked(self.login())

    def test_lock_expires_after_window(self):
        self.fail(5)
        LoginAttempt.objects.update(created_at=timezone.now() - timedelta(minutes=16))
        self.assertEqual(self.login().status_code, 302)

    def test_success_resets_counter(self):
        self.fail(4)
        self.assertEqual(self.login().status_code, 302)
        self.client.logout()
        self.fail(4)
        self.assertEqual(self.login().status_code, 302)

    def test_username_case_does_not_bypass(self):
        for name in ("foreas_a", "FOREAS_A", "Foreas_A", " foreas_a", "foreas_A"):
            self.login(username=name, password="λάθος")
        self.assertLocked(self.login())

    # --- Τρία όρια ---
    def test_lock_is_per_ip_for_single_user(self):
        """Ο επιτιθέμενος από μία IP δεν κλειδώνει τον πραγματικό χρήστη σε άλλη IP."""
        self.fail(5, ip="10.0.0.66")
        self.assertEqual(self.login(ip="10.0.0.1").status_code, 302)

    def test_ip_limit_across_usernames(self):
        for i in range(20):
            self.login(username=f"user{i}", password="λάθος", ip="10.0.0.66")
        self.assertLocked(self.login(ip="10.0.0.66"))
        self.client.logout()
        self.assertEqual(self.login(ip="10.0.0.1").status_code, 302)

    def test_user_limit_across_ips(self):
        for i in range(30):
            self.login(password="λάθος", ip=f"10.1.{i}.1")
        self.assertLocked(self.login(ip="10.9.9.9"))

    def test_unknown_username_gets_same_lock_message(self):
        """Το μήνυμα δεν αποκαλύπτει αν ο λογαριασμός υπάρχει."""
        self.fail(5, username="den_yparxei")
        self.assertLocked(self.login(username="den_yparxei"))

    def test_inactive_organisation_is_not_counted_as_failure(self):
        self.org.is_active = False
        self.org.save()
        for _ in range(6):
            self.login()
        self.assertFalse(LoginAttempt.objects.filter(successful=False).exists())

    # --- Πίσω πόρτες ---
    def test_admin_login_is_throttled_too(self):
        url = reverse("admin:login")
        for _ in range(5):
            self.login(username="admin", password="λάθος", url=url)
        r = self.login(username="admin", url=url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Πάρα πολλές αποτυχημένες προσπάθειες")

    def test_forged_forwarded_for_ignored_without_trusted_proxy(self):
        for i in range(5):
            self.login(password="λάθος", HTTP_X_FORWARDED_FOR=f"1.2.3.{i}")
        self.assertLocked(self.login(HTTP_X_FORWARDED_FOR="9.9.9.9"))

    @override_settings(TRUSTED_PROXY_COUNT=1)
    def test_forwarded_for_used_behind_trusted_proxy(self):
        rf = RequestFactory()
        req = rf.get("/", REMOTE_ADDR="172.17.0.1", HTTP_X_FORWARDED_FOR="6.6.6.6, 203.0.113.7")
        self.assertEqual(throttle.client_ip(req), "203.0.113.7")  # η τελευταία, που την έβαλε ο δικός μας proxy

    # --- Διαχείριση και δεδομένα ---
    def test_admin_action_unlocks(self):
        self.fail(5)
        self.client.force_login(self.admin)
        self.client.post(reverse("admin:accounts_user_changelist"),
                         {"action": "unlock_login", "_selected_action": [self.user.pk]})
        self.client.logout()
        self.assertEqual(self.login().status_code, 302)

    def test_old_attempts_deleted(self):
        old = LoginAttempt.objects.create(username="x", ip_address="10.0.0.9")
        LoginAttempt.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=31))
        self.login()
        self.assertFalse(LoginAttempt.objects.filter(pk=old.pk).exists())

    def test_attempts_are_read_only_in_admin(self):
        self.login()
        self.client.force_login(self.admin)
        a = LoginAttempt.objects.first()
        r = self.client.post(reverse("admin:accounts_loginattempt_change", args=[a.pk]), {"username": "άλλο"})
        a.refresh_from_db()
        self.assertEqual(a.username, "foreas_a")
        self.assertEqual(self.client.get(reverse("admin:accounts_loginattempt_add")).status_code, 403)
