import random
import uuid
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from . import test_api
from .models import Measurement
from .sensors.vital_signs import make_event


class VitalSignsTests(TestCase):
    def setUp(self):
        test_api.TelemetryAPITests.setUp(self)
        call_command("setup_vital_signs", self.session.identifier, verbosity=0)
        from .models import Device
        self.credential.device = Device.objects.get(identifier="studywatch-sim-001")
        self.credential.save()

    def event(self, scenario="baseline", index=0):
        return make_event(index, 6, scenario, random.Random(42), timezone.now() - timedelta(seconds=10), uuid.uuid4().hex)

    def test_simulator_event_persists_five_metrics_and_retries(self):
        event = self.event()
        url = "/api/v1/telemetry/vital-signs/"
        response = self.device_client.post(url, event, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Measurement.objects.count(), 5)
        self.assertTrue(Measurement.objects.filter(metric="pulse_rate", unit="bpm").exists())
        self.assertEqual(self.device_client.post(url, event, format="json").status_code, 200)
        event["metrics"]["heart_rate_bpm"] += 1
        self.assertEqual(self.device_client.post(url, event, format="json").status_code, 409)

    def test_missing_and_invalid_simulator_scenarios(self):
        url = "/api/v1/telemetry/vital-signs/"
        response = self.device_client.post(url, self.event("signal-loss", 2), format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Measurement.objects.filter(value__isnull=True, quality="missing").count(), 5)
        self.assertEqual(self.device_client.post(url, self.event("invalid"), format="json").status_code, 400)
