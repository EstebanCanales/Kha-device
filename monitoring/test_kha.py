"""Kha-device 01 profiles, session analysis, the summary endpoint, and the dashboard shell."""

import uuid
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from ia import IAError

from .analysis import analyze_session
from .models import (
    CounterEpoch,
    Device,
    DeviceCredential,
    Measurement,
    MonitoringSession,
    Sensor,
    SensorCapability,
    SessionDevice,
    TelemetryPacket,
)


class KhaTestCase(TestCase):
    def setUp(self):
        out = StringIO()
        call_command("setup_kha_devices", stdout=out)
        self.session = MonitoringSession.objects.get(identifier="session-kha-001")
        self.start = self.session.started_at + timedelta(hours=1)
        self.vitals = SessionDevice.objects.get(session=self.session, device__identifier="kha-vitals-sim-001")
        self.cad = SessionDevice.objects.get(session=self.session, device__identifier="cad-sim-001")

    def store(self, assignment, sensor_id, metric, unit, values, epoch=None, step=30):
        """Store one packet per value, step seconds apart; None stores a missing reading."""
        sensor = Sensor.objects.get(identifier=sensor_id)
        for i, value in enumerate(values):
            packet = TelemetryPacket.objects.create(
                packet_id=uuid.uuid4(), schema_version=1, assignment=assignment, device=assignment.device,
                observed_at=self.start + timedelta(seconds=i * step), source="simulated", content_sha256="0" * 64,
            )
            Measurement.objects.create(
                packet=packet, sensor=sensor, metric=metric, unit=unit,
                value=None if value is None else Decimal(str(value)),
                quality="missing" if value is None else "valid", counter_epoch=epoch,
            )

    def heart_rate(self, values):
        self.store(self.vitals, "max86178-ppg-001", "heart_rate", "bpm", values)


class ProfileTests(KhaTestCase):
    def test_setup_registers_both_devices_with_enabled_capabilities(self):
        self.assertEqual(set(self.session.device_assignments.values_list("device__identifier", flat=True)),
                         {"cad-sim-001", "kha-vitals-sim-001"})
        self.assertTrue(SensorCapability.objects.filter(
            sensor__identifier="cad-dis-high-001", metric="absorbed_dose_cumulative", unit="mGy", enabled=True).exists())
        self.assertTrue(SensorCapability.objects.filter(
            sensor__identifier="cad-tmp117-001", metric="internal_temperature", unit="degC", enabled=True).exists())
        self.assertTrue(Device.objects.filter(source="simulated").count() == 2)

    def test_each_dis_chamber_has_its_own_open_epoch(self):
        epochs = CounterEpoch.objects.filter(ended_at__isnull=True)
        self.assertEqual({e.sensor.identifier for e in epochs}, {"cad-dis-high-001", "cad-dis-low-001"})

    def test_setup_is_idempotent(self):
        before = (Sensor.objects.count(), SensorCapability.objects.count(), CounterEpoch.objects.count())
        call_command("setup_kha_devices", stdout=StringIO())
        self.assertEqual(before, (Sensor.objects.count(), SensorCapability.objects.count(), CounterEpoch.objects.count()))


