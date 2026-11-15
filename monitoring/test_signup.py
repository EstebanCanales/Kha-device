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


class OpenReadAccessTests(TestCase):
    """OPEN_READ_ACCESS lets every signed-in account read every session; writing stays staff-only."""

    def setUp(self):
        participant = Participant.objects.create(pseudonym="p-open")
        self.session = MonitoringSession.objects.create(participant=participant, identifier="session-open", started_at=timezone.now())
        self.user = User.objects.create_user("lectora", password="Clave-anterior-2026")
        self.client.force_login(self.user)

    def test_closed_by_default(self):
        self.assertEqual(self.client.get("/api/v1/sessions/").json()["results"], [])
        self.assertEqual(self.client.get(f"/api/v1/sessions/{self.session.pk}/overview/?source=simulated").status_code, 404)

    @override_settings(OPEN_READ_ACCESS=True)
    def test_open_lets_any_account_read_every_session(self):
        listed = [s["identifier"] for s in self.client.get("/api/v1/sessions/").json()["results"]]
        self.assertEqual(listed, ["session-open"])
        self.assertEqual(self.client.get(f"/api/v1/sessions/{self.session.pk}/overview/?source=simulated").status_code, 200)

    @override_settings(OPEN_READ_ACCESS=True)
    def test_open_does_not_allow_writing_or_configuration(self):
        self.assertEqual(self.client.delete(f"/api/v1/sessions/{self.session.pk}/").status_code, 403)
        self.assertEqual(self.client.get("/api/v1/config/devices/").status_code, 403)

    @override_settings(OPEN_READ_ACCESS=True)
    def test_open_still_requires_an_account(self):
        self.client.logout()
        self.assertIn(self.client.get("/api/v1/sessions/").status_code, (401, 403))


class PublicDemoTests(TestCase):
    """PUBLIC_DEMO lets visitors without an account open the dashboard and read simulated data, and nothing else."""

    def setUp(self):
        cache.clear()
        participant = Participant.objects.create(pseudonym="p-public")
        self.session = MonitoringSession.objects.create(participant=participant, identifier="session-public", started_at=timezone.now())
        self.base = f"/api/v1/sessions/{self.session.pk}"

    def test_closed_by_default(self):
        self.assertRedirects(self.client.get("/app/"), "/accounts/login/?next=/app/", fetch_redirect_response=False)
        self.assertIn(self.client.get("/api/v1/sessions/").status_code, (401, 403))
        self.assertIn(self.client.get(f"{self.base}/overview/?source=simulated").status_code, (401, 403))
        self.assertIn(self.client.post(f"{self.base}/summary/?source=simulated").status_code, (401, 403))

    @override_settings(PUBLIC_DEMO=True, LANDING_URL="https://landing.example/")
    def test_visitor_opens_the_dashboard_and_reads_simulated_data(self):
        page = self.client.get("/app/")
        self.assertEqual(page.status_code, 200)
        # A way out is always there: the link back to the landing page.
        self.assertContains(page, 'href="https://landing.example/"')
        self.assertContains(page, "Volver al inicio")
        # No sign-in is offered to a visitor: no account block and no login link.
        self.assertNotContains(page, "accounts/login")
        self.assertNotContains(page, "accounts/logout")
        self.assertEqual([s["identifier"] for s in self.client.get("/api/v1/sessions/").json()["results"]], ["session-public"])
        self.assertEqual(self.client.get(f"{self.base}/overview/?source=simulated").status_code, 200)
        self.assertEqual(self.client.get(f"{self.base}/measurements/?source=simulated").status_code, 200)
        self.assertEqual(self.client.post(f"{self.base}/summary/?source=simulated").status_code, 200)

    @override_settings(PUBLIC_DEMO=True)
    def test_visitor_never_reads_hardware_data(self):
        for path in ("overview", "analysis", "measurements", "latest"):
            self.assertEqual(self.client.get(f"{self.base}/{path}/?source=hardware").status_code, 403, path)
        self.assertEqual(self.client.post(f"{self.base}/summary/?source=hardware").status_code, 403)
        report = f"{self.base}/report/?source=hardware&observed_from=2026-11-01T00:00:00Z&observed_to=2026-11-02T00:00:00Z"
        self.assertEqual(self.client.get(report).status_code, 403)

    @override_settings(PUBLIC_DEMO=True)
    def test_visitor_cannot_write_or_configure_or_ingest(self):
        self.assertIn(self.client.delete(f"{self.base}/").status_code, (401, 403))
        self.assertIn(self.client.post("/api/v1/sessions/", {}, content_type="application/json").status_code, (401, 403))
        self.assertIn(self.client.get("/api/v1/config/devices/").status_code, (401, 403))
        self.assertEqual(self.client.post("/api/v1/telemetry/batches/", {}, content_type="application/json").status_code, 401)

    @override_settings(PUBLIC_DEMO=True)
    def test_signed_in_account_still_reads_hardware_when_authorized(self):
        user = User.objects.create_user("operadora", password="Clave-anterior-2026")
        self.session.authorized_users.add(user)
        self.client.force_login(user)
        self.assertEqual(self.client.get(f"{self.base}/overview/?source=hardware").status_code, 200)
