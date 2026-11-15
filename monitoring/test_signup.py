"""Self-service sign-up: account creation, least privilege, switch, and rate limit."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import MonitoringSession, Participant

User = get_user_model()
GOOD = {"username": "ana", "email": "ana@example.test", "password1": "Muy-larga-clave-2026", "password2": "Muy-larga-clave-2026"}


@override_settings(ALLOW_SIGNUP=True, SIGNUP_DEMO_SESSION="")
class SignUpTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_form_renders(self):
        response = self.client.get("/accounts/signup/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Crear cuenta")

    def test_creates_account_logs_in_and_can_open_app(self):
        response = self.client.post("/accounts/signup/", GOOD)
        self.assertRedirects(response, "/app/", fetch_redirect_response=False)
        user = User.objects.get(username="ana")
        self.assertTrue(user.check_password(GOOD["password1"]))
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(self.client.get("/app/").status_code, 200)

    def test_new_account_reads_no_sessions(self):
        self.client.post("/accounts/signup/", GOOD)
        self.assertEqual(self.client.get("/api/v1/sessions/").json()["results"], [])

    def test_rejects_mismatch_weak_and_duplicate(self):
        for bad in ({**GOOD, "password2": "otra"}, {**GOOD, "password1": "12345678", "password2": "12345678"}):
            self.assertEqual(self.client.post("/accounts/signup/", bad).status_code, 200)
        self.assertFalse(User.objects.filter(username="ana").exists())
        User.objects.create_user("ana", password="x" * 12)
        self.assertEqual(self.client.post("/accounts/signup/", GOOD).status_code, 200)
        self.assertEqual(User.objects.filter(username="ana").count(), 1)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user("otro", email="ana@example.test", password="x" * 12)
        response = self.client.post("/accounts/signup/", GOOD)
        self.assertContains(response, "Ya existe una cuenta con ese correo")

    def test_authenticated_user_is_sent_to_app(self):
        self.client.force_login(User.objects.create_user("luis", password="x" * 12))
        self.assertRedirects(self.client.get("/accounts/signup/"), "/app/", fetch_redirect_response=False)

    def test_rate_limit(self):
        for _ in range(10):
            self.client.post("/accounts/signup/", {**GOOD, "password2": "mal"})
        self.assertEqual(self.client.post("/accounts/signup/", GOOD).status_code, 429)
        self.assertFalse(User.objects.filter(username="ana").exists())

    def test_login_page_links_to_signup(self):
        self.assertContains(self.client.get("/accounts/login/"), "/accounts/signup/")


class SignUpDisabledTests(TestCase):
    @override_settings(ALLOW_SIGNUP=False)
    def test_disabled_returns_404_and_hides_link(self):
        self.assertEqual(self.client.get("/accounts/signup/").status_code, 404)
        self.assertEqual(self.client.post("/accounts/signup/", GOOD).status_code, 404)
        self.assertNotContains(self.client.get("/accounts/login/"), "/accounts/signup/")
        self.assertFalse(User.objects.filter(username="ana").exists())


@override_settings(ALLOW_SIGNUP=True, SIGNUP_DEMO_SESSION="session-demo")
class SignUpDemoAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        participant = Participant.objects.create(pseudonym="p-demo")
        self.demo = MonitoringSession.objects.create(participant=participant, identifier="session-demo", started_at=timezone.now())
        self.other = MonitoringSession.objects.create(participant=participant, identifier="session-private", started_at=timezone.now())

    def test_only_the_named_demo_session_is_granted(self):
        self.client.post("/accounts/signup/", GOOD)
        user = User.objects.get(username="ana")
        self.assertTrue(self.demo.authorized_users.filter(pk=user.pk).exists())
        self.assertFalse(self.other.authorized_users.filter(pk=user.pk).exists())

    def test_existing_account_gets_the_demo_session_at_login(self):
        user = User.objects.create_user("vieja", password="Clave-anterior-2026")
        self.assertFalse(self.demo.authorized_users.filter(pk=user.pk).exists())
        self.client.post("/accounts/login/", {"username": "vieja", "password": "Clave-anterior-2026"})
        self.assertTrue(self.demo.authorized_users.filter(pk=user.pk).exists())
        self.assertFalse(self.other.authorized_users.filter(pk=user.pk).exists())

    @override_settings(ALLOW_SIGNUP=False)
    def test_login_grants_nothing_when_sign_up_is_off(self):
        user = User.objects.create_user("cerrada", password="Clave-anterior-2026")
        self.client.post("/accounts/login/", {"username": "cerrada", "password": "Clave-anterior-2026"})
        self.assertFalse(self.demo.authorized_users.filter(pk=user.pk).exists())
