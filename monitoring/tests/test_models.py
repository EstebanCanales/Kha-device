import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import UUIDField
from django.test import TestCase

from monitoring.models import (
    CounterEpoch,
    Device,
    Measurement,
    Metric,
    MonitoringSession,
    Participant,
    Sensor,
    SensorCapability,
    SessionDevice,
    TelemetryPacket,
)


class MonitoringModelTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 14, 16, tzinfo=timezone.utc)
        self.participant = Participant.objects.create(pseudonym="synthetic-001")
        self.session = MonitoringSession.objects.create(
            identifier="session-demo-001", participant=self.participant, started_at=self.now
        )
        self.device = Device.objects.create(
            identifier="dosimeter-sim-001", kind=Device.Kind.DOSIMETER, source=Device.Source.SIMULATED
        )
        self.assignment = SessionDevice.objects.create(
            session=self.session, device=self.device, assigned_at=self.now
        )
        self.sensor = Sensor.objects.create(identifier="dose-sim-001", device=self.device, channel="dose")
        SensorCapability.objects.create(
            sensor=self.sensor, metric=Metric.ABSORBED_DOSE_CUMULATIVE, unit="uGy", enabled=True
        )
        self.packet = TelemetryPacket.objects.create(
            packet_id=uuid.uuid4(), schema_version=1, assignment=self.assignment,
            device=self.device, observed_at=self.now + timedelta(seconds=5),
            source=Device.Source.SIMULATED, content_sha256="a" * 64,
        )

    def test_monitoring_primary_keys_are_uuids(self):
        for model in apps.get_app_config("monitoring").get_models():
            with self.subTest(model=model.__name__):
                self.assertIsInstance(model._meta.pk, UUIDField)
        self.assertIsInstance(self.participant.pk, uuid.UUID)
        self.assertIsInstance(self.packet.assignment_id, uuid.UUID)

    def test_counter_epoch_and_quality_preserve_original_value(self):
        epoch = CounterEpoch.objects.create(
            assignment=self.assignment, sensor=self.sensor, started_at=self.now
        )
        reading = Measurement(
            packet=self.packet, sensor=self.sensor, metric=Metric.ABSORBED_DOSE_CUMULATIVE,
            value=Decimal("0.000000000001"), unit="uGy", quality=Measurement.Quality.VALID,
            counter_epoch=epoch,
        )
        reading.full_clean()
        reading.save()
        saved = Measurement.objects.select_related("packet__assignment__session__participant").get(pk=reading.pk)
        self.assertEqual(saved.value, Decimal("0.000000000001"))
        self.assertIsInstance(saved.pk, uuid.UUID)
        self.assertEqual(saved.packet.assignment.session.participant, self.participant)

    def test_rejects_wrong_unit_and_missing_counter_epoch(self):
        reading = Measurement(
            packet=self.packet, sensor=self.sensor, metric=Metric.ABSORBED_DOSE_CUMULATIVE,
            value=Decimal("1"), unit="uSv", quality=Measurement.Quality.VALID,
        )
        with self.assertRaises(ValidationError):
            reading.full_clean()

    def test_missing_is_null_and_packet_identity_is_unique(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Measurement.objects.create(
                    packet=self.packet, sensor=self.sensor, metric=Metric.ABSORBED_DOSE_CUMULATIVE,
                    value=Decimal("0"), unit="uGy", quality=Measurement.Quality.MISSING,
                )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TelemetryPacket.objects.create(
                    packet_id=self.packet.packet_id, schema_version=1, assignment=self.assignment,
                    device=self.device, observed_at=self.now, source=Device.Source.SIMULATED,
                    content_sha256="a" * 64,
                )

    def test_overlapping_assignment_is_rejected(self):
        other_session = MonitoringSession.objects.create(
            identifier="other-session", participant=self.participant, started_at=self.now
        )
        overlapping = SessionDevice(
            session=other_session, device=self.device, assigned_at=self.now + timedelta(seconds=1)
        )
        with self.assertRaises(ValidationError):
            overlapping.full_clean()

    def test_packet_after_session_end_is_rejected(self):
        self.session.ended_at = self.now + timedelta(seconds=2)
        self.session.save()
        with self.assertRaises(ValidationError):
            self.packet.full_clean()

    def test_counter_epoch_must_cover_measurement_time(self):
        epoch = CounterEpoch.objects.create(
            assignment=self.assignment, sensor=self.sensor,
            started_at=self.now + timedelta(seconds=10),
        )
        reading = Measurement(
            packet=self.packet, sensor=self.sensor, metric=Metric.ABSORBED_DOSE_CUMULATIVE,
            value=Decimal("1"), unit="uGy", quality=Measurement.Quality.VALID,
            counter_epoch=epoch,
        )
        with self.assertRaises(ValidationError):
            reading.full_clean()