class AnalysisTests(KhaTestCase):
    def test_sustained_shift_from_personal_baseline_is_reported(self):
        self.heart_rate([70 + (i % 3) for i in range(30)] + [96] * 10)
        result = analyze_session(self.session, "simulated")["metrics"]["heart_rate"]
        self.assertEqual(result["status"], "shift_up")
        self.assertGreater(result["z_score"], 3)
        self.assertEqual(result["unit"], "bpm")

    def test_steady_readings_are_stable(self):
        self.heart_rate([70 + (i % 3) for i in range(40)])
        self.assertEqual(analyze_session(self.session, "simulated")["metrics"]["heart_rate"]["status"], "stable")

    def test_few_readings_are_not_enough_for_a_baseline(self):
        self.heart_rate([70, 71, 72])
        self.assertEqual(analyze_session(self.session, "simulated")["metrics"]["heart_rate"]["status"], "insufficient_data")

    def test_missing_readings_are_counted_and_never_used_as_zero(self):
        self.heart_rate([70 + (i % 3) for i in range(30)] + [None, None])
        result = analyze_session(self.session, "simulated")
        self.assertEqual(result["metrics"]["heart_rate"]["quality_counts"]["missing"], 2)
        self.assertEqual(result["metrics"]["heart_rate"]["status"], "stable")
        self.assertIn({"code": "missing_readings", "metric": "heart_rate", "count": 2}, result["missing_data"])

    def test_source_is_never_mixed(self):
        self.heart_rate([70 + (i % 3) for i in range(40)])
        self.assertEqual(analyze_session(self.session, "hardware")["metrics"]["heart_rate"]["status"], "no_data")

    def test_dose_rate_rise_is_reported_per_chamber_without_summing(self):
        epoch = CounterEpoch.objects.get(sensor__identifier="cad-dis-high-001", ended_at__isnull=True)
        slow = [0.2 + i * 0.0002 for i in range(30)]
        fast = [slow[-1] + (i + 1) * 0.002 for i in range(10)]
        self.store(self.cad, "cad-dis-high-001", "absorbed_dose_cumulative", "mGy", slow + fast, epoch=epoch)
        chambers = analyze_session(self.session, "simulated")["dose"]["chambers"]
        self.assertEqual(len(chambers), 1)
        self.assertEqual(chambers[0]["status"], "rate_up")
        self.assertEqual(chambers[0]["unit"], "mGy")
        self.assertFalse(chambers[0]["counter_decreased"])

    def test_decreasing_counter_inside_an_epoch_is_flagged(self):
        epoch = CounterEpoch.objects.get(sensor__identifier="cad-dis-high-001", ended_at__isnull=True)
        self.store(self.cad, "cad-dis-high-001", "absorbed_dose_cumulative", "mGy", [0.5, 0.6, 0.4], epoch=epoch)
        self.assertTrue(analyze_session(self.session, "simulated")["dose"]["chambers"][0]["counter_decreased"])

    def test_timeline_pause_is_reported(self):
        self.heart_rate([70 + (i % 3) for i in range(20)])
        sensor = Sensor.objects.get(identifier="max86178-ppg-001")
        late = TelemetryPacket.objects.create(
            packet_id=uuid.uuid4(), schema_version=1, assignment=self.vitals, device=self.vitals.device,
            observed_at=self.start + timedelta(hours=2), source="simulated", content_sha256="1" * 64,
        )
        Measurement.objects.create(packet=late, sensor=sensor, metric="heart_rate", unit="bpm", value=Decimal("71"), quality="valid")
        result = analyze_session(self.session, "simulated")
        self.assertEqual(result["gaps"][0]["seconds"], int((timedelta(hours=2) - timedelta(seconds=19 * 30)).total_seconds()))


class SummaryEndpointTests(KhaTestCase):
    def setUp(self):
        super().setUp()
        user = get_user_model()
        self.reader = user.objects.create_user("reader", password="reader-password")
        self.stranger = user.objects.create_user("stranger", password="stranger-password")
        self.session.authorized_users.add(self.reader)
        self.heart_rate([70 + (i % 3) for i in range(30)] + [96] * 10)
        self.client = APIClient()

    def url(self, name, source="simulated"):
        return f"/api/v1/sessions/{self.session.pk}/{name}/?source={source}"

    def test_reader_gets_analysis_and_summary(self):
        self.client.force_authenticate(self.reader)
        analysis = self.client.get(self.url("analysis"))
        self.assertEqual(analysis.status_code, 200)
        self.assertEqual(analysis.json()["changes"][0]["metric"], "heart_rate")
        summary = self.client.post(self.url("summary"))
        self.assertEqual(summary.status_code, 200)
        body = summary.json()
        self.assertEqual(body["engine"], "rules")
        self.assertTrue(any("Frecuencia cardíaca" in f and "Cambiaron" in f for f in body["summary"]["findings"]))
        self.assertTrue(any("subió" in h for h in body["health"]["highlights"]))
        self.assertIn("No es un diagnóstico", body["disclaimer"])

    def test_overview_bundles_analysis_series_and_engine_in_one_request(self):
        self.client.force_authenticate(self.reader)
        body = self.client.get(self.url("overview")).json()
        self.assertEqual(body["session"]["identifier"], "session-kha-001")
        self.assertEqual(body["ia"]["engine"], "rules")
        self.assertFalse(body["ia"]["real_models"])
        self.assertEqual(body["analysis"]["metrics"]["heart_rate"]["status"], "shift_up")
        (hr,) = [s for s in body["sensors"] if s["metric"] == "heart_rate"]
        self.assertEqual(hr["device_kind"], "harness")
        self.assertEqual(hr["latest"]["value"], 96.0)
        self.assertEqual(hr["readings"], 40)
        self.assertEqual(len(hr["points"]), 40)

    def test_overview_downsamples_long_series_and_keeps_the_last_point(self):
        # 300 readings every 30 s span 2.5 h, inside the 3 h chart window.
        self.heart_rate_more = [70 + (i % 5) for i in range(300)]
        self.client.force_authenticate(self.reader)
        self.start += timedelta(hours=2)
        self.heart_rate(self.heart_rate_more)
        (hr,) = [s for s in self.client.get(self.url("overview")).json()["sensors"] if s["metric"] == "heart_rate"]
        self.assertLessEqual(len(hr["points"]), 121)
        self.assertEqual(hr["points"][-1][1], float(self.heart_rate_more[-1]))
        self.assertEqual(hr["readings"], 300)

    def test_overview_without_readings_is_empty_not_an_error(self):
        self.client.force_authenticate(self.reader)
        body = self.client.get(self.url("overview", "hardware")).json()
        self.assertEqual(body["sensors"], [])
        self.assertEqual(body["analysis"]["window"]["packets"], 0)

    def test_overview_respects_session_authorization_and_source(self):
        self.client.force_authenticate(self.stranger)
        self.assertEqual(self.client.get(self.url("overview")).status_code, 404)
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.client.get(f"/api/v1/sessions/{self.session.pk}/overview/").status_code, 400)

    def test_source_is_required_and_validated(self):
        self.client.force_authenticate(self.reader)
        self.assertEqual(self.client.get(f"/api/v1/sessions/{self.session.pk}/analysis/").status_code, 400)
        self.assertEqual(self.client.post(self.url("summary", "other")).status_code, 400)

    def test_unauthorized_user_cannot_see_the_session_results(self):
        self.client.force_authenticate(self.stranger)
        self.assertEqual(self.client.get(self.url("analysis")).status_code, 404)
        self.assertEqual(self.client.post(self.url("summary")).status_code, 404)

    def test_anonymous_requests_are_refused(self):
        self.assertIn(self.client.get(self.url("analysis")).status_code, (401, 403))
        self.assertIn(self.client.post(self.url("summary")).status_code, (401, 403))

    def test_engine_failure_is_a_503_without_leaking_details(self):
        self.client.force_authenticate(self.reader)
        with mock.patch("monitoring.views.run_pipeline", side_effect=IAError("RuntimeError while running engine x.")):
            response = self.client.post(self.url("summary"))
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("96", response.content.decode())


