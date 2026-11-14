"""Create explicit simulated profiles for the HTTP demonstration."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from monitoring.models import (
    CounterEpoch,
    Device,
    Metric,
    MonitoringSession,
    Participant,
    Sensor,
    SensorCapability,
    SessionDevice,
)


class Command(BaseCommand):
    help = "Create synthetic participant, session, devices, sensors, and counter epochs."

    def add_arguments(self, parser):
        parser.add_argument("--reader", help="Existing username allowed to read the demo session")

    @transaction.atomic
    def handle(self, *args, **options):
        reader = None
        if options["reader"]:
            reader = get_user_model().objects.filter(username=options["reader"], is_active=True).first()
            if reader is None:
                raise CommandError("Reader user does not exist or is inactive.")
        now = timezone.now().replace(microsecond=0)
        session = MonitoringSession.objects.filter(identifier="session-demo-001").first()
        if session is None:
            participant, _ = Participant.objects.get_or_create(pseudonym="synthetic-demo-001")
            session = MonitoringSession.objects.create(
                identifier="session-demo-001", participant=participant,
                started_at=now - timedelta(days=2), gravity_context="unknown",
            )
        elif session.participant.pseudonym != "synthetic-demo-001":
            self.stderr.write(
                f"Using existing demo session for participant {session.participant.pseudonym}; participant unchanged."
            )
        if reader:
            session.authorized_users.add(reader)

        devices = {}
        assignments = {}
        for identifier, kind in (("harness-sim-001", Device.Kind.HARNESS), ("dosimeter-sim-001", Device.Kind.DOSIMETER)):
            device, _ = Device.objects.get_or_create(
                identifier=identifier, defaults={"kind": kind, "source": Device.Source.SIMULATED}
            )
            if device.kind != kind or device.source != Device.Source.SIMULATED:
                raise CommandError(f"{identifier} already exists with an incompatible profile.")
            assignment = SessionDevice.objects.filter(device=device, session=session, released_at__isnull=True).first()
            if assignment is None:
                if SessionDevice.objects.filter(device=device, released_at__isnull=True).exists():
                    raise CommandError(f"{identifier} is already assigned elsewhere.")
                assignment = SessionDevice.objects.create(session=session, device=device, assigned_at=session.started_at)
            devices[identifier] = device
            assignments[identifier] = assignment

        profiles = (
            ("hr-sim-001", "harness-sim-001", "heart_rate", Metric.HEART_RATE, "bpm"),
            ("rr-sim-001", "harness-sim-001", "respiratory_rate", Metric.RESPIRATORY_RATE, "breaths/min"),
            ("spo2-sim-001", "harness-sim-001", "spo2", Metric.SPO2, "%"),
            ("skin-temp-sim-001", "harness-sim-001", "skin_temperature", Metric.SKIN_TEMPERATURE, "degC"),
            ("accel-x-sim-001", "harness-sim-001", "acceleration_x", Metric.ACCELERATION_X, "m/s2"),
            ("accel-y-sim-001", "harness-sim-001", "acceleration_y", Metric.ACCELERATION_Y, "m/s2"),
            ("accel-z-sim-001", "harness-sim-001", "acceleration_z", Metric.ACCELERATION_Z, "m/s2"),
            ("dose-rate-sim-001", "dosimeter-sim-001", "dose_rate", Metric.ABSORBED_DOSE_RATE, "uGy/h"),
            ("dose-total-sim-001", "dosimeter-sim-001", "dose_total", Metric.ABSORBED_DOSE_CUMULATIVE, "uGy"),
            ("exposure-sim-001", "dosimeter-sim-001", "exposure", Metric.EXPOSURE_DURATION, "s"),
        )
        for sensor_id, device_id, channel, metric, unit in profiles:
            sensor, _ = Sensor.objects.get_or_create(
                identifier=sensor_id,
                defaults={"device": devices[device_id], "channel": channel, "profile_version": "synthetic-v1"},
            )
            if sensor.device_id != devices[device_id].pk:
                raise CommandError(f"{sensor_id} already belongs to another device.")
            SensorCapability.objects.get_or_create(sensor=sensor, metric=metric, unit=unit, defaults={"enabled": True})

        dose_sensor = Sensor.objects.get(identifier="dose-total-sim-001")
        assignment = assignments["dosimeter-sim-001"]
        reset_at = session.started_at + timedelta(days=1)
        old_epoch = CounterEpoch.objects.filter(assignment=assignment, sensor=dose_sensor, ended_at=reset_at).first()
        if old_epoch is None:
            old_epoch = CounterEpoch.objects.create(
                assignment=assignment, sensor=dose_sensor, started_at=session.started_at,
                ended_at=reset_at, reference="synthetic-before-reset",
            )
        new_epoch = CounterEpoch.objects.filter(assignment=assignment, sensor=dose_sensor, ended_at__isnull=True).first()
        if new_epoch is None:
            new_epoch = CounterEpoch.objects.create(
                assignment=assignment, sensor=dose_sensor, started_at=reset_at,
                reference="synthetic-after-reset",
            )
        self.stdout.write(f"session_uuid={session.pk}")
        self.stdout.write(f"old_epoch={old_epoch.identifier}")
        self.stdout.write(f"new_epoch={new_epoch.identifier}")
        self.stdout.write(f"reset_at={reset_at.isoformat()}")
