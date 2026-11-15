"""Synthetic fixtures shared without inheriting another suite's test methods."""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from monitoring.models import (
    CounterEpoch,
    Device,
    DeviceCredential,
    MonitoringSession,
    Participant,
    Sensor,
    SensorCapability,
    SessionDevice,
)


class TelemetryFixtures:
    def setUp(self):
        super().setUp()
        cache.clear()
        self.now = timezone.now().replace(microsecond=0)
        self.participant = Participant.objects.create(pseudonym="synthetic-api-001")
        self.session = MonitoringSession.objects.create(
            identifier="session-demo-001", participant=self.participant,
            started_at=self.now - timedelta(days=2),
        )
        self.other_session = MonitoringSession.objects.create(
            identifier="session-other-001", participant=self.participant,
            started_at=self.now - timedelta(days=2),
        )
        self.device = Device.objects.create(identifier="harness-sim-001", kind=Device.Kind.HARNESS, source=Device.Source.SIMULATED)
        self.other_device = Device.objects.create(identifier="harness-sim-002", kind=Device.Kind.HARNESS, source=Device.Source.SIMULATED)
        self.assignment = SessionDevice.objects.create(session=self.session, device=self.device, assigned_at=self.now - timedelta(days=2))
        self.sensor = Sensor.objects.create(identifier="hr-sim-001", device=self.device, channel="hr", profile_version="demo-1")
        SensorCapability.objects.create(sensor=self.sensor, metric="heart_rate", unit="bpm", enabled=True)
        self.dose_sensor = Sensor.objects.create(identifier="dose-sim-001", device=self.device, channel="dose")
        SensorCapability.objects.create(sensor=self.dose_sensor, metric="absorbed_dose_cumulative", unit="uGy", enabled=True)
        self.epoch = CounterEpoch.objects.create(assignment=self.assignment, sensor=self.dose_sensor, started_at=self.now - timedelta(days=2))
        self.reader = get_user_model().objects.create_user(username="reader", password="reader-password")
        self.stranger = get_user_model().objects.create_user(username="stranger", password="stranger-password")
        self.staff = get_user_model().objects.create_user(username="staff", password="staff-password", is_staff=True)
        self.session.authorized_users.add(self.reader)
        self.secret = "synthetic-test-device-secret"
        self.credential = DeviceCredential.objects.create(device=self.device, secret_hash=make_password(self.secret))
        self.device_client = APIClient()
        self.device_client.credentials(HTTP_AUTHORIZATION=f"Device {self.credential.pk}:{self.secret}")

    def packet(self, *, packet_id=None, observed_at=None, value="78.0", readings=None):
        return {
            "packet_id": str(packet_id or uuid.uuid4()),
            "device_id": self.device.identifier,
            "session_id": self.session.identifier,
            "observed_at": (observed_at or self.now).isoformat(),
            "source": "simulated",
            "readings": readings if readings is not None else [
                {"sensor_id": self.sensor.identifier, "metric": "heart_rate", "value": value, "unit": "bpm", "quality": "valid"}
            ],
        }

    def send(self, packets, client=None, version=1):
        return (client or self.device_client).post(
            "/api/v1/telemetry/batches/", {"schema_version": version, "packets": packets}, format="json"
        )

