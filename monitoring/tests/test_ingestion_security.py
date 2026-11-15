import io
import random
import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from monitoring.models import Device, Measurement
from monitoring.sensors.vital_signs import make_event

from .fixtures import TelemetryFixtures


class IngestionSecurityTests(TelemetryFixtures, TestCase):
    def endpoints(self):
        yield "/api/v1/telemetry/batches/", {"schema_version": 1, "packets": [self.packet()]}
        call_command("setup_vital_signs", self.session.identifier, stdout=io.StringIO())
        self.credential.device = Device.objects.get(identifier="studywatch-sim-001")
        self.credential.save()
        yield "/api/v1/telemetry/vital-signs/", make_event(0, 6, "baseline", random.Random(42), self.now, uuid.uuid4().hex)

    def test_both_endpoints_reject_missing_malformed_revoked_and_inactive_credentials(self):
        for url, payload in self.endpoints():
            with self.subTest(url=url):
                for header in (None, "Device broken", f"Device {self.credential.pk}:wrong", "Basic bm9wZTpub3Bl"):
                    client = APIClient()
                    if header:
                        client.credentials(HTTP_AUTHORIZATION=header)
                    self.assertEqual(client.post(url, payload, format="json").status_code, 401)
                self.credential.is_active = False
                self.credential.save()
                self.assertEqual(self.device_client.post(url, payload, format="json").status_code, 401)
                self.credential.is_active = True
                self.credential.save()
                device = self.credential.device
                device.is_active = False
                device.save()
                self.assertEqual(self.device_client.post(url, payload, format="json").status_code, 401)
                device.is_active = True
                device.save()
        self.assertEqual(Measurement.objects.count(), 0)

    def test_both_endpoints_enforce_request_limits_and_supported_methods(self):
        for url, payload in self.endpoints():
            with self.subTest(url=url):
                with override_settings(TELEMETRY_MAX_BODY_BYTES=16):
                    self.assertEqual(self.device_client.post(url, payload, format="json").status_code, 413)
                self.assertEqual(self.device_client.post(url, b'{', content_type="application/json").status_code, 400)
                self.assertEqual(self.device_client.post(url, "plain", content_type="text/plain").status_code, 415)
                for method in ("get", "put", "patch", "delete"):
                    self.assertEqual(getattr(self.device_client, method)(url).status_code, 405)
                cache.clear()
                with patch("monitoring.authentication.DeviceRateThrottle.get_rate", return_value="1/min"):
                    self.assertEqual(self.device_client.post(url, payload, format="json").status_code, 201)
                    throttled = self.device_client.post(url, payload, format="json")
                    self.assertEqual(throttled.status_code, 429)
                    self.assertIn("Retry-After", throttled)
                cache.clear()

    def test_batch_structural_limits(self):
        url = "/api/v1/telemetry/batches/"
        for packets in ([], [self.packet()] * 101, [self.packet(readings=[])],
                        [self.packet(readings=[self.packet()["readings"][0]] * 33)]):
            response = self.device_client.post(url, {"schema_version": 1, "packets": packets}, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(Measurement.objects.count(), 0)