class DashboardTests(TestCase):
    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get("/app/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("/accounts/login/"))

    def test_signed_in_user_sees_the_dashboard(self):
        get_user_model().objects.create_user("operator", password="operator-password")
        self.client.login(username="operator", password="operator-password")
        response = self.client.get("/app/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Actualizar análisis")
        self.assertContains(response, "No se pudo conectar con el servidor")

    @override_settings(LOGOUT_REDIRECT_URL="https://landing.example/")
    def test_signing_out_sends_the_user_to_the_landing_page(self):
        get_user_model().objects.create_user("operator", password="operator-password")
        self.client.login(username="operator", password="operator-password")
        response = self.client.post("/accounts/logout/")
        self.assertRedirects(response, "https://landing.example/", fetch_redirect_response=False)
        # The session is really closed: the app asks for a login again.
        self.assertEqual(self.client.get("/app/").status_code, 302)

    def test_logout_destination_defaults_to_the_local_landing(self):
        from django.conf import settings

        self.assertEqual(settings.LANDING_URL, "http://localhost:4321/")
        self.assertEqual(settings.LOGOUT_REDIRECT_URL, settings.LANDING_URL)

    def test_root_redirects_to_the_app(self):
        self.assertEqual(self.client.get("/")["Location"], "/app/")


class DemoCommandTests(TestCase):
    def run_demo(self, *args):
        out = StringIO()
        call_command("demo_kha", *args, stdout=out)
        return out.getvalue()

    def test_one_command_leaves_a_user_who_can_read_data_through_the_api(self):
        text = self.run_demo("--password", "una-clave-de-prueba-9", "--minutes", "30")
        self.assertIn("Se cargaron 120 paquetes", text)
        self.assertIn("una-clave-de-prueba-9", text)
        client = APIClient()
        self.assertTrue(client.login(username="demo", password="una-clave-de-prueba-9"))
        session = client.get("/api/v1/sessions/").json()["results"][0]
        overview = client.get(f"/api/v1/sessions/{session['id']}/overview/?source=simulated").json()
        self.assertEqual(overview["analysis"]["window"]["packets"], 60)
        self.assertEqual(overview["analysis"]["metrics"]["heart_rate"]["status"], "shift_up")
        self.assertEqual({s["device_kind"] for s in overview["sensors"]}, {"harness", "dosimeter"})

    def test_running_it_again_keeps_the_password_and_does_not_duplicate_data(self):
        self.run_demo("--password", "clave-original-1", "--minutes", "30")
        before = Measurement.objects.count()
        text = self.run_demo("--password", "otra-clave-2", "--minutes", "30")
        self.assertIn("ya tiene datos simulados", text)
        self.assertIn("su contraseña no se cambió", text)
        self.assertNotIn("otra-clave-2", text)
        self.assertEqual(Measurement.objects.count(), before)
        self.assertTrue(get_user_model().objects.get(username="demo").check_password("clave-original-1"))

    def test_more_adds_another_window_without_colliding_with_the_first(self):
        self.run_demo("--minutes", "20")
        before = Measurement.objects.count()
        self.run_demo("--minutes", "20", "--more")
        self.assertGreater(Measurement.objects.count(), before)

    def test_no_device_credential_is_left_behind(self):
        self.run_demo("--minutes", "10")
        self.assertEqual(DeviceCredential.objects.count(), 0)
